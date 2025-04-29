import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import html
import re
from datetime import datetime, timedelta
import os
import json
import time
from queue import Queue
from threading import Lock, Thread
import pytz
from typing import Dict, List, Any, Optional
import hashlib
import asyncio
from urllib.parse import quote
import aiohttp

# استيراد دوال API الجديدة
from api_calls import (
    get_stock_chart_data,
    get_stock_holders_data,
    get_stock_insights_data,
    get_stock_sec_filing_data,
    get_stock_analyst_reports,
    get_linkedin_profile # إضافة دالة LinkedIn
)

# استيراد معالجات الميزات الجديدة
from feature_handlers import FeatureHandlers

# استيراد مكونات واجهة المستخدم المحسنة
from ui_components import UIComponents

# تكوين المفاتيح الأساسية
TELEGRAM_TOKEN = "7571078091:AAGGMX-aHTc8X5BuaDB5-yEIfppQFh-AzEs"
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_API_KEY = "AIzaSyDV1Hwzgo6HaUctAch0B6qzXZ8ujr14jIM"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "YOUR_CLAUDE_API_KEY")  # يجب استبداله بمفتاح حقيقي من Anthropic
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "YOUR_MISTRAL_API_KEY")  # يجب استبداله بمفتاح حقيقي من Mistral AI
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY") # يجب استبداله بمفتاح حقيقي من DeepSeek
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions" # عنوان URL لـ DeepSeek
# MANUS_API_KEY = os.getenv("MANUS_API_KEY", "INTERNAL_MANUS_KEY") # مفتاح Manus (قد يكون داخليًا)
# MANUS_URL = "INTERNAL_MANUS_ENDPOINT" # نقطة نهاية Manus (قد تكون داخلية)

MODEL = "gpt-3.5-turbo"
ADMIN_IDS = [7091341079]
MAX_CONTEXT_LENGTH = 10
MAX_REQUESTS_PER_MINUTE = 50
REQUEST_DELAY = 1
TIMEZONE = pytz.timezone('Asia/Riyadh')
MAX_MESSAGE_LENGTH = 40000
WEB_SEARCH_ENABLED = True
SESSION_TIMEOUT = 3600  # 1 hour session timeout

# إعداد السجل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='ai_bot.log',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# إنشاء المجلدات اللازمة
os.makedirs('user_files', exist_ok=True)
os.makedirs('user_data', exist_ok=True)
os.makedirs('training_data', exist_ok=True)
os.makedirs('logs', exist_ok=True)


