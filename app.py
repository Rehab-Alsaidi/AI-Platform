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
import re
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import logging

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
    url_for,
)
from flask_mail import Mail, Message
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import secrets
import string
import random
import threading
import zipfile

# Local application imports
from qa import initialize_qa, get_qa_system, get_system_status

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

_followup_system_initialized = False

def validate_app_environment():
    """Validate all required environment variables at startup."""
    required_vars = {
        "DB_HOST": DB_HOST,
        "DB_PASSWORD": DB_PASSWORD,
        "FLASK_SECRET_KEY": app.secret_key,
        "MAIL_USERNAME": app.config.get("MAIL_USERNAME"),
        "ACCESS_PASSWORD": ACCESS_PASSWORD,
    }

    missing = [var for var, value in required_vars.items() if not value]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    logger.info("✅ All required environment variables validated")


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fiftyone_learning")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address, app=app, default_limits=["200 per day", "50 per hour"]
)

# Configuration
UPLOAD_FOLDER = "static/uploads"
DOCUMENTS_DIR = os.path.join(os.getcwd(), "documents")
VECTOR_DB_PATH = os.path.join(os.getcwd(), "vector_db")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "ppt", "pptx", "doc", "docx"}
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "5151")
# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# bootcamp configuration to include all three camps consistently
BOOTCAMP_TYPES = ["Chinese", "English", "Middle East"]

CAMPS = {"Chinese": "Chinese", "English": "English", "Middle East": "Middle East"}

# Configure Flask-Mail
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() in (
    "true",
    "1",
    "t",
)
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

# Create mail instance
mail = Mail(app)

_qa_instance = None

# Global database connection pool
db_connection_pool: Optional[pool.SimpleConnectionPool] = None

app_metrics = {
    "qa_requests": 0,
    "qa_errors": 0,
    "response_times": [],
    "active_users": set(),
}
# ==============================================
# Supported languages
LANGUAGES: Dict[str, str] = {"en": "English", "zh": "中文", "ar": "العربية"}


TRANSLATIONS = {
    "en": {
        "welcome": "51Talk AI Hub",
        "login": "Login",
        "register": "Register",
        "username": "Username",
        "password": "Password",
        "submit": "Submit",
        "dashboard": "Dashboard",
        "ai_chat": "AI Chat",
        "learning": "Learning",
        "progress": "Progress",
        "settings": "Settings",
        "logout": "Logout",
        "welcome_msg": "Welcome to the 51Talk AI Learning Platform!",
        "continue_learning": "Continue Learning",
        "your_progress": "Your Progress",
        "unit": "Unit",
        "completed": "Completed",
        "score": "Score",
        "ask_ai": "Ask the AI",
        "chat_here": "Type your message here",
        "send": "Send",
        "learning_materials": "Learning Materials",
        "quizzes": "Quizzes",
        "videos": "Videos",
        "projects": "Projects",
        "feedback": "Feedback",
        "account": "Account",
        "language": "Language",
        "save": "Save",
        "learn_unit_desc": "Learn essential concepts and practice with interactive exercises.",
        "review_unit": "Review Unit",
        "start_unit": "Start Unit",
        "locked": "Locked",
        "units_completed": "Units Completed",
        "units_remaining": "Units Remaining",
        "daily_tip": "Daily Tip",
        "submit_feedback": "Submit Feedback",
        "your_feedback": "Your Feedback",
        "rating": "Rating",
        "excellent": "Excellent",
        "good": "Good",
        "average": "Average",
        "fair": "Fair",
        "poor": "Poor",
        "ai_learning_assistant": "AI Learning Assistant",
        "ask_course_question": "Ask any question about the course material",
        "your_question": "Your question",
        "ask_ai_placeholder": "Ask anything about course materials...",
        "ask_assistant": "Ask Assistant",
        "assistant_response": "Assistant's Response",
        "ask_another_question": "Ask Another Question",
        "email": "Email",
        "confirm_password": "Confirm Password",
        "reset_password": "Reset Password",
        "forgot_password": "Forgot Password",
        "email_verification": "Email Verification",
        "source_documents": "Source Documents",
        "quiz_completed": "Quiz Completed",
        "passed": "Passed",
        "not_passed": "Not Passed",
        "unknown_date": "Unknown date",
        "quiz_already_taken": "You have already taken this quiz. Click below to review your answers and explanations.",
        "review_quiz_results": "Review Quiz Results",
        "test_knowledge": "Test your knowledge with this unit quiz. You can only take this quiz once, so make sure you are ready!",
        "important": "Important",
        "quiz_one_attempt_warning": "This quiz can only be taken once. Make sure you have studied the material before proceeding.",
        "take_quiz_one_attempt": "Take Quiz (One Attempt Only)",
        "no_quiz_available": "No quiz available for this unit yet.",
        "quiz_review_mode": "Quiz Review Mode",
        "quiz_review": "Quiz Review",
        "completed_on": "Completed on",
        "note": "Note",
        "quiz_one_attempt_note": "This quiz can only be taken once. You can review your answers and explanations below.",
        "correct": "Correct",
        "incorrect": "Incorrect",
        "your_answer": "Your Answer",
        "correct_answer": "Correct Answer",
        "explanation": "Explanation",
        "back_to_unit": "Back to Unit",
        "quiz": "Quiz",
        "mindmap": "Mindmap",
        "ai_mindmap": "AI Mindmap", 
        "generate_mindmap": "Generate Mindmap",
        "view_mindmap": "View Mindmap",
        "interactive_mindmap": "Interactive Mindmap",
        "mindmap_generator": "Mindmap Generator",
        "mindmap_analysis": "AI is analyzing your materials",
        "mindmap_ready": "Mindmap ready for exploration",
        "change_username": "Change Username",
        "update_your_username": "Update your username",
        "current_username": "Current Username",
        "new_username": "New Username",
        "enter_new_username": "Enter new username",
        "username_requirements": "Username can only contain letters, numbers, and underscores",
        "username_help_text": "3-50 characters, letters, numbers, and underscores only",
        "confirm_with_password": "Confirm with Password",
        "enter_current_password": "Enter your current password",
        "password_confirmation_help": "Required to confirm your identity",
        "update_username": "Update Username",
        "cancel": "Cancel",
        "important_notice": "Important Notice",
        "username_change_notice": "Changing your username will affect how others see you in the system. Your login email remains the same.",
        "show_password": "Show Password",
        "hide_password": "Hide Password",
        "video_type": "Video Type",
        "youtube_video": "YouTube Video",
        "lark_video": "Lark Recording",
        "upload_video": "Upload Video File",
        "youtube_url": "YouTube URL",
        "lark_url": "Lark Recording URL",
        "video_file": "Video File",
        "select_video_type": "Select video type",
        "youtube_url_placeholder": "https://youtube.com/watch?v=...",
        "lark_url_placeholder": "https://meetings.lark.cn/...",
        "video_file_help": "Supported formats: MP4, AVI, MOV, WMV, FLV, WEBM",
        "leaderboard": "Leaderboard",
        "your_camp_leaderboard": "Your Camp Leaderboard",
        "all_camps_leaderboard": "All Camps Leaderboard",
        "team_name": "Team Name",
        "team_score": "Score",
        "team_leader": "Team Leader",
        "no_teams_yet": "No teams created yet",
        "generating_mindmap": "Generating mindmap...",
        "mindmap_error": "Error generating mindmap",
        "mindmap_ready": "Mindmap ready!",
        "expand_node": "Click to expand",
        "mindmap_materials": "Learning Materials Mindmap",
        "mindmap_vocabulary": "Vocabulary Mindmap",
        "loading": "Loading...",
        "error_occurred": "An error occurred",
        "try_again": "Try Again",
        "success": "Success",
        "change_username": "Change Username",
        "update_your_username": "Update your username",
        "current_username": "Current Username",
        "new_username": "New Username",
        "enter_new_username": "Enter new username",
        "username_requirements": "Username can only contain letters, numbers, and underscores",
        "username_help_text": "3-50 characters, letters, numbers, and underscores only",
        "confirm_with_password": "Confirm with Password",
        "enter_current_password": "Enter your current password",
        "password_confirmation_help": "Required to confirm your identity",
        "update_username": "Update Username",
        "cancel": "Cancel",
        "important_notice": "Important Notice",
        "username_change_notice": "Changing your username will affect how others see you in the system. Your login email remains the same.",
        "video_type": "Video Type",
        "youtube_video": "YouTube Video",
        "lark_video": "Lark Recording",
        "upload_video": "Upload Video File",
        "leaderboard": "Leaderboard",
        "your_camp_leaderboard": "Your Camp Leaderboard",
        "team_name": "Team Name",
        "team_score": "Score",
        "team_leader": "Team Leader",
    },
    "zh": {
        "welcome": "51Talk 智能中心",
        "login": "登录",
        "register": "注册",
        "username": "用户名",
        "password": "密码",
        "submit": "提交",
        "dashboard": "仪表板",
        "ai_chat": "AI聊天",
        "learning": "学习",
        "progress": "进度",
        "settings": "设置",
        "logout": "退出",
        "welcome_msg": "欢迎来到51Talk人工智能学习平台！",
        "continue_learning": "继续学习",
        "your_progress": "您的进度",
        "unit": "单元",
        "completed": "已完成",
        "score": "分数",
        "ask_ai": "问AI",
        "chat_here": "在这里输入您的消息",
        "send": "发送",
        "learning_materials": "学习材料",
        "quizzes": "小测验",
        "videos": "视频",
        "projects": "项目",
        "feedback": "反馈",
        "account": "账户",
        "language": "语言",
        "save": "保存",
        "learn_unit_desc": "学习基本概念并通过互动练习进行练习。",
        "review_unit": "复习单元",
        "start_unit": "开始单元",
        "locked": "已锁定",
        "units_completed": "已完成单元",
        "units_remaining": "剩余单元",
        "daily_tip": "每日提示",
        "submit_feedback": "提交反馈",
        "your_feedback": "您的反馈",
        "rating": "评分",
        "excellent": "优秀",
        "good": "良好",
        "average": "一般",
        "fair": "尚可",
        "poor": "差",
        "ai_learning_assistant": "AI学习助手",
        "ask_course_question": "提出任何关于课程材料的问题",
        "your_question": "您的问题",
        "ask_ai_placeholder": "询问任何关于课程材料的问题...",
        "ask_assistant": "询问助手",
        "assistant_response": "助手的回答",
        "ask_another_question": "提出另一个问题",
        "email": "电子邮件",
        "confirm_password": "确认密码",
        "reset_password": "重置密码",
        "forgot_password": "忘记密码",
        "email_verification": "电子邮件验证",
        "source_documents": "参考文档",
        "quiz_completed": "测验已完成",
        "passed": "通过",
        "not_passed": "未通过",
        "unknown_date": "未知日期",
        "quiz_already_taken": "您已经参加过此测验。点击下方查看您的答案和解释。",
        "review_quiz_results": "查看测验结果",
        "test_knowledge": "用这个单元测验测试您的知识。您只能参加一次此测验，所以请确保您已准备好！",
        "important": "重要",
        "quiz_one_attempt_warning": "此测验只能参加一次。在继续之前，请确保您已学习了材料。",
        "take_quiz_one_attempt": "参加测验（仅限一次）",
        "no_quiz_available": "此单元还没有可用的测验。",
        "quiz_review_mode": "测验复习模式",
        "quiz_review": "测验复习",
        "completed_on": "完成于",
        "note": "注意",
        "quiz_one_attempt_note": "此测验只能参加一次。您可以在下面查看您的答案和解释。",
        "correct": "正确",
        "incorrect": "错误",
        "your_answer": "您的答案",
        "correct_answer": "正确答案",
        "explanation": "解释",
        "back_to_unit": "返回单元",
        "quiz": "测验",
        "mindmap": "思维导图",
        "ai_mindmap": "AI思维导图", 
       "generate_mindmap": "生成思维导图",
       "view_mindmap": "查看思维导图",
       "interactive_mindmap": "交互式思维导图",
       "mindmap_generator": "思维导图生成器",
       "mindmap_analysis": "AI正在分析您的材料",
       "mindmap_ready": "思维导图准备就绪",
       "change_username": "更改用户名",
        "update_your_username": "更新您的用户名",
        "current_username": "当前用户名",
        "new_username": "新用户名",
        "enter_new_username": "输入新用户名",
        "username_requirements": "用户名只能包含字母、数字和下划线",
        "username_help_text": "3-50个字符，仅限字母、数字和下划线",
        "confirm_with_password": "密码确认",
        "enter_current_password": "输入您的当前密码",
        "password_confirmation_help": "需要确认您的身份",
        "update_username": "更新用户名",
        "cancel": "取消",
        "important_notice": "重要提示",
        "username_change_notice": "更改用户名将影响其他人在系统中看到您的方式。您的登录邮箱保持不变。",
        "show_password": "显示密码",
        "hide_password": "隐藏密码",
        "video_type": "视频类型",
        "youtube_video": "YouTube视频",
        "lark_video": "飞书录像",
        "upload_video": "上传视频文件",
        "youtube_url": "YouTube链接",
        "lark_url": "飞书录像链接",
        "video_file": "视频文件",
        "select_video_type": "选择视频类型",
        "youtube_url_placeholder": "https://youtube.com/watch?v=...",
        "lark_url_placeholder": "https://meetings.lark.cn/...",
        "video_file_help": "支持格式：MP4、AVI、MOV、WMV、FLV、WEBM",
        "leaderboard": "排行榜",
        "your_camp_leaderboard": "您的训练营排行榜",
        "all_camps_leaderboard": "所有训练营排行榜",
        "team_name": "团队名称",
        "team_score": "分数",
        "team_leader": "团队负责人",
        "no_teams_yet": "尚未创建团队",
        "generating_mindmap": "正在生成思维导图...",
        "mindmap_error": "生成思维导图时出错",
        "mindmap_ready": "思维导图已准备就绪！",
        "expand_node": "点击展开",
        "mindmap_materials": "学习材料思维导图",
        "mindmap_vocabulary": "词汇思维导图",
        "loading": "加载中...",
        "error_occurred": "发生错误",
        "try_again": "重试",
        "success": "成功",
        "change_username": "更改用户名",
        "update_your_username": "更新您的用户名",
        "current_username": "当前用户名",
        "new_username": "新用户名",
        "enter_new_username": "输入新用户名",
        "username_requirements": "用户名只能包含字母、数字和下划线",
        "username_help_text": "3-50个字符，仅限字母、数字和下划线",
        "confirm_with_password": "密码确认",
        "enter_current_password": "输入您的当前密码",
        "password_confirmation_help": "需要确认您的身份",
        "update_username": "更新用户名",
        "cancel": "取消",
        "important_notice": "重要提示",
        "username_change_notice": "更改用户名将影响其他人在系统中看到您的方式。您的登录邮箱保持不变。",
        "video_type": "视频类型",
        "youtube_video": "YouTube视频",
        "lark_video": "飞书录像",
        "upload_video": "上传视频文件",
        "leaderboard": "排行榜",
        "your_camp_leaderboard": "您的训练营排行榜",
        "team_name": "团队名称",
        "team_score": "分数",
        "team_leader": "团队负责人",
    },
    "ar": {
        "welcome": "51Talk مركز الذكاءالاصطناعي",
        "login": "تسجيل الدخول",
        "register": "التسجيل",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "submit": "إرسال",
        "dashboard": "اللوحة الرئيسية",
        "ai_chat": "محادثة الذكاء الاصطناعي",
        "learning": "التعلم",
        "progress": "التقدم",
        "settings": "الإعدادات",
        "logout": "تسجيل الخروج",
        "welcome_msg": "مرحباً بك في منصة 51Talk للتعلم بالذكاء الاصطناعي!",
        "continue_learning": "متابعة التعلم",
        "your_progress": "تقدمك",
        "unit": "الوحدة",
        "completed": "مكتمل",
        "score": "الدرجة",
        "ask_ai": "اسأل الذكاء الاصطناعي",
        "chat_here": "اكتب رسالتك هنا",
        "send": "إرسال",
        "learning_materials": "المواد التعليمية",
        "quizzes": "الاختبارات",
        "videos": "الفيديوهات",
        "projects": "المشاريع",
        "feedback": "التعليقات",
        "account": "الحساب",
        "language": "اللغة",
        "save": "حفظ",
        "learn_unit_desc": "تعلم المفاهيم الأساسية وتدرب باستخدام التمارين التفاعلية.",
        "review_unit": "مراجعة الوحدة",
        "start_unit": "بدء الوحدة",
        "locked": "مقفل",
        "units_completed": "الوحدات المكتملة",
        "units_remaining": "الوحدات المتبقية",
        "daily_tip": "نصيحة اليوم",
        "submit_feedback": "إرسال تعليق",
        "your_feedback": "تعليقك",
        "rating": "التقييم",
        "excellent": "ممتاز",
        "good": "جيد",
        "average": "متوسط",
        "fair": "مقبول",
        "poor": "ضعيف",
        "ai_learning_assistant": "مساعد التعلم بالذكاء الاصطناعي",
        "ask_course_question": "اطرح أي سؤال حول مواد الدورة",
        "your_question": "سؤالك",
        "ask_ai_placeholder": "اسأل أي شيء عن مواد الدورة...",
        "ask_assistant": "اسأل المساعد",
        "assistant_response": "رد المساعد",
        "ask_another_question": "اطرح سؤالاً آخر",
        "email": "البريد الإلكتروني",
        "confirm_password": "تأكيد كلمة المرور",
        "reset_password": "إعادة تعيين كلمة المرور",
        "forgot_password": "نسيت كلمة المرور",
        "email_verification": "التحقق من البريد الإلكتروني",
        "source_documents": "المستندات المصدر",
        "quiz_completed": "تم إكمال الاختبار",
        "passed": "نجح",
        "not_passed": "لم ينجح",
        "unknown_date": "تاريخ غير معروف",
        "quiz_already_taken": "لقد أخذت هذا الاختبار بالفعل. انقر أدناه لمراجعة إجاباتك والتفسيرات.",
        "review_quiz_results": "مراجعة نتائج الاختبار",
        "test_knowledge": "اختبر معرفتك بهذا الاختبار للوحدة. يمكنك أخذ هذا الاختبار مرة واحدة فقط، لذا تأكد من أنك مستعد!",
        "important": "مهم",
        "quiz_one_attempt_warning": "يمكن أخذ هذا الاختبار مرة واحدة فقط. تأكد من أنك درست المادة قبل المتابعة.",
        "take_quiz_one_attempt": "خذ الاختبار (محاولة واحدة فقط)",
        "no_quiz_available": "لا يوجد اختبار متاح لهذه الوحدة حتى الآن.",
        "quiz_review_mode": "وضع مراجعة الاختبار",
        "quiz_review": "مراجعة الاختبار",
        "completed_on": "أكمل في",
        "note": "ملاحظة",
        "quiz_one_attempt_note": "يمكن أخذ هذا الاختبار مرة واحدة فقط. يمكنك مراجعة إجاباتك والتفسيرات أدناه.",
        "correct": "صحيح",
        "incorrect": "خطأ",
        "your_answer": "إجابتك",
        "correct_answer": "الإجابة الصحيحة",
        "explanation": "التفسير",
        "back_to_unit": "العودة إلى الوحدة",
        "quiz": "اختبار",
        "mindmap": "خريطة ذهنية",
       "ai_mindmap": "خريطة ذهنية بالذكاء الاصطناعي", 
       "generate_mindmap": "إنشاء خريطة ذهنية",
       "view_mindmap": "عرض الخريطة الذهنية",
       "interactive_mindmap": "خريطة ذهنية تفاعلية",
       "mindmap_generator": "مولد الخرائط الذهنية",
       "mindmap_analysis": "الذكاء الاصطناعي يحلل موادك",
       "mindmap_ready": "الخريطة الذهنية جاهزة للاستكشاف",
       "change_username": "تغيير اسم المستخدم",
        "update_your_username": "تحديث اسم المستخدم الخاص بك",
        "current_username": "اسم المستخدم الحالي",
        "new_username": "اسم المستخدم الجديد",
        "enter_new_username": "أدخل اسم المستخدم الجديد",
        "username_requirements": "يمكن أن يحتوي اسم المستخدم على أحرف وأرقام وشرطات سفلية فقط",
        "username_help_text": "3-50 حرف، أحرف وأرقام وشرطات سفلية فقط",
        "confirm_with_password": "التأكيد بكلمة المرور",
        "enter_current_password": "أدخل كلمة المرور الحالية",
        "password_confirmation_help": "مطلوب لتأكيد هويتك",
        "update_username": "تحديث اسم المستخدم",
        "cancel": "إلغاء",
        "important_notice": "تنبيه مهم",
        "username_change_notice": "تغيير اسم المستخدم سيؤثر على كيفية رؤية الآخرين لك في النظام. بريدك الإلكتروني للدخول يبقى كما هو.",
        
        # Password Visibility
        "show_password": "إظهار كلمة المرور",
        "hide_password": "إخفاء كلمة المرور",
        
        # Video Types
        "video_type": "نوع الفيديو",
        "youtube_video": "فيديو يوتيوب",
        "lark_video": "تسجيل لارك",
        "upload_video": "رفع ملف فيديو",
        "youtube_url": "رابط يوتيوب",
        "lark_url": "رابط تسجيل لارك",
        "video_file": "ملف الفيديو",
        "select_video_type": "اختر نوع الفيديو",
        "youtube_url_placeholder": "https://youtube.com/watch?v=...",
        "lark_url_placeholder": "https://meetings.lark.cn/...",
        "video_file_help": "الصيغ المدعومة: MP4، AVI، MOV، WMV، FLV، WEBM",
        "leaderboard": "لوحة المتصدرين",
        "your_camp_leaderboard": "لوحة متصدري معسكرك",
        "all_camps_leaderboard": "لوحة متصدري جميع المعسكرات",
        "team_name": "اسم الفريق",
        "team_score": "النقاط",
        "team_leader": "قائد الفريق",
        "no_teams_yet": "لم يتم إنشاء فرق بعد",
        "generating_mindmap": "جاري إنشاء الخريطة الذهنية...",
        "mindmap_error": "خطأ في إنشاء الخريطة الذهنية",
        "mindmap_ready": "الخريطة الذهنية جاهزة!",
        "expand_node": "انقر للتوسيع",
        "mindmap_materials": "خريطة ذهنية للمواد التعليمية",
        "mindmap_vocabulary": "خريطة ذهنية للمفردات",
        "loading": "جاري التحميل...",
        "error_occurred": "حدث خطأ",
        "try_again": "حاول مرة أخرى",
        "success": "نجح",
        "change_username": "تغيير اسم المستخدم",
        "update_your_username": "تحديث اسم المستخدم الخاص بك",
        "current_username": "اسم المستخدم الحالي",
        "new_username": "اسم المستخدم الجديد",
        "enter_new_username": "أدخل اسم المستخدم الجديد",
        "username_requirements": "يمكن أن يحتوي اسم المستخدم على أحرف وأرقام وشرطات سفلية فقط",
        "username_help_text": "3-50 حرف، أحرف وأرقام وشرطات سفلية فقط",
        "confirm_with_password": "التأكيد بكلمة المرور",
        "enter_current_password": "أدخل كلمة المرور الحالية",
        "password_confirmation_help": "مطلوب لتأكيد هويتك",
        "update_username": "تحديث اسم المستخدم",
        "cancel": "إلغاء",
        "important_notice": "تنبيه مهم",
        "username_change_notice": "تغيير اسم المستخدم سيؤثر على كيفية رؤية الآخرين لك في النظام. بريدك الإلكتروني للدخول يبقى كما هو.",
        "video_type": "نوع الفيديو",
        "youtube_video": "فيديو يوتيوب",
        "lark_video": "تسجيل لارك",
        "upload_video": "رفع ملف فيديو",
        "leaderboard": "لوحة المتصدرين",
        "your_camp_leaderboard": "لوحة متصدري معسكرك",
        "team_name": "اسم الفريق",
        "team_score": "النقاط",
        "team_leader": "قائد الفريق",
    },
}

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
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "fiftyone_learning"),
                user=os.getenv("DB_USER", "admin"),
                password=os.getenv("DB_PASSWORD", "admin123"),
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
            logger.warning("Connection pool not available, creating direct connection")
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "fiftyone_learning"),
                user=os.getenv("DB_USER", "admin"),
                password=os.getenv("DB_PASSWORD", "admin123"),
            )
            return conn
    except Exception as e:
        logger.error(f"Failed to get database connection: {str(e)}")
        raise


def release_db_connection(conn: Optional[psycopg2.extensions.connection]) -> None:
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


def safely_parse_options(options_data):
    """Safely parse quiz options regardless of whether they're stored as JSON string or list"""
    if options_data is None:
        return []
    elif isinstance(options_data, list):
        # Already a list (PostgreSQL JSONB automatically converts), return as-is
        return options_data
    elif isinstance(options_data, str):
        # JSON string, parse it
        try:
            return json.loads(options_data)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse options JSON: {options_data}")
            return []
    else:
        # Unknown type, return empty list
        logger.warning(f"Unknown options data type: {type(options_data)}")
        return []


def generate_verification_code(length: int = 32) -> str:
    """Generate a random verification code."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def validate_ai_input(data):
    """Validate AI request input."""
    if not data:
        raise ValueError("No data provided")

    question = data.get("question", "").strip()

    if not question:
        raise ValueError("Question is required")

    if len(question) > 2000:
        raise ValueError("Question too long (max 2000 characters)")

    # Check for potential injection attempts
    suspicious_patterns = ["<script", "javascript:", "data:", "vbscript:"]
    question_lower = question.lower()

    for pattern in suspicious_patterns:
        if pattern in question_lower:
            raise ValueError("Invalid characters detected")

    return question


def send_verification_email(email: str, verification_code: str) -> bool:
    """Send verification email to a user."""
    try:
        verification_link = url_for(
            "verify_email", code=verification_code, _external=True
        )

        msg = Message("Verify Your Email - 51Talk AI Learning", recipients=[email])
        msg.body = f"""Please verify your email by clicking on the link below:
{verification_link}

If you did not create an account, please ignore this email.
"""
        msg.html = f"""
<h1>Email Verification</h1>
<p>Thank you for registering with 51Talk AI Learning Platform!</p>
<p>Please verify your email by clicking on the link below:</p>
<p><a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 15px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">Verify Email</a></p>
<p>If you did not create an account, please ignore this email.</p>
<p>Best regards,<br>51Talk AI Learning Team</p>
"""

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
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f: Callable) -> Callable:
    """Decorator that checks if user has admin privileges."""

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not session.get("admin"):
            flash("Admin access required", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated_function


def get_text(key: str, fallback: str = None) -> str:
    """Get translated text based on current language with optional fallback."""
    lang = session.get("language", "en")
    text = TRANSLATIONS.get(lang, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get("en", {}).get(key)
    if text is None:
        # Use provided fallback or the key itself
        text = fallback if fallback is not None else key
    return text


def allowed_file(filename: str) -> bool:
    """Check if a file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        cursor.execute(
            """
            SELECT completed, quiz_score, project_completed
            FROM progress
            WHERE user_id = %s AND unit_number = %s
        """,
            (user_id, unit_id),
        )
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return result if result else (0, 0, 0)
    except Exception as e:
        logger.error(f"Error in get_progress: {str(e)}")
        return (0, 0, 0)


def has_attempted_quiz(user_id: int, unit_id: int) -> bool:
    """Check if a user has attempted a quiz (regardless of pass/fail)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s AND score IS NOT NULL
        """,
            (user_id, unit_id),
        )
        result = cursor.fetchone()[0] > 0
        cursor.close()
        release_db_connection(conn)
        return result
    except Exception as e:
        logger.error(f"Error in has_attempted_quiz: {str(e)}")
        return False


