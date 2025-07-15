"""
Fixed QA System for Railway Deployment - Document Access Issue Resolution
"""

import os
import logging
import threading
import time
import json
import re
import requests
import hashlib
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime

# Document processing
import pptx
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# FIXED DATABASE CONNECTION FOR RAILWAY
# ============================================================================

def get_openrouter_config():
    """Get OpenRouter configuration with better error handling."""
    try:
        # Try to get from environment variables first
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

        if api_key:
            logger.info(f"✅ OpenRouter config loaded from env vars - Model: {model}")
            return api_key, model

        # Fallback to config.py
        try:
            from config import get_config

            Config = get_config()

            api_key = getattr(Config, "OPENROUTER_API_KEY", None)
            model = getattr(Config, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

            if api_key:
                logger.info(
                    f"✅ OpenRouter config loaded from config.py - Model: {model}"
                )
                return api_key, model

        except ImportError:
            logger.warning("⚠️ config.py not found, using env vars only")

        logger.error("❌ OPENROUTER_API_KEY not found in environment or config")
        return None, None

    except Exception as e:
        logger.error(f"❌ Error getting OpenRouter config: {e}")
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
        self.conversations[user_id].append(
            {
                "question": question,
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if len(self.conversations[user_id]) > self.max_history:
            self.conversations[user_id] = self.conversations[user_id][
                -self.max_history :
            ]

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
# OPENROUTER GPT LLM
# ============================================================================


class OpenRouterLLM:
    """OpenRouter GPT API wrapper with improved error handling."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = 60

    def generate_response(self, prompt: str) -> str:
        """Generate response with comprehensive error handling."""
        if not prompt or not prompt.strip():
            return "[Error] Empty prompt provided"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://51talk-ai-learning.com",
            "X-Title": "51Talk AI Learning Platform",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.7,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
        }

        try:
            response = requests.post(
                self.base_url, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 429:
                return "[Rate Limited] Too many requests. Please wait a moment and try again."
            elif response.status_code == 401:
                return "[Authentication Error] Invalid OpenRouter API key. Please check your API configuration."
            elif response.status_code == 402:
                return "[Insufficient Credits] Please check your OpenRouter account balance."
            elif response.status_code == 404:
                return f"[Model Error] Model '{self.model}' not found. Please check your model configuration."
            elif response.status_code != 200:
                logger.error(
                    f"OpenRouter API error: {response.status_code} - {response.text}"
                )
                return (
                    f"[API Error] Service unavailable (Status: {response.status_code})"
                )

            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return "[Error] No response generated by GPT model"

        except requests.exceptions.Timeout:
            return "[Timeout] GPT request timed out. Please try again."
        except requests.exceptions.ConnectionError:
            return "[Connection Error] Unable to connect to OpenRouter service."
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
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
                            "filename": filename,
                        },
                    }
                    docs.append(doc)
            logger.info(f"📄 Loaded {len(docs)} slides from {filename}")
            return docs
        except Exception as e:
            logger.error(f"❌ Error processing PPTX {self.file_path}: {str(e)}")
            return []


# ============================================================================
# DOCUMENT PROCESSOR - RAILWAY COMPATIBLE
# ============================================================================


class DocumentProcessor:
    """FIXED Document processor for Railway deployment."""

    def __init__(self, documents_dir: str = None):
        self.documents_dir = documents_dir or create_temp_documents_from_db()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=100, length_function=len
        )

    def load_documents(self) -> List[Any]:
        all_docs = []

        # Check if documents directory exists and has files
        if not os.path.exists(self.documents_dir):
            logger.error(f"❌ Documents directory does not exist: {self.documents_dir}")
            return []

        files_found = []
        for root, _, files in os.walk(self.documents_dir):
            for file in files:
                if file.lower().endswith((".pdf", ".pptx", ".ppt", ".txt")):
                    files_found.append(file)

        if not files_found:
            logger.warning(
                f"⚠️ No supported document files found in {self.documents_dir}"
            )
            return []

        logger.info(f"📁 Found {len(files_found)} document files: {files_found}")

        # Process each file
        for root, _, files in os.walk(self.documents_dir):
            for file in files:
                file_path = os.path.join(root, file)
                filename = os.path.basename(file_path)
                try:
                    if file.lower().endswith(".pdf"):
                        docs = self._load_pdf(file_path, filename)
                        all_docs.extend(docs)
                        logger.info(f"📄 Loaded {len(docs)} pages from PDF: {filename}")
                    elif file.lower().endswith((".pptx", ".ppt")):
                        loader = PPTXLoader(file_path)
                        docs = loader.load()
                        all_docs.extend(docs)
                        logger.info(
                            f"📄 Loaded {len(docs)} slides from PPTX: {filename}"
                        )
                    elif file.lower().endswith(".txt"):
                        docs = self._load_txt(file_path, filename)
                        all_docs.extend(docs)
                        logger.info(f"📄 Loaded text file: {filename}")
                except Exception as e:
                    logger.error(f"❌ Error processing {file_path}: {str(e)}")
                    continue

        logger.info(f"✅ Total loaded document sections: {len(all_docs)}")
        return all_docs

    def _load_pdf(self, file_path: str, filename: str) -> List[Any]:
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata["filename"] = filename
            return docs
        except Exception as e:
            logger.error(f"❌ Error loading PDF {filename}: {str(e)}")
            return []

    def _load_txt(self, file_path: str, filename: str) -> List[Any]:
        encodings = ["utf-8", "utf-16", "iso-8859-1", "windows-1252"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                if content.strip():
                    return [
                        {
                            "page_content": content.strip(),
                            "metadata": {
                                "source": file_path,
                                "page": 1,
                                "filename": filename,
                            },
                        }
                    ]
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"❌ Error loading TXT {filename}: {str(e)}")
                break
        return []

    def process_documents(self) -> List[Any]:
        docs = self.load_documents()
        if not docs:
            logger.warning("⚠️ No documents loaded")
            return []

        logger.info(f"📄 Processing {len(docs)} documents into chunks...")
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
                content = re.sub(r"\s+", " ", content).strip()
                if len(content) > 50:
                    texts.append(content)
                    metadatas.append(metadata)

            splits = self.text_splitter.create_documents(texts, metadatas=metadatas)
            logger.info(f"✅ Created {len(splits)} document chunks")
            return splits
        except Exception as e:
            logger.error(f"❌ Error processing documents: {str(e)}")
            return []


# ============================================================================
# VECTOR STORE - RAILWAY COMPATIBLE
# ============================================================================


class VectorStore:
    """FIXED Vector store manager for Railway deployment."""

    def __init__(self, documents_dir: str = None, vector_db_path: str = "vector_db"):
        self.documents_dir = documents_dir or create_temp_documents_from_db()
        self.vector_db_path = vector_db_path
        self.embeddings = None
        self.vector_store_instance = None
        self.document_chunks = []
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
                    logger.info(
                        "🚀 Starting Railway-compatible vector store initialization..."
                    )

                    # Load documents from temporary directory (created from database)
                    processor = DocumentProcessor(self.documents_dir)
                    self.document_chunks = processor.process_documents()
                    
                    # Mark as complete - we don't need actual vector store for OpenRouter/GPT
                    self._initialization_complete = True
                    self._is_initializing = False

            except Exception as e:
                self._initialization_error = str(e)
                self._is_initializing = False
                logger.error(f"❌ Failed to initialize vector store: {str(e)}")

        thread = threading.Thread(target=initialize, daemon=True)
        thread.start()

    def get_vector_store(self, timeout: int = 30):
        """For Railway deployment, return a mock retriever that searches document chunks."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._initialization_complete:
                return MockRetriever(self.document_chunks)
            elif self._initialization_error:
                raise Exception(f"Vector store failed: {self._initialization_error}")
            time.sleep(0.5)
        raise TimeoutError("Vector store initialization timed out")

    def is_ready(self) -> bool:
        """For OpenRouter/GPT mode, ready when document chunks are loaded."""
        return self._initialization_complete and len(self.document_chunks) > 0


class MockRetriever:
    """FIXED Mock retriever for Railway deployment."""

    def __init__(self, document_chunks):
        self.document_chunks = document_chunks
        logger.info(f"🔍 MockRetriever initialized with {len(document_chunks)} chunks")

    def as_retriever(self, search_kwargs=None):
        return self

    def get_relevant_documents(self, query, search_kwargs=None):
        """Improved text-based search through document chunks."""
        if not self.document_chunks:
            logger.warning("⚠️ No document chunks available for search")
            return []

        query_lower = query.lower()
        scored_docs = []

        for doc in self.document_chunks:
            content = (
                doc.page_content
                if hasattr(doc, "page_content")
                else doc.get("page_content", "")
            )
            if not content:
                continue

            content_lower = content.lower()

            # Improved scoring based on keyword matches
            score = 0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 2:  # Skip short words
                    # Exact word matches
                    score += content_lower.count(word) * 2
                    # Partial matches
                    if word in content_lower:
                        score += 1

            # Bonus for question words
            question_words = ["what", "how", "why", "when", "where", "which", "who"]
            for qword in question_words:
                if qword in query_lower and qword in content_lower:
                    score += 3

            if score > 0:
                scored_docs.append((score, doc))

        # Sort by score and return top results
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        k = search_kwargs.get("k", 6) if search_kwargs else 6

        results = [doc for score, doc in scored_docs[:k]]
        logger.info(
            f"🔍 Found {len(results)} relevant documents for query: {query[:50]}..."
        )
        return results


# ============================================================================
# MAIN QA SYSTEM - RAILWAY COMPATIBLE
# ============================================================================


class DocumentQA:
    """FIXED Main Document QA system for Railway deployment."""

    def __init__(self, documents_dir: str = None):
        self.documents_dir = documents_dir or create_temp_documents_from_db()
        self.vector_store_manager = VectorStore(self.documents_dir)
        self.gpt_llm = None
        self.conversation_memory = ConversationMemory()
        self.response_cache = {}
        self.cache_max_size = 50

        # Initialize OpenRouter GPT
        api_key, model = get_openrouter_config()
        if api_key and model:
            self.gpt_llm = OpenRouterLLM(api_key, model)
            logger.info(
                f"✅ OpenRouter GPT initialized successfully with model: {model}"
            )
        else:
            logger.error("❌ OpenRouter API not configured properly")

        self.greetings = {
            'hi': "Hello! I'm your AI learning assistant powered by GPT. I can help you with course materials, explain concepts, or just chat about your studies. What would you like to know?",
            'hello': "Hi there! I'm here to help with your learning journey using GPT. You can ask me about course topics, request explanations, or get study tips. How can I assist you today?",
            'hey': "Hey! Great to see you here. I'm your GPT-powered AI tutor ready to help with anything you're studying. What's on your mind?",
            'good morning': "Good morning! Ready to learn something new today? I'm here to help with your course materials using GPT.",
            'good afternoon': "Good afternoon! How's your learning going today? I'm here to help with explanations or questions.",
            'good evening': "Good evening! Perfect time for some learning. What would you like to explore?"
        }

    def answer_question(self, question: str, user_id: str = None) -> Dict[str, Any]:
        """Main method to answer questions using GPT."""
        if not question or not question.strip():
            return {
                "answer": "Hello! I'm your AI assistant. I'm here and ready to help! What would you like to know or discuss?",
                "sources": [],
                "conversation_type": "greeting",
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
                    "conversation_type": "greeting",
                }

            response = self._handle_document_question(question, user_id)
            if user_id:
                self.conversation_memory.add_message(
                    user_id, question, response["answer"]
                )
            return response

        except Exception as e:
            logger.error(f"❌ Error in answer_question: {str(e)}")
            return {
                "answer": "I encountered an error, but I'm still here to help! Could you try rephrasing your question?",
                "sources": [],
                "conversation_type": "error",
            }

    def _detect_conversation_type(self, question_lower: str) -> str:
        greeting_patterns = [
            r"\b(hi|hello|hey|hiya)\b",
            r"\bgood (morning|afternoon|evening|night)\b",
            r"\bhow are you\b",
            r"\bwhat\'?s up\b",
        ]
        if any(re.search(pattern, question_lower) for pattern in greeting_patterns):
            return "greeting"

        document_keywords = [
            "explain",
            "definition",
            "what is",
            "how does",
            "tell me about",
            "course material",
            "lesson",
            "chapter",
            "according to",
        ]
        if any(keyword in question_lower for keyword in document_keywords):
            return "document_based"
        return "general"

    def _handle_greeting(self, question_lower: str) -> str:
        for greeting, response in self.greetings.items():
            if greeting in question_lower:
                return response
        return "Hello! I'm your AI learning assistant. I'm here to help you understand course materials, answer questions, or discuss topics you're studying. What would you like to explore today?"

    def _handle_document_question(
        self, question: str, user_id: str = None
    ) -> Dict[str, Any]:
        """FIXED Handle document questions for Railway deployment."""
        try:
            if not self.gpt_llm:
                return {
                    "answer": "❌ OpenRouter GPT is not properly configured. Please check your API settings in the environment variables.",
                    "sources": [],
                    "conversation_type": "error",
                }

            if not self.vector_store_manager.is_ready():
                if self.vector_store_manager._is_initializing:
                    return {
                        "answer": "⏳ I'm currently loading course materials from the database. Please wait a moment and try again.",
                        "sources": [],
                        "conversation_type": "loading",
                    }
                else:
                    return {
                        "answer": "I don't have access to course materials right now. Please ensure documents are uploaded to the documents directory.",
                        "sources": [],
                        "conversation_type": "error"
                    }
            
            # Get the mock retriever for OpenRouter/GPT mode
            retriever = self.vector_store_manager.get_vector_store(timeout=10)
            if not retriever:
                return {
                    "answer": "❌ I'm having trouble accessing course materials. Please try again.",
                    "sources": [],
                    "conversation_type": "error",
                }

            # Get relevant documents
            docs = retriever.get_relevant_documents(question, search_kwargs={"k": 6})
            
            # Enhanced search with keywords
            keywords = self._extract_keywords(question)
            if keywords:
                keyword_query = " ".join(keywords)
                additional_docs = retriever.get_relevant_documents(keyword_query, search_kwargs={"k": 4})
                seen_contents = {doc.page_content if hasattr(doc, "page_content") else doc.get("page_content", "") for doc in docs}
                for doc in additional_docs:
                    content = doc.page_content if hasattr(doc, "page_content") else doc.get("page_content", "")
                    if content not in seen_contents:
                        docs.append(doc)
                        seen_contents.add(content)
            
            if not docs:
                # If no relevant documents found, still try to answer using GPT general knowledge
                logger.info("No relevant documents found, using GPT general knowledge")
                answer = self._generate_gpt_response_general(question, user_id)
                return {
                    "answer": answer,
                    "sources": [],
                    "conversation_type": "general"
                }
            
            # Prepare context and generate response
            context = self._prepare_context(docs)
            sources = self._extract_sources(docs)
            answer = self._generate_gpt_response(question, context, user_id)

            return {
                "answer": answer,
                "sources": sources,
                "conversation_type": "document_based",
            }

        except Exception as e:
            logger.error(f"❌ Document question error: {str(e)}")
            return {
                "answer": "❌ I encountered an error while processing your question. Please try again.",
                "sources": [],
                "conversation_type": "error",
            }

    def _generate_gpt_response_general(self, question: str, user_id: str = None) -> str:
        """Generate response using GPT without course materials."""
        if not self.gpt_llm:
            return "[Error: OpenRouter GPT not configured. Please check your API settings.]"
        
        prompt = f"""You are a helpful AI learning assistant for an educational platform. The user is asking about a topic that wasn't found in the course materials.

Please provide a helpful, educational response based on your general knowledge. Be clear that this information is not from the specific course materials.

Student Question: {question}

Please provide a helpful, educational response:"""

        try:
            response = self.gpt_llm.generate_response(prompt)
            response += "\n\n*Note: This response is based on general knowledge since I couldn't find specific information about this topic in your course materials.*"
            return response
        except Exception as e:
            logger.error(f"❌ Error generating general GPT response: {e}")
            return "I encountered an issue generating a response. Please try again."

    def _extract_keywords(self, question: str) -> List[str]:
        import string

        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "what",
            "where",
            "when",
            "why",
            "how",
            "who",
            "which",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
        }
        question_clean = question.lower().translate(
            str.maketrans("", "", string.punctuation)
        )
        words = question_clean.split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords[:5]

    def _prepare_context(self, docs, max_length: int = 3000) -> str:
        context_parts = []
        total_length = 0
        for doc in docs:
            content = (
                doc.page_content
                if hasattr(doc, "page_content")
                else doc.get("page_content", "")
            )
            if total_length + len(content) > max_length:
                break
            context_parts.append(content)
            total_length += len(content)
        return "\n\n".join(context_parts)

    def _extract_sources(self, docs) -> List[Dict[str, str]]:
        sources = []
        seen_sources = set()
        for doc in docs:
            metadata = (
                doc.metadata if hasattr(doc, "metadata") else doc.get("metadata", {})
            )
            filename = metadata.get(
                "filename", os.path.basename(metadata.get("source", "Unknown"))
            )
            page = metadata.get("page", metadata.get("slide_number", "Unknown"))
            source_key = f"{filename}_{page}"
            if source_key not in seen_sources:
                sources.append({"file": filename, "page": str(page)})
                seen_sources.add(source_key)
        return sources[:4]

    def _get_cache_key(self, question: str, context: str) -> str:
        combined = f"{question}||{context}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _generate_gpt_response(
        self, question: str, context: str, user_id: str = None
    ) -> str:
        """Generate response using OpenRouter GPT."""
        if not self.gpt_llm:
            return "[Error: OpenRouter GPT not configured. Please check your API settings.]"

        # Check cache
        cache_key = self._get_cache_key(question, context)
        if cache_key in self.response_cache:
            logger.debug("💾 Cache hit for question")
            return self.response_cache[cache_key]

        # Create prompt optimized for GPT models
        prompt = f"""You are a helpful AI learning assistant for the 51Talk AI Learning Platform. You provide clear, accurate, and educational responses based on course materials.

Guidelines:
- Use the course materials provided to give accurate, helpful answers
- Be conversational and friendly in your tone
- Provide specific examples from the course materials when relevant
- If the materials don't fully answer the question, acknowledge this clearly
- Keep responses educational and informative, tailored to the learning context
- Focus on helping students understand concepts rather than just providing facts

Course Materials:
{context}

Student Question: {question}

Please provide a helpful, educational response based on the course materials above:"""

        try:
            response = self.gpt_llm.generate_response(prompt)

            # Cache response
            if len(self.response_cache) >= self.cache_max_size:
                # Remove oldest entry
                oldest_key = next(iter(self.response_cache))
                del self.response_cache[oldest_key]
            self.response_cache[cache_key] = response

            return response
        except Exception as e:
            logger.error(f"❌ Error generating GPT response: {e}")
            return "[Error] I encountered an issue generating a response. Please try again."

    def get_status(self) -> Dict[str, Any]:
        """Get status for Railway deployment."""
        # Count documents in database
        documents = get_documents_from_database()
        document_count = len(documents)

        return {
            "ready": self.vector_store_manager.is_ready() and self.gpt_llm is not None,
            "initializing": self.vector_store_manager._is_initializing,
            "error": self.vector_store_manager._initialization_error,
            "document_count": document_count,
            "llm_provider": "OpenRouter GPT",
            "gpt_available": self.gpt_llm is not None,
            "cache_size": len(self.response_cache),
            "deployment": "Railway Compatible",
            "documents_dir": self.documents_dir,
            "chunks_loaded": len(self.vector_store_manager.document_chunks),
        }


# ============================================================================
# GLOBAL INSTANCE MANAGEMENT
# ============================================================================

_qa_instance = None


def initialize_qa(
    documents_dir: str = None, llama_model_path: str = None
) -> DocumentQA:
    """Initialize the QA system for Railway deployment."""
    global _qa_instance
    if _qa_instance is None:
        # For Railway, always create temp directory from database
        temp_dir = documents_dir or create_temp_documents_from_db()
        logger.info(f"🚀 Initializing Railway-compatible QA system from: {temp_dir}")
        _qa_instance = DocumentQA(temp_dir)
    return _qa_instance


def get_qa_system() -> Optional[DocumentQA]:
    """Get the global QA instance."""
    return _qa_instance


def ask_question(
    question: str,
    documents_dir: str = None,
    llama_model_path: str = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """Simple function to ask a question using GPT on Railway."""
    qa_system = initialize_qa(documents_dir)
    return qa_system.answer_question(question, user_id)


def get_system_status(
    documents_dir: str = None, llama_model_path: str = None
) -> Dict[str, Any]:
    """Get system status for Railway deployment."""
    qa_system = initialize_qa(documents_dir)
    return qa_system.get_status()


def cleanup_qa():
    """Cleanup function for graceful shutdown."""
    global _qa_instance
    try:
        if _qa_instance:
            logger.info("🧹 Cleaning up Railway QA system resources...")
            _qa_instance.response_cache.clear()
            _qa_instance.conversation_memory.conversations.clear()
            _qa_instance = None
            logger.info("✅ Railway QA cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error during QA cleanup: {str(e)}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    try:
        print("🚀 Starting QA System Test with OpenRouter GPT...")
        qa = DocumentQA("documents")
        status = qa.get_status()
        print("QA System Status:", json.dumps(status, indent=2))

        if status["ready"]:
            response = qa.answer_question("Hello!")
            print(f"\n👋 Greeting Response: {response['answer']}")
            
            response = qa.answer_question("What is artificial intelligence?")
            print(f"\n🤖 AI Question Response: {response['answer']}")
        else:
            print("⏳ QA system is not ready. Add documents to the 'documents' directory.")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback

        traceback.print_exc()