class PremiumAIBot:
    def __init__(self):
        self.setup_keyboards()
        self.load_all_data()
        self.setup_queues()
        self.start_background_tasks()
        self.web_search_cache = {}
        self.active_sessions = {}
        self.session_lock = Lock()
        self.http_session = aiohttp.ClientSession()
        # إضافة قائمة النماذج المتاحة
        self.available_models = {
            "gpt-3.5-turbo": {"name": "🚀 GPT-3.5 Turbo", "api": "openrouter"},
            "gemini-1.5-flash": {"name": "✨ Gemini 1.5 Flash", "api": "gemini"},
            "claude-3-haiku": {"name": "🧠 Claude 3 Haiku", "api": "claude"},
            "mistral-medium": {"name": "🌬️ Mistral Medium", "api": "mistral"},
            "deepseek-chat": {"name": "🔍 DeepSeek Chat", "api": "deepseek"},
            "manus": {"name": "🤖 Manus (Internal)", "api": "manus"} # إضافة Manus
        }
        # النموذج الافتراضي لكل مستخدم
        self.user_models = {}
        # حالات المستخدمين (لتتبع حالة المحادثة)
        self.user_states = {}
        # إنشاء معالج الميزات الإضافية
        self.feature_handlers = FeatureHandlers(self)

    def __del__(self):
        asyncio.get_event_loop().run_until_complete(self.http_session.close())

    def load_all_data(self):
        """تحميل جميع البيانات من الملفات"""
        try:
            self.user_context = self.load_data('user_context.json', {})
            self.user_ratings = self.load_data('user_ratings.json', {})
            self.user_feedback = self.load_data('user_feedback.json', {})
            self.user_count = self.load_data('user_count.json', 0)
            self.last_broadcast = self.load_data('last_broadcast.json', None)
            self.user_join_dates = self.load_data('user_join_dates.json', {})
            self.show_footer = self.load_data('footer_settings.json', {})
            self.pending_activations = self.load_data(
                'pending_activations.json', {})
            self.maintenance_mode = self.load_data(
                'maintenance_mode.json', False)
            self.user_usage = self.load_data('user_usage.json', {})
            self.training_data = self.load_training_data()
            self.bot_stats = self.load_data('bot_stats.json', {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "active_users": 0,
                "last_updated": datetime.now(TIMEZONE).isoformat()
            })
            self.conversation_history = self.load_data(
                'conversation_history.json', {})
            self.user_models = self.load_data('user_models.json', {})
            logger.info("All data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            raise

    def setup_queues(self):
        """إعداد قوائم الانتظار والمسارات"""
        self.request_queue = Queue()
        self.broadcast_queue = Queue()
        self.training_queue = Queue()
        self.request_lock = Lock()
        self.last_request_time = 0
        self.request_count = 0
        self.request_reset_time = time.time() + 60
        self.cache_lock = Lock()

    def start_background_tasks(self):
        """بدء المهام في الخلفية"""
        Thread(target=self.run_async_task, args=(
            self.process_api_requests,), daemon=True).start()
        Thread(target=self.run_async_task, args=(
            self.periodic_save_task,), daemon=True).start()
        Thread(target=self.run_async_task, args=(
            self.analyze_data_task,), daemon=True).start()
        Thread(target=self.run_async_task, args=(
            self.auto_training_task,), daemon=True).start()
        Thread(target=self.run_async_task, args=(
            self.session_cleanup_task,), daemon=True).start()

    def run_async_task(self, coro):
        """تشغيل مهمة غير متزامنة في thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)

    async def session_cleanup_task(self):
        """تنظيف الجلسات المنتهية"""
        while True:
            await asyncio.sleep(3600)  # كل ساعة
            current_time = time.time()
            expired_sessions = [
                user_id for user_id, session_time in self.active_sessions.items()
                if current_time - session_time > SESSION_TIMEOUT
            ]

            with self.session_lock:
                for user_id in expired_sessions:
                    del self.active_sessions[user_id]

            if expired_sessions:
                logger.info(
                    f"Cleaned up {len(expired_sessions)} expired sessions")

    async def periodic_save_task(self):
        """حفظ البيانات بشكل دوري"""
        while True:
            await asyncio.sleep(1800)  # كل 30 دقيقة
            self.save_all_data()
            logger.info("Periodic data save completed")

    async def analyze_data_task(self):
        """تحليل البيانات وتحديث الإحصائيات"""
        while True:
            await asyncio.sleep(3600)  # كل ساعة
            try:
                active_users = len([
                    user_id for user_id, usage in self.user_usage.items()
                    if usage.get("last_used") and
                    datetime.fromisoformat(usage["last_used"]) > 
                    datetime.now(TIMEZONE) - timedelta(days=1)
                ])
                
                self.bot_stats["active_users"] = active_users
                self.bot_stats["last_updated"] = datetime.now(TIMEZONE).isoformat()
                self.save_data('bot_stats.json', self.bot_stats)
                logger.info("Data analysis completed")
            except Exception as e:
                logger.error(f"Error in data analysis: {str(e)}")

    async def auto_training_task(self):
        """مهمة التدريب التلقائي"""
        while True:
            await asyncio.sleep(86400)  # كل 24 ساعة
            try:
                # هنا يمكن إضافة منطق التدريب التلقائي
                self.save_training_data()
                logger.info("Auto training task completed")
            except Exception as e:
                logger.error(f"Error in auto training: {str(e)}")

    def load_data(self, filename: str, default: Any) -> Any:
        """تحميل البيانات من ملف"""
        try:
            with open(f'user_data/{filename}', 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(
                f"Loading {filename} failed, using default: {str(e)}")
            return default
        except Exception as e:
            logger.error(f"Unexpected error loading {filename}: {str(e)}")
            return default

    def save_data(self, filename: str, data: Any):
        """حفظ البيانات إلى ملف"""
        try:
            temp_file = f'user_data/{filename}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # استبدال الملف الأصلي بعد التأكد من الحفظ الناجح
            os.replace(temp_file, f'user_data/{filename}')
        except Exception as e:
            logger.error(f"Error saving {filename}: {str(e)}")

    def load_training_data(self) -> Dict[str, Any]:
        """تحميل بيانات التدريب"""
        training_data = {
            "questions": [],
            "responses": [],
            "corrections": [],
            "feedback": []
        }

        try:
            for filename in os.listdir('training_data'):
                if filename.endswith('.json') and not filename.startswith('conversation_'):
                    try:
                        with open(f'training_data/{filename}', 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            for key in training_data.keys():
                                if key in data:
                                    training_data[key].extend(data[key])
                    except Exception as e:
                        logger.error(
                            f"Error loading training file {filename}: {str(e)}")
                        continue
        except FileNotFoundError:
            os.makedirs('training_data', exist_ok=True)

        return training_data

    def save_training_data(self):
        """حفظ بيانات التدريب مع طابع زمني"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'training_data/training_{timestamp}.json'

            temp_file = f'{filename}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.training_data, f, ensure_ascii=False, indent=2)

            os.replace(temp_file, filename)
        except Exception as e:
            logger.error(f"Error saving training data: {str(e)}")

    def save_all_data(self):
        """حفظ جميع البيانات"""
        try:
            self.save_data('user_context.json', self.user_context)
            self.save_data('user_ratings.json', self.user_ratings)
            self.save_data('user_feedback.json', self.user_feedback)
            self.save_data('user_count.json', self.user_count)
            self.save_data('last_broadcast.json', self.last_broadcast)
            self.save_data('user_join_dates.json', self.user_join_dates)
            self.save_data('footer_settings.json', self.show_footer)
            self.save_data('pending_activations.json',
                           self.pending_activations)
            self.save_data('maintenance_mode.json', self.maintenance_mode)
            self.save_data('user_usage.json', self.user_usage)
            self.save_data('bot_stats.json', self.bot_stats)
            self.save_data('conversation_history.json',
                           self.conversation_history)
            self.save_data('user_models.json', self.user_models)
            self.save_training_data()
            logger.info("All data saved successfully")
        except Exception as e:
            logger.error(f"Error saving all data: {str(e)}")

    def setup_keyboards(self):
        """إعداد لوحات المفاتيح"""
        # لوحة المفاتيح الرئيسية للمستخدم
        self.main_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("✨ طرح سؤال متميز")],
            [KeyboardButton("📈 معلومات الأسهم"), KeyboardButton("🔗 بحث LinkedIn")], # إضافة زر LinkedIn
            [KeyboardButton("🌐 التواصل مع المطور"),
             KeyboardButton("ℹ️ مميزات البوت")],
            [KeyboardButton("📢 قنواتنا"), KeyboardButton("⭐️ تقييم البوت")],
            [KeyboardButton("⚙️ إعدادات التذييل"),
             KeyboardButton("📊 إحصائياتي")],
            [KeyboardButton("🤖 تغيير نموذج الذكاء")]
        ], resize_keyboard=True, input_field_placeholder="اكتب رسالتك هنا...")

        # --- لوحات مفاتيح الأدمن (Inline) ---
        # اللوحة الرئيسية للأدمن
        self.admin_main_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
             InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
            [InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="admin_settings"),
             InlineKeyboardButton("📣 بث رسالة", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔄 تحديث البيانات", callback_data="admin_update_data")]
        ])

        # لوحة إحصائيات الأدمن
        self.admin_stats_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 إحصائيات عامة", callback_data="admin_show_stats"),
             InlineKeyboardButton("👥 إحصائيات المستخدمين", callback_data="admin_show_user_stats")],
            [InlineKeyboardButton("⭐ تقرير التقييمات", callback_data="admin_show_ratings"),
             InlineKeyboardButton("📝 تقرير الاستخدام", callback_data="admin_show_usage")],
            [InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="admin_main")]
        ])

        # لوحة إدارة المستخدمين للأدمن
        self.admin_users_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 طلبات التفعيل", callback_data="admin_pending_activations"),
             InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_list_users")], # زر جديد مقترح
            [InlineKeyboardButton("➕ إضافة مستخدم", callback_data="admin_add_user"), # زر جديد مقترح
             InlineKeyboardButton("➖ إزالة مستخدم", callback_data="admin_remove_user")], # زر جديد مقترح
            [InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="admin_main")]
        ])

        # لوحة إعدادات البوت للأدمن
        self.admin_settings_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛠 وضع الصيانة", callback_data="admin_maintenance"),
             InlineKeyboardButton("🤖 إدارة النماذج", callback_data="admin_manage_models")], # زر جديد مقترح
            [InlineKeyboardButton("🔑 إدارة API", callback_data="admin_manage_apis"), # زر جديد مقترح
             InlineKeyboardButton("🌐 إعدادات البحث", callback_data="admin_search_settings")], # زر جديد مقترح
            [InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="admin_main")]
        ])
        # --- نهاية لوحات مفاتيح الأدمن ---

        # لوحة التقييم
        self.rating_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ 1", callback_data="rate_1"),
             InlineKeyboardButton("⭐⭐ 2", callback_data="rate_2"),
             InlineKeyboardButton("⭐⭐⭐ 3", callback_data="rate_3")],
            [InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data="rate_4"),
             InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data="rate_5")]
        ])

        # لوحة تأكيد البث
        self.broadcast_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "✅ تأكيد البث", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("✏️ تعديل الرسالة",
                                  callback_data="edit_broadcast")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")]
        ])

        # لوحة الروابط
        self.links_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "قناة التحديثات", url="https://t.me/G_G_G_A_I")],
            [InlineKeyboardButton("الدعم الفني", url="https://t.me/HH_F_Q")],
            [InlineKeyboardButton("المستودع البرمجي",
                                  url="https://github.com/yourrepo")]
        ])

        # لوحة إعدادات التذييل
        self.footer_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ عرض التذييل", callback_data="footer_on")],
            [InlineKeyboardButton(
                "❌ إخفاء التذييل", callback_data="footer_off")]
        ])

        # لوحة تفعيل المستخدم المتقدمة (تبقى كما هي للاستخدام مع طلبات التفعيل)
        self.advanced_activation_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث المعلومات",
                                  callback_data="refresh_activation")],
            [InlineKeyboardButton("✅ تفعيل المستخدم",
                                  callback_data="activate_user")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data="reject_user")],
            [InlineKeyboardButton("📩 مراسلة المستخدم",
                                  callback_data="message_user")],
            [InlineKeyboardButton(
                "🚫 إلغاء الطلب", callback_data="cancel_activation")]
        ])

        # لوحة وضع الصيانة (ستُستدعى من لوحة الإعدادات)
        self.maintenance_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تفعيل وضع الصيانة",
                                  callback_data="enable_maintenance")],
            [InlineKeyboardButton("❌ إلغاء وضع الصيانة",
                                  callback_data="disable_maintenance")],
            [InlineKeyboardButton("🔙 العودة للإعدادات", callback_data="admin_settings")] # زر عودة جديد
        ])

        # لوحة الملاحظات
        self.feedback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👍 الإجابة صحيحة", callback_data="feedback_correct")],
            [InlineKeyboardButton(
                "👎 تصحيح الإجابة", callback_data="feedback_incorrect")]
        ])

        # لوحة روابط البحث (تبقى كما هي)
        self.search_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔍 بحث في جوجل", callback_data="web_search_google")],
            [InlineKeyboardButton("📚 بحث في ويكيبيديا",
                                  callback_data="web_search_wiki")]
        ])
        
        # لوحة اختيار النموذج (تبقى كما هي)
        model_buttons = []
        for model_id, model_info in self.available_models.items():
            model_buttons.append([InlineKeyboardButton(
                model_info["name"], callback_data=f"select_model_{model_id}")])
        
        self.model_selection_keyboard = InlineKeyboardMarkup(model_buttons)

    async def welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """رسالة الترحيب"""
        user = update.effective_user
        user_id = str(user.id)

        with self.session_lock:
            self.active_sessions[user_id] = time.time()

        if self.maintenance_mode and user.id not in ADMIN_IDS:
            await update.message.reply_text("""
🛠 البوت في وضع الصيانة حاليًا

نقوم بإجراء بعض التحديثات والتحسينات على البوت.
سيتم إعلامك عند عودة البوت للعمل.

شكرًا لتفهمك! ❤️
""")
            return

        if user_id not in self.user_context and user.id not in ADMIN_IDS:
            await self.send_activation_request(update, user)
            return

        self.register_new_user(user)
        
        welcome_msg = f"""
🎊 أهلاً وسهلاً بك {user.first_name} في بوت الذكاء الاصطناعي المتميز!

⚡️ المميزات الرئيسية:
• إجابات دقيقة باستخدام نماذج ذكاء اصطناعي متعددة
• دعم متكامل للأسئلة التقنية والعلمية
• واجهة سهلة الاستخدام
• نظام تدريب متقدم لتحسين الإجابات
• إحصائيات استخدام مفصلة

💡 كيف تستخدم البوت:
1. اختر "طرح سؤال متميز"
2. اكتب سؤالك
3. اضغط على زر "عرض الإجابة" عندما تكون جاهزة
4. قيم الإجابة لمساعدتنا على التحسين

🔍 يمكنك أيضاً إرسال ملفات أو صور لتحليلها
"""
        
        # إظهار لوحة المفاتيح المناسبة
        if user.id in ADMIN_IDS:
            await update.message.reply_text(welcome_msg, reply_markup=self.main_keyboard) # إظهار لوحة المفاتيح الرئيسية للمستخدم العادي أولاً
            await update.message.reply_text("🔑 أهلاً أيها الأدمن! استخدم لوحة التحكم أدناه:", reply_markup=self.admin_main_keyboard) # ثم إظهار لوحة تحكم الأدمن
        else:
            await update.message.reply_text(welcome_msg, reply_markup=self.main_keyboard)
            
        await self.maybe_send_footer(update, user.id)

    def register_new_user(self, user):
        """تسجيل مستخدم جديد"""
        user_id = str(user.id)
        if user_id not in self.user_join_dates:
            self.user_count += 1
            self.user_join_dates[user_id] = datetime.now(TIMEZONE).isoformat()
            self.show_footer[user_id] = True
            self.user_context[user_id] = []
            self.user_usage[user_id] = {"count": 0, "last_used": None}
            self.user_models[user_id] = "gpt-3.5-turbo"  # النموذج الافتراضي
            self.save_all_data()

    async def send_activation_request(self, update: Update, user):
        """إرسال طلب تفعيل"""
        await update.message.reply_text("""
🔒 الذكاء الاصطناعي تحت التطوير حاليًا

لتفعيل حسابك والوصول إلى كامل الميزات، يرجى الضغط على زر التفعيل أدناه.

سيتم إرسال طلبك إلى المسؤولين للتحقق والموافقة.
""", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "تفعيل الحساب", callback_data="request_activation")]
        ]))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل الواردة"""
        user = update.effective_user
        user_id = str(user.id)

        with self.session_lock:
            self.active_sessions[user_id] = time.time()

        if self.maintenance_mode and user.id not in ADMIN_IDS:
            await update.message.reply_text("🛠 البوت في وضع الصيانة حالياً. الرجاء المحاولة لاحقاً.")
            return

        if user_id not in self.user_context and user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "🔒 حسابك غير مفعل بعد. يرجى الانتظار حتى يتم تفعيله من قبل المسؤولين.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "تفعيل الحساب", callback_data="request_activation")]
                ])
            )
            return

        message = update.message
        self.register_new_user(user)
        self.update_user_stats(user.id)

        if message.text:
            await self.handle_text_message(update, context)
        elif message.document:
            await self.handle_document(update, context)
        elif message.photo:
            await self.handle_photo(update, context)

    def update_user_stats(self, user_id: int):
        """تحديث إحصائيات المستخدم"""
        user_id_str = str(user_id)
        if user_id_str not in self.user_usage:
            self.user_usage[user_id_str] = {"count": 0, "last_used": None}

        self.user_usage[user_id_str]["count"] += 1
        self.user_usage[user_id_str]["last_used"] = datetime.now(
            TIMEZONE).isoformat()
        self.bot_stats["total_requests"] += 1

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل النصية"""
        user = update.effective_user
        message_text = update.message.text

        # الأوامر الخاصة بالمستخدمين العاديين
        commands = {
            "✨ طرح سؤال متميز": None,
            "🌐 التواصل مع المطور": self.contact_developer,
            "ℹ️ مميزات البوت": self.show_features,
            "📢 قنواتنا": self.show_channels,
            "⭐️ تقييم البوت": self.request_rating,
            "⚙️ إعدادات التذييل": self.show_footer_settings,
            "📊 إحصائياتي": self.show_user_usage,
            "🤖 تغيير نموذج الذكاء": self.show_model_selection,
            "📈 معلومات الأسهم": self.request_stock_symbol, # إضافة معالج زر الأسهم
            "🔗 بحث LinkedIn": self.request_linkedin_username # إضافة معالج زر LinkedIn
        }

        if message_text in commands:
            if commands[message_text]:
                await commands[message_text](update)
            # إذا كان الأمر هو "طرح سؤال متميز" أو أي أمر لا يتطلب دالة، لا نضع الطلب في قائمة الانتظار
            # فقط الأوامر التي لها دالة مرتبطة هي التي يتم تنفيذها هنا
            # الرسائل النصية العادية ستمر للمعالجة كـ AI request
            if commands[message_text] is not None:
                 return

        # الأوامر الإدارية النصية تم إزالتها، ستتم إدارتها عبر الأزرار التفاعلية
        # if user.id in ADMIN_IDS:
        #     admin_commands = { ... }
        #     if message_text in admin_commands:
        #         await admin_commands[message_text]()
        #         return

        # إذا لم تكن الرسالة أمرًا معروفًا، اعتبرها سؤالاً للذكاء الاصطناعي
        self.request_queue.put((update, user.id, message_text))

    async def process_api_requests(self):
        """معالجة طلبات API في الخلفية"""
        while True:
            try:
                task = self.request_queue.get()
                update, user_id, question = task
                await self.process_ai_request(update, user_id, question)
                await asyncio.sleep(REQUEST_DELAY)
            except Exception as e:
                logger.error(f"Error in request processor: {str(e)}")

    async def process_ai_request(self, update: Update, user_id: int, question: str):
        """معالجة طلب الذكاء الاصطناعي"""
        with self.request_lock:
            current_time = time.time()
            if current_time > self.request_reset_time:
                self.request_count = 0
                self.request_reset_time = current_time + 60

            if self.request_count >= MAX_REQUESTS_PER_MINUTE:
                await update.message.reply_text("⚠️ تم تجاوز الحد الأقصى لطلبات API. يرجى المحاولة لاحقاً.")
                return

            self.request_count += 1
            self.last_request_time = current_time

        processing_msg = await update.message.reply_text("🔄 جاري معالجة سؤالك، يرجى الانتظار...")

        # إعداد سياق المحادثة
        user_id_str = str(user_id)
        if user_id_str not in self.user_context:
            self.user_context[user_id_str] = []

        if len(self.user_context[user_id_str]) >= MAX_CONTEXT_LENGTH:
            self.user_context[user_id_str] = self.user_context[user_id_str][-MAX_CONTEXT_LENGTH+1:]

        user_message = {"role": "user", "content": question}
        self.user_context[user_id_str].append(user_message)

        # تسجيل السؤال للتدريب
        self.record_conversation(user_id, question, is_user=True)

        # تحديد النموذج المستخدم
        model_id = self.user_models.get(user_id_str, "gpt-3.5-turbo")
        model_info = self.available_models.get(model_id, {"api": "openrouter"})

        # الحصول على الإجابة من النموذج المناسب
        if self.is_security_question(question):
            answer = await self.get_gemini_response(question)
        elif model_info["api"] == "gemini":
            answer = await self.get_gemini_response(question)
        elif model_info["api"] == "claude":
            answer = await self.get_claude_response(question)
        elif model_info["api"] == "mistral":
            answer = await self.get_mistral_response(question)
        elif model_info["api"] == "deepseek":
            answer = await self.get_deepseek_response(self.user_context[user_id_str])
        elif model_info["api"] == "manus":
            answer = await self.get_manus_response(self.user_context[user_id_str])
        else:
            answer = await self.get_ai_response(self.user_context[user_id_str])

        await processing_msg.delete()

        if not answer.startswith(("⚠️", "❌")):
            bot_response = {"role": "assistant", "content": answer}
            self.user_context[user_id_str].append(bot_response)

            # تسجيل الإجابة للتدريب
            self.record_conversation(user_id, answer, is_user=False)

            self.bot_stats["successful_requests"] += 1
            
            # إرسال زر للحصول على الإجابة بدلاً من إرسال الإجابة مباشرة
            await update.message.reply_text(
                "✅ تم الحصول على إجابة لسؤالك. اضغط على الزر أدناه لعرضها.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 عرض الإجابة", callback_data=f"show_answer_{user_id}_{self.generate_question_hash(question)}")]
                ])
            )
        else:
            self.bot_stats["failed_requests"] += 1
            await update.message.reply_text(answer)

    def is_security_question(self, question: str) -> bool:
        """تحديد ما إذا كان السؤال متعلقاً بالأمن السيبراني"""
        security_keywords = ["هاكر", "اختراق", "أمن",
                             "ثغرة", "اختراق", "حماية", "سايبر"]
        return any(keyword in question.lower() for keyword in security_keywords)

    async def get_ai_response(self, messages: List[Dict[str, str]]) -> str:
        """الحصول على إجابة من الذكاء الاصطناعي (OpenRouter)"""
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yourdomain.com",
            "X-Title": "Telegram AI Bot"
        }

        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "frequency_penalty": 0.2
        }

        try:
            async with self.http_session.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                if not data.get("choices"):
                    logger.error(f"Invalid API response: {data}")
                    return "⚠️ عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة لاحقاً."

                return data["choices"][0]["message"]["content"]

        except aiohttp.ClientError as e:
            logger.error(f"API Connection error: {str(e)}")
            return "❌ تعذر الاتصال بخدمة الذكاء الاصطناعي. يرجى المحاولة لاحقاً."
        except asyncio.TimeoutError:
            logger.error("API request timed out")
            return "⚠️ تجاوز الوقت المحدد للاتصال. يرجى المحاولة لاحقاً."
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return "⚠️ حدث خطأ غير متوقع. يرجى إعادة المحاولة."

    async def get_gemini_response(self, message: str) -> str:
        """الحصول على إجابة من Gemini API"""
        headers = {
            'Content-Type': 'application/json',
        }
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": message,
                        },
                    ],
                },
            ],
        }

        try:
            async with self.http_session.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=body,
                timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()

                if 'candidates' in data:
                    for candidate in data['candidates']:
                        for part in candidate['content']['parts']:
                            return part['text']
                else:
                    logger.error(f"Invalid Gemini response: {data}")
                    return "⚠️ عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة لاحقاً."

        except aiohttp.ClientError as e:
            logger.error(f"Gemini API Connection error: {str(e)}")
            return "❌ تعذر الاتصال بخدمة الذكاء الاصطناعي. يرجى المحاولة لاحقاً."
        except asyncio.TimeoutError:
            logger.error("Gemini API request timed out")
            return "⚠️ تجاوز الوقت المحدد للاتصال. يرجى المحاولة لاحقاً."
        except Exception as e:
            logger.error(f"Unexpected Gemini error: {str(e)}")
            return "⚠️ حدث خطأ غير متوقع. يرجى إعادة المحاولة."

    async def get_claude_response(self, message: str) -> str:
        """الحصول على إجابة من Claude API"""
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": message}
            ]
        }
        
        try:
            async with self.http_session.post(
                CLAUDE_URL,
                headers=headers,
                json=body,
                timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if 'content' in data:
                    return data['content'][0]['text']
                else:
                    logger.error(f"Invalid Claude response: {data}")
                    return "⚠️ عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة لاحقاً."
                
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            return "❌ تعذر الاتصال بخدمة Claude. يرجى المحاولة لاحقاً."

    async def get_mistral_response(self, message: str) -> str:
        """الحصول على إجابة من Mistral API"""
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": "mistral-medium",
            "messages": [
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            async with self.http_session.post(
                MISTRAL_URL,
                headers=headers,
                json=body,
                timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"Invalid Mistral response: {data}")
                    return "⚠️ عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة لاحقاً."
                
        except Exception as e:
            logger.error(f"Mistral API error: {str(e)}")
            return "❌ تعذر الاتصال بخدمة Mistral. يرجى المحاولة لاحقاً."

    async def get_deepseek_response(self, messages: List[Dict[str, str]]) -> str:
        """الحصول على إجابة من DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # استخدام السياق الكامل للرسائل
        payload = {
            "model": "deepseek-chat", # أو deepseek-coder حسب الحاجة
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            async with self.http_session.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"Invalid DeepSeek response: {data}")
                    return "⚠️ عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة لاحقاً."

        except aiohttp.ClientError as e:
            logger.error(f"DeepSeek API Connection error: {str(e)}")
            return "❌ تعذر الاتصال بخدمة DeepSeek. يرجى المحاولة لاحقاً."
        except asyncio.TimeoutError:
            logger.error("DeepSeek API request timed out")
            return "⚠️ تجاوز الوقت المحدد للاتصال. يرجى المحاولة لاحقاً."
        except Exception as e:
            logger.error(f"Unexpected DeepSeek error: {str(e)}")
            return "⚠️ حدث خطأ غير متوقع. يرجى إعادة المحاولة."

    async def get_manus_response(self, messages: List[Dict[str, str]]) -> str:
        """الحصول على إجابة من نموذج Manus (محاكاة/داخلي)"""
        # نظرًا لأن Manus هو نظام داخلي، لا يمكن استدعاؤه عبر واجهة برمجة تطبيقات عامة.
        # سنقوم بمحاكاة استجابة أو إرجاع رسالة توضيحية.
        # يجب تجنب الكشف عن أي تفاصيل خاصة بالنظام.
        logger.info("Manus model selected, returning placeholder response.")
        # يمكنك هنا إضافة منطق لاستدعاء Manus إذا كان هناك طريقة داخلية لذلك
        # أو ببساطة إرجاع رسالة توضح أن النموذج قيد التطوير أو للاستخدام الداخلي.
        last_user_message = "" 
        if messages and messages[-1]["role"] == "user":
            last_user_message = messages[-1]["content"]
            
        # محاكاة بسيطة للرد
        return f"🤖 (Manus) تم استلام رسالتك: '{last_user_message}'. أنا نموذج Manus، قيد التطوير حاليًا للاستخدام الداخلي. قد لا أتمكن من الرد على جميع الاستفسارات في الوقت الحالي."

    def record_conversation(self, user_id: int, message: str, is_user: bool = True):
        """تسجيل المحادثة للتدريب التلقائي"""
        user_id_str = str(user_id)
        if user_id_str not in self.conversation_history:
            self.conversation_history[user_id_str] = []

        self.conversation_history[user_id_str].append({
            "message": message,
            "is_user": is_user,
            "timestamp": datetime.now(TIMEZONE).isoformat()
        })

        # حفظ المحادثات الطويلة في ملفات منفصلة
        if len(self.conversation_history[user_id_str]) > 50:
            self.save_conversation_history(user_id_str)
            self.conversation_history[user_id_str] = []

    def save_conversation_history(self, user_id_str: str):
        """حفظ تاريخ المحادثات في ملف"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'training_data/conversation_{user_id_str}_{timestamp}.json'

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "user_id": user_id_str,
                    "conversation": self.conversation_history[user_id_str]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversation history: {str(e)}")

    async def show_ai_answer(self, query):
        """عرض إجابة الذكاء الاصطناعي عند الضغط على الزر"""
        data = query.data.split('_')
        user_id = int(data[2])
        question_hash = data[3]
        
        user_id_str = str(user_id)
        
        # الحصول على آخر إجابة من سياق المحادثة
        if user_id_str in self.user_context and len(self.user_context[user_id_str]) >= 2:
            answer = self.user_context[user_id_str][-1]["content"]
            formatted_text = self.format_response(answer)
            
            # حذف رسالة الزر
            await query.message.delete()
            
            # إرسال الإجابة
            if len(formatted_text) > MAX_MESSAGE_LENGTH:
                parts = [formatted_text[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(formatted_text), MAX_MESSAGE_LENGTH)]
                for part in parts:
                    await query.message.reply_text(part, parse_mode='HTML')
            else:
                await query.message.reply_text(formatted_text, parse_mode='HTML')
            
            # إضافة أزرار التقييم
            feedback_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👍 الإجابة صحيحة", callback_data=f"feedback_correct_{user_id}_{question_hash}")],
                [InlineKeyboardButton("👎 تصحيح الإجابة", callback_data=f"feedback_incorrect_{user_id}_{question_hash}")]
            ])
            
            await query.message.reply_text(
                "هل كانت الإجابة مفيدة؟",
                reply_markup=feedback_keyboard
            )
            
            # إضافة أزرار البحث إذا كان السؤال مناسباً
            question = self.user_context[user_id_str][-2]["content"]
            if self.should_show_search_buttons(question):
                search_query = quote(question)
                search_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 بحث في جوجل", url=f"https://www.google.com/search?q={search_query}")],
                    [InlineKeyboardButton("📚 بحث في ويكيبيديا", url=f"https://ar.wikipedia.org/wiki/{search_query}")],
                    [InlineKeyboardButton("🎥 بحث في يوتيوب", url=f"https://www.youtube.com/results?search_query={search_query}")]
                ])
                await query.message.reply_text("يمكنك البحث عن المزيد من المعلومات:", reply_markup=search_keyboard)
            
            # إرسال التذييل إذا كان مفعلاً
            await self.maybe_send_footer(query.message, user_id)
        else:
            await query.message.reply_text("⚠️ عذراً، لم يتم العثور على الإجابة. يرجى طرح السؤال مرة أخرى.")

    async def send_response_with_feedback(self, update: Update, text: str, user_id: int, question: str):
        """إرسال الإجابة مع خيار التقييم"""
        formatted_text = self.format_response(text)

        if len(formatted_text) > MAX_MESSAGE_LENGTH:
            parts = [formatted_text[i:i+MAX_MESSAGE_LENGTH]
                     for i in range(0, len(formatted_text), MAX_MESSAGE_LENGTH)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='HTML')
        else:
            await update.message.reply_text(formatted_text, parse_mode='HTML')

        # إنشاء معرف فريد للسؤال
        question_hash = self.generate_question_hash(question)

        # إضافة أزرار روابط البحث إذا كان السؤال مناسباً
        if self.should_show_search_buttons(question):
            search_query = quote(question)
            search_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔍 بحث في جوجل", url=f"https://www.google.com/search?q={search_query}")],
                [InlineKeyboardButton(
                    "📚 بحث في ويكيبيديا", url=f"https://ar.wikipedia.org/wiki/{search_query}")],
                [InlineKeyboardButton(
                    "🎥 بحث في يوتيوب", url=f"https://www.youtube.com/results?search_query={search_query}")]
            ])
            await update.message.reply_text("يمكنك البحث عن المزيد من المعلومات:", reply_markup=search_keyboard)

        feedback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👍 الإجابة صحيحة", callback_data=f"feedback_correct_{user_id}_{question_hash}")],
            [InlineKeyboardButton(
                "👎 تصحيح الإجابة", callback_data=f"feedback_incorrect_{user_id}_{question_hash}")]
        ])

        await update.message.reply_text(
            "هل كانت الإجابة مفيدة؟",
            reply_markup=feedback_keyboard
        )

        await self.maybe_send_footer(update, user_id)

    def generate_question_hash(self, question: str) -> str:
        """إنشاء هاش فريد للسؤال"""
        return hashlib.md5(question.encode('utf-8')).hexdigest()

    def format_response(self, text: str) -> str:
        """تنسيق الإجابة"""
        text = html.escape(text)
        text = re.sub(r'```(\w*)\n(.*?)```',
                      r'<pre><code class="language-\1">\2</code></pre>', text, flags=re.DOTALL)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
        text = text.replace('\n\n', '<br><br>')
        return text
        
    def should_show_search_buttons(self, question: str) -> bool:
        """تحديد ما إذا كان يجب عرض أزرار البحث"""
        if not WEB_SEARCH_ENABLED:
            return False

        search_keywords = ["معلومات عن", "ما هو", "من هو",
                          "تعريف", "بحث عن", "أين", "متى", "كيف"]
        personal_keywords = ["أنا", "لي", "عندي", "خاص", "رسالة", "طلب"]

        return (any(keyword in question.lower() for keyword in search_keywords)
                and not any(keyword in question.lower() for keyword in personal_keywords))

    async def maybe_send_footer(self, update: Update, user_id: int):
        """إرسال تذييل الرسالة إذا كان مفعلاً"""
        user_id_str = str(user_id)
        if self.show_footer.get(user_id_str, True):
            footer = """
━━━━━━━━━━━━━━━━━
💎 البوت المتميز للذكاء الاصطناعي
📅 الإصدار: 3.0 | المطور: @HH_F_Q
"""
            await update.message.reply_text(footer)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأزرار التفاعلية"""
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = str(query.from_user.id)

        # --- معالجة أزرار الأدمن الجديدة ---
        if data == "admin_main":
            await self.show_admin_main_menu(query)
        elif data == "admin_stats":
            await self.show_admin_stats_menu(query)
        elif data == "admin_users":
            await self.show_admin_users_menu(query)
        elif data == "admin_settings":
            await self.show_admin_settings_menu(query)
        elif data == "admin_broadcast":
            await self.request_broadcast(update, context) # استخدام الدالة الموجودة
        elif data == "admin_update_data":
            await self.update_data(update) # استخدام الدالة الموجودة
        elif data == "admin_show_stats":
            await self.show_stats(update) # استخدام الدالة الموجودة
        elif data == "admin_show_user_stats":
            await self.show_user_stats(update) # استخدام الدالة الموجودة
        elif data == "admin_show_ratings":
            await self.show_ratings_report(update) # استخدام الدالة الموجودة
        elif data == "admin_show_usage":
            await self.show_usage_report(update) # استخدام الدالة الموجودة
        elif data == "admin_pending_activations":
            await self.show_pending_activations(update) # استخدام الدالة الموجودة
        elif data == "admin_maintenance":
            await self.show_maintenance_settings(update) # استخدام الدالة الموجودة
        # --- نهاية معالجة أزرار الأدمن الجديدة ---
        
        # --- معالجة الأزرار الأخرى ---
        elif data.startswith("rate_"):
            await self.process_rating(query)
        elif data.startswith("feedback_"):
            await self.process_feedback(query)
        elif data.startswith("show_answer_"):
            await self.show_ai_answer(query)
        elif data.startswith("select_model_"):
            await self.select_ai_model(query)
        elif data.startswith(("activate_", "reject_", "refresh_", "message_", "cancel_")):
            # هذه خاصة بلوحة تفعيل المستخدم المتقدمة
            await self.process_activation_action(query)
        elif data == "confirm_broadcast":
            await self.send_broadcast(context)
        elif data == "edit_broadcast":
            await self.edit_broadcast(query, context)
        elif data == "cancel_broadcast":
            await query.edit_message_text("❌ تم إلغاء عملية البث")
        elif data == "footer_on":
            await self.toggle_footer(query, True)
        elif data == "footer_off":
            await self.toggle_footer(query, False)
        elif data == "enable_maintenance":
            await self.set_maintenance_mode(query, True)
        elif data == "disable_maintenance":
            await self.set_maintenance_mode(query, False)
        elif data == "request_activation":
            await self.request_activation(query)
        elif data == "refresh_activations": # هذا الزر قد يكون مكررًا مع admin_pending_activations
            await self.show_pending_activations(query)
        elif data == "cancel_activation":
            await self.cancel_activation_request(query)
        elif data.startswith("web_search_"):
            await self.handle_web_search(query)
        # --- نهاية معالجة الأزرار الأخرى ---
        # يمكنك إضافة معالجات للأزرار الجديدة المقترحة هنا لاحقًا
        # elif data == "admin_list_users":
        #     await self.admin_list_users_handler(query)
        # elif data == "admin_add_user":
        #     await self.admin_add_user_handler(query)
        # ... etc.

    # --- دوال عرض قوائم الأدمن الجديدة ---
    async def show_admin_main_menu(self, query):
        await query.edit_message_text("🔑 لوحة تحكم الأدمن الرئيسية:", reply_markup=self.admin_main_keyboard)

    async def show_admin_stats_menu(self, query):
        await query.edit_message_text("📊 قائمة الإحصائيات:", reply_markup=self.admin_stats_keyboard)

    async def show_admin_users_menu(self, query):
        await query.edit_message_text("👥 قائمة إدارة المستخدمين:", reply_markup=self.admin_users_keyboard)

    async def show_admin_settings_menu(self, query):
        await query.edit_message_text("⚙️ قائمة إعدادات البوت:", reply_markup=self.admin_settings_keyboard)
    # --- نهاية دوال عرض قوائم الأدمن الجديدة ---

    async def select_ai_model(self, query):
        """اختيار نموذج الذكاء الاصطناعي"""
        model_id = query.data.split('_')[-1]
        user_id = str(query.from_user.id)
        
        if model_id in self.available_models:
            self.user_models[user_id] = model_id
            self.save_data('user_models.json', self.user_models)
            
            model_name = self.available_models[model_id]["name"]
            await query.edit_message_text(f"✅ تم تغيير نموذج الذكاء الاصطناعي إلى {model_name} بنجاح!")
        else:
            await query.edit_message_text("❌ النموذج المحدد غير متوفر. يرجى اختيار نموذج آخر.")

    async def show_model_selection(self, update: Update):
        """عرض قائمة اختيار النموذج"""
        user_id = str(update.effective_user.id)
        current_model = self.user_models.get(user_id, "gpt-3.5-turbo")
        current_model_name = self.available_models[current_model]["name"]
        
        await update.message.reply_text(
            f"🤖 النموذج الحالي: {current_model_name}\n\nاختر نموذج الذكاء الاصطناعي الذي تريد استخدامه:",
            reply_markup=self.model_selection_keyboard
        )

    async def handle_web_search(self, query):
        """معالجة طلبات البحث في الويب"""
        search_type = query.data.split('_')[-1]
        question = query.message.reply_to_message.text

        if search_type == "google":
            url = f"https://www.google.com/search?q={quote(question)}"
        elif search_type == "wiki":
            url = f"https://ar.wikipedia.org/wiki/{quote(question)}"
        else:
            url = f"https://www.google.com/search?q={quote(question)}"

        await query.edit_message_text(f"جارٍ تحويلك إلى نتائج البحث عن: {question[:50]}...")
        await asyncio.sleep(2)
        await query.message.reply_text(f"يمكنك الاطلاع على نتائج البحث هنا: {url}")

    async def process_feedback(self, query):
        """معالجة ملاحظات المستخدمين"""
        data = query.data.split('_')
        action = data[1]
        user_id = int(data[2])
        question_hash = data[3]

        if action == "correct":
            await self.handle_positive_feedback(query, user_id, question_hash)
        elif action == "incorrect":
            await self.handle_negative_feedback(query, user_id, question_hash)

    async def handle_positive_feedback(self, query, user_id: int, question_hash: str):
        """معالجة الملاحظات الإيجابية"""
        feedback_id = f"{user_id}_{question_hash}"
        self.user_feedback[feedback_id] = {
            "is_correct": True,
            "feedback_time": datetime.now(TIMEZONE).isoformat(),
            "feedback_user": query.from_user.id
        }

        self.save_data('user_feedback.json', self.user_feedback)
        await query.edit_message_text("✅ شكراً لتقييمك! تم تسجيل ملاحظاتك بنجاح.")

    async def handle_negative_feedback(self, query, user_id: int, question_hash: str):
        """معالجة الملاحظات السلبية"""
        await query.edit_message_text(
            "📝 يرجى إدخال التصحيح أو الإجابة الصحيحة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "إلغاء", callback_data="feedback_cancel")]
            ])
        )
        # هنا يمكن حفظ حالة أن المستخدم في وضع التصحيح

    async def request_activation(self, query):
        """طلب تفعيل حساب المستخدم"""
        user = query.from_user
        user_id = str(user.id)

        if user_id in self.pending_activations:
            await query.edit_message_text("⏳ يوجد طلب تفعيل قيد المراجعة بالفعل. الرجاء الانتظار...")
            return

        self.pending_activations[user_id] = {
            "name": user.full_name,
            "username": user.username,
            "time": datetime.now(TIMEZONE).isoformat(),
            "user_info": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code
            }
        }
        self.save_data('pending_activations.json', self.pending_activations)

        admin_msg = f"""
