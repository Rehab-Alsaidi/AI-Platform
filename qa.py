"""
Complete Document QA System - Enhanced but Simple Version
A reliable module for document-based question answering using Hugging Face API.
"""

import os
import logging
import threading
import time
import json
import re
import requests
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

# Document processing
import pptx
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

def get_hf_config():
    """Get Hugging Face configuration with validation."""
    try:
        from config import get_config
        Config = get_config()
        
        # Try different attribute names for compatibility
        api_key = getattr(Config, 'HF_API_KEY', None) or getattr(Config, 'HUGGINGFACE_API_KEY', None)
        model = getattr(Config, 'HF_MODEL', 'meta-llama/Llama-3-8B-Instruct')
        
        if not api_key:
            logger.error("HF_API_KEY not found in config")
            return None, None
            
        return api_key, model
        
    except Exception as e:
        logger.error(f"Error getting HF config: {e}")
        return None, None

# ============================================================================
# CONVERSATION MEMORY
# ============================================================================

class ConversationMemory:
    """Simple conversation memory for context."""
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.conversations: Dict[str, List[Dict[str, str]]] = {}

    def add_message(self, user_id: str, question: str, answer: str) -> None:
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append({
            'question': question,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        })
        if len(self.conversations[user_id]) > self.max_history:
            self.conversations[user_id] = self.conversations[user_id][-self.max_history:]

    def get_context(self, user_id: str, last_n: int = 3) -> str:
        if user_id not in self.conversations:
            return ""
        recent = self.conversations[user_id][-last_n:]
        context_parts = []
        for item in recent:
            context_parts.append(f"Human: {item['question']}")
            context_parts.append(f"Assistant: {item['answer']}")
        return "\n".join(context_parts)

# ============================================================================
# HUGGING FACE LLM WITH ERROR HANDLING
# ============================================================================