def get_quiz_attempt_info(user_id: int, unit_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about a user's quiz attempt."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT score, attempted_at, passed
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s AND score IS NOT NULL
            ORDER BY attempted_at DESC
            LIMIT 1
        """,
            (user_id, unit_id),
        )
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)

        if result:
            return {
                "score": result["score"],
                "attempted_at": result["attempted_at"],
                "passed": result["passed"],
            }
        return None
    except Exception as e:
        logger.error(f"Error in get_quiz_attempt_info: {str(e)}")
        return None


def can_take_quiz(user_id: int, unit_id: int) -> bool:
    """Check if a user can take a quiz (hasn't attempted it yet).
    Returns False if user has already attempted, regardless of pass/fail."""
    return not has_attempted_quiz(user_id, unit_id)


def get_quiz_status(user_id: int, unit_id: int) -> Dict[str, Any]:
    """Get comprehensive quiz status for a user and unit."""
    try:
        attempt_info = get_quiz_attempt_info(user_id, unit_id)
        has_attempted = has_attempted_quiz(user_id, unit_id)
        can_take = can_take_quiz(user_id, unit_id)

        return {
            "has_attempted": has_attempted,
            "can_take": can_take,
            "attempt_info": attempt_info,
            "can_review": has_attempted,  # Can review if attempted
        }
    except Exception as e:
        logger.error(f"Error in get_quiz_status: {str(e)}")
        return {
            "has_attempted": False,
            "can_take": True,
            "attempt_info": None,
            "can_review": False,
        }


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
        if "user_id" not in session:
            return redirect(url_for("login"))

        user_camp = get_user_camp(session["user_id"])
        if not user_camp:
            flash("Please select your training camp first.", "warning")
            return redirect(url_for("select_camp"))

        session["user_camp"] = user_camp
        return f(*args, **kwargs)

    return decorated_function


# ADDED: Validation helper functions
def validate_bootcamp_type(bootcamp_type):
    """Validate bootcamp type against allowed types."""
    return bootcamp_type in BOOTCAMP_TYPES


def validate_content_camps(selected_camps):
    """Validate selected camps for content."""
    if not selected_camps:
        return False, "Please select at least one bootcamp type."

    invalid_camps = [camp for camp in selected_camps if camp not in BOOTCAMP_TYPES]
    if invalid_camps:
        return False, f"Invalid bootcamp types: {', '.join(invalid_camps)}"

    return True, None


def get_admin_stats() -> Dict[str, int]:
    """Get statistics for admin dashboard."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        stats: Dict[str, int] = {}

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count_result = cursor.fetchone()
        stats["total_users"] = user_count_result[0] if user_count_result else 0

        cursor.execute("SELECT COUNT(*) FROM quizzes")
        quiz_count_result = cursor.fetchone()
        stats["total_quizzes"] = quiz_count_result[0] if quiz_count_result else 0

        cursor.execute("SELECT COUNT(*) FROM materials")
        material_count_result = cursor.fetchone()
        stats["total_materials"] = (
            material_count_result[0] if material_count_result else 0
        )

        video_count_result = cursor.fetchone()
        stats["total_videos"] = video_count_result[0] if video_count_result else 0

        submission_count_result = cursor.fetchone()
        stats["total_submissions"] = (
            submission_count_result[0] if submission_count_result else 0
        )

        today_qa_result = cursor.fetchone()
        stats["today_qa"] = today_qa_result[0] if today_qa_result else 0

        today_quiz_attempts_result = cursor.fetchone()
        stats["today_quiz_attempts"] = (
            today_quiz_attempts_result[0] if today_quiz_attempts_result else 0
        )

        team_count_result = cursor.fetchone()
        stats["total_teams"] = team_count_result[0] if team_count_result else 0

        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count_result = cursor.fetchone()
        stats["total_projects"] = project_count_result[0] if project_count_result else 0

        document_count = 0
        for root, _, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                if (
                    file.endswith(".pdf")
                    or file.endswith(".ppt")
                    or file.endswith(".pptx")
                ):
                    document_count += 1
        stats["total_documents"] = document_count

        cursor.close()
        release_db_connection(conn)
        return stats
    except Exception as e:
        logger.error(f"Error in get_admin_stats: {str(e)}")
        return {
            "total_users": 0,
            "total_quizzes": 0,
            "total_materials": 0,
            "total_videos": 0,
            "total_projects": 0,
            "total_submissions": 0,
            "today_qa": 0,
            "today_quiz_attempts": 0,
            "total_teams": 0,
            "total_documents": 0,
        }


def generate_csv_file(
    data: List, filename: str, headers: Optional[List[str]] = None
) -> Optional[str]:
    """Create a CSV file from data."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv")

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

        cursor.execute(
            """
            SELECT tm.team_id
            FROM team_members tm
            WHERE tm.user_id = %s
        """,
            (user_id,),
        )

        result = cursor.fetchone()
        if not result:
            return

        team_id = result[0]

        cursor.execute(
            """
            SELECT id FROM team_scores WHERE team_id = %s
        """,
            (team_id,),
        )

        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE team_scores
                SET score = score + %s, updated_at = CURRENT_TIMESTAMP
                WHERE team_id = %s
            """,
                (score_to_add, team_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, %s)
            """,
                (team_id, score_to_add),
            )

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
                if (
                    file.endswith(".pdf")
                    or file.endswith(".ppt")
                    or file.endswith(".pptx")
                ):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    documents.append(
                        {
                            "name": file,
                            "size": f"{file_size / 1024 / 1024:.2f} MB",
                            "type": file.split(".")[-1].upper(),
                            "added": datetime.fromtimestamp(
                                os.path.getctime(file_path)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "path": os.path.relpath(root, DOCUMENTS_DIR),
                        }
                    )
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
    return documents


def save_qa_history_async(user_id: int, question: str, answer: str):
    """Save QA history asynchronously to avoid blocking main thread."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO qa_history (user_id, question, answer)
            VALUES (%s, %s, %s)
        """,
            (user_id, question, answer),
        )
        conn.commit()
        cursor.close()
        logger.debug(f"QA history saved successfully for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving QA history async: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)


def initialize_enhanced_qa_system():
    """FIXED: Initialize the QA system properly for Railway deployment"""
    try:

        def init_in_background():
            try:
                logger.info("🚀 Starting QA system initialization...")

                # Import the proper initialization function
                from qa import initialize_qa, get_system_status

                # Initialize using the qa.py function
                qa_system = initialize_qa()

                # Wait for initialization to complete
                max_wait = 60  # 1 minute max
                wait_time = 0

                while wait_time < max_wait:
                    status = get_system_status()

                    if status.get("ready"):
                        logger.info(f"✅ QA system ready after {wait_time} seconds!")
                        logger.info(
                            f"📚 Documents loaded: {status.get('document_count', 0)}"
                        )
                        logger.info(
                            f"🤖 LLM Provider: {status.get('llm_provider', 'Unknown')}"
                        )
                        return

                    elif status.get("error"):
                        logger.error(
                            f"❌ QA initialization failed: {status.get('error')}"
                        )
                        return

                    elif status.get("initializing"):
                        logger.info(f"⏳ QA system initializing... ({wait_time}s)")

                    time.sleep(2)
                    wait_time += 2

                logger.warning("❌ QA initialization timed out after 1 minute")

            except Exception as e:
                logger.error(f"Failed to initialize QA system: {str(e)}")
                import traceback

                traceback.print_exc()

        # Start initialization in background thread
        init_thread = threading.Thread(target=init_in_background, daemon=True)
        init_thread.start()

    except Exception as e:
        logger.error(f"Error starting QA initialization: {str(e)}")


def track_qa_request(user_id: str, response_time: float, success: bool):
    """Track QA request metrics"""
    try:
        app_metrics["qa_requests"] += 1
        if not success:
            app_metrics["qa_errors"] += 1
        app_metrics["response_times"].append(response_time)
        app_metrics["active_users"].add(user_id)

        # Keep only last 100 response times
        if len(app_metrics["response_times"]) > 100:
            app_metrics["response_times"] = app_metrics["response_times"][-100:]

    except Exception as e:
        logger.error(f"Error tracking QA metrics: {str(e)}")


# ===============================================
# metrics endpoints
# ===============================================

@app.route("/metrics")
@admin_required
def metrics():
    """Application metrics for monitoring (visual dashboard)."""
    try:
        # Calculate QA metrics from app_metrics
        avg_response_time = (
            sum(app_metrics["response_times"]) / len(app_metrics["response_times"])
            if app_metrics["response_times"]
            else 0
        )
        
        success_rate = (
            (app_metrics["qa_requests"] - app_metrics["qa_errors"]) / app_metrics["qa_requests"]
            if app_metrics["qa_requests"] > 0
            else 0
        )
        
        # Get additional stats from database
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get today's QA activity
            cursor.execute("""
                SELECT COUNT(*) FROM qa_history 
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            today_qa = cursor.fetchone()[0] or 0
            
            # Get total QA requests (all time)
            cursor.execute("SELECT COUNT(*) FROM qa_history")
            total_qa_requests = cursor.fetchone()[0] or 0
            
            # Get active users today
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM qa_history 
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            today_active_users = cursor.fetchone()[0] or 0
            
            # Get total users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0] or 0
            
            # Get quiz attempts today
            cursor.execute("""
                SELECT COUNT(*) FROM quiz_attempts 
                WHERE DATE(attempted_at) = CURRENT_DATE
            """)
            today_quiz_attempts = cursor.fetchone()[0] or 0
            
            cursor.close()
            
        except Exception as db_error:
            logger.error(f"Database error in metrics: {str(db_error)}")
            today_qa = 0
            total_qa_requests = 0
            today_active_users = 0
            total_users = 0
            today_quiz_attempts = 0
        finally:
            if conn:
                release_db_connection(conn)
        
        # Get QA system status
        qa_system_status = "Unknown"
        document_count = 0
        try:
            from qa import get_system_status
            status = get_system_status()
            if status.get("ready"):
                qa_system_status = "Ready"
                document_count = status.get("document_count", 0)
            elif status.get("initializing"):
                qa_system_status = "Initializing"
            elif status.get("error"):
                qa_system_status = f"Error: {status.get('error')}"
            else:
                qa_system_status = "Not Ready"
        except Exception as qa_error:
            logger.error(f"QA status error: {str(qa_error)}")
            qa_system_status = "Error"
        
        # Prepare metrics data for template
        metrics_data = {
            # QA Metrics (from app_metrics)
            "qa_requests_total": app_metrics["qa_requests"],
            "qa_errors_total": app_metrics["qa_errors"],
            "qa_success_rate": success_rate,
            "avg_response_time_seconds": round(avg_response_time, 2),
            "active_users_count": len(app_metrics["active_users"]),
            
            # Additional metrics from database
            "total_qa_requests_db": total_qa_requests,
            "today_qa_requests": today_qa,
            "today_active_users": today_active_users,
            "total_users": total_users,
            "today_quiz_attempts": today_quiz_attempts,
            
            # System metrics
            "qa_system_status": qa_system_status,
            "document_count": document_count,
            
            # Timestamp
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        
        return render_template("admin/metrics_dashboard.html", metrics=metrics_data)
        
    except Exception as e:
        logger.error(f"Error in metrics dashboard: {str(e)}")
        # Return safe default values
        metrics_data = {
            "qa_requests_total": 0,
            "qa_errors_total": 0,
            "qa_success_rate": 0,
            "avg_response_time_seconds": 0,
            "active_users_count": 0,
            "total_qa_requests_db": 0,
            "today_qa_requests": 0,
            "today_active_users": 0,
            "total_users": 0,
            "today_quiz_attempts": 0,
            "qa_system_status": "Error",
            "document_count": 0,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        return render_template("admin/metrics_dashboard.html", metrics=metrics_data)


@app.route("/admin/export_data", methods=["GET"])
@admin_required
def admin_export_data():
    """Export filtered data to CSV or PDF."""
    
    # Get filter parameters
    student_types = request.args.getlist("student_type")
    selected_tags = request.args.getlist("tags")
    format_type = request.args.get("format", "csv")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build WHERE clause for filters
        where_conditions = []
        params = []
        
        if student_types:
            where_conditions.append("u.student_type = ANY(%s)")
            params.append(student_types)
        
        if selected_tags:
            where_conditions.append("""
                EXISTS (
                    SELECT 1 FROM user_tags ut 
                    JOIN tags t ON ut.tag_id = t.id 
                    WHERE ut.user_id = u.id AND t.name = ANY(%s)
                )
            """)
            params.append(selected_tags)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Get detailed user data for export
        cursor.execute(f"""
            SELECT 
                u.id,
                u.username,
                u.email,
                u.camp,
                u.student_type,
                u.cohort_name,
                u.created_at,
                u.email_verified,
                COUNT(DISTINCT s.id) as submission_count,
                COUNT(DISTINCT qa.id) as quiz_attempts,
                COUNT(DISTINCT qh.id) as qa_questions,
                MAX(s.submitted_at) as last_submission,
                MAX(qa.attempted_at) as last_quiz_attempt,
                MAX(qh.created_at) as last_qa_activity,
                STRING_AGG(DISTINCT t.name, ', ') as user_tags
            FROM users u
            LEFT JOIN submissions s ON u.id = s.user_id
            LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
            LEFT JOIN qa_history qh ON u.id = qh.user_id
            LEFT JOIN user_tags ut ON u.id = ut.user_id
            LEFT JOIN tags t ON ut.tag_id = t.id
            {where_clause}
            GROUP BY u.id, u.username, u.email, u.camp, u.student_type, u.cohort_name, u.created_at, u.email_verified
            ORDER BY u.username
        """, params)
        
        export_data = cursor.fetchall()
        cursor.close()
        
        if format_type == "csv":
            return export_to_csv(export_data, student_types, selected_tags)
        elif format_type == "pdf":
            return export_to_pdf(export_data, student_types, selected_tags)
        else:
            flash("Invalid export format", "error")
            return redirect(url_for("admin_export_advanced"))
            
    except Exception as e:
        logger.error(f"Error in export_data: {str(e)}")
        flash(f"Error exporting data: {str(e)}", "error")
        return redirect(url_for("admin_export_advanced"))
    finally:
        if conn:
            release_db_connection(conn)


def create_followup_table():
    """Create the followup_emails table for tracking follow-up emails."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followup_emails (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                sent_by VARCHAR(255) NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_type VARCHAR(50) NOT NULL DEFAULT 'assignment_reminder',
                subject VARCHAR(255),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_followup_emails_user_id ON followup_emails(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_followup_emails_sent_at ON followup_emails(sent_at)
        """)
        
        conn.commit()
        cursor.close()
        logger.info("Follow-up emails table created successfully")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating follow-up table: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)


@app.before_request
def initialize_followup_system():
    """Initialize the follow-up system on first request."""
    global _followup_system_initialized
    if not _followup_system_initialized:
        create_followup_table()
        _followup_system_initialized = True


def export_to_csv(data, student_types, selected_tags):
    """Export data to CSV format."""
    try:
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            "ID", "Username", "Email", "Camp", "Student Type", "Cohort", 
            "Registered", "Email Verified", "Submissions", "Quiz Attempts", 
            "QA Questions", "Last Submission", "Last Quiz", "Last QA Activity", "Tags"
        ]
        writer.writerow(headers)
        
        # Write data rows
        for row in data:
            writer.writerow([
                row["id"],
                row["username"],
                row["email"],
                row["camp"] or "No camp",
                row["student_type"] or "Unknown",
                row["cohort_name"] or "No cohort",
                row["created_at"].strftime("%Y-%m-%d") if row["created_at"] else "Unknown",
                "Yes" if row["email_verified"] else "No",
                row["submission_count"],
                row["quiz_attempts"],
                row["qa_questions"],
                row["last_submission"].strftime("%Y-%m-%d") if row["last_submission"] else "Never",
                row["last_quiz_attempt"].strftime("%Y-%m-%d") if row["last_quiz_attempt"] else "Never",
                row["last_qa_activity"].strftime("%Y-%m-%d") if row["last_qa_activity"] else "Never",
                row["user_tags"] or "No tags"
            ])
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filter_desc = []
        if student_types:
            filter_desc.append(f"types_{'_'.join(student_types)}")
        if selected_tags:
            filter_desc.append(f"tags_{len(selected_tags)}")
        
        filter_suffix = "_".join(filter_desc) if filter_desc else "all"
        filename = f"student_export_{filter_suffix}_{timestamp}.csv"
        
        # Create response
        output.seek(0)
        return app.response_class(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error creating CSV: {str(e)}")
        flash(f"Error creating CSV export: {str(e)}", "error")
        return redirect(url_for("admin_export_advanced"))


def export_to_pdf(data, student_types, selected_tags):
    """Export data to PDF format (simplified HTML to PDF)."""
    try:
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Student Export Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .header {{ margin-bottom: 20px; }}
                .filter-info {{ background-color: #f8f9fa; padding: 10px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Student Export Report</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="filter-info">
                <h3>Applied Filters:</h3>
                <p><strong>Student Types:</strong> {', '.join(student_types) if student_types else 'All'}</p>
                <p><strong>Tags:</strong> {', '.join(selected_tags) if selected_tags else 'All'}</p>
                <p><strong>Total Records:</strong> {len(data)}</p>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Camp</th>
                        <th>Student Type</th>
                        <th>Cohort</th>
                        <th>Submissions</th>
                        <th>Quiz Attempts</th>
                        <th>QA Questions</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for row in data:
            html_content += f"""
                <tr>
                    <td>{row['username']}</td>
                    <td>{row['email']}</td>
                    <td>{row['camp'] or 'No camp'}</td>
                    <td>{row['student_type'] or 'Unknown'}</td>
                    <td>{row['cohort_name'] or 'No cohort'}</td>
                    <td>{row['submission_count']}</td>
                    <td>{row['quiz_attempts']}</td>
                    <td>{row['qa_questions']}</td>
                </tr>
            """
        
        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"student_export_{timestamp}.html"
        
        # Return HTML (can be converted to PDF by browser)
        return app.response_class(
            html_content,
            mimetype="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        flash(f"Error creating PDF export: {str(e)}", "error")
        return redirect(url_for("admin_export_advanced"))
    

# ==============================================
# APPLICATION HOOKS
# ==============================================


@app.before_request
def before_request() -> None:
    """Ensure language is set before each request."""
    if "language" not in session:
        if "user_id" in session:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT language FROM users WHERE id = %s", (session["user_id"],)
                )
                result = cursor.fetchone()
                cursor.close()
                release_db_connection(conn)
                if result and result[0]:
                    session["language"] = result[0]
                    logger.info(
                        f"Setting language to {result[0]} from database for user {session['user_id']}"
                    )
                else:
                    session["language"] = "en"
                    logger.info("No language found for user, defaulting to 'en'")
            except Exception as e:
                logger.error(f"Error retrieving language from database: {str(e)}")
                session["language"] = "en"
        else:
            session["language"] = "en"
            logger.debug("No user logged in, defaulting to 'en'")


@app.after_request
def add_header(response: Any) -> Any:
    """Add headers to prevent caching."""
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response


@app.context_processor
def inject_globals() -> Dict[str, Any]:
    """Make important variables available to all templates."""
    return {
        "LANGUAGES": LANGUAGES,
        "get_text": get_text,
        "current_language": session.get("language", "en"),
        "get_quiz_attempt_info": get_quiz_attempt_info,
        "has_attempted_quiz": has_attempted_quiz,
        "can_take_quiz": can_take_quiz,
        "get_content_tags": get_content_tags,  # Add this line
        "get_user_tags": get_user_tags,  # Add this line
        "user_has_tag": user_has_tag,  # Add this line
    }


@app.context_processor
def inject_camps() -> Dict[str, Any]:
    """Make camps available to all templates."""
    return {
        "CAMPS": CAMPS,
        "get_user_camp": get_user_camp,
        "user_camp": session.get("user_camp"),
    }


@app.context_processor
def inject_tag_helpers() -> Dict[str, Any]:
    """Make tag helper functions available to templates."""
    return {
        "get_available_tags_grouped": get_available_tags_grouped,
    }


@app.context_processor
def inject_date_helpers() -> Dict[str, Any]:
    """Make date helpers available to all templates."""
    from datetime import date

    return {
        "today": date.today(),
        "now": datetime.now(),
        "current_year": date.today().year,
    }


def initialize_tag_system():
    """Initialize the tag system with default data."""
    try:
        ensure_default_tags()
        logger.info("Tag system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize tag system: {str(e)}")


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


@app.route("/", methods=["GET", "POST"])
def password_gate() -> Any:
    """Handle the initial password gate to access the application."""
    if request.method == "POST":
        password = request.form.get("password")
        if password == ACCESS_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("home"))
        else:
            flash("Incorrect password. Please try again.", "error")
    return render_template("password_gate.html")


@app.route("/home", methods=["GET"])
def home() -> Any:
    """Display the home page or redirect to dashboard if logged in."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/logout")
def logout() -> Any:
    """Handle user logout for both regular users and admin users."""
    session.pop("authenticated", None)
    session.pop("username", None)
    session.pop("language", None)
    session.pop("admin", None)
    session.pop("admin_username", None)
    session.pop("user_id", None)
    flash("You have been logged out", "info")
    return redirect(url_for("password_gate"))


# ==============================================
# USER AUTHENTICATION ROUTES
# ==============================================


@app.route("/register", methods=["GET", "POST"])
def register() -> Any:
    """Step 1: Basic info + bootcamp experience question."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        has_attended_bootcamp = request.form.get("has_attended_bootcamp")

        if not all(
            [username, email, password, confirm_password, has_attended_bootcamp]
        ):
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if not EMAIL_REGEX.match(email):
            flash("Invalid email address.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html")

        # Store in session for next step
        session["registration_data"] = {
            "username": username,
            "email": email,
            "password": password,
            "has_attended_bootcamp": has_attended_bootcamp,
        }

        return redirect(url_for("register_bootcamp_selection"))

    return render_template("register.html")


@app.route("/register/bootcamp_selection", methods=["GET", "POST"])
def register_bootcamp_selection() -> Any:
    """Step 2: Bootcamp type selection based on experience - FIXED."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if "registration_data" not in session:
        return redirect(url_for("register"))

    reg_data = session["registration_data"]

    if request.method == "POST":
        if reg_data["has_attended_bootcamp"] == "yes":
            previous_bootcamp_type = request.form.get("previous_bootcamp_type")
            upcoming_bootcamp_type = request.form.get("upcoming_bootcamp_type")

            if not all([previous_bootcamp_type, upcoming_bootcamp_type]):
                flash(
                    "Please select both previous and upcoming bootcamp types.", "error"
                )
                return render_template(
                    "register_bootcamp_info.html",
                    registration_data=reg_data,
                    bootcamp_types=BOOTCAMP_TYPES,
                )

            if not validate_bootcamp_type(
                previous_bootcamp_type
            ) or not validate_bootcamp_type(upcoming_bootcamp_type):
                flash("Invalid bootcamp type selection.", "error")
                return render_template(
                    "register_bootcamp_info.html",
                    registration_data=reg_data,
                    bootcamp_types=BOOTCAMP_TYPES,
                )

            reg_data.update(
                {
                    "student_type": "existing",
                    "previous_bootcamp_type": previous_bootcamp_type,
                    "upcoming_bootcamp_type": upcoming_bootcamp_type,
                }
            )
        else:
            upcoming_bootcamp_type = request.form.get("upcoming_bootcamp_type")

            if not upcoming_bootcamp_type or not validate_bootcamp_type(
                upcoming_bootcamp_type
            ):
                flash("Please select a valid bootcamp type.", "error")
                return render_template(
                    "register_bootcamp_info.html",
                    registration_data=reg_data,
                    bootcamp_types=BOOTCAMP_TYPES,
                )

            reg_data.update(
                {
                    "student_type": "new",
                    "upcoming_bootcamp_type": upcoming_bootcamp_type,
                }
            )

        session["registration_data"] = reg_data
        return redirect(url_for("register_cohort_selection"))

    # Get past cohorts if needed
    conn = None
    past_cohorts = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT name, start_date, end_date FROM cohorts 
            WHERE end_date < CURRENT_DATE 
            ORDER BY end_date DESC LIMIT 10
        """
        )
        past_cohorts = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Error getting past cohorts: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "register_bootcamp_info.html",
        registration_data=reg_data,
        bootcamp_types=BOOTCAMP_TYPES,
        past_cohorts=past_cohorts,
    )


@app.route("/register/cohort_selection", methods=["GET", "POST"])
def register_cohort_selection() -> Any:
    """Step 3: Cohort selection."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if "registration_data" not in session:
        return redirect(url_for("register"))

    reg_data = session["registration_data"]

    if request.method == "POST":
        cohort_id = request.form.get("cohort_id")

        if not cohort_id:
            flash("Please select a cohort.", "error")
            return render_template(
                "register_cohort_selection.html", registration_data=reg_data
            )

        # Complete registration
        hashed_password = generate_password_hash(
            reg_data["password"], method="pbkdf2:sha256"
        )
        verification_code = generate_verification_code()

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check existing username/email
            cursor.execute(
                "SELECT username FROM users WHERE username = %s",
                (reg_data["username"],),
            )
            if cursor.fetchone():
                flash("Username already exists.", "error")
                return render_template(
                    "register_cohort_selection.html", registration_data=reg_data
                )

            cursor.execute(
                "SELECT email FROM users WHERE email = %s", (reg_data["email"],)
            )
            if cursor.fetchone():
                flash("Email already exists.", "error")
                return render_template(
                    "register_cohort_selection.html", registration_data=reg_data
                )

            # Get cohort info
            cursor.execute(
                "SELECT name, bootcamp_type FROM cohorts WHERE id = %s", (cohort_id,)
            )
            cohort_info = cursor.fetchone()

            # Create user
            cursor.execute(
                """
                INSERT INTO users (username, email, password, verification_code, language, 
                                 camp, student_type, cohort_id, previous_bootcamp_type, cohort_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
                (
                    reg_data["username"],
                    reg_data["email"],
                    hashed_password,
                    verification_code,
                    "en",
                    reg_data["upcoming_bootcamp_type"],
                    reg_data["student_type"],
                    cohort_id,
                    reg_data.get("previous_bootcamp_type"),
                    cohort_info[0] if cohort_info else None,
                ),
            )
            user_id = cursor.fetchone()[0]

            # Assign tags automatically
            tags_to_assign = []

            # Student type tag
            if reg_data["student_type"] == "new":
                tags_to_assign.append("New Student")
            else:
                tags_to_assign.append("Existing Student")

            # Bootcamp type tag
            tags_to_assign.append(reg_data["upcoming_bootcamp_type"])

            # Cohort tag
            if cohort_info:
                tags_to_assign.append(cohort_info[0])  # cohort name

            # Assign tags
            assign_user_tags_by_names(user_id, tags_to_assign, "registration")

            conn.commit()

            # Send verification email
            if send_verification_email(reg_data["email"], verification_code):
                flash(
                    "Registration successful! Please check your email to verify your account.",
                    "success",
                )
            else:
                flash(
                    "Registration successful but failed to send verification email. Please contact support.",
                    "warning",
                )

            # Clear registration data
            session.pop("registration_data", None)
            return redirect(url_for("login"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash("An error occurred during registration. Please try again.", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    # Get available cohorts
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT * FROM cohorts 
            WHERE bootcamp_type = %s AND is_active = TRUE 
            ORDER BY start_date
        """,
            (reg_data["upcoming_bootcamp_type"],),
        )
        available_cohorts = cursor.fetchall()

        cursor.close()
    except Exception as e:
        logger.error(f"Error getting cohorts: {str(e)}")
        available_cohorts = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "register_cohort_selection.html",
        registration_data=reg_data,
        available_cohorts=available_cohorts,
    )


@app.route("/verify-email/<code>")
def verify_email(code: str) -> Any:
    """Verify a user's email address with the provided code."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email FROM users WHERE verification_code = %s AND email_verified = FALSE",
            (code,),
        )
        user = cursor.fetchone()

        if user:
            cursor.execute(
                "UPDATE users SET email_verified = TRUE, verification_code = NULL WHERE id = %s",
                (user[0],),
            )
            conn.commit()
            flash("Email verified successfully! You can now log in.", "success")
        else:
            flash("Invalid or expired verification link.", "error")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Email verification error: {str(e)}")
        flash("An error occurred during email verification.", "error")
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    """User and admin login with email verification and role check."""
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password, email_verified, role FROM users WHERE email = %s",
                (email,),
            )
            user = cursor.fetchone()
            if not user:
                flash("Invalid email or password.", "error")
                return render_template("login.html")
            user_id, username, hashed_password, email_verified, role = user
            if not check_password_hash(hashed_password, password):
                flash("Invalid email or password.", "error")
                return render_template("login.html")
            if not email_verified:
                flash("Please verify your email before logging in.", "error")
                return render_template("login.html")
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = role
            if role == "admin":
                session["admin"] = True
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("dashboard"))
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash("An error occurred during login.", "error")
        finally:
            if conn:
                release_db_connection(conn)
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password() -> Any:
    """Handle password reset request."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if request.method == "POST":
        email = request.form.get("email")

        if not email:
            flash("Email is required.", "error")
            return render_template("forgot_password.html")

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                reset_code = generate_verification_code()

                cursor.execute(
                    "UPDATE users SET verification_code = %s WHERE id = %s",
                    (reset_code, user[0]),
                )
                conn.commit()

                reset_link = url_for("reset_password", code=reset_code, _external=True)

                msg = Message(
                    "Reset Your Password - 51Talk AI Learning", recipients=[email]
                )
                msg.body = f"""Click the link below to reset your password:
{reset_link}

If you didn't request a password reset, please ignore this email.
"""
                msg.html = f"""
<h1>Password Reset</h1>
<p>You've requested to reset your password for your 51Talk AI Learning account.</p>
<p>Click the link below to reset your password:</p>
<p><a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 15px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">Reset Password</a></p>
<p>If you didn't request a password reset, please ignore this email.</p>
<p>Best regards,<br>51Talk AI Learning Team</p>
"""
                mail.send(msg)
                logger.info(f"Password reset email sent to {email}")

            flash(
                "If an account with that email exists, a password reset link has been sent.",
                "success",
            )
            return redirect(url_for("login"))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Password reset error: {str(e)}")
            flash("An error occurred. Please try again later.", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template("forgot_password.html")


@app.route("/reset-password/<code>", methods=["GET", "POST"])
def reset_password(code: str) -> Any:
    """Handle password reset functionality."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("reset_password.html", code=code)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", code=code)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("reset_password.html", code=code)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE verification_code = %s", (code,))
            user = cursor.fetchone()

            if user:
                hashed_password = generate_password_hash(
                    password, method="pbkdf2:sha256"
                )
                cursor.execute(
                    "UPDATE users SET password = %s, verification_code = NULL WHERE id = %s",
                    (hashed_password, user[0]),
                )
                conn.commit()

                flash("Your password has been updated successfully.", "success")
                return redirect(url_for("login"))
            else:
                flash("Invalid or expired reset link.", "error")
                return redirect(url_for("login"))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Password reset error: {str(e)}")
            flash("An error occurred. Please try again later.", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE verification_code = %s", (code,))
        user = cursor.fetchone()

        if not user:
            flash("Invalid or expired reset link.", "error")
            return redirect(url_for("login"))
    except Exception as e:
        logger.error(f"Password reset validation error: {str(e)}")
        flash("An error occurred. Please try again later.", "error")
        return redirect(url_for("login"))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)

    return render_template("reset_password.html", code=code)