📩 **طلب تفعيل جديد**

👤 **المعلومات الأساسية:**
- الاسم: {user.full_name}
- المعرف: @{user.username if user.username else 'N/A'}
- الرمز اللغوي: {user.language_code if user.language_code else 'غير معروف'}

🆔 **User ID:** `{user.id}`
📅 **وقت الطلب:** {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}

📊 **إحصائيات الطلب:**
- الطلبات المعلقة: {len(self.pending_activations)}
- المستخدمون الجدد اليوم: {self.get_new_users_today()}
"""
        await self.notify_admins(query.bot, admin_msg, reply_markup=self.advanced_activation_keyboard)

        await query.edit_message_text("""
✅ **تم إرسال طلب التفعيل بنجاح**

سيتم مراجعة طلبك من قبل المسؤولين قريباً. سيصلك إشعار عند الموافقة على طلبك.

⏳ **مدة الانتظار المتوقعة:** عادةً ما تتم المراجعة خلال 24 ساعة
""")

    async def cancel_activation_request(self, query):
        """إلغاء طلب التفعيل"""
        user_id = str(query.from_user.id)

        if user_id in self.pending_activations:
            del self.pending_activations[user_id]
            self.save_data('pending_activations.json',
                           self.pending_activations)
            await query.edit_message_text("✅ تم إلغاء طلب التفعيل بنجاح")
        else:
            await query.edit_message_text("⚠️ لا يوجد طلب تفعيل قيد الانتظار لإلغائه")

    async def process_activation_action(self, query):
        """معالجة إجراءات التفعيل من الأدمن"""
        data = query.data.split('_')
        action = data[0]
        user_id = data[1] if len(data) > 1 else None

        if not user_id or user_id not in self.pending_activations:
            await query.answer("❌ هذا الطلب لم يعد موجوداً")
            return

        user_data = self.pending_activations[user_id]

        if action == "activate":
            await self.activate_user_account(query, user_id, user_data)
        elif action == "reject":
            await self.reject_user_account(query, user_id, user_data)
        elif action == "refresh":
            await self.refresh_user_info(query, user_id)
        elif action == "message":
            await self.prepare_admin_message(query, user_id, user_data)
        elif action == "cancel":
            await self.cancel_activation_request(query)

    async def activate_user_account(self, query, user_id: str, user_data: dict):
        """تفعيل حساب المستخدم"""
        self.user_context[user_id] = []
        del self.pending_activations[user_id]
        self.save_all_data()

        await query.edit_message_text(f"""
