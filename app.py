"""
51Talk AI Learning Platform

A Flask web application providing AI-assisted learning experiences with multilingual support.
This application includes authentication, content management, quiz functionality, and admin features.
"""

from __future__ import annotations

# Standard library imports
import csv
import io
import json
import logging
import os
import random
import re
import secrets
import string
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Callable

# Third-party imports
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Local application imports
from qa import initialize_qa, get_qa_system, get_system_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def validate_app_environment():
    """Validate all required environment variables at startup."""
    required_vars = {
        'DB_HOST': DB_HOST,
        'DB_PASSWORD': DB_PASSWORD,
        'FLASK_SECRET_KEY': app.secret_key,
        'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
        'ACCESS_PASSWORD': ACCESS_PASSWORD
    }
    
    missing = [var for var, value in required_vars.items() if not value]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")
    
    logger.info("✅ All required environment variables validated")

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'fiftyone_learning')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin123')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))


from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,  # key_func as first positional argument
    app=app,             # all other arguments as keyword arguments
    default_limits=["200 per day", "50 per hour"]
)
# Configuration
UPLOAD_FOLDER = 'static/uploads'
LLAMA_MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "models", "Llama-3.2-3B-Instruct-Q3_K_L.gguf"))
# Add this debug line temporarily to check the path:
print(f"DEBUG: Looking for Llama model at: {LLAMA_MODEL_PATH}")
print(f"DEBUG: Model file exists: {os.path.exists(LLAMA_MODEL_PATH)}")
print(f"DEBUG: Current working directory: {os.getcwd()}")
print(f"DEBUG: App file directory: {os.path.dirname(__file__)}")
DOCUMENTS_DIR = os.path.join(os.getcwd(), 'documents')
VECTOR_DB_PATH = os.path.join(os.getcwd(), 'vector_db')
ALLOWED_EXTENSIONS = {
    'pdf',
    'png',
    'jpg',
    'jpeg',
    'gif',
    'ppt',
    'pptx',
    'doc',
    'docx'}
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "5151")
# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv(
    'MAIL_USE_TLS', 'True').lower() in (
        'true', '1', 't')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Create mail instance
mail = Mail(app)

# Global database connection pool
db_connection_pool: Optional[pool.SimpleConnectionPool] = None

app_metrics = {
    'qa_requests': 0,
    'qa_errors': 0,
    'response_times': [],
    'active_users': set()
}
# ==============================================
# Supported languages
LANGUAGES: Dict[str, str] = {
    'en': 'English',
    'zh': '中文',
    'ar': 'العربية'
}

# Camps
CAMPS = {
    'Middle East': 'Middle East',
    'Chinese': 'Chinese'
}

# Translation dictionaries
TRANSLATIONS = {
    'en': {
        'welcome': '51Talk AI Hub',
        'login': 'Login',
        'register': 'Register',
        'username': 'Username',
        'password': 'Password',
        'submit': 'Submit',
        'dashboard': 'Dashboard',
        'ai_chat': 'AI Chat',
        'learning': 'Learning',
        'progress': 'Progress',
        'settings': 'Settings',
        'logout': 'Logout',
        'welcome_msg': 'Welcome to the 51Talk AI Learning Platform!',
        'continue_learning': 'Continue Learning',
        'your_progress': 'Your Progress',
        'unit': 'Unit',
        'completed': 'Completed',
        'score': 'Score',
        'ask_ai': 'Ask the AI',
        'chat_here': 'Type your message here',
        'send': 'Send',
        'learning_materials': 'Learning Materials',
        'quizzes': 'Quizzes',
        'videos': 'Videos',
        'projects': 'Projects',
        'feedback': 'Feedback',
        'account': 'Account',
        'language': 'Language',
        'save': 'Save',
        'learn_unit_desc': 'Learn essential concepts and practice with interactive exercises.',
        'review_unit': 'Review Unit',
        'start_unit': 'Start Unit',
        'locked': 'Locked',
        'units_completed': 'Units Completed',
        'units_remaining': 'Units Remaining',
        'daily_tip': 'Daily Tip',
        'submit_feedback': 'Submit Feedback',
        'your_feedback': 'Your Feedback',
        'rating': 'Rating',
        'excellent': 'Excellent',
        'good': 'Good',
        'average': 'Average',
        'fair': 'Fair',
        'poor': 'Poor',
        'ai_learning_assistant': 'AI Learning Assistant',
        'ask_course_question': 'Ask any question about the course material',
        'your_question': 'Your question',
        'ask_ai_placeholder': 'Ask anything about course materials...',
        'ask_assistant': 'Ask Assistant',
        'assistant_response': 'Assistant\'s Response',
        'ask_another_question': 'Ask Another Question',
        'email': 'Email',
        'confirm_password': 'Confirm Password',
        'reset_password': 'Reset Password',
        'forgot_password': 'Forgot Password',
        'email_verification': 'Email Verification',
        'source_documents': 'Source Documents',
        'quiz_completed': 'Quiz Completed',
        'passed': 'Passed',
        'not_passed': 'Not Passed',
        'unknown_date': 'Unknown date',
        'quiz_already_taken': 'You have already taken this quiz. Click below to review your answers and explanations.',
        'review_quiz_results': 'Review Quiz Results',
        'test_knowledge': 'Test your knowledge with this unit quiz. You can only take this quiz once, so make sure you are ready!',
        'important': 'Important',
        'quiz_one_attempt_warning': 'This quiz can only be taken once. Make sure you have studied the material before proceeding.',
        'take_quiz_one_attempt': 'Take Quiz (One Attempt Only)',
        'no_quiz_available': 'No quiz available for this unit yet.',
        'quiz_review_mode': 'Quiz Review Mode',
        'quiz_review': 'Quiz Review',
        'completed_on': 'Completed on',
        'note': 'Note',
        'quiz_one_attempt_note': 'This quiz can only be taken once. Below is your review showing your answers, the correct answers, and explanations.',
        'correct': 'Correct',
        'incorrect': 'Incorrect',
        'your_answer': 'Your Answer',
        'correct_answer': 'Correct Answer',
        'explanation': 'Explanation',
        'back_to_unit': 'Back to Unit'},
    'zh': {
        'welcome': '51Talk 智能中心',
        'login': '登录',
        'register': '注册',
        'username': '用户名',
        'password': '密码',
        'submit': '提交',
        'dashboard': '仪表板',
        'ai_chat': 'AI聊天',
        'learning': '学习',
        'progress': '进度',
        'settings': '设置',
        'logout': '退出',
        'welcome_msg': '欢迎来到51Talk人工智能学习平台！',
        'continue_learning': '继续学习',
        'your_progress': '您的进度',
        'unit': '单元',
        'completed': '已完成',
        'score': '分数',
        'ask_ai': '问AI',
        'chat_here': '在这里输入您的消息',
        'send': '发送',
        'learning_materials': '学习材料',
        'quizzes': '小测验',
        'videos': '视频',
        'projects': '项目',
        'feedback': '反馈',
        'account': '账户',
        'language': '语言',
        'save': '保存',
        'learn_unit_desc': '学习基本概念并通过互动练习进行练习。',
        'review_unit': '复习单元',
        'start_unit': '开始单元',
        'locked': '已锁定',
        'units_completed': '已完成单元',
        'units_remaining': '剩余单元',
        'daily_tip': '每日提示',
        'submit_feedback': '提交反馈',
        'your_feedback': '您的反馈',
        'rating': '评分',
        'excellent': '优秀',
        'good': '良好',
        'average': '一般',
        'fair': '尚可',
        'poor': '差',
        'ai_learning_assistant': 'AI学习助手',
        'ask_course_question': '提出任何关于课程材料的问题',
        'your_question': '您的问题',
        'ask_ai_placeholder': '询问任何关于课程材料的问题...',
        'ask_assistant': '询问助手',
        'assistant_response': '助手的回答',
        'ask_another_question': '提出另一个问题',
        'email': '电子邮件',
        'confirm_password': '确认密码',
        'reset_password': '重置密码',
        'forgot_password': '忘记密码',
        'email_verification': '电子邮件验证',
        'source_documents': '参考文档',
    },
    'ar': {
        'welcome': '51Talk مركز الذكاءالاصطناعي',
        'login': 'تسجيل الدخول',
        'register': 'التسجيل',
        'username': 'اسم المستخدم',
        'password': 'كلمة المرور',
        'submit': 'إرسال',
        'dashboard': 'اللوحة الرئيسية',
        'ai_chat': 'محادثة الذكاء الاصطناعي',
        'learning': 'التعلم',
        'progress': 'التقدم',
        'settings': 'الإعدادات',
        'logout': 'تسجيل الخروج',
        'welcome_msg': 'مرحباً بك في منصة 51Talk للتعلم بالذكاء الاصطناعي!',
        'continue_learning': 'متابعة التعلم',
        'your_progress': 'تقدمك',
        'unit': 'الوحدة',
                'completed': 'مكتمل',
                'score': 'الدرجة',
                'ask_ai': 'اسأل الذكاء الاصطناعي',
                'chat_here': 'اكتب رسالتك هنا',
                'send': 'إرسال',
                'learning_materials': 'المواد التعليمية',
                'quizzes': 'الاختبارات',
                'videos': 'الفيديوهات',
                'projects': 'المشاريع',
                'feedback': 'التعليقات',
                'account': 'الحساب',
                'language': 'اللغة',
                'save': 'حفظ',
                'learn_unit_desc': 'تعلم المفاهيم الأساسية وتدرب باستخدام التمارين التفاعلية.',
                'review_unit': 'مراجعة الوحدة',
                'start_unit': 'بدء الوحدة',
                'locked': 'مقفل',
                'units_completed': 'الوحدات المكتملة',
                'units_remaining': 'الوحدات المتبقية',
                'daily_tip': 'نصيحة اليوم',
                'submit_feedback': 'إرسال تعليق',
                'your_feedback': 'تعليقك',
                'rating': 'التقييم',
                'excellent': 'ممتاز',
                'good': 'جيد',
                'average': 'متوسط',
                'fair': 'مقبول',
                'poor': 'ضعيف',
                'ai_learning_assistant': 'مساعد التعلم بالذكاء الاصطناعي',
                'ask_course_question': 'اطرح أي سؤال حول مواد الدورة',
                'your_question': 'سؤالك',
                'ask_ai_placeholder': 'اسأل أي شيء عن مواد الدورة...',
                'ask_assistant': 'اسأل المساعد',
                'assistant_response': 'رد المساعد',
                'ask_another_question': 'اطرح سؤالاً آخر',
                'email': 'البريد الإلكتروني',
                'confirm_password': 'تأكيد كلمة المرور',
                'reset_password': 'إعادة تعيين كلمة المرور',
                'forgot_password': 'نسيت كلمة المرور',
                'email_verification': 'التحقق من البريد الإلكتروني',
                'source_documents': 'المستندات المصدر',
    }}

# ==============================================
# UTILITY FUNCTIONS
# ==============================================

def init_db_pool() -> None:
    """Initialize the database connection pool."""
    global db_connection_pool
    try:
        if db_connection_pool is None or db_connection_pool.closed:
            db_connection_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # minconn
                10,  # maxconn
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'fiftyone_learning'),
                user=os.getenv('DB_USER', 'admin'),
                password=os.getenv('DB_PASSWORD', 'admin123')
            )
            logger.info("PostgreSQL connection pool established successfully")
    except Exception as e:
        logger.error(f"Failed to create database connection pool: {str(e)}")
        db_connection_pool = None


def get_db_connection() -> psycopg2.extensions.connection:
    """Get a database connection from the pool."""
    global db_connection_pool

    if db_connection_pool is None or db_connection_pool.closed:
        init_db_pool()

    try:
        if db_connection_pool is not None and not db_connection_pool.closed:
            conn = db_connection_pool.getconn()
            return conn
        else:
            logger.warning(
                "Connection pool not available, creating direct connection")
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'fiftyone_learning'),
                user=os.getenv('DB_USER', 'admin'),
                password=os.getenv('DB_PASSWORD', 'admin123')
            )
            return conn
    except Exception as e:
        logger.error(f"Failed to get database connection: {str(e)}")
        raise


def release_db_connection(
        conn: Optional[psycopg2.extensions.connection]) -> None:
    """Return a connection to the pool."""
    global db_connection_pool

    if conn is None:
        return

    try:
        if db_connection_pool is not None and not db_connection_pool.closed:
            db_connection_pool.putconn(conn)
        else:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to release connection: {str(e)}")
        try:
            conn.close()
        except Exception:
            pass


def generate_verification_code(length: int = 32) -> str:
    """Generate a random verification code."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def validate_ai_input(data):
    """Validate AI request input."""
    if not data:
        raise ValueError("No data provided")
    
    question = data.get('question', '').strip()
    
    if not question:
        raise ValueError("Question is required")
    
    if len(question) > 2000:
        raise ValueError("Question too long (max 2000 characters)")
    
    # Check for potential injection attempts
    suspicious_patterns = ['<script', 'javascript:', 'data:', 'vbscript:']
    question_lower = question.lower()
    
    for pattern in suspicious_patterns:
        if pattern in question_lower:
            raise ValueError("Invalid characters detected")
    
    return question


def send_verification_email(email: str, verification_code: str) -> bool:
    """Send verification email to a user."""
    try:
        verification_link = url_for(
            'verify_email',
            code=verification_code,
            _external=True)

        msg = Message(
            'Verify Your Email - 51Talk AI Learning',
            recipients=[email])
        msg.body = f'''Please verify your email by clicking on the link below:
{verification_link}

If you did not create an account, please ignore this email.
'''
        msg.html = f'''
<h1>Email Verification</h1>
<p>Thank you for registering with 51Talk AI Learning Platform!</p>
<p>Please verify your email by clicking on the link below:</p>
<p><a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 15px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">Verify Email</a></p>
<p>If you did not create an account, please ignore this email.</p>
<p>Best regards,<br>51Talk AI Learning Team</p>
'''

        mail.send(msg)
        logger.info(f"Verification email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False


def login_required(f: Callable) -> Callable:
    """Decorator that checks if user is logged in."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f: Callable) -> Callable:
    """Decorator that checks if user has admin privileges."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not session.get('admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def get_text(key: str) -> str:
    """Get translated text based on current language."""
    lang = session.get('language', 'en')
    text = TRANSLATIONS.get(lang, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get('en', {}).get(key)
    if text is None:
        text = key
    return text


def allowed_file(filename: str) -> bool:
    """Check if a file has an allowed extension."""
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_user_id(username: str) -> Optional[int]:
    """Get user ID by username."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error in get_user_id: {str(e)}")
        return None


def get_progress(user_id: int, unit_id: int) -> Tuple[int, int, int]:
    """Get user progress for a specific unit."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT completed, quiz_score, project_completed
            FROM progress
            WHERE user_id = %s AND unit_number = %s
        """, (user_id, unit_id))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return result if result else (0, 0, 0)
    except Exception as e:
        logger.error(f"Error in get_progress: {str(e)}")
        return (0, 0, 0)