@app.route("/select_camp", methods=["GET", "POST"])
@login_required
def select_camp() -> Any:
    """Allow users to select their training camp."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    user_id = session["user_id"]

    # Check if user already has a camp
    current_camp = get_user_camp(user_id)
    if current_camp:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        camp = request.form.get("camp")

        if not validate_bootcamp_type(camp):
            flash("Please select a valid training camp.", "error")
            return render_template("select_camp.html", camps=CAMPS)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET camp = %s WHERE id = %s", (camp, user_id))
            conn.commit()
            cursor.close()

            session["user_camp"] = camp
            flash(f"Welcome to {camp} training camp!", "success")
            return redirect(url_for("dashboard"))

        except Exception as e:
            logger.error(f"Error setting user camp: {str(e)}")
            flash("An error occurred. Please try again.", "error")
        finally:
            if conn:
                release_db_connection(conn)

    return render_template("select_camp.html", camps=CAMPS)

def create_fallback_words_mindmap(words, unit_id):
    """Create a simple fallback mindmap structure from vocabulary words."""
    mindmap = {
        "central_topic": f"Unit {unit_id} Vocabulary",
        "branches": []
    }
    
    # Group words by sections if available
    sections = {}
    for word in words[:10]:  # Limit to 10 words
        section = word.get('section', 1)
        if section not in sections:
            sections[section] = []
        sections[section].append(word)
    
    for section_num, section_words in sections.items():
        branch = {
            "name": f"Section {section_num}",
            "children": []
        }
        
        for word in section_words:
            child = {
                "name": word['word'],
                "type": "vocabulary"
            }
            
            # Add definition if available
            if word.get('daily_definition'):
                child['definition'] = word['daily_definition'][:50] + "..." if len(word['daily_definition']) > 50 else word['daily_definition']
            
            branch["children"].append(child)
        
        mindmap["branches"].append(branch)
    
    return mindmap


# ==============================================
# TAG SYSTEM UTILITY FUNCTIONS
# ==============================================


def get_user_tags(user_id: int) -> List[Dict[str, Any]]:
    """Get all tags assigned to a user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT tg.name as group_name, t.name as tag_name, t.id as tag_id
            FROM user_tags ut
            JOIN tags t ON ut.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ut.user_id = %s AND t.is_active = TRUE
            ORDER BY tg.name, t.name
        """,
            (user_id,),
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting user tags: {str(e)}")
        return []
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def user_has_tag(user_id: int, tag_name: str) -> bool:
    """Check if user has a specific tag."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM user_tags ut
            JOIN tags t ON ut.tag_id = t.id
            WHERE ut.user_id = %s AND t.name = %s AND t.is_active = TRUE
        """,
            (user_id, tag_name),
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking user tag: {str(e)}")
        return False
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def get_content_with_tag_filtering(content_type: str, unit_id: int, user_id: int):
    """FIXED content filtering - shows content if user's camp matches ANY of the content's assigned camps"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get user's camp
        cursor.execute("SELECT camp FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        user_camp = user_result["camp"] if user_result else None

        logger.info(f"FIXED FILTERING: User {user_id} has camp: {user_camp}")

        if not user_camp:
            logger.warning(
                f"FIXED FILTERING: User {user_id} has no camp - returning empty"
            )
            return []

        table_name = f"{content_type}s" if content_type != "quiz" else "quizzes"

        # Check if user's camp matches ANY of the content's bootcamp tags OR the main camp field
        cursor.execute(
            f"""
            SELECT DISTINCT c.* FROM {table_name} c
            WHERE c.unit_id = %s 
            AND (
                -- Match main camp field (backward compatibility)
                c.camp = %s 
                OR 
                -- Match any bootcamp type tag assigned to this content
                EXISTS (
                    SELECT 1 FROM content_tags ct
                    JOIN tags t ON ct.tag_id = t.id
                    JOIN tag_groups tg ON t.tag_group_id = tg.id
                    WHERE ct.content_type = %s 
                    AND ct.content_id = c.id
                    AND tg.name = 'Bootcamp Type'
                    AND t.name = %s
                )
            )
            ORDER BY c.id
            """,
            (unit_id, user_camp, content_type, user_camp),
        )

        content = cursor.fetchall()

        logger.info(
            f"FIXED FILTERING: Found {len(content)} {content_type}s for {user_camp} camp in unit {unit_id}"
        )

        cursor.close()
        return content

    except Exception as e:
        logger.error(f"FIXED FILTERING ERROR: {str(e)}")
        return []
    finally:
        if conn:
            release_db_connection(conn)


def get_content_no_filtering(content_type: str, unit_id: int):
    """Get ALL content for a unit without any tag filtering - for testing"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        table_name = f"{content_type}s" if content_type != "quiz" else "quizzes"

        cursor.execute(
            f"""
            SELECT * FROM {table_name} WHERE unit_id = %s ORDER BY id
        """,
            (unit_id,),
        )

        results = cursor.fetchall()
        logger.info(
            f"Found {len(results)} {content_type} items for unit {unit_id} (no filtering)"
        )
        return results

    except Exception as e:
        logger.error(f"Error getting content (no filtering): {str(e)}")
        return []
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def assign_content_tags(content_type: str, content_id: int, tag_ids: List[int]) -> bool:
    """Assign tags to content by tag ID."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Remove existing content tags
        cursor.execute(
            """
            DELETE FROM content_tags 
            WHERE content_type = %s AND content_id = %s
        """,
            (content_type, content_id),
        )
        # Add new tags
        for tag_id in tag_ids:
            cursor.execute(
                """
                INSERT INTO content_tags (content_type, content_id, tag_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """,
                (content_type, content_id, tag_id),
            )
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error assigning content tags: {str(e)}")
        return False
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def get_available_tags_grouped() -> Dict[str, List[Dict[str, Any]]]:
    """Get all available tags grouped by tag group."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT tg.name as group_name, t.id, t.name, t.description
            FROM tags t
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE t.is_active = TRUE AND tg.is_active = TRUE
            ORDER BY tg.name, t.name
        """
        )

        results = cursor.fetchall()
        grouped_tags = {}

        for row in results:
            group_name = row["group_name"]
            if group_name not in grouped_tags:
                grouped_tags[group_name] = []

            grouped_tags[group_name].append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                }
            )

        cursor.close()
        return grouped_tags
    except Exception as e:
        logger.error(f"Error getting grouped tags: {str(e)}")
        return {}
    finally:
        if conn:
            release_db_connection(conn)


def ensure_default_tags():
    """Ensure default tags exist for the system - FIXED VERSION."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure default tag groups exist
        default_groups = [
            ("Bootcamp Type", "Tags for different bootcamp types"),
            ("Student Type", "Tags for different student types"),
            ("Cohort", "Tags for different cohorts"),
            ("Skill Level", "Tags for different skill levels"),
        ]

        for group_name, description in default_groups:
            cursor.execute(
                """
                INSERT INTO tag_groups (name, description) 
                VALUES (%s, %s) 
                ON CONFLICT (name) DO NOTHING
            """,
                (group_name, description),
            )

        # Get group IDs
        cursor.execute(
            "SELECT id, name FROM tag_groups WHERE name = ANY(%s)",
            ([group[0] for group in default_groups],),
        )
        group_map = {row[1]: row[0] for row in cursor.fetchall()}

        default_tags = [
            ("Bootcamp Type", "Chinese", "Chinese bootcamp participants"),
            ("Bootcamp Type", "English", "English bootcamp participants"),
            ("Bootcamp Type", "Middle East", "Middle East bootcamp participants"),
            ("Student Type", "New Student", "First-time participants"),
            ("Student Type", "Existing Student", "Returning participants"),
            ("Skill Level", "Beginner", "Beginner level content"),
            ("Skill Level", "Intermediate", "Intermediate level content"),
            ("Skill Level", "Advanced", "Advanced level content"),
        ]

        for group_name, tag_name, description in default_tags:
            if group_name in group_map:
                cursor.execute(
                    """
                    INSERT INTO tags (tag_group_id, name, description) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (tag_group_id, name) DO NOTHING
                """,
                    (group_map[group_name], tag_name, description),
                )

        conn.commit()
        cursor.close()
        logger.info("Default tags ensured with all bootcamp types")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error ensuring default tags: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)


def get_content_tags(content_type: str, content_id: int) -> List[str]:
    """Get tag names for content."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.name FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            WHERE ct.content_type = %s AND ct.content_id = %s
        """,
            (content_type, content_id),
        )
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting content tags: {str(e)}")
        return []
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


def assign_user_tags_by_names(
    user_id: int, tag_names: List[str], assigned_by: str = "admin"
) -> bool:
    """Assign tags to user by tag names."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Remove existing tags first
        cursor.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))

        # Add new tags
        for tag_name in tag_names:
            cursor.execute(
                """
                SELECT id FROM tags WHERE name = %s AND is_active = TRUE
            """,
                (tag_name,),
            )
            tag_result = cursor.fetchone()

            if tag_result:
                cursor.execute(
                    """
                    INSERT INTO user_tags (user_id, tag_id, assigned_by)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """,
                    (user_id, tag_result[0], assigned_by),
                )

        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error assigning user tags: {str(e)}")
        return False
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


# ==============================================
# USER DASHBOARD & LEARNING ROUTES
# ==============================================

@app.route("/dashboard")
@login_required
def dashboard() -> Any:
    """Display user dashboard with user's camp leaderboard only."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]
    current_language = session.get("language", "en")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get user's camp
        cursor.execute("SELECT camp FROM users WHERE id = %s", (user_id,))
        user_result = cursor.fetchone()
        user_camp = user_result["camp"] if user_result else None

        # Get completed units count
        cursor.execute(
            "SELECT COUNT(DISTINCT unit_number) FROM progress WHERE user_id=%s AND completed=1",
            (user_id,),
        )
        completed_units = cursor.fetchone()["count"] or 0

        # Get user's team info
        cursor.execute(
            """
            SELECT t.id, t.name, t.camp, u.username AS team_lead_name
            FROM teams t
            JOIN team_members tm ON t.id = tm.team_id
            JOIN users u ON t.team_lead_id = u.id
            WHERE tm.user_id = %s
        """,
            (user_id,),
        )
        user_team = cursor.fetchone()

        # FIXED: Get only user's camp leaderboard (top 10 for user's specific camp)
        user_camp_leaderboard = []
        if user_camp:
            cursor.execute(
                """
                SELECT t.name, ts.score, u.username AS team_lead_name, t.camp,
                       CASE WHEN tm_user.user_id = %s THEN true ELSE false END as user_team
                FROM teams t
                JOIN team_scores ts ON t.id = ts.team_id
                JOIN users u ON t.team_lead_id = u.id
                LEFT JOIN team_members tm_user ON t.id = tm_user.team_id AND tm_user.user_id = %s
                WHERE t.camp = %s
                ORDER BY ts.score DESC
                LIMIT 10
            """,
                (user_id, user_id, user_camp)
            )
            user_camp_leaderboard = cursor.fetchall()

        # REMOVED: all_camps_leaderboard - only show user's camp
        all_camps_leaderboard = {}

        cursor.close()

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        completed_units = 0
        user_team = None
        all_camps_leaderboard = {}
        user_camp_leaderboard = []
        user_camp = None
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "dashboard.html",
        username=username,
        completed_units=completed_units,
        current_language=current_language,
        user_team=user_team,
        user_camp=user_camp,
        all_camps_leaderboard=all_camps_leaderboard,  
        user_camp_leaderboard=user_camp_leaderboard,
        show_only_user_camp=True 
    )



@app.route("/set_language/<language>")
def set_language(language: str) -> Any:
    """Change the user interface language and AI response language."""
    if language in LANGUAGES:
        session.pop("language", None)
        session["language"] = language

        if "user_id" in session:
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET language=%s WHERE id=%s",
                    (language, session["user_id"]),
                )
                conn.commit()
                logger.info(f"Language updated to {language} for user {session['user_id']}")
            except Exception as e:
                logger.error(f"Error updating language in database: {str(e)}")
            finally:
                if conn:
                    cursor.close()
                    release_db_connection(conn)

        session.modified = True
        flash(f"Language changed to {LANGUAGES[language]}. AI assistant and mindmap will now respond in {LANGUAGES[language]}.", "success")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/unit/<int:unit_id>", methods=["GET", "POST"])
@login_required
def unit(unit_id: int) -> Any:
    """UPDATED unit route with prerequisites removed"""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]

    # Get user's camp
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT camp FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        user_camp = result["camp"] if result else None

        if not user_camp:
            flash("Please contact admin to set your camp.", "error")
            return redirect(url_for("dashboard"))

        # REMOVED: Prerequisite check - all units are now open

        # Handle project submission
        if request.method == "POST" and request.form.get("submit_project"):
            try:
                project_file = request.files.get("project_file")
                project_notes = request.form.get("project_notes", "")

                filename = None
                if project_file and project_file.filename:
                    filename = secure_filename(project_file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    project_file.save(file_path)

                cursor.execute(
                    "INSERT INTO submissions (user_id, unit_id, file_path) VALUES (%s, %s, %s)",
                    (user_id, unit_id, filename or "No file uploaded"),
                )

                cursor.execute(
                    """
                    INSERT INTO progress (user_id, unit_number, project_completed, completed)
                    VALUES (%s, %s, 1, 1)
                    ON CONFLICT (user_id, unit_number) 
                    DO UPDATE SET project_completed = 1, completed = 1
                """,
                    (user_id, unit_id),
                )

                conn.commit()
                flash("Project submitted successfully!", "success")
                return redirect(url_for("unit", unit_id=unit_id))

            except Exception as e:
                conn.rollback()
                logger.error(f"Error submitting project: {str(e)}")
                flash("Error submitting project. Please try again.", "error")

        # Get content for the unit
        materials = get_content_with_tag_filtering("material", unit_id, user_id)
        videos = get_content_with_tag_filtering("video", unit_id, user_id)
        projects_list = get_content_with_tag_filtering("project", unit_id, user_id)
        words = get_content_with_tag_filtering("word", unit_id, user_id)
        quizzes = get_content_with_tag_filtering("quiz", unit_id, user_id)

        # Convert projects list to single project (backward compatibility)
        project = projects_list[0] if projects_list else None

        # Get user progress
        progress = get_progress(user_id, unit_id)
        project_completed = progress[2] if progress else 0
        quiz_attempted = has_attempted_quiz(user_id, unit_id)
        quiz_attempt_info = None
        if quiz_attempted:
            quiz_attempt_info = get_quiz_attempt_info(user_id, unit_id)
        quiz_id = quizzes[0]["id"] if quizzes else None

        cursor.close()

        return render_template(
            "unit.html",
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
            user_camp=user_camp,
        )

    except Exception as e:
        logger.error(f"Unit page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("dashboard"))
    finally:
        if conn:
            release_db_connection(conn)



@app.route("/quiz/<int:unit_id>", methods=["GET", "POST"])
@login_required
@camp_required
def quiz(unit_id: int) -> Any:
    """UPDATED quiz route with prerequisites removed"""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]
    user_camp = session.get("user_camp")

    # REMOVED: Prerequisite check - all quizzes are now accessible

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user has already attempted the quiz
        cursor.execute(
            """
            SELECT id, score, attempted_at, passed
            FROM quiz_attempts
            WHERE user_id = %s AND unit_id = %s AND score IS NOT NULL
            ORDER BY attempted_at DESC
            LIMIT 1
        """,
            (user_id, unit_id),
        )
        attempt = cursor.fetchone()

        # If user has already attempted, redirect to review
        if attempt and attempt[1] is not None:
            return redirect(url_for("quiz_review", unit_id=unit_id))

        # Rest of the quiz logic remains the same...
        # [Keep all the existing quiz logic here]
        
    except Exception as e:
        logger.error(f"Quiz page error: {str(e)}")
        flash(f"An error occurred loading the quiz: {str(e)}", "error")
        return redirect(url_for("unit", unit_id=unit_id))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route("/quiz_review/<int:unit_id>")
@login_required
@camp_required
def quiz_review(unit_id: int) -> Any:
    """FIXED quiz review route - shows user's quiz attempt with answers and explanations"""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]
    user_camp = session.get("user_camp")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get the user's most recent quiz attempt for this unit
        cursor.execute(
            """
            SELECT qa.id as attempt_id, qa.score, qa.attempted_at, qa.passed, qa.user_id
            FROM quiz_attempts qa
            WHERE qa.user_id = %s AND qa.unit_id = %s AND qa.score IS NOT NULL
            ORDER BY qa.attempted_at DESC
            LIMIT 1
        """,
            (user_id, unit_id),
        )

        attempt = cursor.fetchone()

        if not attempt:
            flash("No quiz attempt found for this unit.", "error")
            return redirect(url_for("unit", unit_id=unit_id))

        attempt_id = attempt["attempt_id"]

        # Get all quiz questions that were part of this attempt
        cursor.execute(
            """
            SELECT DISTINCT q.id, q.question, q.options, q.correct_answer, q.explanation,
                   qr.user_answer, qr.is_correct
            FROM quiz_responses qr
            JOIN quizzes q ON qr.question_id = q.id
            WHERE qr.attempt_id = %s
            ORDER BY q.id
        """,
            (attempt_id,),
        )

        quiz_data = cursor.fetchall()

        if not quiz_data:
            # Fallback: get quiz questions for this unit using our filtering
            available_quizzes = get_content_with_tag_filtering("quiz", unit_id, user_id)

            if not available_quizzes:
                flash("No quiz questions found for this unit.", "error")
                return redirect(url_for("unit", unit_id=unit_id))

            # If no quiz_responses found, create a basic structure
            quiz_data = []
            for quiz in available_quizzes:
                quiz_data.append(
                    {
                        "id": quiz["id"],
                        "question": quiz["question"],
                        "options": quiz["options"],
                        "correct_answer": quiz["correct_answer"],
                        "explanation": quiz.get(
                            "explanation", "No explanation available"
                        ),
                        "user_answer": None,  # User didn't answer this question
                        "is_correct": False,
                    }
                )

        # Process the quiz data to make it template-friendly
        processed_questions = []
        for q in quiz_data:
            options = safely_parse_options(q["options"])

            # Get user answer text and correct answer text
            user_answer_text = (
                "No answer"
                if q["user_answer"] is None
                else (
                    options[q["user_answer"]]
                    if q["user_answer"] < len(options)
                    else "Invalid answer"
                )
            )

            correct_answer_text = (
                options[q["correct_answer"]]
                if q["correct_answer"] < len(options)
                else "Invalid correct answer"
            )

            processed_questions.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "options": options,
                    "user_answer": q["user_answer"],
                    "user_answer_text": user_answer_text,
                    "correct_answer": q["correct_answer"],
                    "correct_answer_text": correct_answer_text,
                    "is_correct": q["is_correct"],
                    "explanation": q["explanation"] or "No explanation provided",
                }
            )

        cursor.close()

        return render_template(
            "quiz_review.html",
            username=username,
            unit_id=unit_id,
            attempt=attempt,
            questions=processed_questions,
            total_questions=len(processed_questions),
            user_camp=user_camp,
        )

    except Exception as e:
        logger.error(f"Quiz review error: {str(e)}")
        flash(f"An error occurred loading the quiz review: {str(e)}", "error")
        return redirect(url_for("unit", unit_id=unit_id))
    finally:
        if conn:
            release_db_connection(conn)


# Also add this debug route that was referenced in the code
@app.route("/debug/force_quiz_review/<int:unit_id>")
@login_required
def debug_force_quiz_review(unit_id: int):
    """Debug route to force quiz review - redirects to proper review route"""
    return redirect(url_for("quiz_review", unit_id=unit_id))


# Add this debug route to test quiz review functionality