✅ **تم تفعيل المستخدم بنجاح**

👤 **المستخدم:** {user_data['name']}
🆔 **User ID:** `{user_id}`
⏱ **وقت التفعيل:** {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}
""")

        try:
            await query.bot.send_message(
                chat_id=int(user_id),
                text="""
🎉 **تم تفعيل حسابك بنجاح!**

يمكنك الآن استخدام جميع ميزات البوت:

✨ **طرح أسئلة متميزة**
📊 **الوصول إلى إحصائياتك**
⚙️ **تخصيص إعداداتك**

ابدأ رحلتك مع الذكاء الاصطناعي الآن!
""",
                reply_markup=self.main_keyboard
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {str(e)}")

    async def reject_user_account(self, query, user_id: str, user_data: dict):
        """رفض طلب التفعيل"""
        del self.pending_activations[user_id]
        self.save_data('pending_activations.json', self.pending_activations)

        await query.edit_message_text(f"""
❌ **تم رفض طلب التفعيل**

👤 **المستخدم:** {user_data['name']}
🆔 **User ID:** `{user_id}`
⏱ **وقت الرفض:** {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}
""")

        try:
            await query.bot.send_message(
                chat_id=int(user_id),
                text="""
⚠️ **نأسف، تم رفض طلب تفعيل حسابك**