def has_attempted_quiz(user_id: int, unit_id: int) -> bool:
    """Check if a user has attempted a quiz."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s
        """, (user_id, unit_id))
        result = cursor.fetchone()[0] > 0
        cursor.close()
        release_db_connection(conn)
        return result
    except Exception as e:
        logger.error(f"Error in has_attempted_quiz: {str(e)}")
        return False


def get_quiz_attempt_info(
        user_id: int, unit_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about a user's quiz attempt."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT score, attempted_at, passed
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s
            ORDER BY attempted_at DESC
            LIMIT 1
        """, (user_id, unit_id))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)

        if result:
            return {
                'score': result['score'],
                'attempted_at': result['attempted_at'],
                'passed': result['passed']
            }
        return None
    except Exception as e:
        logger.error(f"Error in get_quiz_attempt_info: {str(e)}")
        return None


def can_take_quiz(user_id: int, unit_id: int) -> bool:
    """Check if a user can take a quiz (hasn't attempted it yet)."""
    return not has_attempted_quiz(user_id, unit_id)


def get_user_camp(user_id: int) -> Optional[str]:
    """Get user's camp."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT camp FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting user camp: {str(e)}")
        return None
    

def camp_required(f: Callable) -> Callable:
    """Decorator that ensures user has selected a camp."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user_camp = get_user_camp(session['user_id'])
        if not user_camp:
            flash('Please select your training camp first.', 'warning')
            return redirect(url_for('select_camp'))
        
        session['user_camp'] = user_camp
        return f(*args, **kwargs)
    return decorated_function


def get_admin_stats() -> Dict[str, int]:
    """Get statistics for admin dashboard."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        stats: Dict[str, int] = {}

        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM quizzes")
        stats['total_quizzes'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM materials")
        stats['total_materials'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM videos")
        stats['total_videos'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM projects")
        stats['total_projects'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM submissions")
        stats['total_submissions'] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM qa_history WHERE date(created_at) = CURRENT_DATE")
        stats['today_qa'] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM quiz_attempts WHERE date(attempted_at) = CURRENT_DATE")
        stats['today_quiz_attempts'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM teams")
        stats['total_teams'] = cursor.fetchone()[0]

        document_count = 0
        for root, _, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                if file.endswith('.pdf') or file.endswith(
                        '.ppt') or file.endswith('.pptx'):
                    document_count += 1
        stats['total_documents'] = document_count

        cursor.close()
        release_db_connection(conn)
        return stats
    except Exception as e:
        logger.error(f"Error in get_admin_stats: {str(e)}")
        return {
            'total_users': 0,
            'total_quizzes': 0,
            'total_materials': 0,
            'total_videos': 0,
            'total_projects': 0,
            'total_submissions': 0,
            'today_qa': 0,
            'today_quiz_attempts': 0,
            'total_teams': 0,
            'total_documents': 0
        }


def generate_csv_file(data: List, filename: str,
                      headers: Optional[List[str]] = None) -> Optional[str]:
    """Create a CSV file from data."""
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode='w', suffix='.csv')

    try:
        writer = csv.writer(temp_file)

        if headers:
            writer.writerow(headers)

        for row in data:
            writer.writerow(row)

        temp_file.close()
        return temp_file.name
    except Exception as e:
        temp_file.close()
        os.unlink(temp_file.name)
        logger.error(f"Error generating CSV: {str(e)}")
        return None


def update_team_score(user_id: int, score_to_add: int) -> None:
    """Update a team's score based on user activity."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tm.team_id
            FROM team_members tm
            WHERE tm.user_id = %s
        """, (user_id,))

        result = cursor.fetchone()
        if not result:
            return

        team_id = result[0]

        cursor.execute("""
            SELECT id FROM team_scores WHERE team_id = %s
        """, (team_id,))

        if cursor.fetchone():
            cursor.execute("""
                UPDATE team_scores
                SET score = score + %s, updated_at = CURRENT_TIMESTAMP
                WHERE team_id = %s
            """, (score_to_add, team_id))
        else:
            cursor.execute("""
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, %s)
            """, (team_id, score_to_add))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating team score: {str(e)}")
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def get_document_list() -> List[Dict[str, Any]]:
    """Get a list of documents available for Q&A."""
    documents = []
    try:
        for root, _, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                if file.endswith('.pdf') or file.endswith(
                        '.ppt') or file.endswith('.pptx'):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    documents.append({
                        'name': file,
                        'size': f"{file_size / 1024 / 1024:.2f} MB",
                        'type': file.split('.')[-1].upper(),
                        'added': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                        'path': os.path.relpath(root, DOCUMENTS_DIR)
                    })
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
    return documents


def save_qa_history_async(user_id: int, question: str, answer: str):
    """Save QA history asynchronously to avoid blocking main thread."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qa_history (user_id, question, answer)
            VALUES (%s, %s, %s)
        """, (user_id, question, answer))
        conn.commit()
        cursor.close()
        logger.debug(f"QA history saved successfully for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving QA history async: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)


def initialize_enhanced_qa_system():
    """Initialize the enhanced QA system with Llama model and RAG"""
    try:
        documents_dir = DOCUMENTS_DIR

        if not os.path.exists(documents_dir):
            logger.warning(f"Documents directory not found: {documents_dir}")
            os.makedirs(documents_dir, exist_ok=True)
            logger.info(f"Please add your course materials to: {documents_dir}")
            return

        # Check for documents
        supported_files = []
        for root, dirs, files in os.walk(documents_dir):
            for file in files:
                if file.lower().endswith(('.pdf', '.pptx', '.ppt', '.txt')):
                    supported_files.append(file)

        if not supported_files:
            logger.warning(f"No supported documents found in {documents_dir}")
            logger.info("Supported formats: PDF (.pdf), PowerPoint (.pptx, .ppt), Text (.txt)")
            return

        # Check if Llama model exists
        model_path = LLAMA_MODEL_PATH
        model_exists = os.path.exists(model_path) if model_path else False
        
        if model_exists:
            logger.info(f"Found Llama model at: {model_path}")
        else:
            logger.warning(f"Llama model not found at: {model_path}")
            logger.info("QA system will work with RAG but without Llama enhancements")

        logger.info(f"Found {len(supported_files)} document(s) to process")
        logger.info("Starting enhanced QA system initialization...")

        # Initialize in background
        def init_in_background():
            try:
                qa_system = initialize_qa(
                    documents_dir=documents_dir,
                    llama_model_path=model_path if model_exists else None
                )
                if qa_system:
                    logger.info("Enhanced QA system initialization completed successfully")
                    if qa_system.llama_llm:
                        logger.info("✓ Llama model loaded successfully")
                    else:
                        logger.info("⚠ Running without Llama model (rule-based fallback)")
                    logger.info("✓ RAG system with vector embeddings ready")
                else:
                    logger.warning("QA initialization completed but system not ready")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced QA system: {str(e)}")

        init_thread = threading.Thread(target=init_in_background, daemon=True)
        init_thread.start()

    except Exception as e:
        logger.error(f"Error starting enhanced QA initialization: {str(e)}")


def cleanup_simple_qa():
    """Cleanup function for graceful shutdown."""
    try:
        logger.info("Starting cleanup of DocumentQA resources...")
        document_qa = get_qa_system()
        if document_qa and hasattr(document_qa, 'vector_store_manager'):
            logger.info("Cleaning up DocumentQA resources...")
        logger.info("DocumentQA cleanup completed")
    except Exception as e:
        logger.error(f"Error during DocumentQA cleanup: {str(e)}")



# ===============================================
#metrics endpoints
#===============================================
# Add metrics endpoint
@app.route('/metrics')
@admin_required
def metrics():
    """Application metrics for monitoring."""
    avg_response_time = (
        sum(app_metrics['response_times']) / len(app_metrics['response_times'])
        if app_metrics['response_times'] else 0
    )
    
    return jsonify({
        'qa_requests_total': app_metrics['qa_requests'],
        'qa_errors_total': app_metrics['qa_errors'],
        'qa_success_rate': (
            (app_metrics['qa_requests'] - app_metrics['qa_errors']) / app_metrics['qa_requests']
            if app_metrics['qa_requests'] > 0 else 0
        ),
        'avg_response_time_seconds': round(avg_response_time, 2),
        'active_users_count': len(app_metrics['active_users']),
        'timestamp': datetime.utcnow().isoformat()
    })
# ==============================================
# APPLICATION HOOKS
# ==============================================

@app.before_request
def before_request() -> None:
    """Ensure language is set before each request."""
    if 'language' not in session:
        if 'user_id' in session:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT language FROM users WHERE id = %s", (session['user_id'],))
                result = cursor.fetchone()
                cursor.close()
                release_db_connection(conn)
                if result and result[0]:
                    session['language'] = result[0]
                    logger.info(
                        f"Setting language to {result[0]} from database for user {session['user_id']}")
                else:
                    session['language'] = 'en'
                    logger.info(
                        "No language found for user, defaulting to 'en'")
            except Exception as e:
                logger.error(
                    f"Error retrieving language from database: {str(e)}")
                session['language'] = 'en'
        else:
            session['language'] = 'en'
            logger.debug("No user logged in, defaulting to 'en'")

@app.after_request
def add_header(response: Any) -> Any:
    """Add headers to prevent caching."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.context_processor
def inject_globals() -> Dict[str, Any]:
    """Make important variables available to all templates."""
    return {
        'LANGUAGES': LANGUAGES,
        'get_text': get_text,
        'current_language': session.get('language', 'en'),
        'get_quiz_attempt_info': get_quiz_attempt_info,
        'has_attempted_quiz': has_attempted_quiz,
        'can_take_quiz': can_take_quiz
    }


@app.context_processor
def inject_camps() -> Dict[str, Any]:
    """Make camps available to all templates."""
    return {
        'CAMPS': CAMPS,
        'get_user_camp': get_user_camp,
        'user_camp': session.get('user_camp')
    }


@app.teardown_appcontext
def close_db_pool(e: Optional[Exception] = None) -> None:
    """Close the database connection pool when the application context ends."""
    global db_connection_pool
    try:
        if db_connection_pool and not db_connection_pool.closed:
            db_connection_pool.closeall()
            logger.info("Connection pool closed")
    except Exception as e:
        logger.error(f"Error closing connection pool: {str(e)}")

# ==============================================
# MAIN APPLICATION ROUTES
# ==============================================


@app.route('/', methods=['GET', 'POST'])
def password_gate() -> Any:
    """Handle the initial password gate to access the application."""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ACCESS_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('home'))
        else:
            flash('Incorrect password. Please try again.', 'error')
    return render_template('password_gate.html')


@app.route('/home', methods=['GET'])
def home() -> Any:
    """Display the home page or redirect to dashboard if logged in."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    return render_template('index.html')


@app.route('/logout')
def logout() -> Any:
    """Handle user logout for both regular users and admin users."""
    session.pop('authenticated', None)
    session.pop('username', None)
    session.pop('language', None)
    session.pop('admin', None)
    session.pop('admin_username', None)
    session.pop('user_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('password_gate'))

# ==============================================
# USER AUTHENTICATION ROUTES
# ==============================================


@app.route('/register', methods=['GET', 'POST'])
def register() -> Any:
    """Handle user registration with camp selection."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        camp = request.form.get('camp')  # New field

        if not all([username, email, password, confirm_password, camp]):
            flash('All fields are required.', 'error')
            return render_template('register.html', camps=CAMPS)

        if camp not in CAMPS:
            flash('Please select a valid training camp.', 'error')
            return render_template('register.html', camps=CAMPS)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html', camps=CAMPS)

        if not EMAIL_REGEX.match(email):
            flash('Invalid email address.', 'error')
            return render_template('register.html', camps=CAMPS)

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html', camps=CAMPS)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        verification_code = generate_verification_code()

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists.', 'error')
                return render_template('register.html', camps=CAMPS)

            cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already exists.', 'error')
                return render_template('register.html', camps=CAMPS)

            cursor.execute(
                "INSERT INTO users (username, email, password, verification_code, language, camp) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (username, email, hashed_password, verification_code, 'en', camp)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()

            if send_verification_email(email, verification_code):
                flash('Registration successful! Please check your email to verify your account.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Registration successful but failed to send verification email. Please contact support.', 'warning')
                return redirect(url_for('login'))

        except psycopg2.errors.UniqueViolation:
            if conn:
                conn.rollback()
            flash('Username or email already exists.', 'error')
            return render_template('register.html', camps=CAMPS)
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('register.html', camps=CAMPS)
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template('register.html', camps=CAMPS)


@app.route('/verify-email/<code>')
def verify_email(code: str) -> Any:
    """Verify a user's email address with the provided code."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email FROM users WHERE verification_code = %s AND email_verified = FALSE",
            (code,)
        )
        user = cursor.fetchone()

        if user:
            cursor.execute(
                "UPDATE users SET email_verified = TRUE, verification_code = NULL WHERE id = %s",
                (user[0],)
            )
            conn.commit()
            flash('Email verified successfully! You can now log in.', 'success')
        else:
            flash('Invalid or expired verification link.', 'error')
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Email verification error: {str(e)}")
        flash('An error occurred during email verification.', 'error')
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)

    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login() -> Any:
    """Handle user login."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                "SELECT id, username, email, password, email_verified, language FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

            if not user:
                flash('Invalid email or password.', 'error')
                return render_template('login.html')

            if not check_password_hash(user['password'], password):
                flash('Invalid email or password.', 'error')
                return render_template('login.html')

            if not user['email_verified']:
                cursor.execute(
                    "SELECT verification_code FROM users WHERE id = %s", (user['id'],))
                verification_info = cursor.fetchone()

                if verification_info and verification_info['verification_code']:
                    new_code = generate_verification_code()
                    cursor.execute(
                        "UPDATE users SET verification_code = %s WHERE id = %s",
                        (new_code, user['id'])
                    )
                    conn.commit()

                    send_verification_email(user['email'], new_code)
                    flash(
                        'Your email is not verified. A new verification email has been sent.',
                        'warning')
                else:
                    new_code = generate_verification_code()
                    cursor.execute(
                        "UPDATE users SET verification_code = %s WHERE id = %s",
                        (new_code, user['id'])
                    )
                    conn.commit()

                    send_verification_email(user['email'], new_code)
                    flash(
                        'Your email is not verified. A verification email has been sent.',
                        'warning')

                return render_template('login.html')

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['authenticated'] = True

            if user['language']:
                session['language'] = user['language']
            else:
                session['language'] = 'en'

            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login. Please try again.', 'error')
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password() -> Any:
    """Handle password reset request."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Email is required.', 'error')
            return render_template('forgot_password.html')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, email FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                reset_code = generate_verification_code()

                cursor.execute(
                    "UPDATE users SET verification_code = %s WHERE id = %s",
                    (reset_code, user[0])
                )
                conn.commit()

                reset_link = url_for(
                    'reset_password',
                    code=reset_code,
                    _external=True)

                msg = Message(
                    'Reset Your Password - 51Talk AI Learning',
                    recipients=[email])
                msg.body = f'''Click the link below to reset your password:
{reset_link}

If you didn't request a password reset, please ignore this email.
'''
                msg.html = f'''
<h1>Password Reset</h1>
<p>You've requested to reset your password for your 51Talk AI Learning account.</p>
<p>Click the link below to reset your password:</p>
<p><a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 15px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">Reset Password</a></p>
<p>If you didn't request a password reset, please ignore this email.</p>
<p>Best regards,<br>51Talk AI Learning Team</p>
'''
                mail.send(msg)
                logger.info(f"Password reset email sent to {email}")

            flash(
                'If an account with that email exists, a password reset link has been sent.',
                'success')
            return redirect(url_for('login'))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Password reset error: {str(e)}")
            flash('An error occurred. Please try again later.', 'error')
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template('forgot_password.html')


@app.route('/reset-password/<code>', methods=['GET', 'POST'])
def reset_password(code: str) -> Any:
    """Handle password reset functionality."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('reset_password.html', code=code)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', code=code)

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('reset_password.html', code=code)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM users WHERE verification_code = %s", (code,))
            user = cursor.fetchone()

            if user:
                hashed_password = generate_password_hash(password)
                cursor.execute(
                    "UPDATE users SET password = %s, verification_code = NULL WHERE id = %s",
                    (hashed_password, user[0])
                )
                conn.commit()

                flash('Your password has been updated successfully.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Invalid or expired reset link.', 'error')
                return redirect(url_for('login'))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Password reset error: {str(e)}")
            flash('An error occurred. Please try again later.', 'error')
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE verification_code = %s", (code,))
        user = cursor.fetchone()

        if not user:
            flash('Invalid or expired reset link.', 'error')
            return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Password reset validation error: {str(e)}")
        flash('An error occurred. Please try again later.', 'error')
        return redirect(url_for('login'))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)

    return render_template('reset_password.html', code=code)