class HuggingFaceLLM:
    """Enhanced Hugging Face API wrapper with error handling."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.timeout = 60

    def generate_response(self, prompt: str) -> str:
        """Generate response with error handling."""
        if not prompt or not prompt.strip():
            return "[Error] Empty prompt provided"
            
        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt, 
            "parameters": {
                "max_new_tokens": 512,
                "temperature": 0.7,
                "do_sample": True
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 503:
                return "[Model Loading] The AI model is starting up. Please try again in a few minutes."
            elif response.status_code == 429:
                return "[Rate Limited] Too many requests. Please wait a moment and try again."
            elif response.status_code == 401:
                return "[Authentication Error] Invalid API key."
            elif response.status_code != 200:
                return f"[API Error] Service unavailable (Status: {response.status_code})"
                
            data = response.json()
            
            # Parse response
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            elif isinstance(data, list) and len(data) > 0 and "text" in data[0]:
                return data[0]["text"]
            else:
                return str(data)
                
        except requests.exceptions.Timeout:
            return "[Timeout] Request timed out. Please try again."
        except requests.exceptions.ConnectionError:
            return "[Connection Error] Unable to connect to AI service."
        except Exception as e:
            logger.error(f"HF API error: {e}")
            return f"[Error] {str(e)}"

# ============================================================================
# DOCUMENT LOADERS
# ============================================================================

class PPTXLoader:
    """Simple PPTX loader."""
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Dict[str, Any]]:
        docs = []
        try:
            prs = pptx.Presentation(self.file_path)
            filename = os.path.basename(self.file_path)
            for i, slide in enumerate(prs.slides):
                text_content = ""
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text_content += shape.text + "\n"
                    if hasattr(shape, "table"):
                        for row in shape.table.rows:
                            for cell in row.cells:
                                if cell.text.strip():
                                    text_content += cell.text + " "
                            text_content += "\n"
                if text_content.strip():
                    doc = {
                        "page_content": text_content.strip(),
                        "metadata": {
                            "source": self.file_path,
                            "slide_number": i + 1,
                            "page": i + 1,
                            "filename": filename
                        }
                    }
                    docs.append(doc)
            logger.info(f"Loaded {len(docs)} slides from {filename}")
            return docs
        except Exception as e:
            logger.error(f"Error processing PPTX {self.file_path}: {str(e)}")
            return []

# ============================================================================
# DOCUMENT PROCESSOR
# ============================================================================

class DocumentProcessor:
    """Document processor for all supported formats."""
    def __init__(self, documents_dir: str):
        self.documents_dir = documents_dir
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            length_function=len
        )

    def load_documents(self) -> List[Any]:
        all_docs = []
        supported_extensions = {'.pdf', '.pptx', '.ppt', '.txt'}
        if not os.path.exists(self.documents_dir):
            logger.warning(f"Documents directory not found: {self.documents_dir}")
            return []
        
        for root, _, files in os.walk(self.documents_dir):
            for file in files:
                file_path = os.path.join(root, file)
                filename = os.path.basename(file_path)
                try:
                    if file.lower().endswith('.pdf'):
                        docs = self._load_pdf(file_path, filename)
                        all_docs.extend(docs)
                    elif file.lower().endswith(('.pptx', '.ppt')):
                        loader = PPTXLoader(file_path)
                        docs = loader.load()
                        all_docs.extend(docs)
                    elif file.lower().endswith('.txt'):
                        docs = self._load_txt(file_path, filename)
                        all_docs.extend(docs)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
                    continue
        
        logger.info(f"Loaded {len(all_docs)} document sections")
        return all_docs

    def _load_pdf(self, file_path: str, filename: str) -> List[Any]:
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata['filename'] = filename
            return docs
        except Exception as e:
            logger.error(f"Error loading PDF {filename}: {str(e)}")
            return []

    def _load_txt(self, file_path: str, filename: str) -> List[Any]:
        encodings = ['utf-8', 'utf-16', 'iso-8859-1', 'windows-1252']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                if content.strip():
                    return [{
                        "page_content": content.strip(),
                        "metadata": {
                            "source": file_path,
                            "page": 1,
                            "filename": filename
                        }
                    }]
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error loading TXT {filename}: {str(e)}")
                break
        return []

    def process_documents(self) -> List[Any]:
        docs = self.load_documents()
        if not docs:
            logger.warning("No documents loaded")
            return []
        
        logger.info(f"Processing {len(docs)} documents into chunks...")
        try:
            texts = []
            metadatas = []
            for doc in docs:
                if hasattr(doc, "page_content"):
                    content = doc.page_content
                    metadata = doc.metadata
                else:
                    content = doc["page_content"]
                    metadata = doc["metadata"]
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > 50:
                    texts.append(content)
                    metadatas.append(metadata)
            
            splits = self.text_splitter.create_documents(texts, metadatas=metadatas)
            logger.info(f"Created {len(splits)} document chunks")
            return splits
        except Exception as e:
            logger.error(f"Error processing documents: {str(e)}")
            return []

# ============================================================================
# VECTOR STORE
# ============================================================================

class VectorStore:
    """Vector store manager with background initialization."""
    def __init__(self, documents_dir: str, vector_db_path: str = "vector_db"):
        self.documents_dir = documents_dir
        self.vector_db_path = vector_db_path
        self.embeddings = None
        self.vector_store_instance = None
        self._initialization_lock = threading.Lock()
        self._is_initializing = False
        self._initialization_complete = False
        self._initialization_error = None
        self._start_background_initialization()

    def _start_background_initialization(self) -> None:
        def initialize():
            try:
                with self._initialization_lock:
                    if self._initialization_complete or self._is_initializing:
                        return
                    self._is_initializing = True
                    logger.info("Starting vector store initialization...")
                    
                    self.embeddings = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'},
                        encode_kwargs={'normalize_embeddings': True}
                    )
                    
                    self.vector_store_instance = self._load_or_create_vector_store()
                    self._initialization_complete = True
                    self._is_initializing = False
                    logger.info("Vector store initialization completed")
            except Exception as e:
                self._initialization_error = str(e)
                self._is_initializing = False
                logger.error(f"Failed to initialize vector store: {str(e)}")
        
        thread = threading.Thread(target=initialize, daemon=True)
        thread.start()

    def _load_or_create_vector_store(self):
        if os.path.exists(self.vector_db_path):
            try:
                logger.info(f"Loading existing vector database from {self.vector_db_path}")
                return FAISS.load_local(
                    self.vector_db_path, 
                    self.embeddings, 
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.warning(f"Failed to load existing vector store: {str(e)}")
        return self._create_new_vector_store()

    def _create_new_vector_store(self):
        processor = DocumentProcessor(self.documents_dir)
        document_chunks = processor.process_documents()
        if not document_chunks:
            logger.warning("No document chunks available")
            return None
        
        logger.info(f"Creating vector database from {len(document_chunks)} chunks...")
        try:
            vector_store = FAISS.from_documents(
                documents=document_chunks,
                embedding=self.embeddings
            )
            vector_store.save_local(self.vector_db_path)
            logger.info(f"Vector database saved to {self.vector_db_path}")
            return vector_store
        except Exception as e:
            logger.error(f"Failed to create vector database: {str(e)}")
            return None

    def get_vector_store(self, timeout: int = 30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._initialization_complete:
                return self.vector_store_instance
            elif self._initialization_error:
                raise Exception(f"Vector store failed: {self._initialization_error}")
            time.sleep(0.5)
        raise TimeoutError("Vector store initialization timed out")

    def is_ready(self) -> bool:
        return self._initialization_complete and self.vector_store_instance is not None

# ============================================================================
# MAIN QA SYSTEM
# ============================================================================

class DocumentQA:
    """Main Document QA system with conversational capabilities."""
    def __init__(self, documents_dir: str):
        self.documents_dir = documents_dir
        self.vector_store_manager = VectorStore(documents_dir)
        self.hf_llm = None
        self.conversation_memory = ConversationMemory()
        self.response_cache = {}
        self.cache_max_size = 50
        
        # Initialize HF LLM
        api_key, model = get_hf_config()
        if api_key and model:
            self.hf_llm = HuggingFaceLLM(api_key, model)
            logger.info("HuggingFace LLM initialized successfully")
        else:
            logger.error("HuggingFace API not configured properly")
        
        self.greetings = {
            'hi': "Hello! I'm your AI learning assistant. I can help you with course materials, explain concepts, or just chat about your studies. What would you like to know?",
            'hello': "Hi there! I'm here to help with your learning journey. You can ask me about course topics, request explanations, or get study tips. How can I assist you today?",
            'hey': "Hey! Great to see you here. I'm your AI tutor ready to help with anything you're studying. What's on your mind?",
            'good morning': "Good morning! Ready to learn something new today? I'm here to help with your course materials.",
            'good afternoon': "Good afternoon! How's your learning going today? I'm here to help with explanations or questions.",
            'good evening': "Good evening! Perfect time for some learning. What would you like to explore?"
        }

    def answer_question(self, question: str, user_id: str = None) -> Dict[str, Any]:
        """Main method to answer questions."""
        if not question or not question.strip():
            return {
                "answer": "I'm here and ready to help! What would you like to know or discuss?",
                "sources": [],
                "conversation_type": "greeting"
            }
        
        question = question.strip()
        question_lower = question.lower()
        
        try:
            conversation_type = self._detect_conversation_type(question_lower)
            if conversation_type == "greeting":
                response = self._handle_greeting(question_lower)
                if user_id:
                    self.conversation_memory.add_message(user_id, question, response)
                return {
                    "answer": response,
                    "sources": [],
                    "conversation_type": "greeting"
                }
            
            response = self._handle_document_question(question, user_id)
            if user_id:
                self.conversation_memory.add_message(user_id, question, response["answer"])
            return response
            
        except Exception as e:
            logger.error(f"Error in answer_question: {str(e)}")
            return {
                "answer": "I encountered an error, but I'm still here to help! Could you try rephrasing your question?",
                "sources": [],
                "conversation_type": "error"
            }

    def _detect_conversation_type(self, question_lower: str) -> str:
        greeting_patterns = [
            r'\b(hi|hello|hey|hiya)\b',
            r'\bgood (morning|afternoon|evening|night)\b',
            r'\bhow are you\b',
            r'\bwhat\'?s up\b'
        ]
        if any(re.search(pattern, question_lower) for pattern in greeting_patterns):
            return "greeting"
        
        document_keywords = [
            'explain', 'definition', 'what is', 'how does', 'tell me about',
            'course material', 'lesson', 'chapter', 'according to'
        ]
        if any(keyword in question_lower for keyword in document_keywords):
            return "document_based"
        return "general"

    def _handle_greeting(self, question_lower: str) -> str:
        for greeting, response in self.greetings.items():
            if greeting in question_lower:
                return response
        return "Hello! I'm your AI learning assistant. I'm here to help you understand course materials, answer questions, or discuss topics you're studying. What would you like to explore today?"

    def _handle_document_question(self, question: str, user_id: str = None) -> Dict[str, Any]:
        try:
            if not self.vector_store_manager.is_ready():
                if self.vector_store_manager._is_initializing:
                    return {
                        "answer": "I'm currently loading course materials. Please wait a moment and try again.",
                        "sources": [],
                        "conversation_type": "loading"
                    }
                else:
                    return {
                        "answer": "Course materials are not available. Please contact your administrator.",
                        "sources": [],
                        "conversation_type": "error"
                    }
            
            vector_store = self.vector_store_manager.get_vector_store(timeout=10)
            if not vector_store:
                return {
                    "answer": "I don't have access to course materials right now. Please ensure documents are uploaded.",
                    "sources": [],
                    "conversation_type": "error"
                }
            
            retriever = vector_store.as_retriever(search_kwargs={"k": 6})
            docs = retriever.get_relevant_documents(question)
            
            # Enhanced search with keywords
            keywords = self._extract_keywords(question)
            if keywords:
                keyword_query = " ".join(keywords)
                additional_docs = retriever.get_relevant_documents(keyword_query)
                seen_contents = {doc.page_content for doc in docs}
                for doc in additional_docs:
                    if doc.page_content not in seen_contents:
                        docs.append(doc)
                        seen_contents.add(doc.page_content)
            
            if not docs:
                return {
                    "answer": "I couldn't find specific information about that in your course materials. Could you provide more context or try rephrasing your question?",
                    "sources": [],
                    "conversation_type": "document_based"
                }
            
            context = self._prepare_context(docs)
            sources = self._extract_sources(docs)
            answer = self._generate_hf_response(question, context, user_id)
            
            return {
                "answer": answer,
                "sources": sources,
                "conversation_type": "document_based"
            }
            
        except Exception as e:
            logger.error(f"Document question error: {str(e)}")
            return {
                "answer": "I encountered an error while searching course materials. Please try again.",
                "sources": [],
                "conversation_type": "error"
            }

    def _extract_keywords(self, question: str) -> List[str]:
        import string
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'what', 'where', 'when',
            'why', 'how', 'who', 'which', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'
        }
        question_clean = question.lower().translate(str.maketrans('', '', string.punctuation))
        words = question_clean.split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords[:5]

    def _prepare_context(self, docs, max_length: int = 3000) -> str:
        context_parts = []
        total_length = 0
        for doc in docs:
            content = doc.page_content if hasattr(doc, "page_content") else doc.get("page_content", "")
            if total_length + len(content) > max_length:
                break
            context_parts.append(content)
            total_length += len(content)
        return "\n\n".join(context_parts)

    def _extract_sources(self, docs) -> List[Dict[str, str]]:
        sources = []
        seen_sources = set()
        for doc in docs:
            metadata = doc.metadata if hasattr(doc, "metadata") else doc.get("metadata", {})
            filename = metadata.get("filename", os.path.basename(metadata.get("source", "Unknown")))
            page = metadata.get("page", metadata.get("slide_number", "Unknown"))
            source_key = f"{filename}_{page}"
            if source_key not in seen_sources:
                sources.append({
                    "file": filename,
                    "page": str(page)
                })
                seen_sources.add(source_key)
        return sources[:4]

    def _get_cache_key(self, question: str, context: str) -> str:
        combined = f"{question}||{context}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _generate_hf_response(self, question: str, context: str, user_id: str = None) -> str:
        if not self.hf_llm:
            return "[Error: Hugging Face LLM not configured]"
        
        # Check cache
        cache_key = self._get_cache_key(question, context)
        if cache_key in self.response_cache:
            logger.debug("Cache hit for question")
            return self.response_cache[cache_key]
        
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a helpful AI learning assistant for a learning platform. You provide clear, accurate, and educational responses based on course materials.

Guidelines:
- Use the course materials to provide accurate, helpful answers
- Be conversational and friendly in your tone
- Provide specific examples from the course materials when relevant
- If the materials don't fully answer the question, acknowledge this clearly
- Keep responses educational and informative, tailored to the learning context<|eot_id|>

<|start_header_id|>user<|end_header_id|>

I'm studying and need help understanding a topic from my course materials. Here are the relevant sections from my course materials:
{context}

My question is: {question}<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>

"""
        
        try:
            response = self.hf_llm.generate_response(prompt)
            
            # Cache response
            if len(self.response_cache) >= self.cache_max_size:
                # Remove oldest entry
                oldest_key = next(iter(self.response_cache))
                del self.response_cache[oldest_key]
            self.response_cache[cache_key] = response
            
            return response
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "[Error] I encountered an issue generating a response. Please try again."

    def get_status(self) -> Dict[str, Any]:
        document_count = 0
        if os.path.exists(self.documents_dir):
            for root, dirs, files in os.walk(self.documents_dir):
                for file in files:
                    if file.lower().endswith(('.pdf', '.pptx', '.ppt', '.txt')):
                        document_count += 1
        
        return {
            "ready": self.vector_store_manager.is_ready(),
            "initializing": self.vector_store_manager._is_initializing,
            "error": self.vector_store_manager._initialization_error,
            "document_count": document_count,
            "hf_llm_available": self.hf_llm is not None,
            "cache_size": len(self.response_cache)
        }