يمكنك المحاولة مرة أخرى لاحقاً أو التواصل مع الدعم الفني لمزيد من المساعدة.
"""
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {str(e)}")

    async def refresh_user_info(self, query, user_id: str):
        """تحديث معلومات المستخدم"""
        try:
            user = await query.bot.get_chat(user_id)
            self.pending_activations[user_id]["user_info"] = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code
            }
            self.save_data('pending_activations.json',
                           self.pending_activations)

            await query.answer("✅ تم تحديث معلومات المستخدم")
        except Exception as e:
            await query.answer("❌ فشل في تحديث المعلومات")

    async def prepare_admin_message(self, query, user_id: str, user_data: dict):
        """إعداد رسالة الأدمن للمستخدم"""
        await query.edit_message_text(
            f"✉️ **مراسلة المستخدم:** {user_data['name']}\n\n"
            f"أدخل الرسالة التي تريد إرسالها للمستخدم:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "إلغاء", callback_data=f"cancel_message_{user_id}")]
            ])
        )
        # هنا يمكن حفظ حالة أن الأدمن في وضع إرسال رسالة

    async def set_maintenance_mode(self, query, status: bool):
        """تفعيل/إلغاء وضع الصيانة"""
        self.maintenance_mode = status
        self.save_data('maintenance_mode.json', self.maintenance_mode)

        if status:
            await query.edit_message_text("✅ تم تفعيل وضع الصيانة بنجاح. البوت الآن غير متاح للمستخدمين العاديين.")
        else:
            await query.edit_message_text("✅ تم إلغاء وضع الصيانة بنجاح. البوت يعمل الآن بشكل طبيعي.")

    async def toggle_footer(self, query, status: bool):
        """تبديل حالة التذييل"""
        user_id = str(query.from_user.id)
        self.show_footer[user_id] = status
        self.save_data('footer_settings.json', self.show_footer)

        status_text = "✅ تم تفعيل عرض التذييل" if status else "❌ تم إيقاف عرض التذييل"
        await query.edit_message_text(f"{status_text}\n\nيمكنك تغيير الإعدادات في أي وقت من خلال قائمة الإعدادات.")

    async def send_broadcast(self, context: ContextTypes.DEFAULT_TYPE):
        """إرسال رسالة جماعية"""
        if not self.last_broadcast:
            await context.bot.send_message(
                chat_id=ADMIN_IDS[0],
                text="❌ لا توجد رسالة بث محفوظة"
            )
            return

        success = 0
        failed = 0
        total_users = len(self.user_context)

        for user_id in self.user_context:
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"📢 إعلان من الإدارة:\n\n{self.last_broadcast}"
                )
                success += 1
                await asyncio.sleep(0.1)  # تجنب حظر التليجرام
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to {user_id}: {str(e)}")

        report = (
            f"📊 تقرير البث\n\n"
            f"📝 الرسالة: {self.last_broadcast[:50]}...\n"
            f"✅ نجاح: {success}\n"
            f"❌ فشل: {failed}\n"
            f"👥 إجمالي المستخدمين: {total_users}\n"
            f"⏰ الوقت: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self.notify_admins(context.bot, report)

    async def show_stats(self, update: Update):
        """عرض إحصائيات البوت"""
        stats_msg = f"""