@app.route('/select_camp', methods=['GET', 'POST'])
@login_required
def select_camp() -> Any:
    """Allow users to select their training camp."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    user_id = session['user_id']
    
    # Check if user already has a camp
    current_camp = get_user_camp(user_id)
    if current_camp:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        camp = request.form.get('camp')
        
        if camp not in CAMPS:
            flash('Please select a valid training camp.', 'error')
            return render_template('select_camp.html', camps=CAMPS)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET camp = %s WHERE id = %s", (camp, user_id))
            conn.commit()
            cursor.close()
            
            session['user_camp'] = camp
            flash(f'Welcome to {camp} training camp!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            logger.error(f"Error setting user camp: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('select_camp.html', camps=CAMPS)
# ==============================================
# USER DASHBOARD & LEARNING ROUTES
# ==============================================


@app.route('/dashboard')
@login_required
def dashboard() -> Any:
    """Display user dashboard with progress and team information."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = session['user_id']
    current_language = session.get('language', 'en')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT COUNT(DISTINCT unit_number) FROM progress WHERE user_id=%s AND completed=1",
            (user_id,
             ))
        completed_units = cursor.fetchone()['count'] or 0

        cursor.execute("""
            SELECT t.id, t.name, t.camp, u.username AS team_lead_name
            FROM teams t
            JOIN team_members tm ON t.id = tm.team_id
            JOIN users u ON t.team_lead_id = u.id
            WHERE tm.user_id = %s
        """, (user_id,))
        user_team = cursor.fetchone()

        cursor.execute("""
            SELECT t.name, ts.score, u.username AS team_lead_name
            FROM teams t
            JOIN team_scores ts ON t.id = ts.team_id
            JOIN users u ON t.team_lead_id = u.id
            WHERE t.camp = 'Middle East'
            ORDER BY ts.score DESC
            LIMIT 3
        """)
        top_teams_me = cursor.fetchall()

        cursor.execute("""
            SELECT t.name, ts.score, u.username AS team_lead_name
            FROM teams t
            JOIN team_scores ts ON t.id = ts.team_id
            JOIN users u ON t.team_lead_id = u.id
            WHERE t.camp = 'Chinese'
            ORDER BY ts.score DESC
            LIMIT 3
        """)
        top_teams_cn = cursor.fetchall()

        cursor.close()
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        completed_units = 0
        user_team = None
        top_teams_me = []
        top_teams_cn = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('dashboard.html',
                           username=username,
                           completed_units=completed_units,
                           current_language=current_language,
                           user_team=user_team,
                           top_teams_me=top_teams_me,
                           top_teams_cn=top_teams_cn)


@app.route('/set_language/<language>')
def set_language(language: str) -> Any:
    """Change the user interface language."""
    if language in LANGUAGES:
        session.pop('language', None)
        session['language'] = language

        if 'user_id' in session:
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET language=%s WHERE id=%s",
                    (language,
                     session['user_id']))
                conn.commit()
                logger.info(
                    f"Language updated to {language} for user {session['user_id']}")
            except Exception as e:
                logger.error(f"Error updating language in database: {str(e)}")
            finally:
                if conn:
                    cursor.close()
                    release_db_connection(conn)

        session.modified = True
        flash(f"Language changed to {LANGUAGES[language]}", "success")

    return redirect(
        request.referrer +
        f"?lang_change={language}" if request.referrer else url_for('dashboard'))


@app.route('/debug_translation')
def debug_translation() -> Any:
    """Debug endpoint for translation system."""
    current_lang = session.get('language', 'en')
    username = session.get('username', 'not logged in')
    user_id = session.get('user_id', None)

    db_lang = 'unknown'
    if user_id:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT language FROM users WHERE id=%s", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            release_db_connection(conn)
            if result:
                db_lang = result[0]
        except Exception as e:
            db_lang = f"Error: {str(e)}"

    test_keys = [
        'welcome',
        'login',
        'register',
        'dashboard',
        'logout',
        'settings']
    translations = {}
    for key in test_keys:
        translations[key] = get_text(key)

    all_translations = {}
    for key in TRANSLATIONS.get(current_lang, {}):
        all_translations[key] = TRANSLATIONS[current_lang][key]

    return jsonify({
        'username': username,
        'user_id': user_id,
        'session_language': current_lang,
        'db_language': db_lang,
        'sample_translations': translations,
        'available_translations': all_translations,
        'all_languages': LANGUAGES
    })


@app.route('/unit/<int:unit_id>', methods=['GET', 'POST'])
@login_required
@camp_required  # Add this decorator
def unit(unit_id: int) -> Any:
    """Display a learning unit with camp-based filtering."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = session['user_id']
    user_camp = session.get('user_camp')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Handle POST requests (existing logic remains the same)
        if request.method == 'POST' and 'complete' in request.form:
            cursor.execute("SELECT id FROM progress WHERE user_id=%s AND unit_number=%s", (user_id, unit_id))
            if cursor.fetchone():
                cursor.execute("UPDATE progress SET completed=1 WHERE user_id=%s AND unit_number=%s", (user_id, unit_id))
            else:
                cursor.execute("INSERT INTO progress (user_id, unit_number, completed) VALUES (%s, %s, 1)", (user_id, unit_id))
            conn.commit()
            return redirect(url_for('dashboard'))

        if request.method == 'POST' and 'submit_project' in request.form:
            file = request.files.get('project_file')
            if file and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                filename = f"{unit_id}_{user_id}_{original_filename}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)

                cursor.execute("INSERT INTO submissions (user_id, unit_id, file_path) VALUES (%s, %s, %s)", (user_id, unit_id, filename))

                cursor.execute("SELECT id FROM progress WHERE user_id=%s AND unit_number=%s", (user_id, unit_id))
                if cursor.fetchone():
                    cursor.execute("UPDATE progress SET project_completed = 1 WHERE user_id = %s AND unit_number = %s", (user_id, unit_id))
                else:
                    cursor.execute("INSERT INTO progress (user_id, unit_number, project_completed) VALUES (%s, %s, 1)", (user_id, unit_id))

                conn.commit()
                flash('Project submitted successfully!', 'success')
                return redirect(url_for('unit', unit_id=unit_id))

        # Fetch project info with camp filtering
        cursor.execute("""
            SELECT title, description, resources FROM projects 
            WHERE unit_id = %s AND (camp = %s OR camp = 'both')
        """, (unit_id, user_camp))
        project = cursor.fetchone()

        # Fetch materials with camp filtering
        cursor.execute("""
            SELECT title, content, file_path FROM materials 
            WHERE unit_id = %s AND (camp = %s OR camp = 'both')
        """, (unit_id, user_camp))
        materials = cursor.fetchall()

        # Fetch videos with camp filtering
        cursor.execute("""
            SELECT title, youtube_url, description FROM videos 
            WHERE unit_id = %s AND (camp = %s OR camp = 'both')
        """, (unit_id, user_camp))
        videos = cursor.fetchall()

        # Fetch vocabulary words with camp filtering
        cursor.execute("""
            SELECT id, word, definition, example, section,
                   one_sentence_version, daily_definition, life_metaphor,
                   visual_explanation, core_elements, scenario_theater,
                   misunderstandings, reality_connection, thinking_bubble,
                   smiling_conclusion
            FROM words
            WHERE unit_id = %s AND (camp = %s OR camp = 'both')
            ORDER BY section, id
        """, (unit_id, user_camp))

        rows = cursor.fetchall()
        words = []
        columns = ['id', 'word', 'definition', 'example', 'section',
                  'one_sentence_version', 'daily_definition', 'life_metaphor',
                  'visual_explanation', 'core_elements', 'scenario_theater',
                  'misunderstandings', 'reality_connection', 'thinking_bubble',
                  'smiling_conclusion']
        
        for row in rows:
            w = dict(zip(columns, row))
            # Parse core_elements safely (existing logic)
            if w.get('core_elements'):
                try:
                    core_raw = json.loads(w['core_elements'])
                    if isinstance(core_raw, list):
                        if core_raw and isinstance(core_raw[0], dict):
                            w['core_elements'] = core_raw
                        else:
                            parsed = []
                            for item in core_raw:
                                if isinstance(item, str) and '-' in item:
                                    parts = item.split('-', 1)
                                    if len(parts) == 2:
                                        parsed.append({
                                            "core_element": parts[0].strip(),
                                            "everyday_object": parts[1].strip()
                                        })
                            w['core_elements'] = parsed
                    else:
                        w['core_elements'] = []
                except (json.JSONDecodeError, TypeError, IndexError) as e:
                    logger.warning(f"Error parsing core_elements for word {w.get('id', 'unknown')}: {e}")
                    w['core_elements'] = []
            else:
                w['core_elements'] = []
            words.append(w)

        # Get user progress
        progress = get_progress(user_id, unit_id)
        project_completed = progress[2] if progress else 0
        quiz_attempted = has_attempted_quiz(user_id, unit_id)

        # Get quiz attempt info if quiz was attempted
        quiz_attempt_info = None
        if quiz_attempted:
            quiz_attempt_info = get_quiz_attempt_info(user_id, unit_id)

        quiz_id = None
        cursor.execute("SELECT id FROM quizzes WHERE unit_id=%s AND (camp = %s OR camp = 'both') LIMIT 1", (unit_id, user_camp))
        quiz_result = cursor.fetchone()
        if quiz_result:
            quiz_id = quiz_result[0]

        cursor.close()

    except Exception as e:
        logger.error(f"Unit page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "error")
        project = None
        materials = []
        videos = []
        words = []
        project_completed = 0
        quiz_attempted = False
        quiz_attempt_info = None
        quiz_id = None
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('unit.html',
                         username=username,
                         unit_id=unit_id,
                         project=project,
                         materials=materials,
                         videos=videos,
                         words=words,
                         project_completed=project_completed,
                         quiz_attempted=quiz_attempted,
                         quiz_attempt_info=quiz_attempt_info,
                         quiz_id=quiz_id,
                         user_camp=user_camp)


@app.route('/quiz/<int:unit_id>', methods=['GET', 'POST'])
@login_required
@camp_required
def quiz(unit_id: int) -> Any:
    """Display and process quizzes for a unit with camp-based filtering - can only be taken once."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = session['user_id']
    user_camp = session.get('user_camp')

    # Check prerequisite
    if unit_id > 1:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT completed FROM progress WHERE user_id=%s AND unit_number=%s",
                (user_id, unit_id - 1))
            previous_unit = cursor.fetchone()
            cursor.close()

            if not previous_unit or previous_unit[0] != 1:
                flash('You need to complete the previous unit first!', 'warning')
                return redirect(url_for('unit', unit_id=unit_id - 1))
        except Exception as e:
            logger.error(f"Quiz prerequisite check error: {str(e)}")
            flash("An error occurred while checking prerequisites.", "error")
        finally:
            if conn:
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the user's latest quiz attempt for this unit
        cursor.execute("""
            SELECT id, score, attempted_at, passed
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s
            ORDER BY attempted_at DESC
            LIMIT 1
        """, (user_id, unit_id))
        attempt = cursor.fetchone()

        if attempt and attempt[1] is not None:
            # Review mode
            attempt_id, score, attempted_at, passed = attempt

            # Fix passed status if needed
            cursor.execute(
                "SELECT COUNT(*) FROM quizzes WHERE unit_id = %s AND (camp = %s OR camp = 'both')", 
                (unit_id, user_camp))
            total_questions = cursor.fetchone()[0]
            min_passing = max(3, int(total_questions * 0.6))
            should_have_passed = score >= min_passing

            if should_have_passed != passed:
                logger.info(
                    f"Fixing passed status: score={score}, total={total_questions}, should_pass={should_have_passed}")
                cursor.execute(
                    "UPDATE quiz_attempts SET passed = %s WHERE id = %s",
                    (should_have_passed, attempt_id))
                conn.commit()
                passed = should_have_passed

            # Fetch questions + responses with correction logic and camp filtering
            cursor.execute("""
                SELECT q.id, q.question, q.options, q.correct_answer, q.explanation,
                       qr.user_answer, qr.is_correct
                FROM quizzes q
                LEFT JOIN quiz_responses qr ON q.id = qr.question_id AND qr.attempt_id = %s
                WHERE q.unit_id = %s AND (q.camp = %s OR q.camp = 'both')
                ORDER BY q.id
            """, (attempt_id, unit_id, user_camp))
            question_data = cursor.fetchall()

            if not question_data:
                flash('No questions found for this quiz in your camp', 'error')
                return redirect(url_for('unit', unit_id=unit_id))

            review_results = []
            for q_data in question_data:
                q_id, question_text, options_json, correct_answer, explanation, user_answer, is_correct = q_data

                try:
                    options = json.loads(options_json)
                except json.JSONDecodeError:
                    options = []

                # Calculate correctness manually in case DB is inconsistent
                calculated_correct = False
                if user_answer is not None and user_answer == correct_answer:
                    calculated_correct = True

                final_correct = calculated_correct if is_correct is None else is_correct

                if is_correct is not None and is_correct != calculated_correct:
                    logger.warning(
                        f"Database inconsistency: question {q_id}, "
                        f"user_answer={user_answer}, correct_answer={correct_answer}, "
                        f"db_correct={is_correct}, calculated={calculated_correct}"
                    )
                    final_correct = calculated_correct

                review_results.append({
                    'question': question_text,
                    'options': options,
                    'correct_index': correct_answer,
                    'user_answer': user_answer,
                    'explanation': explanation or "No explanation available",
                    'correct': final_correct
                })

            for i, result in enumerate(review_results):
                logger.info(
                    f"Question {i + 1}: user_answer={result['user_answer']}, "
                    f"correct_index={result['correct_index']}, correct={result['correct']}")

            overall_result = f"You passed this quiz with {score}/{total_questions} correct answers!" if passed else f"You scored {score}/{total_questions}. You needed at least {min_passing} to pass."
            motivation = "Great job! You've successfully completed this unit." if passed else "You can review the material and continue learning. Contact your instructor if you need help."

            return render_template('quiz_review.html',
                                   username=username,
                                   unit_id=unit_id,
                                   score=score,
                                   total=total_questions,
                                   passed=passed,
                                   results=review_results,
                                   overall_result=overall_result,
                                   motivation=motivation,
                                   attempted_at=attempted_at,
                                   is_review=True,
                                   user_camp=user_camp)

        # Quiz submission (POST)
        if request.method == 'POST':
            cursor.execute("""
                SELECT id, question, options, correct_answer FROM quizzes 
                WHERE unit_id=%s AND (camp = %s OR camp = 'both')
            """, (unit_id, user_camp))
            questions = cursor.fetchall()

            if not questions:
                flash('No questions found for this quiz in your camp', 'error')
                return redirect(url_for('unit', unit_id=unit_id))

            score = 0
            results = []

            cursor.execute("""
                INSERT INTO quiz_attempts (user_id, unit_id, score, passed)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (user_id, unit_id, 0, False))
            attempt_id = cursor.fetchone()[0]

            for q in questions:
                q_id = q[0]
                user_answer = request.form.get(f'q{q_id}')
                correct = False
                if user_answer and int(user_answer) == q[3]:
                    score += 1
                    correct = True
                cursor.execute("""
                    INSERT INTO quiz_responses (attempt_id, question_id, user_answer, is_correct)
                    VALUES (%s, %s, %s, %s)
                """, (attempt_id, q_id, int(user_answer) if user_answer else None, correct))

                cursor.execute(
                    "SELECT explanation FROM quizzes WHERE id=%s", (q_id,))
                explanation = cursor.fetchone()[0]

                results.append({
                    'question': q[1],
                    'options': json.loads(q[2]),
                    'correct_index': q[3],
                    'user_answer': int(user_answer) if user_answer else None,
                    'explanation': explanation,
                    'correct': correct
                })

            total_questions = len(questions)
            min_passing = max(3, int(total_questions * 0.6))
            passed = score >= min_passing

            cursor.execute("""
                UPDATE quiz_attempts
                SET score = %s, passed = %s
                WHERE id = %s
            """, (score, passed, attempt_id))

            if passed:
                overall_result = f"Congratulations! You passed with {score}/{total_questions} correct answers!"
                motivation = random.choice([
                    "Awesome job! You're making excellent progress!",
                    "You're crushing it! Keep up the fantastic work!",
                    "Success! Your hard work is paying off!",
                    "Brilliant! You're mastering this material!",
                    "Stellar performance! You should be proud!"
                ])
                cursor.execute(
                    "SELECT id FROM progress WHERE user_id=%s AND unit_number=%s",
                    (user_id, unit_id))
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE progress SET quiz_score=%s, completed=1
                        WHERE user_id=%s AND unit_number=%s
                    """, (score, user_id, unit_id))
                else:
                    cursor.execute("""
                        INSERT INTO progress (user_id, unit_number, quiz_score, completed)
                        VALUES (%s, %s, %s, 1)
                    """, (user_id, unit_id, score))
                update_team_score(user_id, score)
            else:
                overall_result = f"You scored {score}/{total_questions}. You need at least {min_passing} correct answers to pass."
                motivation = "You can review the material and contact your instructor for additional help. This quiz can only be taken once."

            conn.commit()

            return render_template('quiz_result.html',
                                   username=username,
                                   unit_id=unit_id,
                                   score=score,
                                   total=total_questions,
                                   passed=passed,
                                   results=results,
                                   overall_result=overall_result,
                                   motivation=motivation,
                                   is_review=False,
                                   user_camp=user_camp)

        # GET first attempt - filter by camp
        cursor.execute("""
            SELECT id, question, options FROM quizzes 
            WHERE unit_id=%s AND (camp = %s OR camp = 'both')
        """, (unit_id, user_camp))
        questions = cursor.fetchall()

        if not questions:
            flash('No questions found for this quiz in your camp', 'error')
            return redirect(url_for('unit', unit_id=unit_id))

        question_list = []
        for row in questions:
            try:
                options = json.loads(row[2])
                question_list.append({
                    'id': row[0],
                    'question': row[1],
                    'options': options
                })
            except json.JSONDecodeError:
                flash('Error loading quiz options', 'error')
                continue

        motivation = random.choice([
            "You've got this! Every question is an opportunity to learn.",
            "Believe in yourself - you're capable of amazing things!",
            "Mistakes are proof you're trying. Keep going!",
            "Your effort today is your success tomorrow.",
            "Learning is a journey, not a destination. Enjoy the process!"
        ])

    except Exception as e:
        logger.error(f"Quiz page error: {str(e)}")
        flash(f"An error occurred loading the quiz: {str(e)}", "error")
        return redirect(url_for('unit', unit_id=unit_id))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)

    return render_template('quiz.html',
                           username=username,
                           unit_id=unit_id,
                           questions=question_list,
                           motivation=motivation,
                           is_first_attempt=True,
                           user_camp=user_camp)

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback() -> Any:
    """Handle user feedback submission."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = session['user_id']

    if request.method == 'POST':
        feedback_text = request.form.get('feedback')
        rating = request.form.get('rating')

        if feedback_text:
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO feedback (user_id, feedback_text, rating)
                    VALUES (%s, %s, %s)
                ''', (user_id, feedback_text, rating))
                conn.commit()
                cursor.close()
                flash('Thank you for your feedback!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                logger.error(f"Feedback submission error: {str(e)}")
                flash(f'Error submitting feedback: {str(e)}', 'danger')
            finally:
                if conn:
                    release_db_connection(conn)

    return render_template('feedback.html', username=username)


@app.route('/download_material/<path:filename>')
def download_material(filename: str) -> Any:
    """Handle material file download with security checks."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        safe_filename = filename.replace('../', '').replace('..\\', '')
        file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(request.referrer or url_for('dashboard'))