@app.route("/debug/quiz_review_test/<int:unit_id>")
@login_required
def debug_quiz_review_test(unit_id: int):
    """Debug route to test quiz review functionality"""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    user_id = session["user_id"]
    username = session["username"]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if user has any quiz attempts
        cursor.execute(
            """
            SELECT qa.id, qa.score, qa.attempted_at, qa.passed, qa.unit_id
            FROM quiz_attempts qa
            WHERE qa.user_id = %s AND qa.unit_id = %s
            ORDER BY qa.attempted_at DESC
        """,
            (user_id, unit_id),
        )
        attempts = cursor.fetchall()

        # Get quiz questions for this unit
        cursor.execute(
            "SELECT id, question, camp FROM quizzes WHERE unit_id = %s",
            (unit_id,),
        )
        quiz_questions = cursor.fetchall()

        # Get user's camp
        cursor.execute("SELECT camp FROM users WHERE id = %s", (user_id,))
        user_camp = cursor.fetchone()["camp"] if cursor.fetchone() else "Unknown"

        cursor.close()

        # Generate HTML report
        html_output = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
            <h2>🧪 Quiz Review Debug Test</h2>
            <p><strong>User:</strong> {username} | <strong>Camp:</strong> {user_camp} | <strong>Unit:</strong> {unit_id}</p>
            
            <div style="margin: 20px 0;">
                <h3>Quiz Attempts:</h3>
                {f"<p style='color: green;'>✅ Found {len(attempts)} attempts</p>" if attempts else "<p style='color: orange;'>⚠️ No quiz attempts found</p>"}
                
                {f'''
                <div style="background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <h4>Latest Attempt:</h4>
                    <ul>
                        <li>Attempt ID: {attempts[0]["id"]}</li>
                        <li>Score: {attempts[0]["score"]}</li>
                        <li>Passed: {"Yes" if attempts[0]["passed"] else "No"}</li>
                        <li>Date: {attempts[0]["attempted_at"]}</li>
                    </ul>
                </div>
                ''' if attempts else ""}
            </div>
            
            <div style="margin: 20px 0;">
                <h3>Available Quiz Questions:</h3>
                {f"<p style='color: green;'>✅ Found {len(quiz_questions)} questions</p>" if quiz_questions else "<p style='color: red;'>❌ No quiz questions found</p>"}
                
                {f'''
                <div style="background: #f3e5f5; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <h4>Questions for Unit {unit_id}:</h4>
                    <ul>
                        {"".join(f"<li>ID: {q['id']} | Camp: {q['camp']} | Question: {q['question'][:50]}...</li>" for q in quiz_questions)}
                    </ul>
                </div>
                ''' if quiz_questions else ""}
            </div>
            
            <div style="margin: 20px 0;">
                <h3>Test Actions:</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    {f'''
                    <a href="/quiz_review/{unit_id}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        📋 View Quiz Review
                    </a>
                    ''' if attempts else ""}
                    
                    <a href="/quiz/{unit_id}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        🎯 Take Quiz
                    </a>
                    
                    <a href="/unit/{unit_id}" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        📚 Back to Unit
                    </a>
                </div>
            </div>
            
            <div style="margin: 20px 0; background: #fff3cd; padding: 15px; border-radius: 5px;">
                <h4>🔧 Debug Info:</h4>
                <ul>
                    <li>Quiz Review Route: <code>/quiz_review/{unit_id}</code></li>
                    <li>Quiz Take Route: <code>/quiz/{unit_id}</code></li>
                    <li>User ID: {user_id}</li>
                    <li>Has Attempts: {"Yes" if attempts else "No"}</li>
                    <li>Can Take Quiz: {"No" if attempts else "Yes"}</li>
                </ul>
            </div>
        </div>
        """

        return html_output

    except Exception as e:
        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background: #f8d7da;">
            <h2>❌ Debug Test Error</h2>
            <p><strong>Error:</strong> {str(e)}</p>
            <a href="/unit/{unit_id}" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Back to Unit</a>
        </div>
        """
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/fix_all_user_tags")
@admin_required
def admin_fix_all_user_tags():
    """Fix tags for all users based on their camp"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all users with camps but no tags
    cursor.execute(
        """
        SELECT u.id, u.username, u.camp 
        FROM users u 
        WHERE u.camp IS NOT NULL 
        AND NOT EXISTS (SELECT 1 FROM user_tags WHERE user_id = u.id)
    """
    )
    users = cursor.fetchall()

    fixed_count = 0
    for user_id, username, camp in users:
        # Find camp tag
        cursor.execute("SELECT id FROM tags WHERE name = %s", (camp,))
        camp_tag = cursor.fetchone()

        if camp_tag:
            cursor.execute(
                "INSERT INTO user_tags (user_id, tag_id, assigned_by) VALUES (%s, %s, 'admin_bulk_fix')",
                (user_id, camp_tag[0]),
            )
            fixed_count += 1

    conn.commit()
    cursor.close()
    release_db_connection(conn)

    flash(f"Fixed tags for {fixed_count} users", "success")
    return redirect(url_for("admin_users"))


# Also add this admin route to fix the tag system completely
@app.route("/admin/emergency_fix_all_tags")
@admin_required
def admin_emergency_fix_all_tags():
    """Emergency fix: Clean ALL user tags and reassign properly"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all users
        cursor.execute(
            "SELECT id, username, camp, student_type, cohort_name FROM users"
        )
        all_users = cursor.fetchall()

        fixed_users = []
        errors = []

        for user_id, username, camp, student_type, cohort_name in all_users:
            try:
                # Clear all tags for this user
                cursor.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))

                user_tags = []

                # Assign camp tag
                if camp and camp in ["Chinese", "English", "Middle East"]:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND id IN (SELECT id FROM tags t JOIN tag_groups tg ON t.tag_group_id = tg.id WHERE tg.name = 'Bootcamp Type')",
                        (camp,),
                    )
                    camp_tag = cursor.fetchone()
                    if camp_tag:
                        cursor.execute(
                            "INSERT INTO user_tags (user_id, tag_id, assigned_by) VALUES (%s, %s, 'admin_emergency_fix')",
                            (user_id, camp_tag[0]),
                        )
                        user_tags.append(camp)

                # Assign student type tag
                if student_type:
                    tag_name = (
                        "New Student"
                        if student_type == "new"
                        else (
                            "Existing Student"
                            if student_type == "existing"
                            else student_type
                        )
                    )
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND id IN (SELECT id FROM tags t JOIN tag_groups tg ON t.tag_group_id = tg.id WHERE tg.name = 'Student Type')",
                        (tag_name,),
                    )
                    student_tag = cursor.fetchone()
                    if student_tag:
                        cursor.execute(
                            "INSERT INTO user_tags (user_id, tag_id, assigned_by) VALUES (%s, %s, 'admin_emergency_fix')",
                            (user_id, student_tag[0]),
                        )
                        user_tags.append(tag_name)

                # Assign cohort tag
                if cohort_name:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND id IN (SELECT id FROM tags t JOIN tag_groups tg ON t.tag_group_id = tg.id WHERE tg.name = 'Cohort')",
                        (cohort_name,),
                    )
                    cohort_tag = cursor.fetchone()
                    if cohort_tag:
                        cursor.execute(
                            "INSERT INTO user_tags (user_id, tag_id, assigned_by) VALUES (%s, %s, 'admin_emergency_fix')",
                            (user_id, cohort_tag[0]),
                        )
                        user_tags.append(cohort_name)

                fixed_users.append(f"✅ {username} ({camp}): {', '.join(user_tags)}")

            except Exception as user_error:
                errors.append(f"❌ {username}: {str(user_error)}")

        conn.commit()
        cursor.close()

        result_html = f"""
        <div style="font-family: monospace; padding: 20px; background: #f8f9fa;">
            <h2>🚨 Emergency Tag Fix Results</h2>
            
            <div style="background: #d4edda; padding: 15px; border: 1px solid #c3e6cb; border-radius: 5px; margin: 10px 0;">
                <h3>✅ Fixed Users ({len(fixed_users)}):</h3>
                <ul style="max-height: 300px; overflow-y: auto;">
                    {"".join(f"<li>{user}</li>" for user in fixed_users)}
                </ul>
            </div>
            
            {f'''
            <div style="background: #f8d7da; padding: 15px; border: 1px solid #f5c6cb; border-radius: 5px; margin: 10px 0;">
                <h3>❌ Errors ({len(errors)}):</h3>
                <ul>
                    {"".join(f"<li>{error}</li>" for error in errors)}
                </ul>
            </div>
            ''' if errors else ""}
            
            <br>
            <a href="/admin/users" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">👥 View Users</a>
        </div>
        """

        flash(
            f"Emergency fix completed: {len(fixed_users)} users fixed, {len(errors)} errors",
            "success" if not errors else "warning",
        )
        return result_html

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Emergency fix error: {str(e)}")
        flash(f"Emergency fix failed: {str(e)}", "error")
        return redirect(url_for("admin_users"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback() -> Any:
    """Handle user feedback submission."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]

    if request.method == "POST":
        feedback_text = request.form.get("feedback")
        rating = request.form.get("rating")

        if feedback_text:
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO feedback (user_id, feedback_text, rating)
                    VALUES (%s, %s, %s)
                """,
                    (user_id, feedback_text, rating),
                )
                conn.commit()
                cursor.close()
                flash("Thank you for your feedback!", "success")
                return redirect(url_for("dashboard"))
            except Exception as e:
                logger.error(f"Feedback submission error: {str(e)}")
                flash(f"Error submitting feedback: {str(e)}", "danger")
            finally:
                if conn:
                    release_db_connection(conn)

    return render_template("feedback.html", username=username)


@app.route("/download_file/<filename>")
@login_required
def download_file_from_db(filename):
    """Download file from database instead of file system."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get file from database
        cursor.execute(
            "SELECT content, content_type FROM stored_documents WHERE filename = %s",
            (filename,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        
        if not result:
            # File not in database, try file system as fallback
            try:
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True, download_name=filename)
            except:
                pass
            
            flash(f"File '{filename}' not found.", "error")
            return redirect(request.referrer or url_for("dashboard"))
        
        content, content_type = result
        
        # Create a BytesIO object from the database content
        file_data = io.BytesIO(content)
        file_data.seek(0)
        
        return send_file(
            file_data,
            mimetype=content_type or "application/octet-stream",
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error downloading file from database: {str(e)}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(request.referrer or url_for("dashboard"))
    finally:
        if conn:
            release_db_connection(conn)



@app.route("/static/uploads/<path:filename>")
def serve_static_upload(filename):
    """Serve uploaded files from database with smart filename matching."""
    
    # Extract just the filename (remove any path prefix)
    clean_filename = os.path.basename(filename)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Strategy 1: Try exact match
        cursor.execute(
            "SELECT content, content_type FROM stored_documents WHERE filename = %s",
            (clean_filename,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Strategy 2: Try case-insensitive match
            cursor.execute(
                "SELECT content, content_type FROM stored_documents WHERE LOWER(filename) = LOWER(%s)",
                (clean_filename,)
            )
            result = cursor.fetchone()
        
        if not result:
            # Strategy 3: Try partial match (remove timestamp prefixes)
            # Handle filenames like "unit_1_Chinese_20250714_141026_E-51Talk-AI-Unit-one.pdf"
            # Look for files that end with the same base name
            base_name = clean_filename.split('_')[-1] if '_' in clean_filename else clean_filename
            cursor.execute(
                "SELECT content, content_type FROM stored_documents WHERE filename LIKE %s",
                (f"%{base_name}",)
            )
            result = cursor.fetchone()
        
        if not result:
            # Strategy 4: Try matching the original file name pattern
            # Look for files that contain key parts of the requested filename
            name_parts = clean_filename.replace('.pdf', '').replace('.ppt', '').replace('.pptx', '').split('_')
            for part in name_parts:
                if len(part) > 3:  # Only use meaningful parts
                    cursor.execute(
                        "SELECT content, content_type FROM stored_documents WHERE filename LIKE %s",
                        (f"%{part}%",)
                    )
                    result = cursor.fetchone()
                    if result:
                        break
        
        cursor.close()
        
        if result:
            content, content_type = result
            
            # Determine the correct content type if not set
            if not content_type:
                if clean_filename.lower().endswith('.pdf'):
                    content_type = 'application/pdf'
                elif clean_filename.lower().endswith(('.ppt', '.pptx')):
                    content_type = 'application/vnd.ms-powerpoint'
                else:
                    content_type = 'application/octet-stream'
            
            # Create response
            response = app.response_class(
                content,
                mimetype=content_type,
                headers={
                    "Content-Disposition": f"inline; filename={clean_filename}",
                    "Cache-Control": "public, max-age=3600"
                }
            )
            return response
        
    except Exception as e:
        logger.error(f"Database error serving {filename}: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)
    
    # Fallback to file system
    try:
        file_path = os.path.join(UPLOAD_FOLDER, clean_filename)
        if os.path.exists(file_path):
            return send_file(file_path)
    except Exception as e:
        logger.error(f"File system error: {str(e)}")
    
    # Return 404
    return "File not found", 404


# Also add this debug route to see what's in your database
@app.route("/debug/files")
@admin_required
def debug_files():
    """Debug route to see what files are in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT filename, content_type, upload_date, length(content) as size FROM stored_documents ORDER BY upload_date DESC")
        files = cursor.fetchall()
        cursor.close()
        
        html = "<h2>Files in Database:</h2><ul>"
        for filename, content_type, upload_date, size in files:
            html += f"<li><strong>{filename}</strong> ({content_type}) - {size} bytes - {upload_date}</li>"
        html += "</ul>"
        
        return html
        
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/download_material/<path:filename>")
def download_material(filename: str) -> Any:
    """Handle material file download with database support."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    if "user_id" not in session:
        return redirect(url_for("login"))

    # Extract just the filename (remove any path prefix)
    clean_filename = os.path.basename(filename)
    
    # Try database first
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT content, content_type FROM stored_documents WHERE filename = %s",
            (clean_filename,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            content, content_type = result
            file_data = io.BytesIO(content)
            file_data.seek(0)
            
            return send_file(
                file_data,
                mimetype=content_type or "application/octet-stream",
                as_attachment=True,
                download_name=clean_filename
            )
    except Exception as e:
        logger.error(f"Database download error: {str(e)}")
    finally:
        if conn:
            release_db_connection(conn)
    
    # Fallback to file system
    try:
        file_path = os.path.join(UPLOAD_FOLDER, clean_filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=clean_filename)
    except Exception as e:
        logger.error(f"File system download error: {str(e)}")

    # File not found anywhere
    flash(f"File '{clean_filename}' not found.", "error")
    return redirect(request.referrer or url_for("dashboard"))

# ==============================================
# AI ASSISTANT ROUTES
# ==============================================


@app.route("/ai_assistant", methods=["GET", "POST"])
@login_required
def ai_assistant() -> Any:
    """FIXED: AI assistant with better error handling."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = str(session["user_id"])

    question = request.args.get("question") or (
        request.form.get("question") if request.method == "POST" else None
    )

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
        cursor.execute(
            """
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """,
            (session["user_id"],),
        )
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
            flash("Message too long. Please keep it under 2000 characters.", "error")
            return redirect(url_for("ai_assistant"))

        current_question = question
        is_processing = True

        try:
            # Get QA system
            qa_system = get_qa_system()

            if qa_system is None:
                logger.warning("QA system is None, checking system status...")
                from qa import get_system_status

                status = get_system_status()
                logger.info(f"QA System Status: {status}")

                if status.get("initializing"):
                    current_answer = "⏳ I'm still loading course materials from the database. Please wait a moment and try again!"
                    current_sources = []
                    conversation_type = "system_loading"
                elif status.get("error"):
                    current_answer = f"❌ I encountered an error during setup: {status.get('error')}. Please try again."
                    current_sources = []
                    conversation_type = "system_error"
                elif status.get("document_count", 0) == 0:
                    current_answer = "📄 I don't have any course materials uploaded yet. Please upload documents through the admin panel (/admin/upload_document) so I can help you with course-specific questions!"
                    current_sources = []
                    conversation_type = "no_documents"
                else:
                    current_answer = "🔄 I'm starting up and loading course materials. Please wait a moment and try again!"
                    current_sources = []
                    conversation_type = "system_loading"
            else:
                logger.info(f"QA system found, processing question: {question[:50]}...")

                try:
                    qa_response = qa_system.answer_question(question, user_id=user_id)

                    current_answer = qa_response.get(
                        "answer",
                        "I'm having trouble responding right now. Could you try again?",
                    )
                    current_sources = qa_response.get("sources", [])
                    conversation_type = qa_response.get("conversation_type", "general")

                    logger.info(
                        f"QA response generated successfully: {conversation_type}"
                    )

                    # Add personality indicators
                    if conversation_type == "greeting":
                        current_answer += "\n\n💡 *Tip: You can ask me about course materials, request explanations, or just chat about what you're learning!*"
                    elif conversation_type == "general":
                        current_answer += "\n\n📚 *Feel free to ask me anything else about your studies or course materials!*"
                    elif conversation_type == "document_based":
                        current_answer += (
                            "\n\n📖 *This answer is based on your course materials.*"
                        )
                    elif conversation_type == "no_documents":
                        current_answer += "\n\n📁 *Once you upload course materials, I'll be able to provide more specific help!*"

                except Exception as qa_error:
                    logger.error(f"Error during QA processing: {str(qa_error)}")
                    current_answer = "I encountered an error while processing your question. Could you try rephrasing it?"
                    current_sources = []
                    conversation_type = "error"

            # Save to database
            try:
                save_qa_history_sync(session["user_id"], question, current_answer)
            except Exception as db_error:
                logger.error(f"Error saving QA history: {str(db_error)}")

            is_processing = False

        except Exception as e:
            logger.error(f"AI Assistant error: {str(e)}")
            import traceback

            traceback.print_exc()
            current_answer = "I encountered an error, but I'm still here to help! Could you try rephrasing your question?"
            current_sources = []
            conversation_type = "error"
            is_processing = False

    return render_template(
        "ai_assistant.html",
        username=username,
        current_question=current_question,
        current_answer=current_answer,
        current_sources=current_sources,
        conversation_type=conversation_type,
        is_processing=is_processing,
        history=history,
    )


@app.route("/ask_ai_enhanced", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def ask_ai_enhanced() -> Any:
    """AI assistant with language support."""
    start_time = time.time()
    success = False
    user_id = str(session.get("user_id", "unknown"))

    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        question = data.get("question", "").strip()
        user_language = session.get("language", "en")

        if not question:
            success = True
            greeting_msg = {
                "en": "Hello! I'm your AI learning assistant. How can I help you today?",
                "zh": "你好！我是你的AI学习助手。今天我可以如何帮助你？",
                "ar": "مرحبا! أنا مساعد التعلم بالذكاء الاصطناعي. كيف يمكنني مساعدتك اليوم؟"
            }
            return jsonify({
                "success": True,
                "answer": greeting_msg.get(user_language, greeting_msg["en"]),
                "sources": [],
                "conversation_type": "greeting",
            })

        if len(question) > 2000:
            error_msg = {
                "en": "Message too long. Please keep it under 2000 characters.",
                "zh": "消息太长。请保持在2000个字符以下。",
                "ar": "الرسالة طويلة جداً. يرجى إبقاؤها تحت 2000 حرف."
            }
            return jsonify({"error": error_msg.get(user_language, error_msg["en"])}), 400

        qa_system = get_qa_system()

        if qa_system is None:
            from qa import get_system_status
            status = get_system_status()

            if status.get("document_count", 0) == 0:
                no_docs_msg = {
                    "en": "📄 I don't have any course materials uploaded yet. Please upload documents through the admin panel so I can help you with course-specific questions!",
                    "zh": "📄 我还没有上传任何课程材料。请通过管理员面板上传文档，这样我就可以帮助您解答课程相关问题！",
                    "ar": "📄 لم يتم رفع أي مواد دراسية بعد. يرجى رفع المستندات من خلال لوحة الإدارة حتى أتمكن من مساعدتك في الأسئلة المتعلقة بالدورة!"
                }
                return jsonify({
                    "success": True,
                    "answer": no_docs_msg.get(user_language, no_docs_msg["en"]),
                    "sources": [],
                    "conversation_type": "no_documents",
                }), 200
            else:
                loading_msg = {
                    "en": "⏳ I'm currently starting up and loading course materials. Please wait a moment and try again!",
                    "zh": "⏳ 我正在启动并加载课程材料。请稍等片刻再试！",
                    "ar": "⏳ أقوم حالياً ببدء التشغيل وتحميل المواد الدراسية. يرجى الانتظار قليلاً والمحاولة مرة أخرى!"
                }
                return jsonify({
                    "success": False,
                    "answer": loading_msg.get(user_language, loading_msg["en"]),
                    "sources": [],
                    "conversation_type": "system_loading",
                }), 503

        try:
            # Add language context to the question
            language_prefixes = {
                "en": "",  # No prefix for English
                "zh": "请用中文回答：",
                "ar": "يرجى الإجابة باللغة العربية: "
            }
            
            prefix = language_prefixes.get(user_language, "")
            enhanced_question = f"{prefix}{question}" if prefix else question
            
            qa_response = qa_system.answer_question(enhanced_question, user_id=user_id)

            answer = qa_response.get("answer", "I'm having trouble responding right now. Could you try again?")
            sources = qa_response.get("sources", [])
            conversation_type = qa_response.get("conversation_type", "general")

            # Add language-specific personality additions
            personality_additions = {
                "en": {
                    "greeting": "\n\n💡 *Tip: You can ask me about course materials, explanations, or just chat about learning!*",
                    "general": "\n\n📚 *Feel free to ask me anything else about your studies!*",
                    "document_based": "\n\n📖 *This answer is based on your course materials.*",
                    "no_documents": "\n\n📁 *Once you upload course materials, I'll be able to provide more specific help!*",
                },
                "zh": {
                    "greeting": "\n\n💡 *提示：您可以询问课程材料、解释或只是聊聊学习！*",
                    "general": "\n\n📚 *请随时询问其他关于学习的问题！*",
                    "document_based": "\n\n📖 *此答案基于您的课程材料。*",
                    "no_documents": "\n\n📁 *上传课程材料后，我将能够提供更具体的帮助！*",
                },
                "ar": {
                    "greeting": "\n\n💡 *نصيحة: يمكنك أن تسألني عن المواد الدراسية أو التفسيرات أو مجرد الدردشة حول التعلم!*",
                    "general": "\n\n📚 *لا تتردد في سؤالي أي شيء آخر عن دراستك!*",
                    "document_based": "\n\n📖 *هذه الإجابة مبنية على موادك الدراسية.*",
                    "no_documents": "\n\n📁 *بمجرد رفع المواد الدراسية، سأتمكن من تقديم مساعدة أكثر تحديداً!*",
                }
            }

            lang_additions = personality_additions.get(user_language, personality_additions["en"])
            if conversation_type in lang_additions:
                answer += lang_additions[conversation_type]

            if not answer.strip():
                fallback_msg = {
                    "en": "I'm here to help! Could you tell me more about what you'd like to know?",
                    "zh": "我在这里帮助您！您能告诉我更多关于您想了解什么吗？",
                    "ar": "أنا هنا للمساعدة! هل يمكنك إخباري المزيد عما تريد معرفته؟"
                }
                answer = fallback_msg.get(user_language, fallback_msg["en"])

        except Exception as qa_error:
            logger.error(f"QA system error: {str(qa_error)}")
            error_response = {
                "en": "I encountered an error while processing your question. I'm still here to help though - could you try rephrasing?",
                "zh": "处理您的问题时遇到错误。不过我仍然在这里帮助您 - 您能试着重新表述吗？",
                "ar": "واجهت خطأ أثناء معالجة سؤالك. ولكنني ما زلت هنا للمساعدة - هل يمكنك المحاولة بإعادة صياغة السؤال؟"
            }
            answer = error_response.get(user_language, error_response["en"])
            sources = []
            conversation_type = "error"

        # Save QA history
        try:
            save_qa_history_sync(int(user_id), question, answer)
        except Exception as db_error:
            logger.error(f"Error saving QA history in API: {str(db_error)}")

        success = True
        response = {
            "success": True,
            "answer": answer,
            "sources": sources,
            "conversation_type": conversation_type,
            "question": question,
            "language": user_language,
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Ask AI API error: {str(e)}")
        error_msg = {
            "en": "An unexpected error occurred while processing your message.",
            "zh": "处理您的消息时发生意外错误。",
            "ar": "حدث خطأ غير متوقع أثناء معالجة رسالتك."
        }
        fallback_answer = {
            "en": "I encountered an error, but I'm still here to help! Could you try again?",
            "zh": "我遇到了错误，但我仍然在这里帮助您！您能再试一次吗？",
            "ar": "واجهت خطأ، لكنني ما زلت هنا للمساعدة! هل يمكنك المحاولة مرة أخرى؟"
        }
        user_language = session.get("language", "en")
        return jsonify({
            "success": False,
            "error": error_msg.get(user_language, error_msg["en"]),
            "answer": fallback_answer.get(user_language, fallback_answer["en"]),
            "sources": [],
            "conversation_type": "error",
        }), 500

    finally:
        response_time = time.time() - start_time
        track_qa_request(user_id, response_time, success)


@app.route("/ask_ai", methods=["POST"])
@limiter.limit("20 per minute")
@login_required
def ask_ai() -> Any:
    """Legacy API endpoint - redirects to simplified system."""
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "No question provided"}), 400

        if len(question) > 1000:
            return (
                jsonify(
                    {
                        "error": "Question too long. Please keep it under 1000 characters."
                    }
                ),
                400,
            )

        qa_system = get_qa_system()

        if qa_system is None:
            return (
                jsonify(
                    {
                        "error": "AI assistant not available. Please contact your administrator.",
                        "answer": "I apologize, but I'm currently unavailable. The system may still be loading course materials.",
                        "sources": [],
                    }
                ),
                503,
            )

        try:
            qa_response = qa_system.answer_question(
                question, user_id=str(session["user_id"])
            )
            answer = qa_response.get("answer", "I couldn't generate a response.")
            sources = qa_response.get("sources", [])

            if not answer or answer.strip() == "":
                answer = "I couldn't find relevant information to answer your question. Please try rephrasing it or asking about a different topic."

            logger.info(
                f"AI Question answered successfully for user {session.get('username', 'unknown')}"
            )

        except Exception as qa_error:
            logger.error(f"QA system error: {str(qa_error)}")
            answer = "I encountered an error while processing your question. Please try again with a simpler question."
            sources = []

        # Save history using the function
        try:
            user_id = session["user_id"]
            save_qa_history_sync(user_id, question, answer)
        except Exception as db_error:
            logger.error(f"Error saving QA history: {str(db_error)}")

        return jsonify(
            {
                "success": True,
                "answer": answer,
                "sources": sources,
                "question": question,
            }
        )

    except Exception as e:
        logger.error(f"Ask AI API error: {str(e)}")
        return (
            jsonify(
                {
                    "error": "An unexpected error occurred while processing your question.",
                    "answer": "I encountered an error while processing your question. Please try again.",
                    "sources": [],
                }
            ),
            500,
        )


@app.route("/user_qa_history")
@login_required
def user_qa_history() -> Any:
    """Enhanced user endpoint to get their own Q&A history as JSON."""
    if not session.get("authenticated"):
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    user_id = session["user_id"]
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    per_page = min(per_page, 50)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT COUNT(*) as total
            FROM qa_history
            WHERE user_id = %s
        """,
            (user_id,),
        )
        total = cursor.fetchone()["total"]

        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            (user_id, per_page, offset),
        )
        history = cursor.fetchall()
        cursor.close()

        history_list = []
        for item in history:
            answer = item["answer"]
            if len(answer) > 200:
                answer = answer[:200] + "..."

            history_list.append(
                {
                    "question": item["question"],
                    "answer": answer,
                    "full_answer": item["answer"],
                    "created_at": (
                        item["created_at"].isoformat() if item["created_at"] else None
                    ),
                }
            )

        return jsonify(
            {
                "success": True,
                "history": history_list,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
            }
        )

    except Exception as e:
        logger.error(f"User QA History error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/qa_history")
@login_required
def qa_history_page() -> Any:
    """Display user's Q&A history in a dedicated page."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    username = session["username"]
    user_id = session["user_id"]

    page = request.args.get("page", 1, type=int)
    per_page = 10

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT COUNT(*) as total
            FROM qa_history
            WHERE user_id = %s
        """,
            (user_id,),
        )
        total = cursor.fetchone()["total"]

        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT question, answer, created_at
            FROM qa_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            (user_id, per_page, offset),
        )
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

    return render_template(
        "qa_history.html",
        username=username,
        history=history,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
        },
    )


@app.route("/clear_history")
@login_required
def clear_history() -> Any:
    """Clear user's Q&A history."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))

    user_id = session["user_id"]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM qa_history WHERE user_id = %s", (user_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()

        if deleted_count > 0:
            flash(f"Cleared {deleted_count} items from history", "success")
        else:
            flash("No history items to clear", "info")

    except Exception as e:
        logger.error(f"Clear history error: {str(e)}")
        flash("Error clearing history", "error")
    finally:
        if conn:
            release_db_connection(conn)

    return redirect(url_for("ai_assistant"))


@app.route("/ai_status")
@login_required
def ai_status() -> Any:
    """FIXED: Get the current status of the AI system."""
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    try:
        # Get detailed status
        from qa import get_system_status

        status = get_system_status()

        # Get QA system instance
        qa_system = get_qa_system()

        # Enhanced status information
        detailed_status = {
            "ready": status.get("ready", False),
            "initializing": status.get("initializing", False),
            "error": status.get("error"),
            "document_count": status.get("document_count", 0),
            "llm_provider": status.get("llm_provider", "Unknown"),
            "qa_system_instance": qa_system is not None,
            "gpt_available": status.get("gpt_available", False),
            "chunks_loaded": status.get("chunks_loaded", 0),
        }

        # Test QA system if available
        if qa_system:
            try:
                test_response = qa_system.answer_question(
                    "Hello", user_id=session.get("user_id", "test")
                )
                detailed_status["qa_system_test"] = "success"
                detailed_status["test_response_type"] = test_response.get(
                    "conversation_type", "unknown"
                )
            except Exception as test_error:
                detailed_status["qa_system_test"] = f"failed: {str(test_error)}"

        if not detailed_status["ready"]:
            if detailed_status["initializing"]:
                return jsonify(
                    {
                        "status": "initializing",
                        "message": "Loading course materials...",
                        "details": detailed_status,
                    }
                )
            elif detailed_status["error"]:
                return jsonify(
                    {
                        "status": "error",
                        "message": f'Initialization error: {detailed_status["error"]}',
                        "details": detailed_status,
                    }
                )
            elif detailed_status["document_count"] == 0:
                return jsonify(
                    {
                        "status": "no_documents",
                        "message": "No course materials uploaded. Please upload documents through the admin panel.",
                        "details": detailed_status,
                    }
                )
            else:
                return jsonify(
                    {
                        "status": "not_ready",
                        "message": "AI assistant not ready",
                        "details": detailed_status,
                    }
                )

        return jsonify(
            {
                "status": "ready",
                "message": f'AI assistant ready ({detailed_status["document_count"]} documents loaded)',
                "details": detailed_status,
            }
        )

    except Exception as e:
        logger.error(f"AI status check error: {str(e)}")
        return jsonify(
            {"status": "error", "message": "Error checking AI status", "error": str(e)}
        )


def save_qa_history_sync(user_id: int, question: str, answer: str) -> bool:
    """Save QA history synchronously with proper error handling."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO qa_history (user_id, question, answer)
            VALUES (%s, %s, %s)
        """,
            (user_id, question, answer),
        )
        conn.commit()
        cursor.close()
        logger.debug(f"QA history saved successfully for user {user_id}")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error saving QA history sync: {str(e)}")
        return False
    finally:
        if conn:
            release_db_connection(conn)


def save_qa_history_async_fixed(user_id: int, question: str, answer: str):
    """Save QA history asynchronously with better connection handling."""

    def save_in_background():
        # Create a new connection for this thread
        conn = None
        try:
            # Get a fresh connection for this thread
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "fiftyone_learning"),
                user=os.getenv("DB_USER", "admin"),
                password=os.getenv("DB_PASSWORD", "admin123"),
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO qa_history (user_id, question, answer)
                VALUES (%s, %s, %s)
            """,
                (user_id, question, answer),
            )
            conn.commit()
            cursor.close()
            logger.debug(f"QA history saved successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving QA history async: {str(e)}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    # Start background thread with better error handling
    try:
        thread = threading.Thread(target=save_in_background, daemon=False)
        thread.start()
    except Exception as e:
        logger.error(f"Error starting QA history save thread: {str(e)}")
        # Fallback to synchronous save
        save_qa_history_sync(user_id, question, answer)


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
    if request.path.startswith("/ask_ai"):
        return (
            jsonify(
                {
                    "error": "Internal server error occurred",
                    "answer": "I encountered an internal error. Please try again.",
                    "sources": [],
                }
            ),
            500,
        )
    return render_template("error.html", error="Internal server error"), 500


@app.errorhandler(504)
def timeout_error(error):
    """Handle timeout errors."""
    logger.error(f"Request timeout: {str(error)}")
    if request.path.startswith("/ask_ai"):
        return (
            jsonify(
                {
                    "error": "Request timed out",
                    "answer": "The request took too long to process. Please try a simpler question.",
                    "sources": [],
                }
            ),
            504,
        )
    return render_template("error.html", error="Request timeout"), 504


# ==============================================
# ADMIN TAG MANAGEMENT ROUTES
# ==============================================


@app.route("/admin/tags")
@admin_required
def admin_tags():
    """Display tag management interface."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get tag groups with counts
        cursor.execute(
            """
            SELECT tg.id, tg.name, tg.description, 
                   COUNT(t.id) as tag_count
            FROM tag_groups tg
            LEFT JOIN tags t ON tg.id = t.tag_group_id AND t.is_active = TRUE
            WHERE tg.is_active = TRUE
            GROUP BY tg.id, tg.name, tg.description
            ORDER BY tg.name
        """
        )
        tag_groups = cursor.fetchall()

        # Get all tags with usage counts
        cursor.execute(
            """
            SELECT t.id, t.name, t.description, tg.name as group_name,
                   COUNT(DISTINCT ut.user_id) as user_count,
                   COUNT(DISTINCT ct.id) as content_count
            FROM tags t
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            LEFT JOIN user_tags ut ON t.id = ut.tag_id
            LEFT JOIN content_tags ct ON t.id = ct.tag_id
            WHERE t.is_active = TRUE
            GROUP BY t.id, t.name, t.description, tg.name
            ORDER BY tg.name, t.name
        """
        )
        tags = cursor.fetchall()

        cursor.close()
        return render_template("admin/tags.html", tag_groups=tag_groups, tags=tags)

    except Exception as e:
        logger.error(f"Error loading tags: {str(e)}")
        flash(f"Error loading tags: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/add_tag_group", methods=["GET", "POST"])