📊 **إحصائيات البوت:**

👥 **المستخدمون:**
- الإجمالي: {self.user_count}
- النشطون: {len(self.user_context)}
- المعلقون: {len(self.pending_activations)}

⭐ **التقييمات:**
- المتوسط: {self.calculate_average_rating()}
- عدد التقييمات: {len(self.user_ratings)}

📅 **المستخدمون الجدد اليوم:** {self.get_new_users_today()}

🔄 **آخر تحديث:** {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')}

📈 **طلبات API:**
- الإجمالي: {self.bot_stats['total_requests']}
- الناجحة: {self.bot_stats['successful_requests']}
- الفاشلة: {self.bot_stats['failed_requests']}
"""
        await update.message.reply_text(stats_msg)

    def calculate_average_rating(self) -> float:
        """حساب متوسط التقييم"""
        if not self.user_ratings:
            return 0.0
        return round(sum(self.user_ratings.values()) / len(self.user_ratings), 2)

    def get_new_users_today(self) -> int:
        """الحصول على عدد المستخدمين الجدد اليوم"""
        today = datetime.now(TIMEZONE).date()
        return sum(
            1 for join_date in self.user_join_dates.values()
            if datetime.fromisoformat(join_date).date() == today
        )

    async def show_user_stats(self, update: Update):
        """عرض إحصائيات المستخدمين"""
        today = datetime.now(TIMEZONE).date()
        new_today = sum(
            1 for join_date in self.user_join_dates.values()
            if datetime.fromisoformat(join_date).date() == today
        )

        stats_msg = f"""
👥 **إحصائيات المستخدمين:**

📅 **اليوم:**
- الجدد: {new_today}

📆 **الإجمالي:**
- الكلي: {self.user_count}
- النشطون: {len(self.user_context)}
- المعلقون: {len(self.pending_activations)}
"""
        await update.message.reply_text(stats_msg)

    async def show_user_usage(self, update: Update):
        """عرض إحصائيات استخدام المستخدم"""
        user = update.effective_user
        user_id = str(user.id)

        if user_id not in self.user_usage:
            self.user_usage[user_id] = {"count": 0, "last_used": None}
            self.save_data('user_usage.json', self.user_usage)

        usage = self.user_usage[user_id]
        last_used = "لم يتم الاستخدام بعد" if not usage.get(
            "last_used") else datetime.fromisoformat(usage["last_used"]).strftime("%Y-%m-%d %H:%M")

        model_id = self.user_models.get(user_id, "gpt-3.5-turbo")
        model_name = self.available_models[model_id]["name"]

        stats_msg = f"""
📊 **إحصائيات استخدامك:**

🔢 **عدد الاستخدامات:** {usage.get("count", 0)}
⏱ **آخر استخدام:** {last_used}
🤖 **النموذج المستخدم:** {model_name}

📅 **تاريخ الانضمام:** {datetime.fromisoformat(self.user_join_dates.get(user_id, datetime.now(TIMEZONE).isoformat())).strftime("%Y-%m-%d")}
"""
        await update.message.reply_text(stats_msg)

    async def show_ratings_report(self, update: Update):
        """عرض تقرير التقييمات"""
        if not self.user_ratings:
            await update.message.reply_text("⚠️ لا توجد تقييمات حتى الآن.")
            return

        avg_rating = self.calculate_average_rating()
        ratings_count = len(self.user_ratings)

        # توزيع التقييمات
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating in self.user_ratings.values():
            distribution[rating] = distribution.get(rating, 0) + 1

        report = f"""
⭐ **تقرير التقييمات:**

📊 **الإحصائيات العامة:**
- متوسط التقييم: {avg_rating}/5
- عدد التقييمات: {ratings_count}

📈 **توزيع التقييمات:**
- ⭐: {distribution[1]} ({round(distribution[1]/ratings_count*100, 1)}%)
- ⭐⭐: {distribution[2]} ({round(distribution[2]/ratings_count*100, 1)}%)
- ⭐⭐⭐: {distribution[3]} ({round(distribution[3]/ratings_count*100, 1)}%)
- ⭐⭐⭐⭐: {distribution[4]} ({round(distribution[4]/ratings_count*100, 1)}%)
- ⭐⭐⭐⭐⭐: {distribution[5]} ({round(distribution[5]/ratings_count*100, 1)}%)
"""
        await update.message.reply_text(report)

    async def show_maintenance_settings(self, update: Update):
        """عرض إعدادات وضع الصيانة"""
        status = "✅ مفعل" if self.maintenance_mode else "❌ غير مفعل"
        await update.message.reply_text(
            f"🛠 **وضع الصيانة:** {status}\n\nاختر الإجراء المناسب:",
            reply_markup=self.maintenance_keyboard
        )

    async def update_data(self, update: Update):
        """تحديث البيانات"""
        self.save_all_data()
        await update.message.reply_text("✅ تم تحديث جميع البيانات بنجاح.")

    async def show_pending_activations(self, update: Update):
        """عرض طلبات التفعيل المعلقة"""
        if not self.pending_activations:
            await update.message.reply_text("✅ لا توجد طلبات تفعيل معلقة.")
            return

        count = len(self.pending_activations)
        await update.message.reply_text(f"🔍 يوجد {count} طلب تفعيل معلق.")

        for user_id, data in list(self.pending_activations.items())[:5]:  # عرض أول 5 طلبات فقط
            user_info = data.get("user_info", {})
            activation_msg = f"""
👤 **طلب تفعيل:**
- الاسم: {data.get('name', 'غير معروف')}
- المعرف: @{data.get('username', 'N/A')}
- الرمز اللغوي: {user_info.get('language_code', 'غير معروف')}
- الوقت: {datetime.fromisoformat(data.get('time', datetime.now(TIMEZONE).isoformat())).strftime('%Y-%m-%d %H:%M')}
- User ID: `{user_id}`
"""
            await update.message.reply_text(
                activation_msg,
                reply_markup=self.advanced_activation_keyboard
            )

        if count > 5:
            await update.message.reply_text(f"⚠️ هناك {count - 5} طلبات إضافية لم يتم عرضها.")

    async def show_usage_report(self, update: Update):
        """عرض تقرير الاستخدام"""
        if not self.user_usage:
            await update.message.reply_text("⚠️ لا توجد بيانات استخدام حتى الآن.")
            return

        total_usage = sum(usage.get("count", 0)
                          for usage in self.user_usage.values())
        active_users = len([
            user_id for user_id, usage in self.user_usage.items()
            if usage.get("last_used") and
            datetime.fromisoformat(usage["last_used"]) >
            datetime.now(TIMEZONE) - timedelta(days=7)
        ])

        # توزيع النماذج
        model_distribution = {}
        for user_id, model_id in self.user_models.items():
            model_name = self.available_models.get(model_id, {"name": model_id})["name"]
            model_distribution[model_name] = model_distribution.get(model_name, 0) + 1

        report = f"""
📊 **تقرير الاستخدام:**

👥 **المستخدمون:**
- النشطون (7 أيام): {active_users}
- إجمالي المستخدمين: {len(self.user_usage)}

🔢 **الاستخدام:**
- إجمالي الطلبات: {total_usage}
- متوسط الطلبات لكل مستخدم: {round(total_usage/len(self.user_usage), 1) if self.user_usage else 0}

🤖 **توزيع النماذج:**
"""
        for model_name, count in model_distribution.items():
            percentage = round(count/len(self.user_models)*100, 1) if self.user_models else 0
            report += f"- {model_name}: {count} ({percentage}%)\n"

        await update.message.reply_text(report)

    async def request_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """طلب إرسال رسالة جماعية"""
        await update.message.reply_text(
            "📣 **إرسال رسالة جماعية**\n\nأدخل الرسالة التي تريد إرسالها لجميع المستخدمين:"
        )
        context.user_data["awaiting_broadcast"] = True

    async def edit_broadcast(self, query, context: ContextTypes.DEFAULT_TYPE):
        """تعديل رسالة البث"""
        await query.edit_message_text(
            f"📝 **تعديل رسالة البث**\n\nالرسالة الحالية:\n\n{self.last_broadcast}\n\nأدخل الرسالة الجديدة:"
        )
        context.user_data["awaiting_broadcast"] = True

    async def request_rating(self, update: Update):
        """طلب تقييم البوت"""
        await update.message.reply_text(
            "⭐ **تقييم البوت**\n\nيرجى تقييم تجربتك مع البوت:",
            reply_markup=self.rating_keyboard
        )

    async def process_rating(self, query):
        """معالجة تقييم المستخدم"""
        rating = int(query.data.split('_')[1])
        user_id = str(query.from_user.id)
        self.user_ratings[user_id] = rating
        self.save_data('user_ratings.json', self.user_ratings)

        await query.edit_message_text(f"✅ شكراً لتقييمك! لقد قمت بتقييم البوت بـ {rating} نجوم.")

    async def show_footer_settings(self, update: Update):
        """عرض إعدادات التذييل"""
        user_id = str(update.effective_user.id)
        status = "✅ مفعل" if self.show_footer.get(user_id, True) else "❌ غير مفعل"
        await update.message.reply_text(
            f"⚙️ **إعدادات التذييل**\n\nحالة التذييل: {status}\n\nاختر الإعداد المناسب:",
            reply_markup=self.footer_keyboard
        )

    async def show_features(self, update: Update):
        """عرض مميزات البوت"""
        features_msg = """
✨ **مميزات البوت المتميز:**

🤖 **نماذج ذكاء اصطناعي متعددة:**
• GPT-3.5 Turbo - نموذج متوازن للمهام العامة
• Gemini 1.5 Flash - نموذج سريع من Google
• Claude 3 Haiku - نموذج متخصص في المحادثات الطبيعية
• Mistral Medium - نموذج مفتوح المصدر عالي الأداء

💬 **دعم متكامل للغة العربية:**
• فهم ممتاز للهجات العربية المختلفة
• إجابات دقيقة ومفصلة باللغة العربية
• تنسيق النصوص العربية بشكل احترافي

🔍 **ميزات متقدمة:**
• حفظ سياق المحادثة لتجربة أكثر تفاعلية
• إمكانية البحث المباشر عن المعلومات
• تقييم الإجابات وتقديم ملاحظات للتحسين
• تخصيص إعدادات البوت حسب تفضيلاتك

📊 **إحصائيات مفصلة:**
• متابعة استخدامك للبوت
• الاطلاع على تقييمات المستخدمين
• تحليل أداء النماذج المختلفة

🔒 **خصوصية وأمان:**
• حماية بيانات المستخدمين
• تشفير المحادثات
• عدم مشاركة البيانات مع أطراف ثالثة
"""
        await update.message.reply_text(features_msg)

    async def show_channels(self, update: Update):
        """عرض قنوات البوت"""
        await update.message.reply_text(
            "📢 **قنواتنا الرسمية**\n\nتابعنا على القنوات التالية للحصول على آخر التحديثات والأخبار:",
            reply_markup=self.links_keyboard
        )

    async def contact_developer(self, update: Update):
        """التواصل مع المطور"""
        await update.message.reply_text(
            "🌐 **التواصل مع المطور**\n\nيمكنك التواصل مع مطور البوت عبر:\n\n"
            "• تيليجرام: @HH_F_Q\n"
            "• البريد الإلكتروني: developer@example.com\n\n"
            "نرحب بملاحظاتك واقتراحاتك لتحسين البوت!"
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الملفات المرسلة"""
        user = update.effective_user
        document = update.message.document
        
        await update.message.reply_text("🔄 جاري معالجة الملف، يرجى الانتظار...")
        
        try:
            file = await context.bot.get_file(document.file_id)
            file_path = f"user_files/{document.file_name}"
            
            await file.download_to_drive(file_path)
            
            # تحليل محتوى الملف حسب نوعه
            if document.file_name.endswith(('.txt', '.md', '.py', '.js', '.html', '.css', '.json')):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # إرسال محتوى الملف للتحليل
                question = f"تحليل محتوى الملف {document.file_name}:\n\n{content[:1000]}..."
                self.request_queue.put((update, user.id, question))
            else:
                await update.message.reply_text(
                    f"✅ تم استلام الملف {document.file_name}. يرجى إخباري بما تريد معرفته عن هذا الملف."
                )
        except Exception as e:
            logger.error(f"Error handling document: {str(e)}")
            await update.message.reply_text("❌ حدث خطأ أثناء معالجة الملف. يرجى المحاولة مرة أخرى.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الصور المرسلة"""
        user = update.effective_user
        photo = update.message.photo[-1]  # أعلى دقة
        
        await update.message.reply_text("🔄 جاري معالجة الصورة، يرجى الانتظار...")
        
        try:
            file = await context.bot.get_file(photo.file_id)
            file_path = f"user_files/photo_{photo.file_id}.jpg"
            
            await file.download_to_drive(file_path)
            
            # إرسال رسالة للمستخدم
            await update.message.reply_text(
                "✅ تم استلام الصورة. يرجى إخباري بما تريد معرفته عن هذه الصورة."
            )
        except Exception as e:
            logger.error(f"Error handling photo: {str(e)}")
            await update.message.reply_text("❌ حدث خطأ أثناء معالجة الصورة. يرجى المحاولة مرة أخرى.")

    async def notify_admins(self, bot, message: str, reply_markup=None):
        """إرسال إشعار لجميع المسؤولين"""
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")

    async def periodic_save_task(self):
        """حفظ البيانات بشكل دوري"""
        while True:
            await asyncio.sleep(1800)  # كل 30 دقيقة
            self.save_all_data()
            logger.info("Periodic data save completed")


async def main():
    """تشغيل البوت"""
    bot = PremiumAIBot()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", bot.welcome))
    application.add_handler(CommandHandler("help", bot.show_features))
    
    # إضافة معالج الرسائل
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # إضافة معالج الملفات والصور
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    
    # إضافة معالج الأزرار التفاعلية
    application.add_handler(CallbackQueryHandler(bot.handle_callback))

    # بدء البوت
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # الانتظار حتى إيقاف البوت
    await application.updater.stop()
    await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