# ==============================================
# AI ASSISTANT ROUTES
# ==============================================


@app.route('/ai_assistant', methods=['GET', 'POST'])
@login_required
def ai_assistant() -> Any:
    """Simplified AI assistant with conversational capabilities."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = str(session['user_id'])

    question = request.args.get('question') or (
        request.form.get('question') if request.method == 'POST' else None)

    current_question = None
    current_answer = None
    current_sources = []
    conversation_type = None
    is_processing = False

    # Get conversation history
    history = []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (session['user_id'],))
        history = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)

    if question and question.strip():
        question = question.strip()

        # Basic validation
        if len(question) > 2000:
            flash(
                'Message too long. Please keep it under 2000 characters.',
                'error')
            return redirect(url_for('ai_assistant'))

        current_question = question
        is_processing = True

        try:
            # Use the simplified QA system
            qa_system = get_qa_system()

            if qa_system:
                qa_response = qa_system.answer_question(
                    question, user_id=user_id)

                current_answer = qa_response.get(
                    "answer", "I'm having trouble responding right now. Could you try again?")
                current_sources = qa_response.get("sources", [])
                conversation_type = qa_response.get(
                    "conversation_type", "general")

                # Add personality indicators
                if conversation_type == "greeting":
                    current_answer += "\n\n💡 *Tip: You can ask me about course materials, request explanations, or just chat about what you're learning!*"
                elif conversation_type == "general":
                    current_answer += "\n\n📚 *Feel free to ask me anything else about your studies or course materials!*"

            else:
                current_answer = "I'm currently starting up and loading course materials. Please wait a moment and try again!"
                current_sources = []
                conversation_type = "system_loading"

            # Save to database
            try:
                threading.Thread(
                    target=save_qa_history_async,
                    args=(session['user_id'], question, current_answer),
                    daemon=True
                ).start()
            except Exception as db_error:
                logger.error(f"Error saving QA history: {str(db_error)}")

            is_processing = False

        except Exception as e:
            logger.error(f"AI Assistant error: {str(e)}")
            current_answer = "I encountered an error, but I'm still here to help! Could you try rephrasing your question?"
            current_sources = []
            conversation_type = "error"
            is_processing = False

    return render_template('ai_assistant.html',
                           username=username,
                           current_question=current_question,
                           current_answer=current_answer,
                           current_sources=current_sources,
                           conversation_type=conversation_type,
                           is_processing=is_processing,
                           history=history)


@app.route('/ask_ai_enhanced', methods=['POST'])
@login_required
@limiter.limit("20 per minute")  # Specific limit for AI calls
def ask_ai_enhanced() -> Any:
    """Simplified API endpoint for conversational chat, now with metrics tracking."""
    start_time = time.time()
    success = False
    user_id = str(session.get('user_id', 'unknown'))

    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        question = data.get('question', '').strip()

        if not question:
            success = True
            return jsonify({
                'success': True,
                'answer': "Hello! I'm your AI learning assistant. How can I help you today?",
                'sources': [],
                'conversation_type': 'greeting'
            })

        if len(question) > 2000:
            return jsonify(
                {'error': 'Message too long. Please keep it under 2000 characters.'}), 400

        qa_system = get_qa_system()

        if qa_system is None:
            return jsonify({
                'success': False,
                'answer': 'I\'m currently starting up and loading course materials. Please wait a moment and try again!',
                'sources': [],
                'conversation_type': 'system_loading'
            }), 503

        try:
            qa_response = qa_system.answer_question(question, user_id=user_id)

            answer = qa_response.get("answer", "I'm having trouble responding right now. Could you try again?")
            sources = qa_response.get("sources", [])
            conversation_type = qa_response.get("conversation_type", "general")

            personality_additions = {
                "greeting": "\n\n💡 *Tip: You can ask me about course materials, explanations, or just chat about learning!*",
                "general": "\n\n📚 *Feel free to ask me anything else about your studies!*",
                "document_based": "\n\n📖 *This answer is based on your course materials.*",
                "hybrid": "\n\n🔍 *I've combined information from your materials with general knowledge.*"
            }

            if conversation_type in personality_additions:
                answer += personality_additions[conversation_type]

            if not answer.strip():
                answer = "I'm here to help! Could you tell me more about what you'd like to know?"

            logger.info(f"AI response generated for user {session.get('username', 'unknown')}: {conversation_type}")

        except Exception as qa_error:
            logger.error(f"QA system error: {str(qa_error)}")
            answer = "I encountered an error while processing your question. I'm still here to help though - could you try rephrasing?"
            sources = []
            conversation_type = "error"

        # Save QA history asynchronously
        try:
            threading.Thread(
                target=save_qa_history_async,
                args=(user_id, question, answer),
                daemon=True
            ).start()
        except Exception as db_error:
            logger.error(f"Error initiating QA history save: {str(db_error)}")

        success = True
        response = {
            'success': True,
            'answer': answer,
            'sources': sources,
            'conversation_type': conversation_type,
            'question': question
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Ask AI API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred while processing your message.',
            'answer': 'I encountered an error, but I\'m still here to help! Could you try again?',
            'sources': [],
            'conversation_type': 'error'
        }), 500

    finally:
        response_time = time.time() - start_time
        track_qa_request(user_id, response_time, success)



@app.route('/ask_ai', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def ask_ai() -> Any:
    """Legacy API endpoint - redirects to simplified system."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': 'No question provided'}), 400

        if len(question) > 1000:
            return jsonify(
                {'error': 'Question too long. Please keep it under 1000 characters.'}), 400

        qa_system = get_qa_system()

        if qa_system is None:
            return jsonify({
                'error': 'AI assistant not available. Please contact your administrator.',
                'answer': 'I apologize, but I\'m currently unavailable. The system may still be loading course materials.',
                'sources': []
            }), 503

        try:
            qa_response = qa_system.answer_question(
                question, user_id=str(session['user_id']))
            answer = qa_response.get(
                "answer", "I couldn't generate a response.")
            sources = qa_response.get("sources", [])

            if not answer or answer.strip() == "":
                answer = "I couldn't find relevant information to answer your question. Please try rephrasing it or asking about a different topic."

            logger.info(f"AI Question answered successfully for user {session.get('username', 'unknown')}")


        except Exception as qa_error:
            logger.error(f"QA system error: {str(qa_error)}")
            answer = "I encountered an error while processing your question. Please try again with a simpler question."
            sources = []

        # Save history
        try:
            user_id = session['user_id']
            threading.Thread(
                target=save_qa_history_async,
                args=(user_id, question, answer),
                daemon=True
            ).start()
        except Exception as db_error:
            logger.error(f"Error initiating QA history save: {str(db_error)}")

        return jsonify({
            'success': True,
            'answer': answer,
            'sources': sources,
            'question': question
        })

    except Exception as e:
        logger.error(f"Ask AI API error: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred while processing your question.',
            'answer': 'I encountered an error while processing your question. Please try again.',
            'sources': []
        }), 500