@admin_required
def admin_add_tag_group():
    """Add a new tag group."""
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description", "")

        if not name:
            flash("Tag group name is required.", "error")
            return render_template("admin/add_tag_group.html")

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if tag group already exists
            cursor.execute("SELECT id FROM tag_groups WHERE name = %s", (name,))
            existing = cursor.fetchone()

            if existing:
                flash("Tag group with this name already exists.", "error")
                return render_template("admin/add_tag_group.html")

            cursor.execute(
                "INSERT INTO tag_groups (name, description) VALUES (%s, %s)",
                (name, description),
            )
            conn.commit()
            cursor.close()

            flash("Tag group created successfully!", "success")
            return redirect(url_for("admin_tags"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error creating tag group: {str(e)}")
            flash(f"Error creating tag group: {str(e)}", "error")
        finally:
            if conn:
                release_db_connection(conn)

    return render_template("admin/add_tag_group.html")


@app.route("/admin/add_tag", methods=["GET", "POST"])
@admin_required
def admin_add_tag():
    """Add a new tag."""
    if request.method == "POST":
        tag_group_id = request.form.get("tag_group_id")
        name = request.form.get("name")
        description = request.form.get("description", "")

        if not all([tag_group_id, name]):
            flash("Tag group and name are required.", "error")
            return redirect(url_for("admin_add_tag"))

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if tag already exists in this group
            cursor.execute(
                "SELECT id FROM tags WHERE tag_group_id = %s AND name = %s",
                (tag_group_id, name),
            )
            existing = cursor.fetchone()

            if existing:
                flash("Tag with this name already exists in this group.", "error")
                return redirect(url_for("admin_add_tag"))

            cursor.execute(
                "INSERT INTO tags (tag_group_id, name, description) VALUES (%s, %s, %s)",
                (tag_group_id, name, description),
            )
            conn.commit()
            cursor.close()

            flash("Tag created successfully!", "success")
            return redirect(url_for("admin_tags"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error creating tag: {str(e)}")
            flash(f"Error creating tag: {str(e)}", "error")
        finally:
            if conn:
                release_db_connection(conn)

    # Get tag groups for dropdown
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, name FROM tag_groups WHERE is_active = TRUE ORDER BY name"
        )
        tag_groups = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Error loading tag groups: {str(e)}")
        tag_groups = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/add_tag.html", tag_groups=tag_groups)


@app.route("/admin/user_tags/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_user_tags(user_id):
    """Manage tags for a specific user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get user info
        cursor.execute(
            "SELECT id, username, email, camp FROM users WHERE id = %s", (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))

        if request.method == "POST":
            selected_tags = request.form.getlist("tags")

            # Remove existing tags
            cursor.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))

            # Add new tags
            for tag_id in selected_tags:
                cursor.execute(
                    "INSERT INTO user_tags (user_id, tag_id, assigned_by) VALUES (%s, %s, %s)",
                    (user_id, tag_id, "admin"),
                )

            conn.commit()
            flash("User tags updated successfully!", "success")

        # Get all tags with assignment status
        cursor.execute(
            """
            SELECT t.id, t.name, tg.name as group_name, 
                   CASE WHEN ut.tag_id IS NOT NULL THEN TRUE ELSE FALSE END as assigned
            FROM tags t
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            LEFT JOIN user_tags ut ON t.id = ut.tag_id AND ut.user_id = %s
            WHERE t.is_active = TRUE AND tg.is_active = TRUE
            ORDER BY tg.name, t.name
        """,
            (user_id,),
        )
        tags = cursor.fetchall()

        cursor.close()
        return render_template("admin/user_tags.html", user=user, tags=tags)

    except Exception as e:
        logger.error(f"Error managing user tags: {str(e)}")
        flash(f"Error managing user tags: {str(e)}", "error")
        return redirect(url_for("admin_users"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/cohorts")
@admin_required
def admin_cohorts() -> Any:
    """Manage cohorts."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT c.*, COUNT(u.id) as user_count
            FROM cohorts c
            LEFT JOIN users u ON c.id = u.cohort_id
            WHERE c.is_active = TRUE
            GROUP BY c.id
            ORDER BY c.bootcamp_type, c.start_date DESC
        """
        )
        cohorts = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Error getting cohorts: {str(e)}")
        cohorts = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/cohorts.html", cohorts=cohorts)


@app.route("/admin/add_cohort", methods=["GET", "POST"])
@admin_required
def admin_add_cohort() -> Any:
    """Add new cohort - FIXED."""
    if request.method == "POST":
        name = request.form.get("name")
        bootcamp_type = request.form.get("bootcamp_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        if not all([name, bootcamp_type]):
            flash("Name and bootcamp type are required.", "error")
            return render_template(
                "admin/add_cohort.html", bootcamp_types=BOOTCAMP_TYPES
            )

        # Validate against BOOTCAMP_TYPES instead of hardcoded list
        if not validate_bootcamp_type(bootcamp_type):
            flash(
                f'Invalid bootcamp type. Must be one of: {", ".join(BOOTCAMP_TYPES)}',
                "error",
            )
            return render_template(
                "admin/add_cohort.html", bootcamp_types=BOOTCAMP_TYPES
            )

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cohorts (name, bootcamp_type, start_date, end_date, description)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    name,
                    bootcamp_type,
                    start_date or None,
                    end_date or None,
                    description,
                ),
            )

            cohort_id = cursor.fetchone()[0]

            # Create corresponding tag in Cohort tag group
            cursor.execute("SELECT id FROM tag_groups WHERE name = 'Cohort'")
            cohort_group = cursor.fetchone()

            if cohort_group:
                cursor.execute(
                    """
                    INSERT INTO tags (tag_group_id, name, description)
                    VALUES (%s, %s, %s)
                """,
                    (cohort_group[0], name, f"Cohort: {name}"),
                )

            conn.commit()
            flash("Cohort created successfully!", "success")
            return redirect(url_for("admin_cohorts"))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error creating cohort: {str(e)}")
            flash("Error creating cohort.", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template("admin/add_cohort.html", bootcamp_types=BOOTCAMP_TYPES)


# =================================================================================
#                           ADMIN ROUTES
# =================================================================================


@app.route("/admin", methods=["GET"])
def admin_redirect() -> Any:
    """Redirect to admin login page."""
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login() -> Any:
    """Handle admin user login."""
    # Clear any existing admin sessions
    if request.method == "GET":
        session.pop("admin", None)
        session.pop("admin_username", None)

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Username and password are required", "danger")
            return render_template("admin/login.html")

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password FROM admin_users WHERE username=%s", (username,)
            )
            admin = cursor.fetchone()
            cursor.close()

            if admin and admin[1] and check_password_hash(admin[1], password):
                session["admin"] = True
                session["admin_username"] = username
                flash("Welcome to the admin panel", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid admin credentials", "danger")
        except Exception as e:
            logger.error(f"Admin login error: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            if conn:
                release_db_connection(conn)

    return render_template("admin/login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard() -> Any:
    """Display admin dashboard with statistics."""
    stats = get_admin_stats()
    return render_template("admin/dashboard.html", stats=stats)


# --- USER MANAGEMENT ROUTES ---
@app.route("/admin/users")
@admin_required
def admin_users():
    """Display and manage users with proper error handling. Show role and tags."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, username, email, language, email_verified, camp, role FROM users ORDER BY username"
        )
        users = cursor.fetchall()
        # For each user, fetch tags
        for user in users:
            cursor_tags = conn.cursor()
            cursor_tags.execute(
                """
                SELECT t.name FROM user_tags ut
                JOIN tags t ON ut.tag_id = t.id
                WHERE ut.user_id = %s AND t.is_active = TRUE
                ORDER BY t.name
            """,
                (user["id"],),
            )
            user["tags"] = [row[0] for row in cursor_tags.fetchall()]
            cursor_tags.close()
        cursor.close()
        return render_template("admin/users.html", users=users)
    except Exception as e:
        logger.error(f"Admin users page error: {str(e)}")
        flash(f"Error loading users: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/add_user", methods=["GET", "POST"])
@admin_required
def admin_add_user():
    """Add a new user with email verification and role support."""
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role", "user")
        verification_code = generate_verification_code()

        if not all([username, email, password]):
            flash("All fields are required.", "error")
            return render_template("admin/add_user.html")

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if username or email already exists
            cursor.execute(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (username, email),
            )
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Username or email already exists.", "error")
                return render_template("admin/add_user.html")

            # Create new user (email_verified False, with verification code)
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
            cursor.execute(
                """
                INSERT INTO users (username, email, password, role, email_verified, verification_code)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (username, email, hashed_password, role, False, verification_code),
            )

            conn.commit()
            cursor.close()

            # Send verification email
            send_verification_email(email, verification_code)

            flash("User added successfully! Verification email sent.", "success")
            return redirect(url_for("admin_users"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding user: {str(e)}")
            flash(f"Error adding user: {str(e)}", "error")
        finally:
            if conn:
                release_db_connection(conn)

    return render_template("admin/add_user.html")


@app.route("/admin/edit_user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_user(user_id):
    """Edit an existing user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))

        if request.method == "POST":
            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")
            role = request.form.get("role", "user")

            if not all([username, email]):
                flash("Username and email are required.", "error")
                return render_template("admin/edit_user.html", user=user)

            # Check if username or email already exists (excluding current user)
            cursor.execute(
                "SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s",
                (username, email, user_id),
            )
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Username or email already exists.", "error")
                return render_template("admin/edit_user.html", user=user)

            # Update user
            if password:
                hashed_password = generate_password_hash(
                    password, method="pbkdf2:sha256"
                )
                cursor.execute(
                    """
                    UPDATE users SET username=%s, email=%s, password=%s, role=%s WHERE id=%s
                """,
                    (username, email, hashed_password, role, user_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE users SET username=%s, email=%s, role=%s WHERE id=%s
                """,
                    (username, email, role, user_id),
                )

            conn.commit()
            flash("User updated successfully!", "success")
            # Refresh user data
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()

        cursor.close()
        return render_template("admin/edit_user.html", user=user)

    except Exception as e:
        logger.error(f"Error editing user: {str(e)}")
        flash(f"Error editing user: {str(e)}", "error")
        return redirect(url_for("admin_users"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    """Delete a user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        flash("User deleted successfully!", "success")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error deleting user: {str(e)}")
        flash(f"Error deleting user: {str(e)}", "error")
    finally:
        if conn:
            release_db_connection(conn)

    return redirect(url_for("admin_users"))


@app.route("/admin/download_submissions")
@admin_required
def admin_download_submissions() -> Any:
    """Show submission download options by camp."""
    return render_template("admin/export_options.html", export_type="submissions")


@app.route("/admin/download_submissions/<camp>")
@admin_required
def admin_download_submissions_by_camp(camp: str) -> Any:
    """Download project submissions as a zip file filtered by camp."""
    if camp not in CAMPS and camp != "all":
        flash("Invalid camp selection", "danger")
        return redirect(url_for("admin_dashboard"))

    # Create a BytesIO object to store the ZIP file
    memory_file = io.BytesIO()

    # Create a ZIP file in memory
    with zipfile.ZipFile(memory_file, "w") as zf:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            if camp == "all":
                cursor.execute(
                    """
                    SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                    FROM submissions s
                    JOIN users u ON s.user_id = u.id
                    ORDER BY u.camp, s.submitted_at DESC
                """
                )
            else:
                cursor.execute(
                    """
                    SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                    FROM submissions s
                    JOIN users u ON s.user_id = u.id
                    WHERE u.camp = %s
                    ORDER BY s.submitted_at DESC
                """,
                    (camp,),
                )

            submissions = cursor.fetchall()
            cursor.close()

            if not submissions:
                flash(f"No submissions found for {camp} camp", "warning")
                return redirect(url_for("admin_submissions"))

            # Add each submission file to the ZIP
            files_added = 0
            for submission in submissions:
                file_path = submission["file_path"]
                if file_path:
                    # Look for file in uploads folder
                    real_path = os.path.join(UPLOAD_FOLDER, file_path)

                    # Check if file exists
                    if os.path.exists(real_path):
                        # Create a descriptive name for the file in the ZIP
                        # Format: Camp_Unit#_Username_OriginalFilename
                        camp_prefix = submission["camp"].replace(" ", "_")
                        file_name = f"{camp_prefix}_Unit{submission['unit_id']}_{submission['username']}_{file_path}"
                        zf.write(real_path, file_name)
                        files_added += 1
                    else:
                        logger.warning(f"File not found: {real_path}")

            if files_added == 0:
                flash(f"No submission files found for {camp} camp", "warning")
                return redirect(url_for("admin_submissions"))

        except Exception as e:
            logger.error(f"Admin download submissions error: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for("admin_submissions"))
        finally:
            if conn:
                release_db_connection(conn)

    # Reset the file pointer to the beginning
    memory_file.seek(0)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if camp == "all":
        filename = f"all_submissions_{timestamp}.zip"
    else:
        camp_safe = camp.replace(" ", "_").lower()
        filename = f"{camp_safe}_submissions_{timestamp}.zip"

    # Send the file for download
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/admin/submissions")
@admin_required
def admin_submissions() -> Any:
    """Display user project submissions with camp filtering."""
    camp_filter = request.args.get("camp", "all")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if camp_filter == "all" or camp_filter not in CAMPS:
            cursor.execute(
                """
                SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                FROM submissions s
                JOIN users u ON s.user_id = u.id
                ORDER BY s.submitted_at DESC
            """
            )
        else:
            cursor.execute(
                """
                SELECT s.id, u.username, u.camp, s.unit_id, s.file_path, s.submitted_at
                FROM submissions s
                JOIN users u ON s.user_id = u.id
                WHERE u.camp = %s
                ORDER BY s.submitted_at DESC
            """,
                (camp_filter,),
            )

        submissions = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Admin submissions page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        submissions = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/submissions.html",
        submissions=submissions,
        camps=CAMPS,
        current_camp=camp_filter,
    )


@app.route("/admin/update_user_language", methods=["POST"])
@admin_required
def admin_update_user_language() -> Any:
    """Update a user's interface language."""
    user_id = request.form.get("user_id")
    language = request.form.get("language")

    if user_id and language in LANGUAGES:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET language = %s WHERE id = %s", (language, user_id)
            )
            conn.commit()
            cursor.close()
            flash("User language updated successfully", "success")
        except Exception as e:
            logger.error(f"Admin update user language error: {str(e)}")
            flash(f"Error updating user language: {str(e)}", "danger")
        finally:
            if conn:
                release_db_connection(conn)
    else:
        flash("Invalid user or language selection", "danger")

    return redirect(url_for("admin_users"))


@app.route("/admin/feedback")
@admin_required
def admin_feedback() -> Any:
    """Display user feedback for admin review."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT feedback.id, users.username, feedback.feedback_text,
                   feedback.rating, feedback.created_at
            FROM feedback
            JOIN users ON feedback.user_id = users.id
            ORDER BY feedback.created_at DESC
        """
        )
        feedback_items = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logger.error(f"Admin feedback page error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        feedback_items = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/feedback.html", feedback=feedback_items)


def parse_core_elements(form_data):
    """Parse core elements from form data into proper JSON structure"""
    grouped = defaultdict(dict)
    pattern = re.compile(r"core_elements\[(\d+)\]\[(\w+)\]")

    for key, value in form_data.items():
        match = pattern.match(key)
        if match:
            idx, field = match.groups()
            if value and value.strip():
                grouped[int(idx)][field] = value.strip()

    core_elements = []
    for idx in sorted(grouped.keys()):
        item = grouped[idx]
        if "core_element" in item and "everyday_object" in item:
            core_elements.append(
                {
                    "core_element": item["core_element"],
                    "everyday_object": item["everyday_object"],
                }
            )

    return core_elements


@app.route("/admin/add_word", methods=["GET", "POST"])
@admin_required
def admin_add_word() -> Any:
    available_tags = get_available_tags_grouped()
    available_cohorts = get_all_cohorts()

    if request.method == "POST":
        conn = None
        try:
            unit_id = request.form["unit_id"]
            word = request.form["word"]
            section = request.form.get("section", 1)
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            one_sentence_version = request.form.get("one_sentence_version", "")
            daily_definition = request.form.get("daily_definition", "")
            life_metaphor = request.form.get("life_metaphor", "")
            visual_explanation = request.form.get("visual_explanation", "")
            scenario_theater = request.form.get("scenario_theater", "")
            misunderstandings = request.form.get("misunderstandings", "")
            reality_connection = request.form.get("reality_connection", "")
            thinking_bubble = request.form.get("thinking_bubble", "")
            smiling_conclusion = request.form.get("smiling_conclusion", "")
            core_elements = parse_core_elements(request.form)
            selected_tags = [int(tag) for tag in request.form.getlist("tags")]

            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/add_word.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            if len(selected_bootcamp_types) > 2:
                flash("You can only select up to 2 bootcamp types.", "error")
                return render_template(
                    "admin/add_word.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            conn = get_db_connection()
            cursor = conn.cursor()

            # Use first selected bootcamp type for the main camp field (backward compatibility)
            primary_camp = selected_bootcamp_types[0]

            cursor.execute(
                """
                INSERT INTO words (
                    unit_id, word, section, camp,
                    one_sentence_version, daily_definition, life_metaphor, visual_explanation,
                    core_elements, scenario_theater, misunderstandings, reality_connection,
                    thinking_bubble, smiling_conclusion
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    unit_id,
                    word,
                    section,
                    primary_camp,
                    one_sentence_version,
                    daily_definition,
                    life_metaphor,
                    visual_explanation,
                    json.dumps(core_elements),
                    scenario_theater,
                    misunderstandings,
                    reality_connection,
                    thinking_bubble,
                    smiling_conclusion,
                ),
            )

            word_id = cursor.fetchone()[0]
            conn.commit()

            # Auto-assign bootcamp type tags for all selected bootcamp types
            bootcamp_tags_to_assign = []
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute("SELECT id FROM tags WHERE name = %s", (bootcamp_type,))
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    bootcamp_tags_to_assign.append(bootcamp_tag[0])

            # Combine with selected additional tags
            all_tags = bootcamp_tags_to_assign + selected_tags

            # Assign all tags
            if all_tags:
                assign_content_tags("word", word_id, all_tags)

            flash("Word added successfully!", "success")
            return redirect(url_for("admin_manage_content"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding word: {str(e)}")
            flash("Error adding word.", "danger")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template(
        "admin/add_word.html",
        available_tags=available_tags,
        available_cohorts=available_cohorts,
    )


@app.route("/admin/add_quiz", methods=["GET", "POST"])
@admin_required
def admin_add_quiz() -> Any:
    """Add quiz with multiple bootcamp type support."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT unit_id FROM materials ORDER BY unit_id")
        available_units = [row[0] for row in cursor.fetchall()]
        cursor.close()
    except Exception as e:
        logger.error(f"Error fetching available units: {str(e)}")
        available_units = []
    finally:
        if conn:
            release_db_connection(conn)

    available_tags = get_available_tags_grouped()

    if request.method == "POST":
        conn = None
        try:
            # Get form data
            data = request.form
            unit_id = data["unit_id"]
            question = data["question"]
            options = [data[f"option{i}"] for i in range(1, 4)]
            correct_answer = int(data["correct_answer"])
            explanation = data["explanation"]
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            selected_additional_tags = [
                int(tag) for tag in request.form.getlist("tags")
            ]

            # Validation
            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/add_quiz.html",
                    available_tags=available_tags,
                    available_units=available_units,
                )

            # Validate bootcamp types
            invalid_camps = [
                camp
                for camp in selected_bootcamp_types
                if not validate_bootcamp_type(camp)
            ]
            if invalid_camps:
                flash(f'Invalid bootcamp types: {", ".join(invalid_camps)}', "error")
                return render_template(
                    "admin/add_quiz.html",
                    available_tags=available_tags,
                    available_units=available_units,
                )

            # Use first selected bootcamp type for the main camp field (backward compatibility)
            primary_camp = selected_bootcamp_types[0]

            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert quiz question
            cursor.execute(
                """
                INSERT INTO quizzes (unit_id, question, options, correct_answer, explanation, camp)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
                (
                    unit_id,
                    question,
                    json.dumps(options),
                    correct_answer,
                    explanation,
                    primary_camp,
                ),
            )

            quiz_id = cursor.fetchone()[0]

            # Prepare tags to assign
            tags_to_assign = []

            # Add bootcamp type tags for all selected bootcamp types
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute(
                    "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                    (bootcamp_type,),
                )
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    tags_to_assign.append(bootcamp_tag[0])
                    logger.info(
                        f"Found bootcamp tag ID: {bootcamp_tag[0]} for {bootcamp_type}"
                    )
                else:
                    logger.warning(f"No tag found for bootcamp type: {bootcamp_type}")

            # Add additional selected tags
            tags_to_assign.extend(selected_additional_tags)

            # Remove duplicates
            tags_to_assign = list(set(tags_to_assign))

            # Assign all tags
            if tags_to_assign:
                success = assign_content_tags("quiz", quiz_id, tags_to_assign)
                if success:
                    logger.info("Tags assigned successfully to quiz")
                else:
                    logger.warning("Failed to assign some tags to quiz")

            conn.commit()

            flash(
                f'Quiz question added successfully for {", ".join(selected_bootcamp_types)} bootcamp(s)!',
                "success",
            )
            return redirect(url_for("admin_add_quiz"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding quiz: {str(e)}")
            flash("Error adding quiz.", "danger")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template(
        "admin/add_quiz.html",
        available_tags=available_tags,
        available_units=available_units,
    )


@app.route("/admin/add_material", methods=["GET", "POST"])
@admin_required
def admin_add_material() -> Any:
    """Add learning material with multiple bootcamp type support."""
    available_tags = get_available_tags_grouped()
    available_cohorts = get_all_cohorts()

    if request.method == "POST":
        conn = None
        try:
            # Debug: Log what we received
            logger.info(f"Form data received: {dict(request.form)}")
            logger.info(f"Files received: {dict(request.files)}")

            # Safely get form data with validation
            unit_id = request.form.get("unit_id")
            title = request.form.get("title")
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            content = request.form.get("content", "")

            # Validate required fields
            if not unit_id:
                flash("Unit ID is required.", "error")
                return render_template(
                    "admin/add_material.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            if not title:
                flash("Title is required.", "error")
                return render_template(
                    "admin/add_material.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/add_material.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            # Validate bootcamp types
            invalid_camps = [
                camp
                for camp in selected_bootcamp_types
                if not validate_bootcamp_type(camp)
            ]
            if invalid_camps:
                flash(f'Invalid bootcamp types: {", ".join(invalid_camps)}', "error")
                return render_template(
                    "admin/add_material.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            # Use first selected bootcamp type for the main camp field (backward compatibility)
            primary_camp = selected_bootcamp_types[0]

            # Safely get additional tags
            try:
                selected_additional_tags = [
                    int(tag) for tag in request.form.getlist("tags") if tag.isdigit()
                ]
            except (ValueError, TypeError):
                selected_additional_tags = []
                logger.warning("Invalid tag values received")

            # Handle file upload
            file = request.files.get("file")
            filename = None

            if file and file.filename:
                if allowed_file(file.filename):
                    try:
                        # Make sure upload folder exists
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                        # Create a unique filename
                        original_filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"unit_{unit_id}_{primary_camp}_{timestamp}_{original_filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(file_path)
                        logger.info(f"File saved to: {file_path}")
                    except Exception as file_error:
                        logger.error(f"File upload error: {str(file_error)}")
                        flash(f"Error uploading file: {str(file_error)}", "error")
                        return render_template(
                            "admin/add_material.html",
                            available_tags=available_tags,
                            available_cohorts=available_cohorts,
                        )
                else:
                    flash(
                        "Invalid file type. Please upload a supported file format.",
                        "error",
                    )
                    return render_template(
                        "admin/add_material.html",
                        available_tags=available_tags,
                        available_cohorts=available_cohorts,
                    )
            else:
                flash("Please select a file to upload.", "error")
                return render_template(
                    "admin/add_material.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            # Database operations
            conn = get_db_connection()
            cursor = conn.cursor()

            logger.info(
                f"Inserting material: unit_id={unit_id}, title={title}, content={content}, file_path={filename}, camp={primary_camp}"
            )

            # Insert material with proper fields including title
            cursor.execute(
                """
                INSERT INTO materials (unit_id, title, content, file_path, camp)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
                (unit_id, title, content, filename, primary_camp),
            )

            material_id = cursor.fetchone()[0]
            logger.info(f"Material created with ID: {material_id}")

            # Prepare tags to assign
            tags_to_assign = []

            # Add bootcamp type tags for all selected bootcamp types
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute(
                    "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                    (bootcamp_type,),
                )
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    tags_to_assign.append(bootcamp_tag[0])
                    logger.info(
                        f"Found bootcamp tag ID: {bootcamp_tag[0]} for {bootcamp_type}"
                    )
                else:
                    logger.warning(f"No tag found for bootcamp type: {bootcamp_type}")

            # Add additional selected tags
            tags_to_assign.extend(selected_additional_tags)

            # Remove duplicates
            tags_to_assign = list(set(tags_to_assign))
            logger.info(f"Assigning tags: {tags_to_assign}")

            # Assign all tags
            if tags_to_assign:
                success = assign_content_tags("material", material_id, tags_to_assign)
                if success:
                    logger.info("Tags assigned successfully")
                else:
                    logger.warning("Failed to assign some tags")

            conn.commit()
            logger.info("Material and tags committed to database")

            flash(
                f'Material added successfully for {", ".join(selected_bootcamp_types)} bootcamp(s)!',
                "success",
            )
            return redirect(url_for("admin_manage_content"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding material: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            flash(f"Error adding material: {str(e)}", "danger")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template(
        "admin/add_material.html",
        available_tags=available_tags,
        available_cohorts=available_cohorts,
    )


@app.route("/admin/edit_material/<int:material_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_material(material_id: int) -> Any:
    """Edit existing learning material with multiple bootcamp type support."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM materials WHERE id=%s", (material_id,))
        material = cursor.fetchone()

        if not material:
            flash("Material not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # Get current tags assigned to this material
        cursor.execute(
            "SELECT tag_id FROM content_tags WHERE content_type = %s AND content_id = %s",
            ("material", material_id),
        )
        tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        # Get current bootcamp types from tags
        cursor.execute(
            """
            SELECT t.name FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name = 'Bootcamp Type'
        """,
            ("material", material_id),
        )
        current_bootcamp_types = [row["name"] for row in cursor.fetchall()]

        # If no bootcamp types in tags, use the camp field as fallback
        if not current_bootcamp_types and material["camp"]:
            current_bootcamp_types = [material["camp"]]

        # Get available tags (excluding bootcamp type tags for separate handling)
        available_tags = get_available_tags_grouped()

        # Get non-bootcamp tag IDs for the additional tags section
        cursor.execute(
            """
            SELECT ct.tag_id FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name != 'Bootcamp Type'
        """,
            ("material", material_id),
        )
        additional_tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        if request.method == "POST":
            try:
                # Get form data
                unit_id = request.form["unit_id"]
                title = request.form["title"]
                content = request.form.get("content", "")
                selected_bootcamp_types = request.form.getlist("bootcamp_types")
                selected_additional_tags = [
                    int(tag_id) for tag_id in request.form.getlist("tags")
                ]

                # Validation
                if not selected_bootcamp_types:
                    flash("Please select at least one bootcamp type.", "danger")
                    return render_template(
                        "admin/edit_material.html",
                        material=material,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Validate bootcamp types
                invalid_camps = [
                    camp
                    for camp in selected_bootcamp_types
                    if not validate_bootcamp_type(camp)
                ]
                if invalid_camps:
                    flash(
                        f'Invalid bootcamp types: {", ".join(invalid_camps)}', "danger"
                    )
                    return render_template(
                        "admin/edit_material.html",
                        material=material,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Use first selected bootcamp type for the main camp field (backward compatibility)
                primary_camp = selected_bootcamp_types[0]

                # Handle file upload
                file = request.files.get("file")
                file_path = material["file_path"]  # Default to existing file

                if file and file.filename:
                    if allowed_file(file.filename):
                        # Remove old file if it exists
                        if material["file_path"]:
                            old_file_path = os.path.join(
                                UPLOAD_FOLDER, material["file_path"]
                            )
                            try:
                                if os.path.exists(old_file_path):
                                    os.remove(old_file_path)
                            except Exception as e:
                                logger.warning(f"Could not remove old file: {e}")

                        # Save new file
                        original_filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_path = f"unit_{unit_id}_{primary_camp}_{timestamp}_{original_filename}"
                        file.save(os.path.join(UPLOAD_FOLDER, file_path))
                    else:
                        allowed_types = ", ".join(ALLOWED_EXTENSIONS)
                        flash(
                            f"Invalid file type. Allowed types: {allowed_types}",
                            "danger",
                        )
                        return render_template(
                            "admin/edit_material.html",
                            material=material,
                            available_tags=available_tags,
                            tag_ids=additional_tag_ids,
                            current_bootcamp_types=current_bootcamp_types,
                            camps=CAMPS,
                        )

                # Update material in database
                cursor.execute(
                    """
                    UPDATE materials
                    SET unit_id=%s, title=%s, content=%s, file_path=%s, camp=%s
                    WHERE id=%s
                """,
                    (unit_id, title, content, file_path, primary_camp, material_id),
                )

                # Prepare tags to assign
                tags_to_assign = []

                # Add bootcamp type tags
                for bootcamp_type in selected_bootcamp_types:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                        (bootcamp_type,),
                    )
                    bootcamp_tag = cursor.fetchone()
                    if bootcamp_tag:
                        tags_to_assign.append(bootcamp_tag["id"])
                    else:
                        logger.warning(
                            f"No tag found for bootcamp type: {bootcamp_type}"
                        )

                # Add additional selected tags
                tags_to_assign.extend(selected_additional_tags)

                # Remove duplicates
                tags_to_assign = list(set(tags_to_assign))

                # Assign all tags (this will replace existing tags)
                success = assign_content_tags("material", material_id, tags_to_assign)

                conn.commit()

                if success:
                    flash("Material updated successfully!", "success")
                    logger.info(
                        f"Material {material_id} updated with bootcamp types: {selected_bootcamp_types}"
                    )
                else:
                    flash(
                        "Material updated, but there was an issue with tag assignment.",
                        "warning",
                    )

                return redirect(url_for("admin_manage_content"))

            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating material: {str(e)}")
                flash(f"Error updating material: {str(e)}", "danger")

        cursor.close()

    except Exception as e:
        logger.error(f"Admin edit material error: {str(e)}")
        flash(f"Error loading material: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/edit_material.html",
        material=material,
        available_tags=available_tags,
        tag_ids=additional_tag_ids,
        current_bootcamp_types=current_bootcamp_types,
        camps=CAMPS,
    )


@app.route("/admin/add_video", methods=["GET", "POST"])
@admin_required
def admin_add_video() -> Any:
    """Add video with support for YouTube, Lark, and direct uploads."""
    available_tags = get_available_tags_grouped()
    available_cohorts = get_all_cohorts()

    if request.method == "POST":
        conn = None
        try:
            # Get form data
            title = request.form["title"]
            description = request.form["description"]
            unit_id = request.form["unit_id"]
            video_type = request.form.get("video_type", "youtube")  # youtube, lark, upload
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            selected_additional_tags = [int(tag) for tag in request.form.getlist("tags")]

            # Validation
            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/add_video.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            primary_camp = selected_bootcamp_types[0]
            video_url = None
            video_file_path = None

            # Handle different video types
            if video_type == "youtube":
                youtube_url = request.form["youtube_url"]
                if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
                    if "v=" in youtube_url:
                        video_url = youtube_url.split("v=")[1].split("&")[0]
                    elif "youtu.be/" in youtube_url:
                        video_url = youtube_url.split("youtu.be/")[1].split("?")[0]
                    else:
                        video_url = youtube_url
                else:
                    video_url = youtube_url

            elif video_type == "lark":
                lark_url = request.form["lark_url"]
                video_url = lark_url

            elif video_type == "upload":
                video_file = request.files.get("video_file")
                if video_file and video_file.filename:
                    # Check file extension
                    allowed_video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
                    if not any(video_file.filename.lower().endswith(ext) for ext in allowed_video_extensions):
                        flash("Invalid video file type. Allowed: MP4, AVI, MOV, WMV, FLV, WEBM", "error")
                        return render_template(
                            "admin/add_video.html",
                            available_tags=available_tags,
                            available_cohorts=available_cohorts,
                        )
                    
                    # Save video file
                    filename = secure_filename(video_file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_file_path = f"video_{unit_id}_{primary_camp}_{timestamp}_{filename}"
                    
                    # Create videos directory if it doesn't exist
                    videos_dir = os.path.join(UPLOAD_FOLDER, "videos")
                    os.makedirs(videos_dir, exist_ok=True)
                    
                    file_path = os.path.join(videos_dir, video_file_path)
                    video_file.save(file_path)
                    
                    # Store full path for database
                    video_url = f"videos/{video_file_path}"

            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert video with new fields
            cursor.execute(
                """
                INSERT INTO videos (unit_id, title, youtube_url, description, camp, video_type, video_file_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
                (unit_id, title, video_url, description, primary_camp, video_type, video_file_path),
            )

            video_id = cursor.fetchone()[0]

            # Handle tags (same as before)
            tags_to_assign = []
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute(
                    "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                    (bootcamp_type,),
                )
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    tags_to_assign.append(bootcamp_tag[0])

            tags_to_assign.extend(selected_additional_tags)
            tags_to_assign = list(set(tags_to_assign))

            if tags_to_assign:
                assign_content_tags("video", video_id, tags_to_assign)

            conn.commit()

            flash(f'Video added successfully for {", ".join(selected_bootcamp_types)} bootcamp(s)!', "success")
            return redirect(url_for("admin_add_video"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding video: {str(e)}")
            flash(f"Error adding video: {str(e)}", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template(
        "admin/add_video.html",
        available_tags=available_tags,
        available_cohorts=available_cohorts,
    )

@app.route("/serve_video/<path:filename>")
@login_required
def serve_video(filename):
    """Serve uploaded video files."""
    try:
        videos_dir = os.path.join(UPLOAD_FOLDER, "videos")
        return send_file(os.path.join(videos_dir, filename))
    except Exception as e:
        logger.error(f"Error serving video: {str(e)}")
        return "Video not found", 404



@app.route("/admin/add_project", methods=["GET", "POST"])
@admin_required
def admin_add_project() -> Any:
    """Add project with multiple bootcamp type support."""
    available_tags = get_available_tags_grouped()
    available_cohorts = get_all_cohorts()

    if request.method == "POST":
        conn = None
        try:
            # Debug: Log form data
            logger.info(f"Project form submitted with data: {dict(request.form)}")

            # Get form data
            unit_id = request.form["unit_id"]
            title = request.form["title"]
            description = request.form["description"]
            resources = request.form["resources"]
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            selected_additional_tags = [
                int(tag) for tag in request.form.getlist("tags")
            ]

            logger.info(
                f"Parsed form data: unit_id={unit_id}, title={title}, bootcamp_types={selected_bootcamp_types}"
            )

            # Validation
            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/add_project.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            # Validate bootcamp types
            invalid_camps = [
                camp
                for camp in selected_bootcamp_types
                if not validate_bootcamp_type(camp)
            ]
            if invalid_camps:
                flash(f'Invalid bootcamp types: {", ".join(invalid_camps)}', "error")
                return render_template(
                    "admin/add_project.html",
                    available_tags=available_tags,
                    available_cohorts=available_cohorts,
                )

            # Use first selected bootcamp type for the main camp field (backward compatibility)
            primary_camp = selected_bootcamp_types[0]

            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert project
            cursor.execute(
                """
                INSERT INTO projects (unit_id, title, description, resources, camp)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
                (unit_id, title, description, resources, primary_camp),
            )

            project_id = cursor.fetchone()[0]

            # Prepare tags to assign
            tags_to_assign = []

            # Add bootcamp type tags for all selected bootcamp types
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute(
                    "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                    (bootcamp_type,),
                )
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    tags_to_assign.append(bootcamp_tag[0])
                    logger.info(
                        f"Found bootcamp tag ID: {bootcamp_tag[0]} for {bootcamp_type}"
                    )
                else:
                    logger.warning(f"No tag found for bootcamp type: {bootcamp_type}")

            # Add additional selected tags
            tags_to_assign.extend(selected_additional_tags)

            # Remove duplicates
            tags_to_assign = list(set(tags_to_assign))

            # Assign all tags
            if tags_to_assign:
                success = assign_content_tags("project", project_id, tags_to_assign)
                if success:
                    logger.info("Tags assigned successfully to project")
                else:
                    logger.warning("Failed to assign some tags to project")

            conn.commit()

            logger.info(f"Project created successfully with ID: {project_id}")
            flash(
                f'Project added successfully for {", ".join(selected_bootcamp_types)} bootcamp(s)!',
                "success",
            )
            return redirect(url_for("admin_manage_content"))

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error adding project: {str(e)}")
            flash("Error adding project.", "danger")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)

    return render_template(
        "admin/add_project.html",
        available_tags=available_tags,
        available_cohorts=available_cohorts,
        available_units=list(range(1, 21)),
    )  # Add available units for consistency


@app.route("/admin/manage_content")
@admin_required
def admin_manage_content() -> Any:
    """Manage all content types with camp information."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all quizzes with camp info
        cursor.execute(
            """
            SELECT id, unit_id, question, explanation, camp 
            FROM quizzes 
            ORDER BY camp, unit_id, id
        """
        )
        quizzes = cursor.fetchall()

        # Get all materials with camp info - include all fields needed by template
        cursor.execute(
            """
            SELECT id, unit_id, title, content, file_path, camp 
            FROM materials 
            ORDER BY camp, unit_id, id
        """
        )
        materials = cursor.fetchall()

        # Get all videos with camp info - include all fields needed by template
        cursor.execute(
            """
            SELECT id, unit_id, title, youtube_url, description, camp 
            FROM videos 
            ORDER BY camp, unit_id, id
        """
        )
        videos = cursor.fetchall()

        # Get all projects with camp info - include description field
        cursor.execute(
            """
            SELECT id, unit_id, title, description, resources, camp 
            FROM projects 
            ORDER BY camp, unit_id, id
        """
        )
        projects = cursor.fetchall()

        # Get all AI vocabulary words with camp info - include all fields
        cursor.execute(
            """
            SELECT id, unit_id, word, section, camp, 
                   one_sentence_version, daily_definition 
            FROM words 
            ORDER BY camp, unit_id, section, id
        """
        )
        words = cursor.fetchall()

        cursor.close()
    except Exception as e:
        logger.error(f"Admin manage content error: {str(e)}")
        flash(f"Error retrieving content: {str(e)}", "danger")
        quizzes = []
        materials = []
        videos = []
        projects = []
        words = []
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/manage_content.html",
        quizzes=quizzes,
        materials=materials,
        videos=videos,
        projects=projects,
        words=words,
        camps=CAMPS,
    )


@app.route("/admin/export_progress")
@admin_required
def admin_export_progress() -> Any:
    """Export progress with camp options."""
    available_tags = get_available_tags_grouped()
    return render_template(
        "admin/export_options.html",
        export_type="progress",
        available_tags=available_tags,
    )


@app.route("/admin/export_progress/<camp>")
@admin_required
def admin_export_progress_by_camp(camp: str) -> Any:
    """Export user progress to CSV filtered by camp."""
    if camp not in CAMPS and camp != "all":
        flash("Invalid camp selection", "danger")
        return redirect(url_for("admin_dashboard"))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if camp == "all":
            cursor.execute(
                """
                SELECT u.id, u.username, u.camp, p.unit_number, p.completed,
                       p.quiz_score, p.project_completed
                FROM users u
                LEFT JOIN progress p ON u.id = p.user_id
                ORDER BY u.camp, u.username, p.unit_number
            """
            )
        else:
            cursor.execute(
                """
                SELECT u.id, u.username, u.camp, p.unit_number, p.completed,
                       p.quiz_score, p.project_completed
                FROM users u
                LEFT JOIN progress p ON u.id = p.user_id
                WHERE u.camp = %s
                ORDER BY u.username, p.unit_number
            """,
                (camp,),
            )

        progress = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        # Convert to list format
        data = []
        for row in progress:
            data.append(
                [
                    row["id"],
                    row["username"],
                    row["camp"],
                    row["unit_number"],
                    row["completed"],
                    row["quiz_score"],
                    row["project_completed"],
                ]
            )

        headers = [
            "User ID",
            "Username",
            "Camp",
            "Unit",
            "Completed",
            "Quiz Score",
            "Project Completed",
        ]
        filename = f"progress_{camp}.csv" if camp != "all" else "progress_all_camps.csv"
        csv_file = generate_csv_file(data, filename, headers)

        if csv_file:
            return send_file(
                csv_file,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )
        else:
            flash("Error generating CSV file", "danger")
            return redirect(url_for("admin_dashboard"))
    except Exception as e:
        logger.error(f"Admin export progress error: {str(e)}")
        flash(f"Error exporting progress: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/export_users")
@admin_required
def admin_export_users() -> Any:
    """Export users with camp and advanced filter options."""
    # Pass available tags for the filter dropdown
    available_tags = (
        get_available_tags_grouped()
        if "get_available_tags_grouped" in globals()
        else {}
    )
    return render_template(
        "admin/export_options.html", export_type="users", available_tags=available_tags
    )


@app.route("/admin/export_users_filtered", methods=["POST"])
@admin_required
def admin_export_users_filtered():
    """Export users to CSV with advanced filtering (search, camp, tag)."""
    search = request.form.get("search", "").strip()
    camp = request.form.get("camp", "").strip()
    tag = request.form.get("tag", "").strip()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Build query
        where_clauses = []
        params = []
        if search:
            where_clauses.append("(u.username ILIKE %s OR u.email ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        if camp:
            where_clauses.append("u.camp = %s")
            params.append(camp)
        if tag:
            where_clauses.append("t.name = %s")
            params.append(tag)
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        query = f"""
            SELECT u.id, u.username, u.email, u.language, u.email_verified, u.camp,
                   STRING_AGG(DISTINCT t.name, ', ') AS tags
            FROM users u
            LEFT JOIN user_tags ut ON u.id = ut.user_id
            LEFT JOIN tags t ON ut.tag_id = t.id
            {where_sql}
            GROUP BY u.id
            ORDER BY u.camp, u.username
        """
        cursor.execute(query, params)
        users = cursor.fetchall()
        cursor.close()
        # Prepare CSV
        headers = [
            "ID",
            "Username",
            "Email",
            "Language",
            "Email Verified",
            "Camp",
            "Tags",
        ]
        data = []
        for row in users:
            data.append([row[0], row[1], row[2], row[3], row[4], row[5], row[6] or ""])
        filename = "users_filtered_export.csv"
        csv_file = generate_csv_file(data, filename, headers)
        if csv_file:
            return send_file(
                csv_file,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )
        else:
            flash("Error generating CSV file", "danger")
            return redirect(url_for("admin_export_users"))
    except Exception as e:
        logger.error(f"Admin export users filtered error: {str(e)}")
        flash(f"Error exporting users: {str(e)}", "danger")
        return redirect(url_for("admin_export_users"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/export_feedback")
@admin_required
def admin_export_feedback() -> Any:
    """Export feedback with camp options."""
    available_tags = get_available_tags_grouped()
    return render_template(
        "admin/export_options.html",
        export_type="feedback",
        available_tags=available_tags,
    )


@app.route("/admin/export_feedback/<camp>")
@admin_required
def admin_export_feedback_by_camp(camp: str) -> Any:
    """Export feedback to CSV filtered by camp."""
    if camp not in CAMPS and camp != "all":
        flash("Invalid camp selection", "danger")
        return redirect(url_for("admin_dashboard"))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if camp == "all":
            cursor.execute(
                """
                SELECT u.username, u.camp, f.feedback_text, f.rating, f.created_at
                FROM feedback f
                JOIN users u ON f.user_id = u.id
                ORDER BY u.camp, f.created_at DESC
            """
            )
        else:
            cursor.execute(
                """
                SELECT u.username, u.camp, f.feedback_text, f.rating, f.created_at
                FROM feedback f
                JOIN users u ON f.user_id = u.id
                WHERE u.camp = %s
                ORDER BY f.created_at DESC
            """,
                (camp,),
            )

        feedback = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        # Convert to list format
        data = []
        for row in feedback:
            data.append(
                [
                    row["username"],
                    row["camp"],
                    row["feedback_text"],
                    row["rating"],
                    row["created_at"],
                ]
            )

        headers = ["Username", "Camp", "Feedback", "Rating", "Created At"]
        filename = f"feedback_{camp}.csv" if camp != "all" else "feedback_all_camps.csv"
        csv_file = generate_csv_file(data, filename, headers)

        if csv_file:
            return send_file(
                csv_file,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )
        else:
            flash("Error generating CSV file", "danger")
            return redirect(url_for("admin_feedback"))
    except Exception as e:
        logger.error(f"Admin export feedback error: {str(e)}")
        flash(f"Error exporting feedback: {str(e)}", "danger")
        return redirect(url_for("admin_feedback"))


@app.route("/admin/reset_db", methods=["GET", "POST"])
@admin_required
def admin_reset_db() -> Any:
    """Reset database tables."""
    if request.method == "POST":
        confirmation = request.form.get("confirmation")
        if confirmation == "RESET":
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Delete all user data except admin users
                tables = [
                    "feedback",
                    "qa_history",
                    "quiz_attempts",
                    "submissions",
                    "progress",
                    "words",
                    "projects",
                    "videos",
                    "materials",
                    "quizzes",
                    "team_members",
                    "team_scores",
                    "teams",
                ]

                for table in tables:
                    cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

                # Maintain admin users but reset regular users
                cursor.execute("TRUNCATE TABLE users CASCADE")

                conn.commit()
                cursor.close()
                release_db_connection(conn)

                flash("Database has been reset successfully", "success")
                return redirect(url_for("admin_dashboard"))
            except Exception as e:
                logger.error(f"DB reset error: {str(e)}")
                flash(f"Error resetting database: {str(e)}", "danger")
                return redirect(url_for("admin_dashboard"))
        else:
            flash("Incorrect confirmation text", "danger")

    return render_template("admin/reset_db.html")


@app.route("/admin/logout")
def admin_logout() -> Any:
    """Handle admin logout."""
    session.pop("admin", None)
    session.pop("admin_username", None)
    flash("You have been logged out from admin panel", "info")
    return redirect(url_for("admin_login"))


# ---------- TEAM MANAGEMENT ROUTES ----------
@app.route("/admin/teams")
@admin_required
def admin_teams() -> Any:
    """Manage teams."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all teams with their lead names and member counts
        cursor.execute(
            """
            SELECT t.id, t.name, t.camp, u.username AS team_lead_name,
                   COUNT(tm.id) AS member_count,
                   COALESCE(ts.score, 0) AS team_score
            FROM teams t
            LEFT JOIN users u ON t.team_lead_id = u.id
            LEFT JOIN team_members tm ON t.id = tm.team_id
            LEFT JOIN team_scores ts ON t.id = ts.team_id
            GROUP BY t.id, u.username, ts.score
            ORDER BY t.camp, COALESCE(ts.score, 0) DESC
        """
        )
        teams = cursor.fetchall()

        cursor.close()
        return render_template("admin/teams.html", teams=teams)
    except Exception as e:
        logger.error(f"Error in admin_teams: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/add_team", methods=["GET", "POST"])
@admin_required
def admin_add_team() -> Any:
    """Add a new team."""
    if request.method == "POST":
        team_name = request.form.get("team_name")
        team_lead_id = request.form.get("team_lead_id")
        camp = request.form.get("camp")

        if not all([team_name, team_lead_id, camp]):
            flash("All fields are required", "danger")
            return redirect(url_for("admin_add_team"))

        # Use validation
        if not validate_bootcamp_type(camp):
            flash(
                f"Invalid camp. Must be one of: {', '.join(BOOTCAMP_TYPES)}", "danger"
            )
            return redirect(url_for("admin_add_team"))

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create the team
            cursor.execute(
                """
                INSERT INTO teams (name, team_lead_id, camp)
                VALUES (%s, %s, %s) RETURNING id
            """,
                (team_name, team_lead_id, camp),
            )
            team_id = cursor.fetchone()[0]

            # Add team lead to team members
            cursor.execute(
                """
                INSERT INTO team_members (team_id, user_id)
                VALUES (%s, %s)
            """,
                (team_id, team_lead_id),
            )

            # Initialize team score
            cursor.execute(
                """
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, 0)
            """,
                (team_id,),
            )

            conn.commit()
            flash("Team created successfully", "success")
            return redirect(url_for("admin_teams"))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in admin_add_team: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for("admin_add_team"))
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
        cursor.execute(
            """
            SELECT id, username, email
            FROM users
            ORDER BY username
        """
        )
        users = cursor.fetchall()

        cursor.close()
        return render_template("admin/add_team.html", users=users, camps=CAMPS)
    except Exception as e:
        logger.error(f"Error in admin_add_team GET: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/edit_team/<int:team_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_team(team_id: int) -> Any:
    """Edit an existing team."""
    if request.method == "POST":
        team_name = request.form.get("team_name")
        team_lead_id = request.form.get("team_lead_id")
        camp = request.form.get("camp")

        if not all([team_name, team_lead_id, camp]):
            flash("All fields are required", "danger")
            return redirect(url_for("admin_edit_team", team_id=team_id))

        # Use validation
        if not validate_bootcamp_type(camp):
            flash(
                f"Invalid camp. Must be one of: {', '.join(BOOTCAMP_TYPES)}", "danger"
            )
            return redirect(url_for("admin_edit_team", team_id=team_id))

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Update the team
            cursor.execute(
                """
                UPDATE teams SET name = %s, team_lead_id = %s, camp = %s
                WHERE id = %s
            """,
                (team_name, team_lead_id, camp, team_id),
            )

            conn.commit()
            flash("Team updated successfully", "success")
            return redirect(url_for("admin_teams"))
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in admin_edit_team: {str(e)}")
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for("admin_edit_team", team_id=team_id))
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
        cursor.execute(
            """
            SELECT * FROM teams WHERE id = %s
        """,
            (team_id,),
        )
        team = cursor.fetchone()

        if not team:
            flash("Team not found", "danger")
            return redirect(url_for("admin_teams"))

        # Get all users for the team lead dropdown
        cursor.execute(
            """
            SELECT id, username, email
            FROM users
            ORDER BY username
        """
        )
        users = cursor.fetchall()

        cursor.close()
        return render_template(
            "admin/edit_team.html", team=team, users=users, camps=CAMPS
        )
    except Exception as e:
        logger.error(f"Error in admin_edit_team GET: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/delete_team/<int:team_id>")
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
        return redirect(url_for("admin_teams"))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_delete_team: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route("/admin/team_members/<int:team_id>")
@admin_required
def admin_team_members(team_id: int) -> Any:
    """Manage team members."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get team info
        cursor.execute(
            """
            SELECT t.*, u.username AS team_lead_name
            FROM teams t
            LEFT JOIN users u ON t.team_lead_id = u.id
            WHERE t.id = %s
        """,
            (team_id,),
        )
        team = cursor.fetchone()

        if not team:
            flash("Team not found", "danger")
            return redirect(url_for("admin_teams"))

        # Get team members
        cursor.execute(
            """
            SELECT tm.id, tm.user_id, u.username, u.email, tm.joined_at
            FROM team_members tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.team_id = %s
            ORDER BY u.username
        """,
            (team_id,),
        )
        members = cursor.fetchall()

        # Get non-team members for adding
        cursor.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM team_members WHERE team_id = %s
            )
            ORDER BY username
        """,
            (team_id,),
        )
        non_members = cursor.fetchall()

        cursor.close()
        return render_template(
            "admin/team_members.html",
            team=team,
            members=members,
            non_members=non_members,
        )
    except Exception as e:
        logger.error(f"Error in admin_team_members: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/add_team_member/<int:team_id>", methods=["POST"])
@admin_required
def admin_add_team_member(team_id: int) -> Any:
    """Add a user to a team."""
    user_id = request.form.get("user_id")

    if not user_id:
        flash("User selection is required", "danger")
        return redirect(url_for("admin_team_members", team_id=team_id))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Add user to team
        cursor.execute(
            """
            INSERT INTO team_members (team_id, user_id)
            VALUES (%s, %s)
        """,
            (team_id, user_id),
        )

        conn.commit()
        flash("Member added to team successfully", "success")
        return redirect(url_for("admin_team_members", team_id=team_id))
    except psycopg2.errors.UniqueViolation:
        # Handle unique constraint violation
        if conn:
            conn.rollback()
        flash("User is already a member of this team", "warning")
        return redirect(url_for("admin_team_members", team_id=team_id))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_add_team_member: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_team_members", team_id=team_id))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route("/admin/remove_team_member/<int:member_id>")
@admin_required
def admin_remove_team_member(member_id: int) -> Any:
    """Remove a user from a team."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get team_id for redirect
        cursor.execute("SELECT team_id FROM team_members WHERE id = %s", (member_id,))
        result = cursor.fetchone()

        if not result:
            flash("Member not found", "danger")
            return redirect(url_for("admin_teams"))

        team_id = result[0]

        # Remove user from team
        cursor.execute("DELETE FROM team_members WHERE id = %s", (member_id,))

        conn.commit()
        flash("Member removed from team successfully", "success")
        return redirect(url_for("admin_team_members", team_id=team_id))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_remove_team_member: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route("/admin/update_team_score/<int:team_id>", methods=["POST"])
@admin_required
def admin_update_team_score(team_id: int) -> Any:
    """Update a team's score manually."""
    score = request.form.get("score")

    if not score or not score.isdigit():
        flash("Valid score is required", "danger")
        return redirect(url_for("admin_teams"))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if score exists
        cursor.execute("SELECT id FROM team_scores WHERE team_id = %s", (team_id,))
        score_record = cursor.fetchone()

        if score_record:
            # Update existing score
            cursor.execute(
                """
                UPDATE team_scores
                SET score = %s, updated_at = CURRENT_TIMESTAMP
                WHERE team_id = %s
            """,
                (score, team_id),
            )
        else:
            # Insert new score
            cursor.execute(
                """
                INSERT INTO team_scores (team_id, score)
                VALUES (%s, %s)
            """,
                (team_id, score),
            )

        conn.commit()
        flash("Team score updated successfully", "success")
        return redirect(url_for("admin_teams"))
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error in admin_update_team_score: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin_teams"))
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


# ---------- ADMIN CONTENT MANAGEMENT ROUTES ----------


# Quiz management
@app.route("/admin/view_quiz/<int:quiz_id>")
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
            flash("Quiz not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # Parse options from JSON
        options = safely_parse_options(quiz["options"])
    except Exception as e:
        logger.error(f"Admin view quiz error: {str(e)}")
        flash(f"Error viewing quiz: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/view_quiz.html", quiz=quiz, options=options)


@app.route("/admin/edit_quiz/<int:quiz_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_quiz(quiz_id: int) -> Any:
    """Edit a quiz question with multiple bootcamp type support."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM quizzes WHERE id=%s", (quiz_id,))
        quiz = cursor.fetchone()

        if not quiz:
            flash("Quiz not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # Parse options from JSON
        options = safely_parse_options(quiz["options"])

        # Get current tags assigned to this quiz
        cursor.execute(
            "SELECT tag_id FROM content_tags WHERE content_type = %s AND content_id = %s",
            ("quiz", quiz_id),
        )
        tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        # Get current bootcamp types from tags
        cursor.execute(
            """
            SELECT t.name FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name = 'Bootcamp Type'
        """,
            ("quiz", quiz_id),
        )
        current_bootcamp_types = [row["name"] for row in cursor.fetchall()]

        # If no bootcamp types in tags, use the camp field as fallback
        if not current_bootcamp_types and quiz["camp"]:
            current_bootcamp_types = [quiz["camp"]]

        # Get available tags (excluding bootcamp type tags for separate handling)
        available_tags = get_available_tags_grouped()

        # Get non-bootcamp tag IDs for the additional tags section
        cursor.execute(
            """
            SELECT ct.tag_id FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name != 'Bootcamp Type'
        """,
            ("quiz", quiz_id),
        )
        additional_tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        if request.method == "POST":
            try:
                # Get form data
                data = request.form
                unit_id = data["unit_id"]
                question = data["question"]
                options = [data[f"option{i}"] for i in range(1, 4)]
                correct_answer = int(data["correct_answer"])
                explanation = data["explanation"]
                selected_bootcamp_types = request.form.getlist("bootcamp_types")
                selected_additional_tags = [
                    int(tag_id) for tag_id in request.form.getlist("tags")
                ]

                # Validation
                if not selected_bootcamp_types:
                    flash("Please select at least one bootcamp type.", "danger")
                    return render_template(
                        "admin/edit_quiz.html",
                        quiz=quiz,
                        options=options,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Validate bootcamp types
                invalid_camps = [
                    camp
                    for camp in selected_bootcamp_types
                    if not validate_bootcamp_type(camp)
                ]
                if invalid_camps:
                    flash(
                        f'Invalid bootcamp types: {", ".join(invalid_camps)}', "danger"
                    )
                    return render_template(
                        "admin/edit_quiz.html",
                        quiz=quiz,
                        options=options,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Use first selected bootcamp type for the main camp field (backward compatibility)
                primary_camp = selected_bootcamp_types[0]

                # Update quiz in database
                cursor.execute(
                    """
                    UPDATE quizzes
                    SET unit_id=%s, question=%s, options=%s, correct_answer=%s, explanation=%s, camp=%s
                    WHERE id=%s
                """,
                    (
                        unit_id,
                        question,
                        json.dumps(options),
                        correct_answer,
                        explanation,
                        primary_camp,
                        quiz_id,
                    ),
                )

                # Prepare tags to assign
                tags_to_assign = []

                # Add bootcamp type tags
                for bootcamp_type in selected_bootcamp_types:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                        (bootcamp_type,),
                    )
                    bootcamp_tag = cursor.fetchone()
                    if bootcamp_tag:
                        tags_to_assign.append(bootcamp_tag["id"])
                    else:
                        logger.warning(
                            f"No tag found for bootcamp type: {bootcamp_type}"
                        )

                # Add additional selected tags
                tags_to_assign.extend(selected_additional_tags)

                # Remove duplicates
                tags_to_assign = list(set(tags_to_assign))

                # Assign all tags (this will replace existing tags)
                success = assign_content_tags("quiz", quiz_id, tags_to_assign)

                conn.commit()

                if success:
                    flash("Quiz updated successfully!", "success")
                    logger.info(
                        f"Quiz {quiz_id} updated with bootcamp types: {selected_bootcamp_types}"
                    )
                else:
                    flash(
                        "Quiz updated, but there was an issue with tag assignment.",
                        "warning",
                    )

                return redirect(url_for("admin_manage_content"))

            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating quiz: {str(e)}")
                flash(f"Error updating quiz: {str(e)}", "danger")

        cursor.close()

    except Exception as e:
        logger.error(f"Admin edit quiz error: {str(e)}")
        flash(f"Error loading quiz: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/edit_quiz.html",
        quiz=quiz,
        options=options,
        available_tags=available_tags,
        tag_ids=additional_tag_ids,
        current_bootcamp_types=current_bootcamp_types,
        camps=CAMPS,
    )


@app.route("/admin/delete_quiz/<int:quiz_id>")
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
        flash("Quiz deleted successfully", "success")
    except Exception as e:
        logger.error(f"Admin delete quiz error: {str(e)}")
        flash(f"Error deleting quiz: {str(e)}", "danger")
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for("admin_manage_content"))


# Material management
@app.route("/admin/view_material/<int:material_id>")
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
            flash("Material not found", "danger")
            return redirect(url_for("admin_manage_content"))
    except Exception as e:
        logger.error(f"Admin view material error: {str(e)}")
        flash(f"Error viewing material: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/view_material.html", material=material)


@app.route("/admin/delete_material/<int:material_id>")
@admin_required
def admin_delete_material(material_id: int) -> Any:
    """Delete learning material."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT file_path FROM materials WHERE id=%s", (material_id,))
        material = cursor.fetchone()

        # Delete the file if it exists
        if material and material["file_path"]:
            file_path = os.path.join(UPLOAD_FOLDER, material["file_path"])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except BaseException:
                    logger.error(f"Could not delete file {file_path}")

        cursor.execute("DELETE FROM materials WHERE id=%s", (material_id,))
        conn.commit()
        cursor.close()
        flash("Material deleted successfully", "success")
    except Exception as e:
        logger.error(f"Admin delete material error: {str(e)}")
        flash(f"Error deleting material: {str(e)}", "danger")
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for("admin_manage_content"))


# Video management
@app.route("/admin/view_video/<int:video_id>")
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
            flash("Video not found", "danger")
            return redirect(url_for("admin_manage_content"))
    except Exception as e:
        logger.error(f"Admin view video error: {str(e)}")
        flash(f"Error viewing video: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/view_video.html", video=video)


@app.route("/admin/edit_video/<int:video_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_video(video_id: int) -> Any:
    """Edit video details with multiple bootcamp type support."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM videos WHERE id=%s", (video_id,))
        video = cursor.fetchone()

        if not video:
            flash("Video not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # Get current tags assigned to this video
        cursor.execute(
            "SELECT tag_id FROM content_tags WHERE content_type = %s AND content_id = %s",
            ("video", video_id),
        )
        tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        # Get current bootcamp types from tags
        cursor.execute(
            """
            SELECT t.name FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name = 'Bootcamp Type'
        """,
            ("video", video_id),
        )
        current_bootcamp_types = [row["name"] for row in cursor.fetchall()]

        # If no bootcamp types in tags, use the camp field as fallback
        if not current_bootcamp_types and video["camp"]:
            current_bootcamp_types = [video["camp"]]

        # Get available tags (excluding bootcamp type tags for separate handling)
        available_tags = get_available_tags_grouped()

        # Get non-bootcamp tag IDs for the additional tags section
        cursor.execute(
            """
            SELECT ct.tag_id FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name != 'Bootcamp Type'
        """,
            ("video", video_id),
        )
        additional_tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        if request.method == "POST":
            try:
                # Get form data
                title = request.form["title"]
                youtube_url = request.form["youtube_url"]
                description = request.form["description"]
                unit_id = request.form["unit_id"]
                selected_bootcamp_types = request.form.getlist("bootcamp_types")
                selected_additional_tags = [
                    int(tag_id) for tag_id in request.form.getlist("tags")
                ]

                # Validation
                if not selected_bootcamp_types:
                    flash("Please select at least one bootcamp type.", "danger")
                    return render_template(
                        "admin/edit_video.html",
                        video=video,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Validate bootcamp types
                invalid_camps = [
                    camp
                    for camp in selected_bootcamp_types
                    if not validate_bootcamp_type(camp)
                ]
                if invalid_camps:
                    flash(
                        f'Invalid bootcamp types: {", ".join(invalid_camps)}', "danger"
                    )
                    return render_template(
                        "admin/edit_video.html",
                        video=video,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Use first selected bootcamp type for the main camp field (backward compatibility)
                primary_camp = selected_bootcamp_types[0]

                # Extract YouTube video ID
                if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
                    if "v=" in youtube_url:
                        youtube_id = youtube_url.split("v=")[1].split("&")[0]
                    elif "youtu.be/" in youtube_url:
                        youtube_id = youtube_url.split("youtu.be/")[1].split("?")[0]
                    else:
                        youtube_id = youtube_url
                else:
                    youtube_id = youtube_url

                # Update video in database
                cursor.execute(
                    """
                    UPDATE videos
                    SET unit_id=%s, title=%s, youtube_url=%s, description=%s, camp=%s
                    WHERE id=%s
                """,
                    (unit_id, title, youtube_id, description, primary_camp, video_id),
                )

                # Prepare tags to assign
                tags_to_assign = []

                # Add bootcamp type tags
                for bootcamp_type in selected_bootcamp_types:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                        (bootcamp_type,),
                    )
                    bootcamp_tag = cursor.fetchone()
                    if bootcamp_tag:
                        tags_to_assign.append(bootcamp_tag["id"])
                    else:
                        logger.warning(
                            f"No tag found for bootcamp type: {bootcamp_type}"
                        )

                # Add additional selected tags
                tags_to_assign.extend(selected_additional_tags)

                # Remove duplicates
                tags_to_assign = list(set(tags_to_assign))

                # Assign all tags (this will replace existing tags)
                success = assign_content_tags("video", video_id, tags_to_assign)

                conn.commit()

                if success:
                    flash("Video updated successfully!", "success")
                    logger.info(
                        f"Video {video_id} updated with bootcamp types: {selected_bootcamp_types}"
                    )
                else:
                    flash(
                        "Video updated, but there was an issue with tag assignment.",
                        "warning",
                    )

                return redirect(url_for("admin_manage_content"))

            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating video: {str(e)}")
                flash(f"Error updating video: {str(e)}", "danger")

        cursor.close()

    except Exception as e:
        logger.error(f"Admin edit video error: {str(e)}")
        flash(f"Error loading video: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/edit_video.html",
        video=video,
        available_tags=available_tags,
        tag_ids=additional_tag_ids,
        current_bootcamp_types=current_bootcamp_types,
        camps=CAMPS,
    )


@app.route("/admin/delete_video/<int:video_id>")
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
        flash("Video deleted successfully", "success")
    except Exception as e:
        logger.error(f"Admin delete video error: {str(e)}")
        flash(f"Error deleting video: {str(e)}", "danger")
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for("admin_manage_content"))


# Project management
@app.route("/admin/view_project/<int:project_id>")
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
            flash("Project not found", "danger")
            return redirect(url_for("admin_manage_content"))
    except Exception as e:
        logger.error(f"Admin view project error: {str(e)}")
        flash(f"Error viewing project: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/view_project.html", project=project)


@app.route("/admin/edit_project/<int:project_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_project(project_id: int) -> Any:
    """Edit project details with multiple bootcamp type support."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        project = cursor.fetchone()

        if not project:
            flash("Project not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # Get current tags assigned to this project
        cursor.execute(
            "SELECT tag_id FROM content_tags WHERE content_type = %s AND content_id = %s",
            ("project", project_id),
        )
        tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        # Get current bootcamp types from tags
        cursor.execute(
            """
            SELECT t.name FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name = 'Bootcamp Type'
        """,
            ("project", project_id),
        )
        current_bootcamp_types = [row["name"] for row in cursor.fetchall()]

        # If no bootcamp types in tags, use the camp field as fallback
        if not current_bootcamp_types and project["camp"]:
            current_bootcamp_types = [project["camp"]]

        # Get available tags (excluding bootcamp type tags for separate handling)
        available_tags = get_available_tags_grouped()

        # Get non-bootcamp tag IDs for the additional tags section
        cursor.execute(
            """
            SELECT ct.tag_id FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE ct.content_type = %s AND ct.content_id = %s 
            AND tg.name != 'Bootcamp Type'
        """,
            ("project", project_id),
        )
        additional_tag_ids = [row["tag_id"] for row in cursor.fetchall()]

        if request.method == "POST":
            try:
                # Get form data
                title = request.form["title"]
                description = request.form["description"]
                resources = request.form["resources"]
                unit_id = request.form["unit_id"]
                deadline = request.form.get("deadline") or None
                selected_bootcamp_types = request.form.getlist("bootcamp_types")
                selected_additional_tags = [
                    int(tag_id) for tag_id in request.form.getlist("tags")
                ]

                # Validation
                if not selected_bootcamp_types:
                    flash("Please select at least one bootcamp type.", "danger")
                    return render_template(
                        "admin/edit_project.html",
                        project=project,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Validate bootcamp types
                invalid_camps = [
                    camp
                    for camp in selected_bootcamp_types
                    if not validate_bootcamp_type(camp)
                ]
                if invalid_camps:
                    flash(
                        f'Invalid bootcamp types: {", ".join(invalid_camps)}', "danger"
                    )
                    return render_template(
                        "admin/edit_project.html",
                        project=project,
                        available_tags=available_tags,
                        tag_ids=additional_tag_ids,
                        current_bootcamp_types=current_bootcamp_types,
                        camps=CAMPS,
                    )

                # Use first selected bootcamp type for the main camp field (backward compatibility)
                primary_camp = selected_bootcamp_types[0]

                # Update project in database
                cursor.execute(
                    """
                    UPDATE projects
                    SET unit_id=%s, title=%s, description=%s, resources=%s, camp=%s, deadline=%s
                    WHERE id=%s
                """,
                    (
                        unit_id,
                        title,
                        description,
                        resources,
                        primary_camp,
                        deadline,
                        project_id,
                    ),
                )

                # Prepare tags to assign
                tags_to_assign = []

                # Add bootcamp type tags
                for bootcamp_type in selected_bootcamp_types:
                    cursor.execute(
                        "SELECT id FROM tags WHERE name = %s AND is_active = TRUE",
                        (bootcamp_type,),
                    )
                    bootcamp_tag = cursor.fetchone()
                    if bootcamp_tag:
                        tags_to_assign.append(bootcamp_tag["id"])
                    else:
                        logger.warning(
                            f"No tag found for bootcamp type: {bootcamp_type}"
                        )

                # Add additional selected tags
                tags_to_assign.extend(selected_additional_tags)

                # Remove duplicates
                tags_to_assign = list(set(tags_to_assign))

                # Assign all tags (this will replace existing tags)
                success = assign_content_tags("project", project_id, tags_to_assign)

                conn.commit()

                if success:
                    flash("Project updated successfully!", "success")
                    logger.info(
                        f"Project {project_id} updated with bootcamp types: {selected_bootcamp_types}"
                    )
                else:
                    flash(
                        "Project updated, but there was an issue with tag assignment.",
                        "warning",
                    )

                return redirect(url_for("admin_manage_content"))

            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating project: {str(e)}")
                flash(f"Error updating project: {str(e)}", "danger")

        cursor.close()

    except Exception as e:
        logger.error(f"Admin edit project error: {str(e)}")
        flash(f"Error loading project: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/edit_project.html",
        project=project,
        available_tags=available_tags,
        tag_ids=additional_tag_ids,
        current_bootcamp_types=current_bootcamp_types,
        camps=CAMPS,
    )


@app.route("/admin/delete_project/<int:project_id>")
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
        flash("Project deleted successfully", "success")
    except Exception as e:
        logger.error(f"Admin delete project error: {str(e)}")
        flash(f"Error deleting project: {str(e)}", "danger")
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for("admin_manage_content"))


# Word management
@app.route("/admin/view_word/<int:word_id>")
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
            flash("Word not found", "danger")
            return redirect(url_for("admin_manage_content"))

        # JSONB is already converted to Python objects
        if not word.get("core_elements"):
            word["core_elements"] = []

    except Exception as e:
        logger.error(f"Admin view word error: {str(e)}")
        flash(f"Error viewing word: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template("admin/view_word.html", word=word)


@app.route("/admin/edit_word/<int:word_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_word(word_id: int) -> Any:
    """Edit AI vocabulary word."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM words WHERE id=%s", (word_id,))
        word = cursor.fetchone()
        if not word:
            flash("Word not found", "danger")
            return redirect(url_for("admin_manage_content"))

        cursor.execute(
            "SELECT tag_id FROM content_tags WHERE content_type = %s AND content_id = %s",
            ("word", word_id),
        )
        tag_ids = [row["tag_id"] for row in cursor.fetchall()]
        available_tags = get_available_tags_grouped()

        selected_bootcamp_types = []
        if tag_ids:
            cursor.execute(
                "SELECT name FROM tags WHERE id = ANY(%s) AND name IN ('Chinese', 'English', 'Middle East')",
                (tag_ids,),
            )
            bootcamp_tags = [row["name"] for row in cursor.fetchall()]
            selected_bootcamp_types = bootcamp_tags

        if not selected_bootcamp_types and word.get("camp"):
            selected_bootcamp_types = [word["camp"]]

        if request.method == "POST":
            unit_id = request.form["unit_id"]
            word_text = request.form["word"]
            section = request.form.get("section", 1)
            selected_bootcamp_types = request.form.getlist("bootcamp_types")
            one_sentence_version = request.form.get("one_sentence_version", "")
            daily_definition = request.form.get("daily_definition", "")
            life_metaphor = request.form.get("life_metaphor", "")
            visual_explanation = request.form.get("visual_explanation", "")
            scenario_theater = request.form.get("scenario_theater", "")
            misunderstandings = request.form.get("misunderstandings", "")
            reality_connection = request.form.get("reality_connection", "")
            thinking_bubble = request.form.get("thinking_bubble", "")
            smiling_conclusion = request.form.get("smiling_conclusion", "")
            core_elements = parse_core_elements(request.form)
            selected_tags = [int(tag_id) for tag_id in request.form.getlist("tags")]

            # ✅ Must select at least one bootcamp type
            if not selected_bootcamp_types:
                flash("Please select at least one bootcamp type.", "error")
                return render_template(
                    "admin/edit_word.html",
                    word=word,
                    available_tags=available_tags,
                    tag_ids=tag_ids,
                    selected_bootcamp_types=selected_bootcamp_types,
                )

            # ✅ Validate all selected bootcamp types
            for bootcamp_type in selected_bootcamp_types:
                if not validate_bootcamp_type(bootcamp_type):
                    flash(f"Invalid bootcamp type: {bootcamp_type}", "danger")
                    return render_template(
                        "admin/edit_word.html",
                        word=word,
                        available_tags=available_tags,
                        tag_ids=tag_ids,
                        selected_bootcamp_types=selected_bootcamp_types,
                    )

            primary_camp = selected_bootcamp_types[0]  # Use first as main camp

            cursor.execute(
                """
                UPDATE words
                SET unit_id=%s, word=%s, section=%s, camp=%s,
                    one_sentence_version=%s, daily_definition=%s, life_metaphor=%s, visual_explanation=%s,
                    core_elements=%s, scenario_theater=%s, misunderstandings=%s, reality_connection=%s,
                    thinking_bubble=%s, smiling_conclusion=%s
                WHERE id=%s
                """,
                (
                    unit_id,
                    word_text,
                    section,
                    primary_camp,
                    one_sentence_version,
                    daily_definition,
                    life_metaphor,
                    visual_explanation,
                    json.dumps(core_elements),
                    scenario_theater,
                    misunderstandings,
                    reality_connection,
                    thinking_bubble,
                    smiling_conclusion,
                    word_id,
                ),
            )
            conn.commit()

            # Handle bootcamp tags
            bootcamp_tags_to_assign = []
            for bootcamp_type in selected_bootcamp_types:
                cursor.execute("SELECT id FROM tags WHERE name = %s", (bootcamp_type,))
                bootcamp_tag = cursor.fetchone()
                if bootcamp_tag:
                    bootcamp_tags_to_assign.append(bootcamp_tag["id"])

            all_tags = bootcamp_tags_to_assign + selected_tags

            if all_tags:
                assign_content_tags("word", word_id, all_tags)

            flash("Word updated successfully", "success")
            return redirect(url_for("admin_manage_content"))
        cursor.close()
    except Exception as e:
        logger.error(f"Admin edit word error: {str(e)}")
        flash(f"Error editing word: {str(e)}", "danger")
        return redirect(url_for("admin_manage_content"))
    finally:
        if conn:
            release_db_connection(conn)

    return render_template(
        "admin/edit_word.html",
        word=word,
        available_tags=available_tags,
        tag_ids=tag_ids,
        selected_bootcamp_types=selected_bootcamp_types,
    )


@app.route("/admin/delete_word/<int:word_id>")
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
        flash("Word deleted successfully", "success")
    except Exception as e:
        logger.error(f"Admin delete word error: {str(e)}")
        flash(f"Error deleting word: {str(e)}", "danger")
    finally:
        if conn:
            release_db_connection(conn)
    return redirect(url_for("admin_manage_content"))


@app.route("/admin/view_submission/<int:submission_id>")
@admin_required
def view_submission(submission_id: int) -> Any:
    """View and download a user submission."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get submission details
        cursor.execute(
            """
            SELECT s.file_path, s.unit_id, s.user_id, u.username
            FROM submissions s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s
        """,
            (submission_id,),
        )

        submission = cursor.fetchone()
        cursor.close()

        if not submission or not submission["file_path"]:
            flash("Submission file not found in database", "error")
            return redirect(url_for("admin_submissions"))

        # Clean up the file path - remove any path prefix if present
        file_path = submission["file_path"]
        if "\\" in file_path:
            file_name = file_path.split("\\")[-1]
        elif "/" in file_path:
            file_name = file_path.split("/")[-1]
        else:
            file_name = file_path

        # Get full path to file
        full_path = os.path.join(UPLOAD_FOLDER, file_name)
        logger.info(f"Attempting to download: {full_path}")

        if not os.path.exists(full_path):
            flash(f"File not found on server: {file_name}", "error")
            return redirect(url_for("admin_submissions"))

        # Create a descriptive filename for the download
        download_name = (
            f"{submission['username']}_submission_{submission_id}_{file_name}"
        )

        # Send the file with explicit parameters
        return send_file(
            full_path,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=download_name,
        )

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for("admin_submissions"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/manage_documents")
@admin_required
def admin_manage_documents() -> Any:
    """FIXED: Manage documents stored in database."""
    documents = get_documents_from_database_admin()
    logger.info(f"📋 Admin viewing {len(documents)} documents")
    return render_template("admin/manage_documents.html", documents=documents)


def store_document_in_database(
    filename: str, content: bytes, content_type: str
) -> bool:
    """Store document content in database - FIXED VERSION."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First ensure the table exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stored_documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                content BYTEA NOT NULL,
                content_type VARCHAR(100),
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(filename)
            )
        """
        )

        # Insert or update document
        cursor.execute(
            """
            INSERT INTO stored_documents (filename, content, content_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (filename) 
            DO UPDATE SET 
                content = EXCLUDED.content, 
                content_type = EXCLUDED.content_type,
                upload_date = CURRENT_TIMESTAMP
            RETURNING id
        """,
            (filename, content, content_type),
        )

        doc_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        logger.info(f"✅ Document {filename} stored in database with ID: {doc_id}")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Error storing document in database: {str(e)}")
        return False
    finally:
        if conn:
            release_db_connection(conn)


def get_documents_from_database_admin() -> List[Dict[str, Any]]:
    """Get all documents from database for admin display."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure table exists first
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stored_documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                content BYTEA NOT NULL,
                content_type VARCHAR(100),
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(filename)
            )
        """
        )

        cursor.execute(
            """
            SELECT id, filename, content_type, upload_date, length(content) as size_bytes
            FROM stored_documents
            ORDER BY upload_date DESC
        """
        )

        documents = cursor.fetchall()
        cursor.close()

        # Format for display
        result = []
        for doc in documents:
            result.append(
                {
                    "id": doc[0],
                    "name": doc[1],
                    "type": doc[2] or "Unknown",
                    "added": (
                        doc[3].strftime("%Y-%m-%d %H:%M:%S") if doc[3] else "Unknown"
                    ),
                    "size": f"{doc[4] / 1024 / 1024:.2f} MB" if doc[4] else "Unknown",
                }
            )

        logger.info(f"📄 Retrieved {len(result)} documents for admin display")
        return result

    except Exception as e:
        logger.error(f"❌ Error getting documents from database: {str(e)}")
        return []
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/upload_document", methods=["GET", "POST"])
@admin_required
def admin_upload_document() -> Any:
    """FIXED: Upload documents and store in database properly."""
    if request.method == "POST":
        # Check if file was uploaded
        if "document" not in request.files:
            flash("No file selected", "error")
            return redirect(request.url)

        file = request.files["document"]

        # Check if file was selected
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(request.url)

        # Check file extension
        allowed_extensions = [".pdf", ".ppt", ".pptx", ".txt", ".doc", ".docx"]
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            flash("Invalid file type. Allowed: PDF, PPT, PPTX, TXT, DOC, DOCX", "error")
            return redirect(request.url)

        try:
            # Read file content
            filename = secure_filename(file.filename)
            file_content = file.read()
            content_type = file.content_type or "application/octet-stream"

            logger.info(f"📤 Uploading: {filename} ({len(file_content)} bytes)")

            # Store in database
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO stored_documents (filename, content, content_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (filename) 
                DO UPDATE SET 
                    content = EXCLUDED.content, 
                    content_type = EXCLUDED.content_type,
                    upload_date = CURRENT_TIMESTAMP
                RETURNING id
            """,
                (filename, file_content, content_type),
            )

            doc_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            release_db_connection(conn)

            # Reset QA system to reload documents
            global _qa_instance
            _qa_instance = None

            flash(
                f"Document '{filename}' uploaded successfully! QA system will reload.",
                "success",
            )
            logger.info(f"✅ Successfully uploaded {filename}")

        except Exception as e:
            logger.error(f"❌ Upload error: {str(e)}")
            flash(f"Error uploading document: {str(e)}", "error")

        return redirect(url_for("admin_manage_documents"))

    # GET request - show upload form
    return render_template("admin/upload_document.html")


@app.route("/admin/delete_document/<filename>")
@admin_required
def admin_delete_document(filename: str) -> Any:
    """FIXED: Delete a document from database."""
    try:
        # Security check
        safe_filename = secure_filename(filename)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete from database
        cursor.execute(
            "DELETE FROM stored_documents WHERE filename = %s RETURNING id",
            (safe_filename,),
        )
        deleted = cursor.fetchone()

        if deleted:
            conn.commit()

            # Reset QA system
            global _qa_instance
            _qa_instance = None

            flash(f"Document '{safe_filename}' deleted successfully.", "success")
            logger.info(f"🗑️ Deleted document: {safe_filename}")
        else:
            flash(f"Document '{safe_filename}' not found.", "error")

        cursor.close()
        release_db_connection(conn)

    except Exception as e:
        logger.error(f"❌ Error deleting document: {str(e)}")
        flash(f"Error deleting document: {str(e)}", "error")

    return redirect(url_for("admin_manage_documents"))

@app.route("/admin/setup_followup_system")
@admin_required
def setup_followup_system():
    """Setup the follow-up email system."""
    try:
        create_followup_table()
        flash("Follow-up email system initialized successfully!", "success")
    except Exception as e:
        flash(f"Error setting up follow-up system: {str(e)}", "error")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/followup_history")
@admin_required
def admin_followup_history():
    """View follow-up email history."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT fe.*, u.username, u.email
            FROM followup_emails fe
            JOIN users u ON fe.user_id = u.id
            ORDER BY fe.sent_at DESC
            LIMIT 100
        """)
        
        followups = cursor.fetchall()
        cursor.close()
        
        return render_template("admin/followup_history.html", followups=followups)
        
    except Exception as e:
        logger.error(f"Error getting follow-up history: {str(e)}")
        flash(f"Error loading follow-up history: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/force_qa_reload")
@admin_required
def admin_force_qa_reload():
    """FIXED: Force QA system to reload from database."""
    try:
        # Reset global QA instance
        global _qa_instance
        _qa_instance = None

        # Force reload from qa.py
        from qa import initialize_qa

        qa_system = initialize_qa()

        return f"""
        <div style="font-family: monospace; padding: 20px; background: #d4edda;">
            <h2>✅ QA System Force Reload Complete!</h2>
            <p>QA system reinitialized with database documents.</p>
            <p><strong>Wait 30 seconds, then test AI assistant!</strong></p>
            <p><a href="/ai_status">🔍 Check QA Status</a></p>
            <p><a href="/ai_assistant">🤖 Test AI Assistant</a></p>
        </div>
        """
    except Exception as e:
        return f"""
        <div style="font-family: monospace; padding: 20px; background: #f8d7da;">
            <h2>❌ Force Reload Failed!</h2>
            <p>Error: {str(e)}</p>
        </div>
        """

@app.route("/admin/check_database_documents")
@admin_required
def admin_check_database_documents():
    """Check what documents are actually in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'stored_documents'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            return """
            <div style="font-family: monospace; padding: 20px; background: #fff3cd;">
                <h2>⚠️ Table Does Not Exist!</h2>
                <p>The stored_documents table has not been created yet.</p>
                <p><a href="/admin/test_database_storage">🔧 Create Table & Test</a></p>
            </div>
            """

        # Get all documents
        cursor.execute("""
            SELECT id, filename, content_type, upload_date, length(content) as size_bytes
            FROM stored_documents
            ORDER BY upload_date DESC
        """)
        documents = cursor.fetchall()
        
        cursor.close()
        release_db_connection(conn)

        # Build rows safely
        rows_html = ""
        for doc in documents:
            rows_html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{doc[0]}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{doc[1]}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{doc[2] or "Unknown"}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{doc[4] / 1024:.1f} KB</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{doc[3].strftime("%Y-%m-%d %H:%M:%S") if doc[3] else "Unknown"}</td>
                </tr>
            """

        # Final HTML
        html = f"""
        <div style="font-family: monospace; padding: 20px; background: #f8f9fa;">
            <h2>📋 Database Documents Report</h2>
            <p><strong>Table exists:</strong> ✅ Yes</p>
            <p><strong>Document count:</strong> {len(documents)}</p>
            {'<p style="color: orange;">⚠️ No documents found in database!</p>' if not documents else ''}
            
            {f'''
            <h3>📄 Documents in Database:</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background: #e9ecef;">
                    <th style="border: 1px solid #dee2e6; padding: 8px;">ID</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Filename</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Type</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Size</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Upload Date</th>
                </tr>
                {rows_html}
            </table>
            ''' if documents else ''}
            
            <br>
            <p><a href="/admin/upload_document" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">📤 Upload Document</a></p>
            <p><a href="/debug/qa_system" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔍 Check QA Status</a></p>
        </div>
        """
        return html

    except Exception as e:
        return f"""
        <div style="font-family: monospace; padding: 20px; background: #f8d7da;">
            <h2>❌ Database Check Error!</h2>
            <p>Error: {str(e)}</p>
        </div>
        """

    
@app.route("/admin/rebuild_qa_system")
@admin_required
def admin_rebuild_qa() -> Any:
    """Rebuild the simplified Q&A system from scratch."""
    try:
        # Check if we have documents
        supported_files = []
        for root, dirs, files in os.walk(DOCUMENTS_DIR):
            for file in files:
                if file.lower().endswith((".pdf", ".pptx", ".ppt", ".txt")):
                    supported_files.append(file)

        if supported_files:
            # Reset and reinitialize the QA system
            from qa import initialize_qa

            global _qa_instance
            _qa_instance = None  # Reset global instance

            # Remove existing vector database to force rebuild
            vector_db_path = os.path.join(os.getcwd(), "vector_db")
            if os.path.exists(vector_db_path):
                import shutil

                shutil.rmtree(vector_db_path)
                logger.info("Removed existing vector database for rebuild")

            # Initialize fresh system
            qa_system = initialize_qa(
                documents_dir=DOCUMENTS_DIR,
                llama_model_path=(
                    LLAMA_MODEL_PATH if "LLAMA_MODEL_PATH" in globals() else None
                ),
            )

            flash(
                f"Q&A system rebuilt successfully with {len(supported_files)} documents",
                "success",
            )

        else:
            flash("No documents found to build the Q&A system", "warning")

    except Exception as e:
        logger.error(f"Error rebuilding QA system: {str(e)}")
        flash(f"Error rebuilding QA system: {str(e)}", "danger")

    return redirect(url_for("admin_manage_documents"))


@app.route("/admin/qa_status")
@admin_required
def admin_qa_status() -> Any:
    """Get detailed QA system status for admin."""
    try:
        from qa import get_system_status, get_qa_system

        status = get_system_status(
            documents_dir=DOCUMENTS_DIR,
            llama_model_path=(
                LLAMA_MODEL_PATH if "LLAMA_MODEL_PATH" in globals() else None
            ),
        )

        qa_system = get_qa_system()

        # Get additional details
        vector_db_path = os.path.join(os.getcwd(), "vector_db")
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
            "ready": status.get("ready", False),
            "initializing": status.get("initializing", False),
            "error": status.get("error"),
            "document_count": status.get("document_count", 0),
            "llama_available": status.get("llama_available", False),
            "vector_db_exists": vector_db_exists,
            "vector_db_size_mb": vector_db_size_mb,
            "documents_dir": DOCUMENTS_DIR,
            "qa_system_initialized": qa_system is not None,
        }

        # If AJAX/JSON request, return JSON
        if (
            request.accept_mimetypes["application/json"]
            >= request.accept_mimetypes["text/html"]
        ):
            return jsonify(status_info)
        # Otherwise, render visual template
        return render_template("admin/qa_status.html", status=status_info)

    except Exception as e:
        logger.error(f"Error getting QA status: {str(e)}")
        if (
            request.accept_mimetypes["application/json"]
            >= request.accept_mimetypes["text/html"]
        ):
            return (
                jsonify({"error": str(e), "ready": False, "initializing": False}),
                500,
            )
        return render_template(
            "admin/qa_status.html",
            status={"error": str(e), "ready": False, "initializing": False},
        )


def ensure_specific_cohort_tags():
    """Ensure specific cohort tags from PDF exist."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get Cohort tag group ID
        cursor.execute("SELECT id FROM tag_groups WHERE name = 'Cohort'")
        cohort_group = cursor.fetchone()

        if cohort_group:
            group_id = cohort_group[0]

            # Specific cohort tags from PDF
            cohort_tags = [
                (
                    "Chinese Cohort 1 (March)",
                    "Chinese AI Bootcamp - Cohort 1 (March 2025)",
                ),
                ("Chinese Cohort 2 (May)", "Chinese AI Bootcamp - Cohort 2 (May 2025)"),
                ("English Cohort 1 (May)", "English AI Bootcamp - Cohort 1 (May 2025)"),
                (
                    "Middle East Cohort 1 (May)",
                    "Middle East AI Bootcamp - Cohort 1 (May 2025)",
                ),
            ]

            for tag_name, description in cohort_tags:
                cursor.execute(
                    """
                    INSERT INTO tags (tag_group_id, name, description) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (tag_group_id, name) DO NOTHING
                """,
                    (group_id, tag_name, description),
                )

        conn.commit()
        logger.info("Specific cohort tags ensured")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error ensuring cohort tags: {str(e)}")
    finally:
        if conn:
            cursor.close()
            release_db_connection(conn)


@app.route("/admin/export_advanced", methods=["GET", "POST"])
@admin_required
def admin_export_advanced():
    """Advanced export with real data calculations."""
    
    # Get filter parameters
    student_types = request.args.getlist("student_type")
    selected_tags = request.args.getlist("tags")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build WHERE clause for filters
        where_conditions = []
        params = []
        
        if student_types:
            where_conditions.append("u.student_type = ANY(%s)")
            params.append(student_types)
        
        if selected_tags:
            where_conditions.append("""
                EXISTS (
                    SELECT 1 FROM user_tags ut 
                    JOIN tags t ON ut.tag_id = t.id 
                    WHERE ut.user_id = u.id AND t.name = ANY(%s)
                )
            """)
            params.append(selected_tags)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Calculate assignment submission rates
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN s.id IS NOT NULL THEN 1 END) as users_with_submissions,
                COUNT(DISTINCT s.id) as total_submissions
            FROM users u
            LEFT JOIN submissions s ON u.id = s.user_id
            {where_clause}
        """, params)
        
        assignment_stats = cursor.fetchone()
        
        # Calculate assignment rate
        total_users = assignment_stats["total_users"] or 0
        users_with_submissions = assignment_stats["users_with_submissions"] or 0
        assignment_rate = round((users_with_submissions / total_users * 100) if total_users > 0 else 0, 1)
        
        # Calculate quiz completion rates (challenge assignments)
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT qa.user_id) as users_with_quiz_attempts
            FROM users u
            LEFT JOIN quiz_attempts qa ON u.id = qa.user_id AND qa.score IS NOT NULL
            {where_clause}
        """, params)
        
        quiz_stats = cursor.fetchone()
        quiz_total = quiz_stats["total_users"] or 0
        quiz_completed = quiz_stats["users_with_quiz_attempts"] or 0
        challenge_rate = round((quiz_completed / quiz_total * 100) if quiz_total > 0 else 0, 1)
        
        # Get students who need follow-up (no submissions)
        cursor.execute(f"""
            SELECT DISTINCT u.id, u.username, u.email, u.camp
            FROM users u
            LEFT JOIN submissions s ON u.id = s.user_id
            {where_clause}
            {'AND' if where_clause else 'WHERE'} s.id IS NULL
            ORDER BY u.username
            LIMIT 50
        """, params)
        
        followup_students = cursor.fetchall()
        
        # Get assignment details for all users
        cursor.execute(f"""
            SELECT 
                u.username as name,
                u.camp as department,
                COALESCE(u.cohort_name, 'No Cohort') as cohort,
                COUNT(s.id) as submission_count,
                COUNT(qa.id) as quiz_attempts,
                MAX(s.submitted_at) as last_submission
            FROM users u
            LEFT JOIN submissions s ON u.id = s.user_id
            LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
            {where_clause}
            GROUP BY u.id, u.username, u.camp, u.cohort_name
            ORDER BY u.username
        """, params)
        
        assignment_details_raw = cursor.fetchall()
        
        # Format assignment details
        assignment_details = []
        for row in assignment_details_raw:
            assignment_details.append({
                "name": row["name"],
                "department": row["department"] or "Unknown",
                "cohort": row["cohort"],
                "assignment_link": f"/admin/user_progress/{row['name']}",
                "submission_count": row["submission_count"],
                "quiz_attempts": row["quiz_attempts"],
                "last_submission": row["last_submission"].strftime("%Y-%m-%d") if row["last_submission"] else "Never"
            })
        
        # Calculate trend (simple comparison with last 30 days)
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN submitted_at >= NOW() - INTERVAL '30 days' THEN 1 END) as recent_submissions,
                COUNT(CASE WHEN submitted_at >= NOW() - INTERVAL '60 days' AND submitted_at < NOW() - INTERVAL '30 days' THEN 1 END) as previous_submissions
            FROM submissions s
            JOIN users u ON s.user_id = u.id
            """ + (where_clause.replace("WHERE", "WHERE") if where_clause else ""))
        
        trend_data = cursor.fetchone()
        recent = trend_data["recent_submissions"] or 0
        previous = trend_data["previous_submissions"] or 0
        
        if previous > 0:
            trend_pct = round(((recent - previous) / previous) * 100, 1)
            if trend_pct > 0:
                trend_text = f"↑ {trend_pct}%"
            elif trend_pct < 0:
                trend_text = f"↓ {abs(trend_pct)}%"
            else:
                trend_text = "→ 0%"
        else:
            trend_text = "No data"
        
        # Build summary
        summary = {
            "assignment_rate": assignment_rate,
            "assignment_submitted": users_with_submissions,
            "assignment_total": total_users,
            "challenge_rate": challenge_rate,
            "challenge_submitted": quiz_completed,
            "challenge_total": quiz_total,
            "trend_text": trend_text,
        }
        
        cursor.close()
        
        # Get available data for filters
        available_tags = get_available_tags_grouped()
        
        # Get cohorts
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT name FROM cohorts WHERE is_active = TRUE ORDER BY name")
        cohorts = cursor.fetchall()
        
        # Get course units
        cursor.execute("SELECT DISTINCT unit_id FROM materials ORDER BY unit_id")
        course_units_result = cursor.fetchall()
        course_units = [row["unit_id"] for row in course_units_result]
        
        # Get tags
        cursor.execute("SELECT name FROM tags WHERE is_active = TRUE ORDER BY name")
        tags = cursor.fetchall()
        
        cursor.close()
        
        return render_template(
            "admin/export_advanced.html",
            available_tags=available_tags,
            summary=summary,
            followup_students=followup_students,
            assignment_details=assignment_details,
            cohorts=cohorts,
            course_units=course_units,
            tags=tags,
            current_filters={
                "student_types": student_types,
                "selected_tags": selected_tags
            }
        )
        
    except Exception as e:
        logger.error(f"Error in export_advanced: {str(e)}")
        flash(f"Error loading export data: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/send_followup_email", methods=["POST"])
@admin_required
def send_followup_email():
    """Send a gentle follow-up email to a student."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        username = data.get('username')
        email = data.get('email')
        
        if not all([user_id, username, email]):
            return jsonify({"success": False, "error": "Missing required data"}), 400
        
        # Get user details from database
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT u.*, 
                   COUNT(s.id) as submission_count,
                   COUNT(qa.id) as quiz_attempts,
                   MAX(s.submitted_at) as last_submission
            FROM users u
            LEFT JOIN submissions s ON u.id = s.user_id
            LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
            WHERE u.id = %s
            GROUP BY u.id
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        # Create personalized email content
        subject = "Friendly Reminder - Your Learning Journey with 51Talk AI"
        
        # Determine appropriate greeting and content based on user's camp
        camp_specific_content = {
            "Chinese": "中文训练营",
            "English": "English Bootcamp", 
            "Middle East": "Middle East Bootcamp"
        }
        
        camp_name = camp_specific_content.get(user['camp'], "AI Bootcamp")
        
        # Create email body
        email_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; color: #666; }}
                .highlight {{ background-color: #e8f5e9; padding: 10px; border-left: 4px solid #4CAF50; margin: 15px 0; }}
                .button {{ background-color: #4CAF50; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>51Talk AI Learning Platform</h2>
                <p>Your Learning Journey Continues</p>
            </div>
            
            <div class="content">
                <p>Hi {username},</p>
                
                <p>I hope this message finds you well! I wanted to reach out with a friendly reminder about your learning journey in our <strong>{camp_name}</strong>.</p>
                
                <div class="highlight">
                    <p><strong>We noticed you haven't submitted any assignments yet</strong>, and we wanted to make sure you have everything you need to succeed.</p>
                </div>
                
                <p>Here's what you can do right now:</p>
                <ul>
                    <li>📚 <strong>Access your course materials</strong> - Log in to review the latest lessons</li>
                    <li>🎯 <strong>Complete assignments</strong> - Start with the unit exercises at your own pace</li>
                    <li>💬 <strong>Ask our AI assistant</strong> - Get instant help with any questions</li>
                    <li>🧪 <strong>Take quizzes</strong> - Test your understanding and track your progress</li>
                </ul>
                
                <p>Remember, learning is a journey, not a race. Every expert was once a beginner, and every step forward is progress worth celebrating.</p>
                
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{url_for('dashboard', _external=True)}" class="button">
                        Continue Your Learning Journey
                    </a>
                </div>
                
                <p><strong>Need help or have questions?</strong> Don't hesitate to reach out! We're here to support you every step of the way.</p>
                
                <p>You've got this! 🚀</p>
                
                <p>Best regards,<br>
                <strong>51Talk AI Learning Team</strong><br>
                <em>Supporting your AI learning journey</em></p>
            </div>
            
            <div class="footer">
                <p>This is an automated reminder to help you stay on track with your learning goals.</p>
                <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version for email clients that don't support HTML
        text_body = f"""
        Hi {username},

        I hope this message finds you well! I wanted to reach out with a friendly reminder about your learning journey in our {camp_name}.

        We noticed you haven't submitted any assignments yet, and we wanted to make sure you have everything you need to succeed.

        Here's what you can do right now:
        - Access your course materials - Log in to review the latest lessons
        - Complete assignments - Start with the unit exercises at your own pace  
        - Ask our AI assistant - Get instant help with any questions
        - Take quizzes - Test your understanding and track your progress

        Remember, learning is a journey, not a race. Every expert was once a beginner, and every step forward is progress worth celebrating.

        Need help or have questions? Don't hesitate to reach out! We're here to support you every step of the way.

        You've got this!

        Best regards,
        51Talk AI Learning Team
        Supporting your AI learning journey

        Visit your dashboard: {url_for('dashboard', _external=True)}
        """
        
        # Send email
        msg = Message(subject, recipients=[email])
        msg.body = text_body
        msg.html = email_body
        
        mail.send(msg)
        
        # Log the follow-up in database (optional - for tracking)
        try:
            cursor.execute("""
                INSERT INTO followup_emails (user_id, sent_by, sent_at, email_type, subject)
                VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s)
            """, (user_id, session.get('admin_username', 'admin'), 'assignment_reminder', subject))
            conn.commit()
        except Exception as log_error:
            # If logging fails, don't fail the whole operation
            logger.warning(f"Failed to log follow-up email: {str(log_error)}")
        
        cursor.close()
        release_db_connection(conn)
        
        logger.info(f"Follow-up email sent to {username} ({email}) by {session.get('admin_username', 'admin')}")
        
        return jsonify({
            "success": True, 
            "message": f"Follow-up email sent successfully to {username}!"
        })
        
    except Exception as e:
        logger.error(f"Error sending follow-up email: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route("/admin/add_content_unified", methods=["GET", "POST"])
@admin_required
def admin_add_content_unified():
    """Unified content creation interface matching PDF mockup."""
    if request.method == "POST":
        content_type = request.form.get("content_type")
        selected_tags = request.form.getlist("visibility_tags")

        # Handle POST logic here based on content_type
        flash(f"Content creation for {content_type} not yet fully implemented", "info")
        return redirect(url_for("admin_add_content_unified"))

    available_tags = get_available_tags_grouped()
    return render_template(
        "admin/add_content_unified.html",
        available_tags=available_tags,
        content_types=["quiz", "material", "video", "project", "word"],
    )


@app.route("/admin/stream_file/<path:filename>")
@admin_required
def stream_file(filename: str) -> Any:
    """Stream a file directly to the browser."""
    try:
        # Extract just the filename portion if it contains path elements
        if "\\" in filename:
            clean_filename = filename.split("\\")[-1]
        elif "/" in filename:
            clean_filename = filename.split("/")[-1]
        else:
            clean_filename = filename

        file_path = os.path.join(UPLOAD_FOLDER, clean_filename)

        if not os.path.exists(file_path):
            return f"File not found: {file_path}", 404

        # Get file size
        file_size = os.path.getsize(file_path)

        # Open the file in binary mode
        with open(file_path, "rb") as f:
            # Stream the file in chunks
            def generate():
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    yield chunk

        # Set appropriate headers
        headers = {
            "Content-Disposition": f'attachment; filename="{os.path.basename(clean_filename)}"',
            "Content-Type": "application/octet-stream",
            "Content-Length": str(file_size),
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        # Return a streaming response
        return app.response_class(generate(), headers=headers, direct_passthrough=True)

    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        return f"Error: {str(e)}", 500


@app.route("/health")
def health_check():
    """Comprehensive health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
    }

    # Check database connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check QA system
    try:
        qa_system = get_qa_system()
        if qa_system and qa_system.vector_store_manager.is_ready():
            health_status["services"]["qa_system"] = "healthy"
        else:
            health_status["services"]["qa_system"] = "initializing"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["qa_system"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check HuggingFace API
    try:
        from qa import get_hf_config

        api_key, model = get_hf_config()
        if api_key and model:
            health_status["services"]["huggingface"] = "configured"
        else:
            health_status["services"]["huggingface"] = "not configured"
    except Exception as e:
        health_status["services"]["huggingface"] = f"error: {str(e)}"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code


@app.errorhandler(404)
def page_not_found(e: Exception) -> tuple:
    """Handle 404 errors."""
    return render_template("error.html", message="Page not found"), 404


# Custom Jinja2 filter to replace newlines with <br>


@app.template_filter("nl2br")
def nl2br_filter(s):
    if s is None:
        return ""
    return s.replace("\n", "<br>")


@app.errorhandler(500)
def internal_server_error(e: Exception) -> tuple:
    """Handle 500 errors."""
    return render_template("error.html", message="Internal server error"), 500


# --- TAG EDIT ---
@app.route("/admin/edit_tag/<int:tag_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_tag(tag_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM tags WHERE id = %s", (tag_id,))
    tag = cursor.fetchone()
    if not tag:
        cursor.close()
        release_db_connection(conn)
        flash("Tag not found.", "danger")
        return redirect(url_for("admin_tags"))
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        if not name:
            flash("Tag name is required.", "danger")
            return render_template("admin/edit_tag.html", tag=tag)
        try:
            cursor.execute(
                "UPDATE tags SET name=%s, description=%s WHERE id=%s",
                (name, description, tag_id),
            )
            conn.commit()
            flash("Tag updated successfully!", "success")
            cursor.execute("SELECT * FROM tags WHERE id = %s", (tag_id,))
            tag = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error editing tag: {str(e)}")
            flash("Error updating tag.", "danger")
    cursor.close()
    release_db_connection(conn)
    return render_template("admin/edit_tag.html", tag=tag)


# --- TAG DELETE ---
@app.route("/admin/delete_tag/<int:tag_id>", methods=["POST"])
@admin_required
def admin_delete_tag(tag_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tags WHERE id = %s", (tag_id,))
        conn.commit()
        flash("Tag deleted successfully!", "success")
    except Exception as e:
        logger.error(f"Error deleting tag: {str(e)}")
        flash("Error deleting tag.", "danger")
    finally:
        cursor.close()
        release_db_connection(conn)
    return redirect(url_for("admin_tags"))


# --- COHORT DELETE ---
@app.route("/admin/delete_cohort/<int:cohort_id>", methods=["POST"])
@admin_required
def admin_delete_cohort(cohort_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM cohorts WHERE id = %s", (cohort_id,))
        conn.commit()
        flash("Cohort deleted successfully!", "success")
    except Exception as e:
        logger.error(f"Error deleting cohort: {str(e)}")
        flash("Error deleting cohort.", "danger")
    finally:
        cursor.close()
        release_db_connection(conn)
    return redirect(url_for("admin_cohorts"))


# --- API ENDPOINTS ---
@app.route("/admin/api/users")
@admin_required
def admin_api_users():
    """API endpoint for user management with filtering."""
    conn = None
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 12))
        search = request.args.get("search", "").strip()
        tag_filter = request.args.get("tag_filter", "").strip()
        camp_filter = request.args.get("camp_filter", "").strip()

        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query conditions
        where_conditions = []
        params = []

        base_query = """
            SELECT u.id, u.username, u.email, u.camp, u.email_verified, u.created_at,
                   STRING_AGG(t.name, ', ') AS user_tags
            FROM users u
            LEFT JOIN user_tags ut ON u.id = ut.user_id
            LEFT JOIN tags t ON ut.tag_id = t.id
        """

        if search:
            where_conditions.append("(u.username ILIKE %s OR u.email ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        if tag_filter:
            where_conditions.append("t.name = %s")
            params.append(tag_filter)

        if camp_filter:
            where_conditions.append("u.camp = %s")
            params.append(camp_filter)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get users
        query = f"""
            {base_query}
            {where_clause}
            GROUP BY u.id
            ORDER BY u.username
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])

        cursor.execute(query, params)
        users = cursor.fetchall()

        # Get total count
        count_query = f"""
            SELECT COUNT(DISTINCT u.id) 
            FROM users u
            LEFT JOIN user_tags ut ON u.id = ut.user_id
            LEFT JOIN tags t ON ut.tag_id = t.id
            {where_clause}
        """
        cursor.execute(count_query, params[:-2])  # Remove LIMIT and OFFSET params
        total = cursor.fetchone()["count"]

        pages = (total + per_page - 1) // per_page

        cursor.close()

        return jsonify(
            {
                "success": True,
                "users": users,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": pages,
                },
            }
        )

    except Exception as e:
        logger.error(f"API users error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/api/tags")
@admin_required
def admin_api_tags():
    """API endpoint for available tags."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT tg.name as group_name, t.id, t.name, t.description
            FROM tags t
            JOIN tag_groups tg ON t.tag_group_id = tg.id
            WHERE t.is_active = TRUE AND tg.is_active = TRUE
            ORDER BY tg.name, t.name
        """
        )
        tags = cursor.fetchall()

        grouped_tags = {}
        for tag in tags:
            group_name = tag["group_name"]
            if group_name not in grouped_tags:
                grouped_tags[group_name] = []
            grouped_tags[group_name].append(
                {
                    "id": tag["id"],
                    "name": tag["name"],
                    "description": tag["description"],
                }
            )

        cursor.close()
        return jsonify({"success": True, "tags": grouped_tags})

    except Exception as e:
        logger.error(f"API tags error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/edit_tag_group/<int:group_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_tag_group(group_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM tag_groups WHERE id = %s", (group_id,))
    group = cursor.fetchone()
    if not group:
        cursor.close()
        release_db_connection(conn)
        flash("Tag group not found.", "danger")
        return redirect(url_for("admin_tags"))
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        if not name:
            flash("Tag group name is required.", "danger")
            return render_template("admin/edit_tag_group.html", group=group)
        try:
            cursor.execute(
                "UPDATE tag_groups SET name=%s, description=%s WHERE id=%s",
                (name, description, group_id),
            )
            conn.commit()
            flash("Tag group updated successfully!", "success")
            cursor.execute("SELECT * FROM tag_groups WHERE id = %s", (group_id,))
            group = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error editing tag group: {str(e)}")
            flash("Error updating tag group.", "danger")
    cursor.close()
    release_db_connection(conn)
    return render_template("admin/edit_tag_group.html", group=group)


@app.route("/admin/delete_tag_group/<int:group_id>", methods=["POST"])
@admin_required
def admin_delete_tag_group(group_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tag_groups WHERE id = %s", (group_id,))
        conn.commit()
        flash("Tag group deleted successfully!", "success")
    except Exception as e:
        logger.error(f"Error deleting tag group: {str(e)}")
        flash("Error deleting tag group.", "danger")
    finally:
        cursor.close()
        release_db_connection(conn)
    return redirect(url_for("admin_tags"))


@app.route("/admin/export_users/<camp>")
@admin_required
def admin_export_users_by_camp(camp: str):
    """Export users to CSV filtered by camp (or all camps)."""
    if camp not in CAMPS and camp != "all":
        flash("Invalid camp selection", "danger")
        return redirect(url_for("admin_dashboard"))
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if camp == "all":
            cursor.execute(
                """
                SELECT u.id, u.username, u.email, u.language, u.email_verified, u.camp,
                       STRING_AGG(DISTINCT t.name, ', ') AS tags
                FROM users u
                LEFT JOIN user_tags ut ON u.id = ut.user_id
                LEFT JOIN tags t ON ut.tag_id = t.id
                GROUP BY u.id
                ORDER BY u.camp, u.username
            """
            )
        else:
            cursor.execute(
                """
                SELECT u.id, u.username, u.email, u.language, u.email_verified, u.camp,
                       STRING_AGG(DISTINCT t.name, ', ') AS tags
                FROM users u
                LEFT JOIN user_tags ut ON u.id = ut.user_id
                LEFT JOIN tags t ON ut.tag_id = t.id
                WHERE u.camp = %s
                GROUP BY u.id
                ORDER BY u.username
            """,
                (camp,),
            )
        users = cursor.fetchall()
        cursor.close()
        # Prepare CSV
        headers = [
            "ID",
            "Username",
            "Email",
            "Language",
            "Email Verified",
            "Camp",
            "Tags",
        ]
        data = []
        for row in users:
            data.append([row[0], row[1], row[2], row[3], row[4], row[5], row[6] or ""])
        filename = f"users_{camp}.csv" if camp != "all" else "users_all_camps.csv"
        csv_file = generate_csv_file(data, filename, headers)
        if csv_file:
            return send_file(
                csv_file,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )
        else:
            flash("Error generating CSV file", "danger")
            return redirect(url_for("admin_export_users"))
    except Exception as e:
        logger.error(f"Admin export users by camp error: {str(e)}")
        flash(f"Error exporting users: {str(e)}", "danger")
        return redirect(url_for("admin_export_users"))
    finally:
        if conn:
            release_db_connection(conn)


@app.route("/admin/edit_cohort/<int:cohort_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_cohort(cohort_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM cohorts WHERE id = %s", (cohort_id,))
    cohort = cursor.fetchone()
    if not cohort:
        cursor.close()
        release_db_connection(conn)
        flash("Cohort not found.", "danger")
        return redirect(url_for("admin_cohorts"))
    if request.method == "POST":
        name = request.form.get("name")
        bootcamp_type = request.form.get("bootcamp_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")
        if not all([name, bootcamp_type]):
            flash("Name and bootcamp type are required.", "error")
            return render_template("admin/add_cohort.html", cohort=cohort)
        if not validate_bootcamp_type(bootcamp_type):
            flash(
                f'Invalid bootcamp type. Must be one of: {", ".join(BOOTCAMP_TYPES)}',
                "error",
            )
            return render_template("admin/add_cohort.html", cohort=cohort)
        try:
            cursor.execute(
                """
                UPDATE cohorts SET name=%s, bootcamp_type=%s, start_date=%s, end_date=%s, description=%s WHERE id=%s
            """,
                (
                    name,
                    bootcamp_type,
                    start_date or None,
                    end_date or None,
                    description,
                    cohort_id,
                ),
            )
            conn.commit()
            flash("Cohort updated successfully!", "success")
            return redirect(url_for("admin_cohorts"))
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating cohort: {str(e)}")
            flash("Error updating cohort.", "danger")
    cursor.close()
    release_db_connection(conn)
    return render_template("admin/add_cohort.html", cohort=cohort)

"""
Add this debug route to your app.py to test the QA system
"""

@app.route("/debug/qa_test")
@admin_required
def debug_qa_test():
    """Debug endpoint to test QA system step by step"""
    debug_info = []
    
    try:
        # Test 1: Check OpenRouter config
        debug_info.append("=== OpenRouter Configuration ===")
        import os
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        
        debug_info.append(f"API Key exists: {bool(api_key)}")
        if api_key:
            debug_info.append(f"API Key length: {len(api_key)} chars")
            debug_info.append(f"API Key starts with: {api_key[:10]}...")
        debug_info.append(f"Model: {model}")
        
        # Test 2: Check database documents
        debug_info.append("\n=== Database Documents ===")
        from qa import get_documents_from_database
        docs = get_documents_from_database()
        debug_info.append(f"Documents in database: {len(docs)}")
        for i, (filename, content, content_type) in enumerate(docs):
            debug_info.append(f"  {i+1}. {filename} ({len(content)} bytes, {content_type})")
        
        # Test 3: Test temp directory creation
        debug_info.append("\n=== Temp Directory ===")
        from qa import create_temp_documents_from_db
        temp_dir = create_temp_documents_from_db()
        debug_info.append(f"Temp directory: {temp_dir}")
        
        if os.path.exists(temp_dir):
            files = os.listdir(temp_dir)
            debug_info.append(f"Files in temp dir: {files}")
        
        # Test 4: Test OpenRouter API call
        debug_info.append("\n=== OpenRouter API Test ===")
        if api_key:
            try:
                from qa import OpenRouterLLM
                llm = OpenRouterLLM(api_key, model)
                test_response = llm.generate_response("Hello, this is a test.")
                debug_info.append(f"✅ API Response: {test_response[:100]}...")
            except Exception as api_error:
                debug_info.append(f"❌ API Error: {str(api_error)}")
        else:
            debug_info.append("❌ No API key to test")
        
        # Test 5: Test QA system initialization
        debug_info.append("\n=== QA System Test ===")
        try:
            qa_system = get_qa_system()
            if not qa_system:
                debug_info.append("Initializing new QA system...")
                from qa import initialize_qa
                qa_system = initialize_qa()
            
            if qa_system:
                debug_info.append("✅ QA system exists")
                debug_info.append(f"GPT LLM available: {qa_system.gpt_llm is not None}")
                debug_info.append(f"Vector store ready: {qa_system.vector_store_manager.is_ready()}")
                
                # Test a simple question
                debug_info.append("\n=== Test Question ===")
                response = qa_system.answer_question("What is artificial intelligence?", user_id="debug")
                debug_info.append(f"Answer type: {response['conversation_type']}")
                debug_info.append(f"Answer: {response['answer'][:200]}...")
                debug_info.append(f"Sources: {len(response['sources'])}")
                
            else:
                debug_info.append("❌ QA system not available")
                
        except Exception as qa_error:
            debug_info.append(f"❌ QA Error: {str(qa_error)}")
            import traceback
            debug_info.append(f"Traceback: {traceback.format_exc()}")
        
    except Exception as e:
        debug_info.append(f"❌ Debug Error: {str(e)}")
        import traceback
        debug_info.append(f"Traceback: {traceback.format_exc()}")
    
    return "<pre>" + "\n".join(debug_info) + "</pre>"


@app.route("/debug/simple_test")
@admin_required  
def debug_simple_test():
    """Simple test to check if basic QA works"""
    try:
        # Force reload QA system
        global _qa_instance
        _qa_instance = None
        
        from qa import initialize_qa
        qa_system = initialize_qa()
        
        if not qa_system:
            return "❌ Failed to initialize QA system"
        
        # Test simple question
        response = qa_system.answer_question("Hello")
        
        return f"""
        <div style="font-family: monospace; padding: 20px;">
            <h2>🧪 Simple QA Test Result</h2>
            <p><strong>Question:</strong> Hello</p>
            <p><strong>Answer:</strong> {response['answer']}</p>
            <p><strong>Type:</strong> {response['conversation_type']}</p>
            <p><strong>Sources:</strong> {len(response['sources'])}</p>
            
            <h3>System Status:</h3>
            <pre>{json.dumps(qa_system.get_status(), indent=2)}</pre>
        </div>
        """
    except Exception as e:
        return f"❌ Error: {str(e)}"
    

def get_all_cohorts():
    """Return all active cohorts for dropdowns."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, name, bootcamp_type FROM cohorts WHERE is_active = TRUE ORDER BY bootcamp_type, name"
        )
        cohorts = cursor.fetchall()
        cursor.close()
        return cohorts
    except Exception as e:
        logger.error(f"Error getting all cohorts: {str(e)}")
        return []
    finally:
        if conn:
            release_db_connection(conn)

# ==============================================
# MindMap Routes
# ==============================================

@app.route("/mindmap")
@login_required
@camp_required
def mindmap_home():
    """Display mindmap interface with unit selection for both materials and words."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))
    
    username = session["username"]
    user_id = session["user_id"]
    user_camp = session.get("user_camp")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get units with both materials and words counts for user's camp
        cursor.execute("""
            WITH unit_materials AS (
                SELECT DISTINCT unit_id, COUNT(*) as material_count
                FROM materials m
                WHERE m.camp = %s OR EXISTS (
                    SELECT 1 FROM content_tags ct
                    JOIN tags t ON ct.tag_id = t.id
                    JOIN tag_groups tg ON t.tag_group_id = tg.id
                    WHERE ct.content_type = 'material' 
                    AND ct.content_id = m.id
                    AND tg.name = 'Bootcamp Type'
                    AND t.name = %s
                )
                GROUP BY unit_id
            ),
            unit_words AS (
                SELECT DISTINCT unit_id, COUNT(*) as word_count
                FROM words w
                WHERE w.camp = %s OR EXISTS (
                    SELECT 1 FROM content_tags ct
                    JOIN tags t ON ct.tag_id = t.id
                    JOIN tag_groups tg ON t.tag_group_id = tg.id
                    WHERE ct.content_type = 'word' 
                    AND ct.content_id = w.id
                    AND tg.name = 'Bootcamp Type'
                    AND t.name = %s
                )
                GROUP BY unit_id
            )
            SELECT 
                COALESCE(um.unit_id, uw.unit_id) as unit_id,
                COALESCE(um.material_count, 0) as material_count,
                COALESCE(uw.word_count, 0) as word_count
            FROM unit_materials um
            FULL OUTER JOIN unit_words uw ON um.unit_id = uw.unit_id
            WHERE COALESCE(um.material_count, 0) > 0 OR COALESCE(uw.word_count, 0) > 0
            ORDER BY COALESCE(um.unit_id, uw.unit_id)
        """, (user_camp, user_camp, user_camp, user_camp))
        
        available_units = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dictionaries for JSON serialization
        units_list = []
        for unit in available_units:
            units_list.append({
                'unit_id': unit['unit_id'],
                'material_count': unit['material_count'],
                'word_count': unit['word_count']
            })
        
        return render_template(
            "mindmap.html", 
            username=username,
            available_units=units_list,
            user_camp=user_camp
        )
        
    except Exception as e:
        logger.error(f"Mindmap home error: {str(e)}")
        flash(f"Error loading mindmap: {str(e)}", "error")
        return redirect(url_for("dashboard"))
    finally:
        if conn:
            release_db_connection(conn)



@app.route("/api/generate_mindmap/<int:unit_id>")
@login_required
@camp_required
def generate_mindmap_api(unit_id):
    """Generate mindmap data with language support."""
    user_id = session["user_id"]
    user_camp = session.get("user_camp")
    user_language = session.get("language", "en")
    
    content_type = request.args.get('content_type', 'material')
    
    if content_type not in ['material', 'word']:
        return jsonify({
            "success": False,
            "error": "Invalid content type. Must be 'material' or 'word'"
        })
    
    try:
        if content_type == 'material':
            content_items = get_content_with_tag_filtering("material", unit_id, user_id)
            content_label = "materials"
        else:
            content_items = get_content_with_tag_filtering("word", unit_id, user_id)
            content_label = "vocabulary words"
        
        if not content_items:
            error_msg = {
                "en": f"No {content_label} found for this unit",
                "zh": f"此单元未找到{content_label}",
                "ar": f"لم يتم العثور على {content_label} لهذه الوحدة"
            }
            return jsonify({
                "success": False,
                "error": error_msg.get(user_language, error_msg["en"])
            })
        
        # Language-specific prompts
        language_prompts = {
            "en": {
                "material": f"""
                Based on the following learning materials, create a structured mindmap with key concepts and their relationships.
                
                Please analyze this content and return a JSON structure for a mindmap with:
                - A central topic
                - Main branches (key concepts)
                - Sub-branches (details/examples)
                - Keep it educational and organized
                
                Please respond in English with a JSON structure.
                """,
                "word": f"""
                Based on the following vocabulary words, create a structured mindmap showing word relationships and concepts.
                
                Please analyze this vocabulary content and return a JSON structure for a mindmap with:
                - A central topic about vocabulary
                - Main branches (word categories or themes)
                - Sub-branches (individual words and their key meanings)
                
                Please respond in English with a JSON structure.
                """
            },
            "zh": {
                "material": f"""
                基于以下学习材料，创建一个具有关键概念及其关系的结构化思维导图。
                
                请分析此内容并返回思维导图的JSON结构，包含：
                - 中心主题
                - 主要分支（关键概念）
                - 子分支（详细信息/示例）
                - 保持教育性和组织性
                
                请用中文回复JSON结构。
                """,
                "word": f"""
                基于以下词汇，创建一个显示词汇关系和概念的结构化思维导图。
                
                请分析此词汇内容并返回思维导图的JSON结构，包含：
                - 关于词汇的中心主题
                - 主要分支（词汇类别或主题）
                - 子分支（单个词汇及其关键含义）
                
                请用中文回复JSON结构。
                """
            },
            "ar": {
                "material": f"""
                بناءً على المواد التعليمية التالية، أنشئ خريطة ذهنية منظمة تحتوي على المفاهيم الأساسية وعلاقاتها.
                
                يرجى تحليل هذا المحتوى وإرجاع هيكل JSON للخريطة الذهنية يحتوي على:
                - موضوع مركزي
                - فروع رئيسية (مفاهيم أساسية)
                - فروع فرعية (تفاصيل/أمثلة)
                - حافظ على الطابع التعليمي والتنظيم
                
                يرجى الرد باللغة العربية مع هيكل JSON.
                """,
                "word": f"""
                بناءً على الكلمات المفردات التالية، أنشئ خريطة ذهنية منظمة تُظهر علاقات الكلمات والمفاهيم.
                
                يرجى تحليل محتوى المفردات هذا وإرجاع هيكل JSON للخريطة الذهنية يحتوي على:
                - موضوع مركزي حول المفردات
                - فروع رئيسية (فئات أو موضوعات الكلمات)
                - فروع فرعية (كلمات فردية ومعانيها الأساسية)
                
                يرجى الرد باللغة العربية مع هيكل JSON.
                """
            }
        }
        
        # Get language-specific prompt
        prompts = language_prompts.get(user_language, language_prompts["en"])
        base_prompt = prompts[content_type]
        
        # Combine content
        combined_content = f"Unit {unit_id} {content_label.title()}:\n\n"
        
        if content_type == 'material':
            for item in content_items:
                combined_content += f"Title: {item['title']}\n"
                if item.get('content'):
                    combined_content += f"Content: {item['content']}\n\n"
        else:
            for item in content_items:
                combined_content += f"Word: {item['word']}\n"
                if item.get('daily_definition'):
                    combined_content += f"Definition: {item['daily_definition']}\n"
                combined_content += "\n"
        
        # Create full prompt
        full_prompt = f"{base_prompt}\n\nContent to analyze:\n{combined_content[:3000]}"
        
        qa_system = get_qa_system()
        
        if not qa_system:
            error_msg = {
                "en": "AI system not available",
                "zh": "AI系统不可用",
                "ar": "نظام الذكاء الاصطناعي غير متاح"
            }
            return jsonify({
                "success": False,
                "error": error_msg.get(user_language, error_msg["en"])
            })
        
        # Get AI response
        response = qa_system.answer_question(full_prompt, user_id=str(user_id))
        ai_answer = response.get("answer", "")
        
        # Try to extract JSON from AI response
        try:
            import re
            json_match = re.search(r'\{.*\}', ai_answer, re.DOTALL)
            if json_match:
                mindmap_data = json.loads(json_match.group())
            else:
                if content_type == 'material':
                    mindmap_data = create_fallback_mindmap(content_items, unit_id, user_language)
                else:
                    mindmap_data = create_fallback_words_mindmap(content_items, unit_id, user_language)
        except:
            if content_type == 'material':
                mindmap_data = create_fallback_mindmap(content_items, unit_id, user_language)
            else:
                mindmap_data = create_fallback_words_mindmap(content_items, unit_id, user_language)
        
        session[f"mindmap_unit_{unit_id}_{content_type}"] = mindmap_data
        
        return jsonify({
            "success": True,
            "mindmap": mindmap_data,
            "unit_id": unit_id,
            "content_type": content_type,
            "content_count": len(content_items),
            "language": user_language
        })
        
    except Exception as e:
        logger.error(f"Generate mindmap error: {str(e)}")
        error_msg = {
            "en": str(e),
            "zh": f"生成思维导图时出错: {str(e)}",
            "ar": f"خطأ في إنشاء الخريطة الذهنية: {str(e)}"
        }
        return jsonify({
            "success": False,
            "error": error_msg.get(user_language, error_msg["en"])
        })

def create_fallback_mindmap(materials, unit_id, language="en"):
    """Create a simple fallback mindmap structure with language support."""
    titles = {
        "en": f"Unit {unit_id} Learning Materials",
        "zh": f"第{unit_id}单元学习材料",
        "ar": f"مواد التعلم - الوحدة {unit_id}"
    }
    
    mindmap = {
        "central_topic": titles.get(language, titles["en"]),
        "branches": []
    }
    
    for i, material in enumerate(materials[:5]):
        branch = {
            "name": material['title'],
            "children": [
                {"name": material.get('content', '')[:50] + "..." if material.get('content') else "Content", "type": "content"}
            ]
        }
        mindmap["branches"].append(branch)
    
    return mindmap

def create_fallback_words_mindmap(words, unit_id, language="en"):
    """Create a simple fallback mindmap structure from vocabulary words with language support."""
    titles = {
        "en": f"Unit {unit_id} Vocabulary",
        "zh": f"第{unit_id}单元词汇",
        "ar": f"مفردات الوحدة {unit_id}"
    }
    
    mindmap = {
        "central_topic": titles.get(language, titles["en"]),
        "branches": []
    }
    
    sections = {}
    for word in words[:10]:
        section = word.get('section', 1)
        if section not in sections:
            sections[section] = []
        sections[section].append(word)
    
    section_labels = {
        "en": "Section",
        "zh": "部分",
        "ar": "القسم"
    }
    
    for section_num, section_words in sections.items():
        branch = {
            "name": f"{section_labels.get(language, section_labels['en'])} {section_num}",
            "children": []
        }
        
        for word in section_words:
            child = {
                "name": word['word'],
                "type": "vocabulary"
            }
            
            if word.get('daily_definition'):
                child['definition'] = word['daily_definition'][:50] + "..." if len(word['daily_definition']) > 50 else word['daily_definition']
            
            branch["children"].append(child)
        
        mindmap["branches"].append(branch)
    
    return mindmap



@app.route("/api/expand_node", methods=["POST"])
@login_required
@camp_required
def expand_mindmap_node():
    """Expand a specific mindmap node with AI-generated details."""
    try:
        data = request.get_json()
        node_name = data.get("node_name")
        unit_id = data.get("unit_id")
        content_type = data.get("content_type", "material")
        context = data.get("context", "")
        
        if not all([node_name, unit_id]):
            return jsonify({
                "success": False,
                "error": "Missing required parameters"
            })
        
        # Validate content type
        if content_type not in ['material', 'word']:
            return jsonify({
                "success": False,
                "error": "Invalid content type"
            })
        
        # Use AI to expand the node
        qa_system = get_qa_system()
        if not qa_system:
            return jsonify({
                "success": False,
                "error": "AI system not available"
            })
        
        # Create appropriate expand prompt based on content type
        if content_type == 'material':
            expand_prompt = f"""
            For the learning topic "{node_name}" in Unit {unit_id}, provide 3-5 detailed sub-topics or key points that students should understand. 
            
            Context: {context}
            
            Focus on educational concepts, theories, and practical applications related to this topic.
            
            Please respond with a simple JSON array of objects like:
            [
                {{"name": "Sub-topic 1", "type": "concept"}},
                {{"name": "Sub-topic 2", "type": "theory"}},
                {{"name": "Sub-topic 3", "type": "application"}}
            ]
            """
        else:  # content_type == 'word'
            expand_prompt = f"""
            For the vocabulary term "{node_name}" in Unit {unit_id}, provide 3-5 related concepts such as:
            - Synonyms or related words
            - Usage examples
            - Contextual applications
            - Related grammatical forms
            
            Context: {context}
            
            Please respond with a simple JSON array of objects like:
            [
                {{"name": "Related concept 1", "type": "synonym"}},
                {{"name": "Usage example 1", "type": "example"}},
                {{"name": "Application 1", "type": "application"}}
            ]
            """
        
        response = qa_system.answer_question(expand_prompt, user_id=str(session["user_id"]))
        ai_answer = response.get("answer", "")
        
        # Try to extract JSON array
        try:
            import re
            json_match = re.search(r'\[.*\]', ai_answer, re.DOTALL)
            if json_match:
                expanded_nodes = json.loads(json_match.group())
            else:
                # Fallback based on content type
                if content_type == 'material':
                    expanded_nodes = [
                        {"name": f"{node_name} - Key Concept 1", "type": "concept"},
                        {"name": f"{node_name} - Key Concept 2", "type": "concept"},
                        {"name": f"{node_name} - Application", "type": "application"}
                    ]
                else:
                    expanded_nodes = [
                        {"name": f"{node_name} - Definition", "type": "definition"},
                        {"name": f"{node_name} - Example", "type": "example"},
                        {"name": f"{node_name} - Usage", "type": "usage"}
                    ]
        except:
            # Create fallback nodes
            expanded_nodes = [
                {"name": f"{node_name} - Detail 1", "type": "detail"},
                {"name": f"{node_name} - Detail 2", "type": "detail"}
            ]
        
        return jsonify({
            "success": True,
            "expanded_nodes": expanded_nodes
        })
        
    except Exception as e:
        logger.error(f"Expand node error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/mindmap/<int:unit_id>")
@login_required
@camp_required  
def view_mindmap(unit_id):
    """View interactive mindmap for a specific unit with content type support."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))
    
    username = session["username"]
    user_camp = session.get("user_camp")
    user_id = session["user_id"]
    
    # Get content type from query parameter (default to 'material')
    content_type = request.args.get('content_type', 'material')
    
    # Validate content type
    if content_type not in ['material', 'word']:
        flash("Invalid content type", "error")
        return redirect(url_for("mindmap_home"))
    
    # Check if user has access to this unit's content
    if content_type == 'material':
        content_items = get_content_with_tag_filtering("material", unit_id, user_id)
        content_label = "materials"
    else:
        content_items = get_content_with_tag_filtering("word", unit_id, user_id)
        content_label = "vocabulary words"
    
    if not content_items:
        flash(f"No {content_label} available for Unit {unit_id} in your camp.", "error")
        return redirect(url_for("mindmap_home"))
    
    return render_template(
        "mindmap_viewer.html",
        username=username,
        unit_id=unit_id,
        user_camp=user_camp,
        content_count=len(content_items),
        content_type=content_type,
        content_label=content_label
    )

@app.route("/change_username", methods=["GET", "POST"])
@login_required
def change_username():
    """Allow users to change their username."""
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))
    
    user_id = session["user_id"]
    current_username = session["username"]
    
    if request.method == "POST":
        new_username = request.form.get("new_username", "").strip()
        password = request.form.get("password", "")
        
        if not new_username:
            flash("New username is required.", "error")
            return render_template("change_username.html", current_username=current_username)
        
        if not password:
            flash("Password is required to change username.", "error")
            return render_template("change_username.html", current_username=current_username)
        
        # Validate password
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check current password
            cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data or not check_password_hash(user_data[0], password):
                flash("Incorrect password.", "error")
                return render_template("change_username.html", current_username=current_username)
            
            # Check if new username already exists
            cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
            if cursor.fetchone():
                flash("Username already exists. Please choose a different one.", "error")
                return render_template("change_username.html", current_username=current_username)
            
            # Update username
            cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, user_id))
            conn.commit()
            
            # Update session
            session["username"] = new_username
            
            flash("Username updated successfully!", "success")
            return redirect(url_for("dashboard"))
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error changing username: {str(e)}")
            flash("An error occurred while changing username.", "error")
        finally:
            if conn:
                cursor.close()
                release_db_connection(conn)
    
    return render_template("change_username.html", current_username=current_username)


if __name__ == "__main__":
    try:
        # Add SQLAlchemy database URI config if Config.get_db_uri() is available
        try:
            from config import Config

            app.config["SQLALCHEMY_DATABASE_URI"] = Config.get_db_uri()
        except ImportError:
            print(
                "Warning: config.py or Config.get_db_uri() not found. Skipping SQLALCHEMY_DATABASE_URI setup."
            )

        initialize_tag_system()
        initialize_enhanced_qa_system()
        init_db_pool()
        validate_app_environment()
        create_followup_table()  # Add this line to initialize followup system
        print("Starting Flask application with enhanced QA system...")
        # Set maximum upload size to 200MB
        app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