# ============================================================================
# GLOBAL INSTANCE MANAGEMENT
# ============================================================================

_qa_instance = None

def initialize_qa(documents_dir: str = "documents", llama_model_path: str = None) -> DocumentQA:
    """Initialize the QA system."""
    global _qa_instance
    if _qa_instance is None:
        logger.info(f"Initializing QA system with documents from: {documents_dir}")
        _qa_instance = DocumentQA(documents_dir)
    return _qa_instance

def get_qa_system() -> Optional[DocumentQA]:
    """Get the global QA instance."""
    return _qa_instance

def ask_question(question: str, documents_dir: str = "documents", 
                llama_model_path: str = None, user_id: str = None) -> Dict[str, Any]:
    """Simple function to ask a question."""
    qa_system = initialize_qa(documents_dir)
    return qa_system.answer_question(question, user_id)

def get_system_status(documents_dir: str = "documents", 
                     llama_model_path: str = None) -> Dict[str, Any]:
    """Get system status."""
    qa_system = initialize_qa(documents_dir)
    return qa_system.get_status()

def cleanup_qa():
    """Cleanup function for graceful shutdown."""
    global _qa_instance
    try:
        if _qa_instance:
            logger.info("Cleaning up QA system resources...")
            _qa_instance.response_cache.clear()
            _qa_instance.conversation_memory.conversations.clear()
            _qa_instance = None
            logger.info("QA cleanup completed")
    except Exception as e:
        logger.error(f"Error during QA cleanup: {str(e)}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    try:
        print("Starting QA System Test...")
        qa = DocumentQA("documents")
        status = qa.get_status()
        print("QA System Status:", json.dumps(status, indent=2))
        
        if status["ready"]:
            response = qa.answer_question("Hello!")
            print("\nGreeting Response:", response["answer"])
            
            response = qa.answer_question("What is artificial intelligence?")
            print("\nAI Question Response:", response["answer"])
        else:
            print("QA system is not ready. Add documents to the 'documents' directory.")
            
    except Exception as e:
        print(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()