@app.route('/user_qa_history')
@login_required
def user_qa_history() -> Any:
    """Enhanced user endpoint to get their own Q&A history as JSON."""
    if not session.get('authenticated'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    per_page = min(per_page, 50)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT COUNT(*) as total
            FROM qa_history
            WHERE user_id = %s
        """, (user_id,))
        total = cursor.fetchone()['total']

        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, per_page, offset))
        history = cursor.fetchall()
        cursor.close()

        history_list = []
        for item in history:
            answer = item['answer']
            if len(answer) > 200:
                answer = answer[:200] + "..."

            history_list.append({
                'question': item['question'],
                'answer': answer,
                'full_answer': item['answer'],
                'created_at': item['created_at'].isoformat() if item['created_at'] else None
            })

        return jsonify({
            'success': True,
            'history': history_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })

    except Exception as e:
        logger.error(f"User QA History error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/qa_history')
@login_required
def qa_history_page() -> Any:
    """Display user's Q&A history in a dedicated page."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    username = session['username']
    user_id = session['user_id']

    page = request.args.get('page', 1, type=int)
    per_page = 10

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT COUNT(*) as total
            FROM qa_history
            WHERE user_id = %s
        """, (user_id,))
        total = cursor.fetchone()['total']

        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, per_page, offset))
        history = cursor.fetchall()
        cursor.close()

        total_pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

    except Exception as e:
        logger.error(f"QA History page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "error")
        history = []
        total = 0
        has_prev = has_next = False
        total_pages = 0
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('qa_history.html',
                           username=username,
                           history=history,
                           pagination={
                               'page': page,
                               'per_page': per_page,
                               'total': total,
                               'total_pages': total_pages,
                               'has_prev': has_prev,
                               'has_next': has_next
                           })


@app.route('/clear_history')
@login_required
def clear_history() -> Any:
    """Clear user's Q&A history."""
    if not session.get('authenticated'):
        return redirect(url_for('password_gate'))

    user_id = session['user_id']

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM qa_history WHERE user_id = %s", (user_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()

        if deleted_count > 0:
            flash(f'Cleared {deleted_count} items from history', 'success')
        else:
            flash('No history items to clear', 'info')

    except Exception as e:
        logger.error(f"Clear history error: {str(e)}")
        flash('Error clearing history', 'error')
    finally:
        if conn:
            release_db_connection(conn)

    return redirect(url_for('ai_assistant'))


@app.route('/ai_status')
@login_required
def ai_status() -> Any:
    """Get the current status of the simplified AI system."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        status = get_system_status(
            documents_dir=DOCUMENTS_DIR,
            llama_model_path=LLAMA_MODEL_PATH if 'LLAMA_MODEL_PATH' in globals() else None)

        if not status.get("ready", False):
            if status.get("initializing", False):
                return jsonify({
                    'status': 'initializing',
                    'message': 'Loading course materials...',
                    'ready': False,
                    'document_count': status.get("document_count", 0)
                })
            elif status.get("error"):
                return jsonify({
                    'status': 'error',
                    'message': f'Initialization error: {status.get("error")}',
                    'ready': False,
                    'document_count': status.get("document_count", 0)
                })
            else:
                return jsonify({
                    'status': 'not_ready',
                    'message': 'AI assistant not ready',
                    'ready': False,
                    'document_count': status.get("document_count", 0)
                })

        return jsonify({
            'status': 'ready',
            'message': f'AI assistant ready ({status.get("document_count", 0)} documents loaded)',
            'ready': True,
            'document_count': status.get("document_count", 0),
            'llama_available': status.get("llama_available", False)
        })

    except Exception as e:
        logger.error(f"AI status check error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error checking AI status',
            'ready': False,
            'document_count': 0
        })


@app.route('/debug_model')
@admin_required
def debug_model():
    """Debug model status"""
    model_path = os.path.abspath("models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf")

    debug_info = {
        'model_path': model_path,
        'model_exists': os.path.exists(model_path),
        'current_dir': os.getcwd(),
        'documents_dir': DOCUMENTS_DIR,
        'documents_exist': os.path.exists(DOCUMENTS_DIR),
        'has_documents': False
    }

    # Check for documents
    if os.path.exists(DOCUMENTS_DIR):
        files = []
        for root, _, filenames in os.walk(DOCUMENTS_DIR):
            for filename in filenames:
                if filename.lower().endswith(('.pdf', '.pptx', '.ppt', '.txt')):
                    files.append(filename)
        debug_info['document_files'] = files
        debug_info['has_documents'] = len(files) > 0

    return jsonify(debug_info)


def save_qa_history_async(user_id: int, question: str, answer: str):
    """Save QA history asynchronously to avoid blocking main thread."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qa_history (user_id, question, answer)
            VALUES (%s, %s, %s)
        """, (user_id, question, answer))
        conn.commit()
        cursor.close()
        logger.debug(f"QA history saved successfully for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving QA history async: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)


def cleanup_qa():
    """Cleanup function for graceful shutdown."""
    try:
        qa_system = get_qa_system()
        if qa_system:
            logger.info("Cleaning up QA system resources...")
        logger.info("QA cleanup completed")
    except Exception as e:
        logger.error(f"Error during QA cleanup: {str(e)}")

# Enhanced error handlers


@app.errorhandler(500)
def internal_error(error):
    """Enhanced error handler for internal server errors."""
    logger.error(f"Internal server error: {str(error)}")
    if request.path.startswith('/ask_ai'):
        return jsonify({
            'error': 'Internal server error occurred',
            'answer': 'I encountered an internal error. Please try again.',
            'sources': []
        }), 500
    return render_template('error.html', error="Internal server error"), 500


@app.errorhandler(504)
def timeout_error(error):
    """Handle timeout errors."""
    logger.error(f"Request timeout: {str(error)}")
    if request.path.startswith('/ask_ai'):
        return jsonify({
            'error': 'Request timed out',
            'answer': 'The request took too long to process. Please try a simpler question.',
            'sources': []
        }), 504
    return render_template('error.html', error="Request timeout"), 504
# ---------- ADMIN ROUTES ----------


@app.route('/admin', methods=['GET'])
def admin_redirect() -> Any:
    """Redirect to admin login page."""
    return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login() -> Any:
    """Handle admin user login."""
    # Clear any existing admin sessions
    if request.method == 'GET':
        session.pop('admin', None)
        session.pop('admin_username', None)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('admin/login.html')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password FROM admin_users WHERE username=%s", (username,))
            admin = cursor.fetchone()
            cursor.close()

            if admin and admin[1] and check_password_hash(admin[1], password):
                session['admin'] = True
                session['admin_username'] = username
                flash('Welcome to the admin panel', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'danger')
        except Exception as e:
            logger.error(f"Admin login error: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/login.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard() -> Any:
    """Display admin dashboard with statistics."""
    stats = get_admin_stats()
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/users')
@admin_required
def admin_users() -> Any:
    """Display and manage users."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, username, email, language, email_verified FROM users ORDER BY username")
        users = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Admin users page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        users = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/users.html', users=users)





@app.route('/admin/download_submissions')
@admin_required
def admin_download_submissions() -> Any:
    """Show submission download options by camp."""
    return render_template('admin/export_options.html', export_type='submissions')

@app.route('/admin/download_submissions/<camp>')
@admin_required
def admin_download_submissions_by_camp(camp: str) -> Any:
    """Download project submissions as a zip file filtered by camp."""
    if camp not in CAMPS and camp != 'all':
        flash('Invalid camp selection', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Create a BytesIO object to store the ZIP file
    memory_file = io.BytesIO()

    # Create a ZIP file in memory
    with zipfile.ZipFile(memory_file, 'w') as zf:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if camp == 'all':
                cursor.execute("""
                    SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                    FROM submissions s
                    JOIN users u ON s.user_id = u.id
                    ORDER BY u.camp, s.submitted_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                    FROM submissions s
                    JOIN users u ON s.user_id = u.id
                    WHERE u.camp = %s
                    ORDER BY s.submitted_at DESC
                """, (camp,))
            
            submissions = cursor.fetchall()
            cursor.close()

            if not submissions:
                flash(f'No submissions found for {camp} camp', 'warning')
                return redirect(url_for('admin_submissions'))

            # Add each submission file to the ZIP
            files_added = 0
            for submission in submissions:
                file_path = submission['file_path']
                if file_path:
                    # Look for file in uploads folder
                    real_path = os.path.join(UPLOAD_FOLDER, file_path)

                    # Check if file exists
                    if os.path.exists(real_path):
                        # Create a descriptive name for the file in the ZIP
                        # Format: Camp_Unit#_Username_OriginalFilename
                        camp_prefix = submission['camp'].replace(' ', '_')
                        file_name = f"{camp_prefix}_Unit{submission['unit_id']}_{submission['username']}_{file_path}"
                        zf.write(real_path, file_name)
                        files_added += 1
                    else:
                        logger.warning(f"File not found: {real_path}")

            if files_added == 0:
                flash(f'No submission files found for {camp} camp', 'warning')
                return redirect(url_for('admin_submissions'))

        except Exception as e:
            logger.error(f"Admin download submissions error: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('admin_submissions'))
        finally:
            if conn:
                release_db_connection(conn)

    # Reset the file pointer to the beginning
    memory_file.seek(0)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if camp == 'all':
        filename = f'all_submissions_{timestamp}.zip'
    else:
        camp_safe = camp.replace(' ', '_').lower()
        filename = f'{camp_safe}_submissions_{timestamp}.zip'

    # Send the file for download
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )


@app.route('/admin/submissions')
@admin_required
def admin_submissions() -> Any:
    """Display user project submissions with camp filtering."""
    camp_filter = request.args.get('camp', 'all')
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if camp_filter == 'all' or camp_filter not in CAMPS:
            cursor.execute("""
                SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                FROM submissions s
                JOIN users u ON s.user_id = u.id
                ORDER BY s.submitted_at DESC
            """)
        else:
            cursor.execute("""
                SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                FROM submissions s
                JOIN users u ON s.user_id = u.id
                WHERE u.camp = %s
                ORDER BY s.submitted_at DESC
            """, (camp_filter,))
        
        submissions = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Admin submissions page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        submissions = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/submissions.html', 
                         submissions=submissions, 
                         camps=CAMPS, 
                         current_camp=camp_filter)


@app.route('/admin/update_user_language', methods=['POST'])
@admin_required
def admin_update_user_language() -> Any:
    """Update a user's interface language."""
    user_id = request.form.get('user_id')
    language = request.form.get('language')

    if user_id and language in LANGUAGES:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET language = %s WHERE id = %s", (language, user_id))
            conn.commit()
            cursor.close()
            flash('User language updated successfully', 'success')
        except Exception as e:
            logger.error(f"Admin update user language error: {str(e)}")
            flash(f'Error updating user language: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)
    else:
        flash('Invalid user or language selection', 'danger')

    return redirect(url_for('admin_users'))


@app.route('/admin/feedback')
@admin_required
def admin_feedback() -> Any:
    """Display user feedback for admin review."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT feedback.id, users.username, feedback.feedback_text,
                   feedback.rating, feedback.created_at
            FROM feedback
            JOIN users ON feedback.user_id = users.id
            ORDER BY feedback.created_at DESC
        ''')
        feedback_items = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Admin feedback page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        feedback_items = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/feedback.html', feedback=feedback_items)


def parse_core_elements(form_data):
    """Parse core elements from form data into proper JSON structure"""
    grouped = defaultdict(dict)
    pattern = re.compile(r'core_elements\[(\d+)\]\[(\w+)\]')

    # Debug print
    print("=== Parsing Core Elements ===")
    print(
        "Form data keys:", [
            k for k in form_data.keys() if 'core_element' in k])

    for key, value in form_data.items():
        match = pattern.match(key)
        if match:
            idx, field = match.groups()
            if value.strip():  # Only add non-empty values
                grouped[int(idx)][field] = value.strip()
                print(f"Found: {key} = {value}")

    core_elements = []
    for idx in sorted(grouped.keys()):
        item = grouped[idx]
        if 'core_element' in item and 'everyday_object' in item:
            core_elements.append({
                'core_element': item['core_element'],
                'everyday_object': item['everyday_object']
            })

    print(f"Parsed core elements: {core_elements}")
    return core_elements


@app.route('/admin/add_word', methods=['GET', 'POST'])
@admin_required
def admin_add_word() -> Any:
    """Add a detailed AI vocabulary word with camp selection."""
    if request.method == 'POST':
        conn = None
        try:
            # Parse core elements properly
            core_elements_list = parse_core_elements(request.form)

            data = {
                'unit_id': request.form['unit_id'],
                'word': request.form['word'],
                'one_sentence_version': request.form.get('one_sentence_version', ''),
                'daily_definition': request.form.get('daily_definition', ''),
                'life_metaphor': request.form.get('life_metaphor', ''),
                'visual_explanation': request.form.get('visual_explanation', ''),
                'core_elements': json.dumps(core_elements_list),
                'scenario_theater': request.form.get('scenario_theater', ''),
                'misunderstandings': request.form.get('misunderstandings', ''),
                'reality_connection': request.form.get('reality_connection', ''),
                'thinking_bubble': request.form.get('thinking_bubble', ''),
                'smiling_conclusion': request.form.get('smiling_conclusion', ''),
                'section': request.form.get('section', 1),
                'camp': request.form['camp']  # New field
            }

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO words (
                    unit_id, word, one_sentence_version, daily_definition, life_metaphor,
                    visual_explanation, core_elements, scenario_theater,
                    misunderstandings, reality_connection, thinking_bubble,
                    smiling_conclusion, section, camp
                )
                VALUES (
                    %(unit_id)s, %(word)s, %(one_sentence_version)s, %(daily_definition)s, %(life_metaphor)s,
                    %(visual_explanation)s, %(core_elements)s::jsonb, %(scenario_theater)s,
                    %(misunderstandings)s, %(reality_connection)s, %(thinking_bubble)s,
                    %(smiling_conclusion)s, %(section)s, %(camp)s
                )
            """, data)

            conn.commit()
            cursor.close()
            flash('AI vocabulary word added successfully', 'success')
            return redirect(url_for('admin_manage_content'))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Admin add word error: {str(e)}")
            flash(f'Error adding word: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/add_word.html', camps=CAMPS)



@app.route('/admin/add_quiz', methods=['GET', 'POST'])
@admin_required
def admin_add_quiz() -> Any:
    """Add a new quiz question with camp selection."""
    if request.method == 'POST':
        conn = None
        try:
            data = request.form
            unit_id = data['unit_id']
            question = data['question']
            options = [data[f'option{i}'] for i in range(1, 4)]  # 3 options
            correct_answer = int(data['correct_answer'])
            explanation = data['explanation']
            camp = data['camp']  # Get camp selection

            # Validate camp selection
            if camp not in CAMPS and camp != 'both':
                flash('Please select a valid training camp.', 'danger')
                return render_template('admin/add_quiz.html', camps=CAMPS)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quizzes (unit_id, question, options, correct_answer, explanation, camp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (unit_id, question, json.dumps(options), correct_answer, explanation, camp))
            conn.commit()
            cursor.close()
            flash('Quiz question added successfully', 'success')
            return redirect(url_for('admin_add_quiz'))
        except Exception as e:
            logger.error(f"Admin add quiz error: {str(e)}")
            flash(f'Error adding quiz: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/add_quiz.html', camps=CAMPS)


@app.route('/admin/add_material', methods=['GET', 'POST'])
@admin_required
def admin_add_material() -> Any:
    """Add new learning material with camp selection."""
    if request.method == 'POST':
        conn = None
        try:
            unit_id = request.form['unit_id']
            camp = request.form['camp']  # New field
            file = request.files.get('file')

            if not file or file.filename == '':
                flash('Please select a file to upload', 'danger')
                return redirect(url_for('admin_add_material'))

            if allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                filename = f"unit_{unit_id}_{camp}_{original_filename}"

                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)

                title = os.path.splitext(original_filename)[0].replace('_', ' ').replace('-', ' ').title()
                content = request.form.get('content', '')

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO materials (unit_id, title, content, file_path, camp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (unit_id, title, content, filename, camp))
                conn.commit()
                cursor.close()
                flash('Material added successfully', 'success')
                return redirect(url_for('admin_manage_content'))
            else:
                flash(f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}', 'danger')
        except Exception as e:
            logger.error(f"Admin add material error: {str(e)}")
            flash(f'Error adding material: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/add_material.html', camps=CAMPS)


