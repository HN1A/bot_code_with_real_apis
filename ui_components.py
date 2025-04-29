from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from typing import Dict, List, Any, Optional
import logging

# استيراد دوال API
from api_calls import (
    get_stock_chart_data,
    get_stock_holders_data,
    get_stock_insights_data,
    get_stock_sec_filing_data,
    get_stock_analyst_reports,
    get_linkedin_profile
)

logger = logging.getLogger(__name__)

# تعريف الحد الأقصى لطول الرسالة
MAX_MESSAGE_LENGTH = 4096

class UIComponents:
    """فئة تحتوي على مكونات واجهة المستخدم المحسنة"""
    
    @staticmethod
    def get_welcome_message(user_first_name: str) -> str:
        """إنشاء رسالة ترحيبية محسنة"""
        welcome_message = f"👋 أهلاً بك يا {user_first_name}!\n\n"
        welcome_message += "أنا بوت الذكاء الاصطناعي المتميز الخاص بك، جاهز لمساعدتك في مجموعة متنوعة من المهام.\n\n"
        welcome_message += "**ماذا يمكنني أن أفعل؟**\n"
        welcome_message += "🧠 الإجابة على أسئلتك باستخدام نماذج AI متقدمة.\n"
        welcome_message += "📈 توفير معلومات محدثة عن أسواق الأسهم.\n"
        welcome_message += "🔗 البحث عن ملفات تعريف LinkedIn.\n"
        welcome_message += "➕ والمزيد! استكشف الأزرار أدناه.\n\n"
        welcome_message += "👇 اختر أحد الخيارات للبدء:"
        
        return welcome_message
    
    @staticmethod
    def get_features_message() -> str:
        """إنشاء رسالة مميزات محسنة"""
        features_text = "✨ **مميزات البوت الرئيسية** ✨\n\n"
        features_text += "1️⃣ **نماذج ذكاء اصطناعي متعددة:**\n"
        features_text += "   - 🚀 GPT-3.5 Turbo (OpenRouter)\n"
        features_text += "   - ✨ Gemini 1.5 Flash (Google)\n"
        features_text += "   - 🧠 Claude 3 Haiku (Anthropic)\n"
        features_text += "   - 🌬️ Mistral Medium (Mistral AI)\n"
        features_text += "   - 🔍 DeepSeek Chat (DeepSeek)\n"
        features_text += "   - 🤖 Manus (Internal - قيد التطوير)\n"
        features_text += "   *يمكنك التبديل بين النماذج المتاحة.*\n\n"
        
        features_text += "2️⃣ **معلومات الأسهم (Yahoo Finance):**\n"
        features_text += "   - 📈 احصل على أسعار الأسهم الحالية والسابقة.\n"
        features_text += "   - 📊 عرض التحليلات الفنية (قصيرة/متوسطة/طويلة المدى).\n"
        features_text += "   - 🎯 معرفة توصيات المحللين والأسعار المستهدفة.\n"
        features_text += "   - 🧑‍💼 الاطلاع على معلومات حول كبار الملاك الداخليين.\n\n"
        
        features_text += "3️⃣ **بحث LinkedIn:**\n"
        features_text += "   - 🔗 ابحث عن ملفات تعريف المستخدمين على LinkedIn باستخدام اسم المستخدم الخاص بهم.\n"
        features_text += "   - 👤 عرض ملخص للملف الشخصي يتضمن الاسم، العنوان الوظيفي، الموقع، الخبرات، التعليم، والمهارات.\n\n"
        
        features_text += "4️⃣ **أدوات إدارية متقدمة:**\n"
        features_text += "   - ⚙️ لوحة تحكم شاملة للمسؤولين.\n"
        features_text += "   - 📊 إحصائيات مفصلة حول استخدام البوت.\n"
        features_text += "   - 👥 إدارة المستخدمين وتفعيل الحسابات.\n"
        features_text += "   - 📢 إرسال رسائل بث للمستخدمين.\n"
        features_text += "   - 🛠️ وضع الصيانة.\n\n"
        
        features_text += "5️⃣ **ميزات إضافية:**\n"
        features_text += "   - 📝 حفظ سياق المحادثة لكل مستخدم.\n"
        features_text += "   - ⭐ نظام تقييم وجمع ملاحظات المستخدمين.\n"
        features_text += "   - 👣 تخصيص ظهور التذييل في الردود.\n"
        features_text += "   - ⏱️ تتبع إحصائيات الاستخدام الشخصية.\n\n"
        
        features_text += "💡 *نعمل باستمرار على إضافة المزيد من الميزات والتحسينات!*"
        
        return features_text
    
    @staticmethod
    def get_admin_welcome_message(admin_name: str) -> str:
        """إنشاء رسالة ترحيبية للمسؤول"""
        admin_welcome = f"👋 مرحباً بك يا {admin_name} في لوحة تحكم المسؤول!\n\n"
        admin_welcome += "**لوحة التحكم المحسنة تتيح لك:**\n"
        admin_welcome += "📊 عرض إحصائيات البوت المفصلة\n"
        admin_welcome += "👥 إدارة المستخدمين وطلبات التفعيل\n"
        admin_welcome += "⚙️ تعديل إعدادات البوت\n"
        admin_welcome += "📢 إرسال رسائل بث للمستخدمين\n"
        admin_welcome += "🛠️ تفعيل/تعطيل وضع الصيانة\n\n"
        admin_welcome += "👇 اختر أحد الخيارات من لوحة التحكم أدناه:"
        
        return admin_welcome
    
    @staticmethod
    def get_stock_info_header(symbol: str) -> str:
        """إنشاء ترويسة معلومات الأسهم"""
        return f"📊 **ملخص معلومات السهم: {symbol.upper()}**\n\n"
    
    @staticmethod
    def get_linkedin_profile_header(username: str) -> str:
        """إنشاء ترويسة ملف LinkedIn"""
        return f"👤 **ملف LinkedIn للمستخدم: {username}**\n\n"
    
    @staticmethod
    def get_model_selection_message() -> str:
        """إنشاء رسالة اختيار النموذج"""
        model_msg = "🤖 **اختر نموذج الذكاء الاصطناعي المفضل لديك:**\n\n"
        model_msg += "كل نموذج له نقاط قوة مختلفة:\n\n"
        model_msg += "• 🚀 **GPT-3.5 Turbo**: متوازن وسريع، مناسب لمعظم الاستخدامات اليومية.\n"
        model_msg += "• ✨ **Gemini 1.5 Flash**: قوي في المعرفة العامة والمهام متعددة الخطوات.\n"
        model_msg += "• 🧠 **Claude 3 Haiku**: ممتاز في التفكير المنطقي والتحليل.\n"
        model_msg += "• 🌬️ **Mistral Medium**: جيد في المهام اللغوية والإبداعية.\n"
        model_msg += "• 🔍 **DeepSeek Chat**: متخصص في الاستدلال العميق والمهام المعقدة.\n"
        model_msg += "• 🤖 **Manus**: نموذج داخلي قيد التطوير.\n\n"
        model_msg += "👇 اختر نموذجًا من القائمة أدناه:"
        
        return model_msg
    
    @staticmethod
    def format_stock_data(chart_data: dict, insights_data: dict, holders_data: dict) -> str:
        """تنسيق بيانات الأسهم بشكل جمالي"""
        response_message = ""
        
        if chart_data and chart_data.get("meta"):
            meta = chart_data["meta"]
            price = meta.get("regularMarketPrice", "N/A")
            currency = meta.get("currency", "")
            prev_close = meta.get("chartPreviousClose", "N/A")
            day_range = f"{meta.get('regularMarketDayLow', 'N/A')} - {meta.get('regularMarketDayHigh', 'N/A')}"
            
            response_message += "💰 **معلومات السعر الأساسية:**\n"
            response_message += f"*السعر الحالي:* {price} {currency}\n"
            response_message += f"*الإغلاق السابق:* {prev_close} {currency}\n"
            response_message += f"*نطاق اليوم:* {day_range}\n"
        else:
            response_message += "⚠️ لم يتم العثور على بيانات السعر الأساسية.\n"
            
        if insights_data and insights_data.get("instrumentInfo") and insights_data["instrumentInfo"].get("technicalEvents"):
            tech_events = insights_data["instrumentInfo"]["technicalEvents"]
            short_term = tech_events.get("shortTermOutlook", {}).get("stateDescription", "N/A")
            mid_term = tech_events.get("intermediateTermOutlook", {}).get("stateDescription", "N/A")
            long_term = tech_events.get("longTermOutlook", {}).get("stateDescription", "N/A")
            
            response_message += f"\n📈 **التحليل الفني (Trading Central):**\n"
            response_message += f"  - قصير المدى: {short_term}\n"
            response_message += f"  - متوسط المدى: {mid_term}\n"
            response_message += f"  - طويل المدى: {long_term}\n"
            
        if insights_data and insights_data.get("recommendation"):
            recommendation = insights_data["recommendation"]
            rating = recommendation.get("rating", "N/A")
            target_price = recommendation.get("targetPrice", "N/A")
            
            response_message += f"\n🎯 **توصية المحللين (Yahoo Finance):**\n"
            response_message += f"  - التقييم: {rating}\n"
            response_message += f"  - السعر المستهدف: {target_price}\n"
            
        if holders_data and holders_data.get("holders"):
            insider_count = len(holders_data["holders"]) 
            response_message += f"\n👥 **حاملو الأسهم الداخليون:**\n"
            response_message += f"  تم العثور على {insider_count} من كبار الملاك الداخليين.\n"
            
        return response_message
    
    @staticmethod
    def format_linkedin_profile(profile_data: dict, username: str) -> str:
        """تنسيق بيانات ملف LinkedIn بشكل جمالي"""
        if not profile_data:
            return f"❌ لم يتم العثور على ملف LinkedIn للمستخدم `{username}` أو حدث خطأ أثناء البحث."
            
        profile_url = profile_data.get("linkedinUrl", "غير متوفر")
        name = f"{profile_data.get('firstName', '')}" + (f" {profile_data.get('LastName', '')}" if profile_data.get("LastName") else "")
        title = profile_data.get("title", "غير متوفر")
        location = profile_data.get("location", {}).get("default", "غير متوفر")
        experience_count = len(profile_data.get("experience", []))
        education_count = len(profile_data.get("education", []))
        skills_count = len(profile_data.get("skills", []))
        
        response_message = ""
        response_message += f"*الاسم:* {name}\n"
        response_message += f"*العنوان الوظيفي:* {title}\n"
        response_message += f"*الموقع:* {location}\n"
        response_message += f"*الرابط:* {profile_url}\n\n"
        
        response_message += "📋 **ملخص المعلومات:**\n"
        response_message += f"*الخبرات:* {experience_count} وظيفة/منصب\n"
        response_message += f"*التعليم:* {education_count} مؤسسة تعليمية\n"
        response_message += f"*المهارات:* {skills_count} مهارة مدرجة\n"
        
        return response_message