@app.route('/admin/edit_material/<int:material_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_material(material_id: int) -> Any:
    """Edit existing learning material."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM materials WHERE id=%s", (material_id,))
        material = cursor.fetchone()

        if not material:
            flash('Material not found', 'danger')
            return redirect(url_for('admin_manage_content'))

        if request.method == 'POST':
            unit_id = request.form['unit_id']
            title = request.form['title']
            content = request.form.get('content', '')  # Now optional
            camp = request.form['camp']  # Get camp from form

            # Validate camp selection
            valid_camps = ['Middle East', 'Chinese', 'both']
            if camp not in valid_camps:
                flash('Please select a valid training camp.', 'danger')
                return redirect(url_for('admin_edit_material', material_id=material_id))

            # Check if a new file was uploaded
            file = request.files.get('file')
            file_path = material['file_path']  # Default to existing file

            if file and file.filename:
                # A new file was uploaded
                if allowed_file(file.filename):
                    # Delete the old file if it exists
                    if material['file_path']:
                        old_file_path = os.path.join(UPLOAD_FOLDER, material['file_path'])
                        try:
                            os.remove(old_file_path)
                        except BaseException:
                            pass  # File might not exist, that's okay

                    # Save the new file
                    original_filename = secure_filename(file.filename)
                    file_path = f"unit_{unit_id}_{camp}_{original_filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, file_path))
                else:
                    allowed_types = ", ".join(ALLOWED_EXTENSIONS)
                    flash(f'Invalid file type. Allowed types: {allowed_types}', 'danger')
                    return redirect(url_for('admin_edit_material', material_id=material_id))

            cursor.execute("""
                UPDATE materials
                SET unit_id=%s, title=%s, content=%s, file_path=%s, camp=%s
                WHERE id=%s
            """, (unit_id, title, content, file_path, camp, material_id))
            conn.commit()
            flash('Material updated successfully', 'success')
            return redirect(url_for('admin_manage_content'))

        cursor.close()
    except Exception as e:
        logger.error(f"Admin edit material error: {str(e)}")
        flash(f'Error editing material: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/edit_material.html', material=material)


@app.route('/admin/add_video', methods=['GET', 'POST'])
@admin_required
def admin_add_video() -> Any:
    """Add a new video resource with camp selection."""
    if request.method == 'POST':
        conn = None
        try:
            title = request.form['title']
            youtube_url = request.form['youtube_url']
            description = request.form['description']
            unit_id = request.form['unit_id']
            camp = request.form['camp']  # New field

            # Extract YouTube video ID if full URL is provided
            if 'youtube.com' in youtube_url or 'youtu.be' in youtube_url:
                if 'v=' in youtube_url:
                    youtube_id = youtube_url.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in youtube_url:
                    youtube_id = youtube_url.split('youtu.be/')[1].split('?')[0]
                else:
                    youtube_id = youtube_url
            else:
                youtube_id = youtube_url

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO videos (unit_id, title, youtube_url, description, camp)
                VALUES (%s, %s, %s, %s, %s)
            """, (unit_id, title, youtube_id, description, camp))
            conn.commit()
            cursor.close()
            flash('Video added successfully', 'success')
            return redirect(url_for('admin_add_video'))
        except Exception as e:
            logger.error(f"Admin add video error: {str(e)}")
            flash(f'Error adding video: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/add_video.html', camps=CAMPS)


@app.route('/admin/add_project', methods=['GET', 'POST'])
@admin_required
def admin_add_project() -> Any:
    """Add a new project assignment with camp selection."""
    if request.method == 'POST':
        conn = None
        try:
            title = request.form['title']
            description = request.form['description']
            resources = request.form['resources']
            unit_id = request.form['unit_id']
            camp = request.form['camp']  # New field

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects (unit_id, title, description, resources, camp)
                VALUES (%s, %s, %s, %s, %s)
            """, (unit_id, title, description, resources, camp))
            conn.commit()
            cursor.close()
            flash('Project added successfully', 'success')
            return redirect(url_for('admin_add_project'))
        except Exception as e:
            logger.error(f"Admin add project error: {str(e)}")
            flash(f'Error adding project: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    return render_template('admin/add_project.html', camps=CAMPS)

@app.route('/admin/manage_content')
@admin_required
def admin_manage_content() -> Any:
    """Manage all content types with camp information."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all quizzes with camp info
        cursor.execute("SELECT id, unit_id, question, camp FROM quizzes ORDER BY camp, unit_id, id")
        quizzes = cursor.fetchall()

        # Get all materials with camp info
        cursor.execute("SELECT id, unit_id, title, camp FROM materials ORDER BY camp, unit_id, id")
        materials = cursor.fetchall()

        # Get all videos with camp info
        cursor.execute("SELECT id, unit_id, title, camp FROM videos ORDER BY camp, unit_id, id")
        videos = cursor.fetchall()

        # Get all projects with camp info
        cursor.execute("SELECT id, unit_id, title, camp FROM projects ORDER BY camp, unit_id, id")
        projects = cursor.fetchall()

        # Get all AI vocabulary words with camp info
        cursor.execute("SELECT id, unit_id, word, section, camp FROM words ORDER BY camp, unit_id, section, id")
        words = cursor.fetchall()

        cursor.close()
    except Exception as e:
        logger.error(f"Admin manage content error: {str(e)}")
        flash(f'Error retrieving content: {str(e)}', 'danger')
        quizzes = []
        materials = []
        videos = []
        projects = []
        words = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/manage_content.html',
                           quizzes=quizzes,
                           materials=materials,
                           videos=videos,
                           projects=projects,
                           words=words,
                           camps=CAMPS)


@app.route('/admin/export_progress')
@admin_required
def admin_export_progress() -> Any:
    """Export progress with camp options."""
    return render_template('admin/export_options.html', export_type='progress')

@app.route('/admin/export_progress/<camp>')
@admin_required
def admin_export_progress_by_camp(camp: str) -> Any:
    """Export user progress to CSV filtered by camp."""
    if camp not in CAMPS and camp != 'all':
        flash('Invalid camp selection', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if camp == 'all':
            cursor.execute("""
                SELECT u.id, u.username, u.camp, p.unit_number, p.completed,
                       p.quiz_score, p.project_completed
                FROM users u
                LEFT JOIN progress p ON u.id = p.user_id
                ORDER BY u.camp, u.username, p.unit_number
            """)
        else:
            cursor.execute("""
                SELECT u.id, u.username, u.camp, p.unit_number, p.completed,
                       p.quiz_score, p.project_completed
                FROM users u
                LEFT JOIN progress p ON u.id = p.user_id
                WHERE u.camp = %s
                ORDER BY u.username, p.unit_number
            """, (camp,))
        
        progress = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        # Convert to list format
        data = []
        for row in progress:
            data.append([
                row['id'], row['username'], row['camp'], row['unit_number'],
                row['completed'], row['quiz_score'], row['project_completed']
            ])

        headers = ['User ID', 'Username', 'Camp', 'Unit', 'Completed', 'Quiz Score', 'Project Completed']
        filename = f'progress_{camp}.csv' if camp != 'all' else 'progress_all_camps.csv'
        csv_file = generate_csv_file(data, filename, headers)

        if csv_file:
            return send_file(csv_file,
                           mimetype='text/csv',
                           as_attachment=True,
                           download_name=filename)
        else:
            flash('Error generating CSV file', 'danger')
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        logger.error(f"Admin export progress error: {str(e)}")
        flash(f'Error exporting progress: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))



@app.route('/admin/export_users')
@admin_required
def admin_export_users() -> Any:
    """Export users with camp options."""
    return render_template('admin/export_options.html', export_type='users')

@app.route('/admin/export_users/<camp>')
@admin_required
def admin_export_users_by_camp(camp: str) -> Any:
    """Export users to CSV filtered by camp."""
    if camp not in CAMPS and camp != 'all':
        flash('Invalid camp selection', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if camp == 'all':
            cursor.execute("SELECT id, username, email, language, email_verified, camp FROM users ORDER BY camp, id")
        else:
            cursor.execute("SELECT id, username, email, language, email_verified, camp FROM users WHERE camp = %s ORDER BY id", (camp,))
        
        users = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        headers = ['ID', 'Username', 'Email', 'Language', 'Email Verified', 'Camp']
        filename = f'users_{camp}.csv' if camp != 'all' else 'users_all_camps.csv'
        csv_file = generate_csv_file(users, filename, headers)

        if csv_file:
            return send_file(csv_file,
                             mimetype='text/csv',
                             as_attachment=True,
                             download_name=filename)
        else:
            flash('Error generating CSV file', 'danger')
            return redirect(url_for('admin_users'))
    except Exception as e:
        logger.error(f"Admin export users error: {str(e)}")
        flash(f'Error exporting users: {str(e)}', 'danger')
        return redirect(url_for('admin_users'))

@app.route('/admin/export_feedback')
@admin_required
def admin_export_feedback() -> Any:
    """Export feedback with camp options."""
    return render_template('admin/export_options.html', export_type='feedback')

@app.route('/admin/export_feedback/<camp>')
@admin_required
def admin_export_feedback_by_camp(camp: str) -> Any:
    """Export feedback to CSV filtered by camp."""
    if camp not in CAMPS and camp != 'all':
        flash('Invalid camp selection', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if camp == 'all':
            cursor.execute("""
                SELECT u.username, u.camp, f.feedback_text, f.rating, f.created_at
                FROM feedback f
                JOIN users u ON f.user_id = u.id
                ORDER BY u.camp, f.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT u.username, u.camp, f.feedback_text, f.rating, f.created_at
                FROM feedback f
                JOIN users u ON f.user_id = u.id
                WHERE u.camp = %s
                ORDER BY f.created_at DESC
            """, (camp,))
        
        feedback = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        # Convert to list format
        data = []
        for row in feedback:
            data.append([
                row['username'], row['camp'], row['feedback_text'],
                row['rating'], row['created_at']
            ])

        headers = ['Username', 'Camp', 'Feedback', 'Rating', 'Created At']
        filename = f'feedback_{camp}.csv' if camp != 'all' else 'feedback_all_camps.csv'
        csv_file = generate_csv_file(data, filename, headers)

        if csv_file:
            return send_file(csv_file,
                           mimetype='text/csv',
                           as_attachment=True,
                           download_name=filename)
        else:
            flash('Error generating CSV file', 'danger')
            return redirect(url_for('admin_feedback'))
    except Exception as e:
        logger.error(f"Admin export feedback error: {str(e)}")
        flash(f'Error exporting feedback: {str(e)}', 'danger')
        return redirect(url_for('admin_feedback'))


@app.route('/admin/reset_db', methods=['GET', 'POST'])
@admin_required
def admin_reset_db() -> Any:
    """Reset database tables."""
    if request.method == 'POST':
        confirmation = request.form.get('confirmation')
        if confirmation == 'RESET':
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Delete all user data except admin users
                tables = [
                    'feedback',
                    'qa_history',
                    'quiz_attempts',
                    'submissions',
                    'progress',
                    'words',
                    'projects',
                    'videos',
                    'materials',
                    'quizzes',
                    'team_members',
                    'team_scores',
                    'teams']

                for table in tables:
                    cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

                # Maintain admin users but reset regular users
                cursor.execute("TRUNCATE TABLE users CASCADE")

                conn.commit()
                cursor.close()
                release_db_connection(conn)

                flash('Database has been reset successfully', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                logger.error(f"DB reset error: {str(e)}")
                flash(f'Error resetting database: {str(e)}', 'danger')
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect confirmation text', 'danger')

    return render_template('admin/reset_db.html')


@app.route('/admin/logout')
def admin_logout() -> Any:
    """Handle admin logout."""
    session.pop('admin', None)
    session.pop('admin_username', None)
    flash('You have been logged out from admin panel', 'info')
    return redirect(url_for('admin_login'))


# ---------- TEAM MANAGEMENT ROUTES ----------
@app.route('/admin/teams')
@admin_required
def admin_teams() -> Any:
    """Manage teams."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all teams with their lead names and member counts
        cursor.execute("""
            SELECT t.id, t.name, t.camp, u.username AS team_lead_name,
                   COUNT(tm.id) AS member_count,
                   COALESCE(ts.score, 0) AS team_score
            FROM teams t
            LEFT JOIN users u ON t.team_lead_id = u.id
            LEFT JOIN team_members tm ON t.id = tm.team_id
            LEFT JOIN team_scores ts ON t.id = ts.team_id
            GROUP BY t.id, u.username, ts.score
            ORDER BY t.camp, COALESCE(ts.score, 0) DESC
        """)
        teams = cursor.fetchall()

        cursor.close()
        return render_template('admin/teams.html', teams=teams)
    except Exception as e:
        logger.error(f"Error in admin_teams: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/admin/add_team', methods=['GET', 'POST'])
@admin_required
def admin_add_team() -> Any:
    """Add a new team."""
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        team_lead_id = request.form.get('team_lead_id')
        camp = request.form.get('camp')

        if not all([team_name, team_lead_id, camp]):
            flash("All fields are required", "danger")
            return redirect(url_for('admin_add_team'))

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create the team
            cursor.execute("""
                INSERT INTO teams (name, team_lead_id, camp)
                VALUES (%s, %s, %s) RETURNING id
            """, (team_name, team_lead_id, camp))
            team_id = cursor.fetchone()[0]

            # Add team lead to team members
            cursor.execute("""
                INSERT INTO team_members (team_id, user_id)
                VALUES (%s, %s)
            """, (team_id, team_lead_id))

            # Initialize team score
            cursor.execute("""
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, 0)
            """, (team_id,))

            conn.commit()
            flash("Team created successfully", "success")
            return redirect(url_for('admin_teams'))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in admin_add_team: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('admin_add_team'))
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    # GET method - display the form
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all users for the team lead dropdown
        cursor.execute("""
            SELECT id, username, email
            FROM users
            ORDER BY username
        """)
        users = cursor.fetchall()

        cursor.close()
        return render_template('admin/add_team.html', users=users)
    except Exception as e:
        logger.error(f"Error in admin_add_team GET: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/admin/edit_team/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_team(team_id: int) -> Any:
    """Edit an existing team."""
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        team_lead_id = request.form.get('team_lead_id')
        camp = request.form.get('camp')

        if not all([team_name, team_lead_id, camp]):
            flash("All fields are required", "danger")
            return redirect(url_for('admin_edit_team', team_id=team_id))

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Update the team
            cursor.execute("""
                UPDATE teams SET name = %s, team_lead_id = %s, camp = %s
                WHERE id = %s
            """, (team_name, team_lead_id, camp, team_id))

            conn.commit()
            flash("Team updated successfully", "success")
            return redirect(url_for('admin_teams'))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in admin_edit_team: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('admin_edit_team', team_id=team_id))
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    # GET method - display the form with current data
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get team data
        cursor.execute("""
            SELECT * FROM teams WHERE id = %s
        """, (team_id,))
        team = cursor.fetchone()

        if not team:
            flash("Team not found", "danger")
            return redirect(url_for('admin_teams'))

        # Get all users for the team lead dropdown
        cursor.execute("""
            SELECT id, username, email
            FROM users
            ORDER BY username
        """)
        users = cursor.fetchall()

        cursor.close()
        return render_template('admin/edit_team.html', team=team, users=users)
    except Exception as e:
        logger.error(f"Error in admin_edit_team GET: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/admin/delete_team/<int:team_id>')
@admin_required
def admin_delete_team(team_id: int) -> Any:
    """Delete a team."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the team (cascade will handle team_members and team_scores)
        cursor.execute("DELETE FROM teams WHERE id = %s", (team_id,))

        conn.commit()
        flash("Team deleted successfully", "success")
        return redirect(url_for('admin_teams'))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_delete_team: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route('/admin/team_members/<int:team_id>')
@admin_required
def admin_team_members(team_id: int) -> Any:
    """Manage team members."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get team info
        cursor.execute("""
            SELECT t.*, u.username AS team_lead_name
            FROM teams t
            LEFT JOIN users u ON t.team_lead_id = u.id
            WHERE t.id = %s
        """, (team_id,))
        team = cursor.fetchone()

        if not team:
            flash("Team not found", "danger")
            return redirect(url_for('admin_teams'))

        # Get team members
        cursor.execute("""
            SELECT tm.id, tm.user_id, u.username, u.email, tm.joined_at
            FROM team_members tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.team_id = %s
            ORDER BY u.username
        """, (team_id,))
        members = cursor.fetchall()

        # Get non-team members for adding
        cursor.execute("""
            SELECT id, username, email
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM team_members WHERE team_id = %s
            )
            ORDER BY username
        """, (team_id,))
        non_members = cursor.fetchall()

        cursor.close()
        return render_template('admin/team_members.html',
                               team=team,
                               members=members,
                               non_members=non_members)
    except Exception as e:
        logger.error(f"Error in admin_team_members: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/admin/add_team_member/<int:team_id>', methods=['POST'])
@admin_required
def admin_add_team_member(team_id: int) -> Any:
    """Add a user to a team."""
    user_id = request.form.get('user_id')

    if not user_id:
        flash("User selection is required", "danger")
        return redirect(url_for('admin_team_members', team_id=team_id))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Add user to team
        cursor.execute("""
            INSERT INTO team_members (team_id, user_id)
            VALUES (%s, %s)
        """, (team_id, user_id))

        conn.commit()
        flash("Member added to team successfully", "success")
        return redirect(url_for('admin_team_members', team_id=team_id))
    except psycopg2.errors.UniqueViolation:
        # Handle unique constraint violation
        if conn:
            conn.rollback()
        flash("User is already a member of this team", "warning")
        return redirect(url_for('admin_team_members', team_id=team_id))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_add_team_member: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_team_members', team_id=team_id))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route('/admin/remove_team_member/<int:member_id>')
@admin_required
def admin_remove_team_member(member_id: int) -> Any:
    """Remove a user from a team."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get team_id for redirect
        cursor.execute(
            "SELECT team_id FROM team_members WHERE id = %s", (member_id,))
        result = cursor.fetchone()

        if not result:
            flash("Member not found", "danger")
            return redirect(url_for('admin_teams'))

        team_id = result[0]

        # Remove user from team
        cursor.execute("DELETE FROM team_members WHERE id = %s", (member_id,))

        conn.commit()
        flash("Member removed from team successfully", "success")
        return redirect(url_for('admin_team_members', team_id=team_id))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_remove_team_member: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route('/admin/update_team_score/<int:team_id>', methods=['POST'])
@admin_required
def admin_update_team_score(team_id: int) -> Any:
    """Update a team's score manually."""
    score = request.form.get('score')

    if not score or not score.isdigit():
        flash("Valid score is required", "danger")
        return redirect(url_for('admin_teams'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if score exists
        cursor.execute(
            "SELECT id FROM team_scores WHERE team_id = %s", (team_id,))
        score_record = cursor.fetchone()

        if score_record:
            # Update existing score
            cursor.execute("""
                UPDATE team_scores
                SET score = %s, updated_at = CURRENT_TIMESTAMP
                WHERE team_id = %s
            """, (score, team_id))
        else:
            # Insert new score
            cursor.execute("""
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, %s)
            """, (team_id, score))

        conn.commit()
        flash("Team score updated successfully", "success")
        return redirect(url_for('admin_teams'))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_update_team_score: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('admin_teams'))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


# ---------- ADMIN CONTENT MANAGEMENT ROUTES ----------

# Quiz management
@app.route('/admin/view_quiz/<int:quiz_id>')
@admin_required
def admin_view_quiz(quiz_id: int) -> Any:
    """View a quiz question."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM quizzes WHERE id=%s", (quiz_id,))
        quiz = cursor.fetchone()
        cursor.close()

        if not quiz:
            flash('Quiz not found', 'danger')
            return redirect(url_for('admin_manage_content'))

        # Parse options from JSON
        try:
            options = json.loads(quiz['options'])
        except BaseException:
            options = []
    except Exception as e:
        logger.error(f"Admin view quiz error: {str(e)}")
        flash(f'Error viewing quiz: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/view_quiz.html', quiz=quiz, options=options)


@app.route('/admin/edit_quiz/<int:quiz_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_quiz(quiz_id: int) -> Any:
    """Edit a quiz question."""
    if request.method == 'POST':
        conn = None
        try:
            data = request.form
            unit_id = data['unit_id']
            question = data['question']
            options = [data[f'option{i}'] for i in range(1, 4)]
            correct_answer = int(data['correct_answer'])
            explanation = data['explanation']
            camp = data['camp']  # Get camp from form

            # Validate camp selection
            valid_camps = ['Middle East', 'Chinese', 'both']
            if camp not in valid_camps:
                flash('Please select a valid training camp.', 'danger')
                return redirect(url_for('admin_edit_quiz', quiz_id=quiz_id))

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE quizzes
                SET unit_id=%s, question=%s, options=%s, correct_answer=%s, explanation=%s, camp=%s
                WHERE id=%s
            """, (unit_id, question, json.dumps(options), correct_answer, explanation, camp, quiz_id))
            conn.commit()
            cursor.close()
            flash('Quiz updated successfully', 'success')
            return redirect(url_for('admin_manage_content'))
        except Exception as e:
            logger.error(f"Admin edit quiz error: {str(e)}")
            flash(f'Error updating quiz: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM quizzes WHERE id=%s", (quiz_id,))
        quiz = cursor.fetchone()
        cursor.close()

        if not quiz:
            flash('Quiz not found', 'danger')
            return redirect(url_for('admin_manage_content'))

        # Parse options from JSON
        try:
            options = json.loads(quiz['options'])
        except BaseException:
            options = []
    except Exception as e:
        logger.error(f"Admin edit quiz error: {str(e)}")
        flash(f'Error loading quiz: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/edit_quiz.html', quiz=quiz, options=options)


@app.route('/admin/delete_quiz/<int:quiz_id>')
@admin_required
def admin_delete_quiz(quiz_id: int) -> Any:
    """Delete a quiz question."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quizzes WHERE id=%s", (quiz_id,))
        conn.commit()
        cursor.close()
        flash('Quiz deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Admin delete quiz error: {str(e)}")
        flash(f'Error deleting quiz: {str(e)}', 'danger')
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for('admin_manage_content'))


# Material management
@app.route('/admin/view_material/<int:material_id>')
@admin_required
def admin_view_material(material_id: int) -> Any:
    """View learning material."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM materials WHERE id=%s", (material_id,))
        material = cursor.fetchone()
        cursor.close()

        if not material:
            flash('Material not found', 'danger')
            return redirect(url_for('admin_manage_content'))
    except Exception as e:
        logger.error(f"Admin view material error: {str(e)}")
        flash(f'Error viewing material: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/view_material.html', material=material)


@app.route('/admin/delete_material/<int:material_id>')
@admin_required
def admin_delete_material(material_id: int) -> Any:
    """Delete learning material."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT file_path FROM materials WHERE id=%s", (material_id,))
        material = cursor.fetchone()

        # Delete the file if it exists
        if material and material['file_path']:
            file_path = os.path.join(UPLOAD_FOLDER, material['file_path'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except BaseException:
                    logger.error(f"Could not delete file {file_path}")

        cursor.execute("DELETE FROM materials WHERE id=%s", (material_id,))
        conn.commit()
        cursor.close()
        flash('Material deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Admin delete material error: {str(e)}")
        flash(f'Error deleting material: {str(e)}', 'danger')
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for('admin_manage_content'))


# Video management
@app.route('/admin/view_video/<int:video_id>')
@admin_required
def admin_view_video(video_id: int) -> Any:
    """View video details."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM videos WHERE id=%s", (video_id,))
        video = cursor.fetchone()
        cursor.close()

        if not video:
            flash('Video not found', 'danger')
            return redirect(url_for('admin_manage_content'))
    except Exception as e:
        logger.error(f"Admin view video error: {str(e)}")
        flash(f'Error viewing video: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/view_video.html', video=video)


@app.route('/admin/edit_video/<int:video_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_video(video_id: int) -> Any:
    """Edit video details."""
    if request.method == 'POST':
        conn = None
        try:
            title = request.form['title']
            youtube_url = request.form['youtube_url']
            description = request.form['description']
            unit_id = request.form['unit_id']
            camp = request.form['camp']  # Get camp from form

            # Validate camp selection
            valid_camps = ['Middle East', 'Chinese', 'both']
            if camp not in valid_camps:
                flash('Please select a valid training camp.', 'danger')
                return redirect(url_for('admin_edit_video', video_id=video_id))

            # Extract YouTube video ID if full URL is provided
            if 'youtube.com' in youtube_url or 'youtu.be' in youtube_url:
                if 'v=' in youtube_url:
                    # Format: https://www.youtube.com/watch?v=VIDEO_ID
                    youtube_id = youtube_url.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in youtube_url:
                    # Format: https://youtu.be/VIDEO_ID
                    youtube_id = youtube_url.split(
                        'youtu.be/')[1].split('?')[0]
                else:
                    youtube_id = youtube_url
            else:
                youtube_id = youtube_url  # Assume ID was provided directly

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos
                SET unit_id=%s, title=%s, youtube_url=%s, description=%s, camp=%s
                WHERE id=%s
            """, (unit_id, title, youtube_id, description, camp, video_id))
            conn.commit()
            cursor.close()
            flash('Video updated successfully', 'success')
            return redirect(url_for('admin_manage_content'))
        except Exception as e:
            logger.error(f"Admin edit video error: {str(e)}")
            flash(f'Error updating video: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM videos WHERE id=%s", (video_id,))
        video = cursor.fetchone()
        cursor.close()

        if not video:
            flash('Video not found', 'danger')
            return redirect(url_for('admin_manage_content'))
    except Exception as e:
        logger.error(f"Admin load video error: {str(e)}")
        flash(f'Error loading video: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/edit_video.html', video=video)


@app.route('/admin/delete_video/<int:video_id>')
@admin_required
def admin_delete_video(video_id: int) -> Any:
    """Delete a video."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id=%s", (video_id,))
        conn.commit()
        cursor.close()
        flash('Video deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Admin delete video error: {str(e)}")
        flash(f'Error deleting video: {str(e)}', 'danger')
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for('admin_manage_content'))


# Project management
@app.route('/admin/view_project/<int:project_id>')
@admin_required
def admin_view_project(project_id: int) -> Any:
    """View project details."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cursor.fetchone()
        cursor.close()

        if not project:
            flash('Project not found', 'danger')
            return redirect(url_for('admin_manage_content'))
    except Exception as e:
        logger.error(f"Admin view project error: {str(e)}")
        flash(f'Error viewing project: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/view_project.html', project=project)


@app.route('/admin/edit_project/<int:project_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_project(project_id: int) -> Any:
    """Edit project details."""
    if request.method == 'POST':
        conn = None
        try:
            title = request.form['title']
            description = request.form['description']
            resources = request.form['resources']
            unit_id = request.form['unit_id']
            camp = request.form['camp']  # Get camp from form

            # Validate camp selection
            valid_camps = ['Middle East', 'Chinese', 'both']
            if camp not in valid_camps:
                flash('Please select a valid training camp.', 'danger')
                return redirect(url_for('admin_edit_project', project_id=project_id))

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE projects
                SET unit_id=%s, title=%s, description=%s, resources=%s, camp=%s
                WHERE id=%s
            """, (unit_id, title, description, resources, camp, project_id))
            conn.commit()
            cursor.close()
            flash('Project updated successfully', 'success')
            return redirect(url_for('admin_manage_content'))
        except Exception as e:
            logger.error(f"Admin edit project error: {str(e)}")
            flash(f'Error updating project: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cursor.fetchone()
        cursor.close()

        if not project:
            flash('Project not found', 'danger')
            return redirect(url_for('admin_manage_content'))
    except Exception as e:
        logger.error(f"Admin load project error: {str(e)}")
        flash(f'Error loading project: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/edit_project.html', project=project)


@app.route('/admin/delete_project/<int:project_id>')
@admin_required
def admin_delete_project(project_id: int) -> Any:
    """Delete a project."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id=%s", (project_id,))
        conn.commit()
        cursor.close()
        flash('Project deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Admin delete project error: {str(e)}")
        flash(f'Error deleting project: {str(e)}', 'danger')
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for('admin_manage_content'))


# Word management
@app.route('/admin/view_word/<int:word_id>')
@admin_required
def admin_view_word(word_id: int) -> Any:
    """View AI vocabulary word."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM words WHERE id=%s", (word_id,))
        word = cursor.fetchone()
        cursor.close()

        if not word:
            flash('Word not found', 'danger')
            return redirect(url_for('admin_manage_content'))

        # Parse core_elements JSON string to list for template use
        if word.get('core_elements'):
            try:
                word['core_elements'] = json.loads(word['core_elements'])
            except Exception:
                word['core_elements'] = []
        else:
            word['core_elements'] = []

    except Exception as e:
        logger.error(f"Admin view word error: {str(e)}")
        flash(f'Error viewing word: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/view_word.html', word=word)


@app.route('/admin/edit_word/<int:word_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_word(word_id: int) -> Any:
    """Edit AI vocabulary word."""
    if request.method == 'POST':
        conn = None
        try:
            # Parse core elements properly
            core_elements_list = parse_core_elements(request.form)

            data = {
                'unit_id': request.form['unit_id'],
                'word': request.form['word'],
                'one_sentence_version': request.form.get('one_sentence_version', ''),
                'daily_definition': request.form.get('daily_definition', ''),
                'life_metaphor': request.form.get('life_metaphor', ''),
                'visual_explanation': request.form.get('visual_explanation', ''),
                # Store as JSON string
                'core_elements': json.dumps(core_elements_list),
                'scenario_theater': request.form.get('scenario_theater', ''),
                'misunderstandings': request.form.get('misunderstandings', ''),
                'reality_connection': request.form.get('reality_connection', ''),
                'thinking_bubble': request.form.get('thinking_bubble', ''),
                'smiling_conclusion': request.form.get('smiling_conclusion', ''),
                'section': request.form.get('section', 1),
                'camp': request.form['camp']  # Get camp from form
            }

            # Validate camp selection
            valid_camps = ['Middle East', 'Chinese', 'both']
            if data['camp'] not in valid_camps:
                flash('Please select a valid training camp.', 'danger')
                return redirect(url_for('admin_edit_word', word_id=word_id))

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE words SET
                    unit_id=%(unit_id)s, word=%(word)s, one_sentence_version=%(one_sentence_version)s,
                    daily_definition=%(daily_definition)s, life_metaphor=%(life_metaphor)s,
                    visual_explanation=%(visual_explanation)s, core_elements=%(core_elements)s,
                    scenario_theater=%(scenario_theater)s, misunderstandings=%(misunderstandings)s,
                    reality_connection=%(reality_connection)s, thinking_bubble=%(thinking_bubble)s,
                    smiling_conclusion=%(smiling_conclusion)s, section=%(section)s, camp=%(camp)s
                WHERE id=%(id)s
            """, {**data, 'id': word_id})

            conn.commit()
            cursor.close()
            flash('Word updated successfully', 'success')
            return redirect(url_for('admin_manage_content'))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Admin edit word error: {str(e)}")
            flash(f'Error updating word: {str(e)}', 'danger')
        finally:
            if conn:
                release_db_connection(conn)

    # GET method - load the word
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM words WHERE id=%s", (word_id,))
        word = cursor.fetchone()
        cursor.close()

        if not word:
            flash('Word not found', 'danger')
            return redirect(url_for('admin_manage_content'))

        # Parse core_elements JSON string to Python list
        if word.get('core_elements'):
            try:
                word['core_elements'] = json.loads(word['core_elements'])
            except Exception:
                word['core_elements'] = []
        else:
            word['core_elements'] = []

    except Exception as e:
        logger.error(f"Admin load word error: {str(e)}")
        flash(f'Error loading word: {str(e)}', 'danger')
        return redirect(url_for('admin_manage_content'))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template('admin/edit_word.html', word=word)


@app.route('/admin/delete_word/<int:word_id>')
@admin_required
def admin_delete_word(word_id: int) -> Any:
    """Delete AI vocabulary word."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM words WHERE id=%s", (word_id,))
        conn.commit()
        cursor.close()
        flash('Word deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Admin delete word error: {str(e)}")
        flash(f'Error deleting word: {str(e)}', 'danger')
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for('admin_manage_content'))


@app.route('/admin/view_submission/<int:submission_id>')
@admin_required
def view_submission(submission_id: int) -> Any:
    """View and download a user submission."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get submission details
        cursor.execute("""
            SELECT s.file_path, s.unit_id, s.user_id, u.username
            FROM submissions s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s
        """, (submission_id,))

        submission = cursor.fetchone()
        cursor.close()

        if not submission or not submission['file_path']:
            flash("Submission file not found in database", "error")
            return redirect(url_for('admin_submissions'))

        # Clean up the file path - remove any path prefix if present
        file_path = submission['file_path']
        if '\\' in file_path:
            file_name = file_path.split('\\')[-1]
        elif '/' in file_path:
            file_name = file_path.split('/')[-1]
        else:
            file_name = file_path

        # Get full path to file
        full_path = os.path.join(UPLOAD_FOLDER, file_name)
        logger.info(f"Attempting to download: {full_path}")

        if not os.path.exists(full_path):
            flash(f"File not found on server: {file_name}", "error")
            return redirect(url_for('admin_submissions'))

        # Create a descriptive filename for the download
        download_name = f"{submission['username']}_submission_{submission_id}_{file_name}"

        # Send the file with explicit parameters
        return send_file(
            full_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=download_name
        )

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for('admin_submissions'))
    finally:
        if conn:
            release_db_connection(conn)


# New routes for documents management
@app.route('/admin/manage_documents')
@admin_required
def admin_manage_documents() -> Any:
    """Manage documents for Q&A system."""
    documents = get_document_list()
    return render_template('admin/manage_documents.html', documents=documents)


@app.route('/admin/upload_document', methods=['GET', 'POST'])
@admin_required
def admin_upload_document() -> Any:
    """Upload documents for the simplified Q&A system."""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'document' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)

        file = request.files['document']

        # Check if file was selected
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)

        # Check file extension
        if file and (file.filename.endswith('.pdf') or
                     file.filename.endswith('.ppt') or
                     file.filename.endswith('.pptx') or
                     file.filename.endswith('.txt')):
            try:
                # Save file
                filename = secure_filename(file.filename)
                file_path = os.path.join(DOCUMENTS_DIR, filename)
                file.save(file_path)

                # Reinitialize the simplified QA system
                from qa import initialize_qa
                global _qa_instance
                class QASystemManager:
                    def __enter__(self):
                       return self.qa_system
                    def __exit__(self, exc_type, exc_val, exc_tb):
                        self.cleanup()

                qa_system = initialize_qa(
                    documents_dir=DOCUMENTS_DIR,
                    llama_model_path=LLAMA_MODEL_PATH if 'LLAMA_MODEL_PATH' in globals() else None)

                flash(
                    'Document uploaded and Q&A system updated successfully',
                    'success')
            except Exception as e:
                logger.error(f"Error uploading document: {str(e)}")
                flash(f'Error uploading document: {str(e)}', 'danger')
        else:
            flash(
                'Invalid file type. Only PDF, PPT, PPTX, and TXT files are allowed',
                'danger')

        return redirect(url_for('admin_manage_documents'))

    # Get documents list for display
    documents = get_document_list()
    return render_template('admin/upload_document.html', documents=documents)


@app.route('/admin/delete_document/<path:filename>')
@admin_required
def admin_delete_document(filename: str) -> Any:
    """Delete a document from the simplified Q&A system."""
    try:
        # Security check to prevent directory traversal
        safe_filename = secure_filename(filename)
        file_path = os.path.join(DOCUMENTS_DIR, safe_filename)

        if os.path.exists(file_path):
            os.remove(file_path)

            # Reset and reinitialize the QA system
            from qa import initialize_qa
            global _qa_instance
            _qa_instance = None  # Reset global instance

            # Check if there are still documents
            remaining_files = []
            for root, dirs, files in os.walk(DOCUMENTS_DIR):
                for file in files:
                    if file.lower().endswith(('.pdf', '.pptx', '.ppt', '.txt')):
                        remaining_files.append(file)

            if remaining_files:
                # Reinitialize with remaining documents
                qa_system = initialize_qa(
                    documents_dir=DOCUMENTS_DIR,
                    llama_model_path=LLAMA_MODEL_PATH if 'LLAMA_MODEL_PATH' in globals() else None)
                flash(
                    f"Document '{safe_filename}' deleted. Q&A system updated with {len(remaining_files)} remaining documents.",
                    "success")
            else:
                # Remove vector db folder if it exists
                vector_db_path = os.path.join(os.getcwd(), 'vector_db')
                if os.path.exists(vector_db_path):
                    import shutil
                    shutil.rmtree(vector_db_path)
                flash(
                    "Document deleted. No documents remaining - Q&A system reset.",
                    "success")

        else:
            flash("Document not found", "error")

    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        flash(f"Error deleting document: {str(e)}", "danger")

    return redirect(url_for('admin_manage_documents'))


@app.route('/admin/rebuild_qa_system')
@admin_required
def admin_rebuild_qa() -> Any:
    """Rebuild the simplified Q&A system from scratch."""
    try:
        # Check if we have documents
        supported_files = []
        for root, dirs, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                if file.lower().endswith(('.pdf', '.pptx', '.ppt', '.txt')):
                    supported_files.append(file)

        if supported_files:
            # Reset and reinitialize the QA system
            from qa import initialize_qa
            global _qa_instance
            _qa_instance = None  # Reset global instance

            # Remove existing vector database to force rebuild
            vector_db_path = os.path.join(os.getcwd(), 'vector_db')
            if os.path.exists(vector_db_path):
                import shutil
                shutil.rmtree(vector_db_path)
                logger.info("Removed existing vector database for rebuild")

            # Initialize fresh system
            qa_system = initialize_qa(
                documents_dir=DOCUMENTS_DIR,
                llama_model_path=LLAMA_MODEL_PATH if 'LLAMA_MODEL_PATH' in globals() else None)

            flash(f"Q&A system rebuilt successfully with {len(supported_files)} documents", "success")

        else:
            flash("No documents found to build the Q&A system", "warning")

    except Exception as e:
        logger.error(f"Error rebuilding QA system: {str(e)}")
        flash(f"Error rebuilding QA system: {str(e)}", "danger")

    return redirect(url_for('admin_manage_documents'))


# Optional: Add a route to check QA system status for admins
@app.route('/admin/qa_status')
@admin_required
def admin_qa_status() -> Any:
    """Get detailed QA system status for admin."""
    try:
        from qa import get_system_status, get_qa_system

        status = get_system_status(
            documents_dir=DOCUMENTS_DIR,
            llama_model_path=LLAMA_MODEL_PATH if 'LLAMA_MODEL_PATH' in globals() else None)

        qa_system = get_qa_system()

        # Get additional details
        vector_db_path = os.path.join(os.getcwd(), 'vector_db')
        vector_db_exists = os.path.exists(vector_db_path)

        if vector_db_exists:
            vector_db_size = sum(
                os.path.getsize(os.path.join(vector_db_path, f))
                for f in os.listdir(vector_db_path)
                if os.path.isfile(os.path.join(vector_db_path, f))
            )
            vector_db_size_mb = round(vector_db_size / (1024 * 1024), 2)
        else:
            vector_db_size_mb = 0

        status_info = {
            'ready': status.get('ready', False),
            'initializing': status.get('initializing', False),
            'error': status.get('error'),
            'document_count': status.get('document_count', 0),
            'llama_available': status.get('llama_available', False),
            'vector_db_exists': vector_db_exists,
            'vector_db_size_mb': vector_db_size_mb,
            'documents_dir': DOCUMENTS_DIR,
            'qa_system_initialized': qa_system is not None
        }

        return jsonify(status_info)

    except Exception as e:
        logger.error(f"Error getting QA status: {str(e)}")
        return jsonify({
            'error': str(e),
            'ready': False,
            'initializing': False
        }), 500


@app.route('/admin/debug_submission/<int:submission_id>')
@admin_required
def debug_submission(submission_id: int) -> Any:
    """Debug tool for troubleshooting submission downloads."""
    debug_info = []

    try:
        debug_info.append(f"Checking submission ID: {submission_id}")

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get submission details
        cursor.execute(
            "SELECT file_path, unit_id, user_id FROM submissions WHERE id=%s",
            (submission_id,
             ))
        submission = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)

        if not submission:
            debug_info.append("ERROR: Submission not found in database")
            return f"<pre>{'<br>'.join(debug_info)}</pre>"

        debug_info.append(f"Found submission: {dict(submission)}")

        # Check file path
        if not submission['file_path']:
            debug_info.append("ERROR: Submission file_path is empty")
            return f"<pre>{'<br>'.join(debug_info)}</pre>"

        # Get user info
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT username FROM users WHERE id=%s",
                       (submission['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)

        debug_info.append(f"User info: {dict(user) if user else 'Not found'}")

        # Clean up the file path if needed
        file_path = submission['file_path']
        if '\\' in file_path:
            clean_filename = file_path.split('\\')[-1]
        elif '/' in file_path:
            clean_filename = file_path.split('/')[-1]
        else:
            clean_filename = file_path

        # Full path to file
        full_path = os.path.join(UPLOAD_FOLDER, clean_filename)
        debug_info.append(f"Original file path: {file_path}")
        debug_info.append(f"Cleaned filename: {clean_filename}")
        debug_info.append(f"Full file path: {full_path}")

        # Check if file exists
        file_exists = os.path.exists(full_path)
        debug_info.append(f"File exists: {file_exists}")

        if not file_exists:
          debug_info.append(f"UPLOAD_FOLDER is configured as: {UPLOAD_FOLDER}")
          debug_info.append(f"UPLOAD_FOLDER absolute path: {os.path.abspath(UPLOAD_FOLDER)}")
          debug_info.append(f"Files in upload folder: {os.listdir(UPLOAD_FOLDER)}")
          return f"<pre>{'<br>'.join(debug_info)}</pre>"


        # File information
        file_size = os.path.getsize(full_path)
        debug_info.append(f"File size: {file_size} bytes")

        # Create direct download link
        direct_link = f"/admin/stream_file/{clean_filename}"
        debug_info.append(f"Direct download link: {direct_link}")

        html = f"""
        <pre>{'<br>'.join(debug_info)}</pre>
        <hr>
        <a href="{direct_link}" style="padding: 10px; background: blue; color: white; text-decoration: none;">
            Direct Download
        </a>
        <hr>
        <a href="{url_for('admin_submissions')}" style="padding: 10px; background: gray; color: white; text-decoration: none;">
            Back to Submissions
        </a>
        """
        return html

    except Exception as e:
        debug_info.append(f"ERROR: {str(e)}")
        return f"<pre>{'<br>'.join(debug_info)}</pre>"


@app.route('/admin/stream_file/<path:filename>')
@admin_required
def stream_file(filename: str) -> Any:
    """Stream a file directly to the browser."""
    try:
        # Extract just the filename portion if it contains path elements
        if '\\' in filename:
            clean_filename = filename.split('\\')[-1]
        elif '/' in filename:
            clean_filename = filename.split('/')[-1]
        else:
            clean_filename = filename

        file_path = os.path.join(UPLOAD_FOLDER, clean_filename)

        if not os.path.exists(file_path):
            return f"File not found: {file_path}", 404

        # Get file size
        file_size = os.path.getsize(file_path)

        # Open the file in binary mode
        with open(file_path, 'rb') as f:
            # Stream the file in chunks
            def generate():
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    yield chunk

        # Set appropriate headers
        headers = {
            'Content-Disposition': f'attachment; filename="{os.path.basename(clean_filename)}"',
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(file_size),
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }

        # Return a streaming response
        return app.response_class(
            generate(),
            headers=headers,
            direct_passthrough=True
        )

    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        return f"Error: {str(e)}", 500


@app.route('/health')
def health_check():
    """Comprehensive health check endpoint."""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {}
    }
    
    # Check database connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Check QA system
    try:
        qa_system = get_qa_system()
        if qa_system and qa_system.vector_store_manager.is_ready():
            health_status['services']['qa_system'] = 'healthy'
        else:
            health_status['services']['qa_system'] = 'initializing'
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['services']['qa_system'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Check HuggingFace API
    try:
        from qa import get_hf_config
        api_key, model = get_hf_config()
        if api_key and model:
            health_status['services']['huggingface'] = 'configured'
        else:
            health_status['services']['huggingface'] = 'not configured'
    except Exception as e:
        health_status['services']['huggingface'] = f'error: {str(e)}'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code



@app.errorhandler(404)
def page_not_found(e: Exception) -> tuple:
    """Handle 404 errors."""
    return render_template('error.html', message="Page not found"), 404
# Custom Jinja2 filter to replace newlines with <br>


@app.template_filter('nl2br')
def nl2br_filter(s):
    if s is None:
        return ""
    return s.replace("\n", "<br>")


@app.errorhandler(500)
def internal_server_error(e: Exception) -> tuple:
    """Handle 500 errors."""
    return render_template('error.html', message="Internal server error"), 500


if __name__ == '__main__':
    try:
        initialize_enhanced_qa_system()  
        init_db_pool()
        validate_app_environment()
        print("Starting Flask application with enhanced QA system...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
