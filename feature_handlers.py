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

class FeatureHandlers:
    """فئة تحتوي على معالجات الميزات الإضافية للبوت"""
    
    def __init__(self, bot_instance):
        """تهيئة المعالجات مع إشارة إلى كائن البوت الرئيسي"""
        self.bot = bot_instance
        
    # --- دوال طلب معلومات إضافية ---
    async def request_stock_symbol(self, update: Update):
        """يطلب من المستخدم إدخال رمز السهم"""
        user_id = str(update.effective_user.id)
        self.bot.user_states[user_id] = "awaiting_stock_symbol"
        await update.message.reply_text("📈 يرجى إدخال رمز السهم الذي ترغب في البحث عنه (مثال: AAPL, GOOGL).")

    async def request_linkedin_username(self, update: Update):
        """يطلب من المستخدم إدخال اسم مستخدم LinkedIn"""
        user_id = str(update.effective_user.id)
        self.bot.user_states[user_id] = "awaiting_linkedin_username"
        await update.message.reply_text("🔗 يرجى إدخال اسم مستخدم LinkedIn الذي ترغب في البحث عنه (الموجود في رابط الملف الشخصي).")

    # --- دوال معالجة المعلومات الإضافية ---
    async def handle_stock_symbol_input(self, update: Update, symbol: str):
        """يعالج رمز السهم المدخل ويبحث عنه"""
        user_id = str(update.effective_user.id)
        await update.message.reply_text(f"🔍 جاري البحث عن معلومات السهم لـ {symbol.upper()}...")
        
        # استدعاء دوال Yahoo Finance API
        chart_data = await get_stock_chart_data(symbol)
        insights_data = await get_stock_insights_data(symbol)
        holders_data = await get_stock_holders_data(symbol)
        # sec_data = await get_stock_sec_filing_data(symbol) # يمكن إضافتها لاحقًا
        # analyst_data = await get_stock_analyst_reports(symbol) # يمكن إضافتها لاحقًا

        response_message = f"📊 **ملخص معلومات السهم: {symbol.upper()}**\n\n"
        
        if chart_data and chart_data.get("meta"):
            meta = chart_data["meta"]
            price = meta.get("regularMarketPrice", "N/A")
            currency = meta.get("currency", "")
            prev_close = meta.get("chartPreviousClose", "N/A")
            day_range = f"{meta.get('regularMarketDayLow', 'N/A')} - {meta.get('regularMarketDayHigh', 'N/A')}"
            response_message += f"*السعر الحالي:* {price} {currency}\n"
            response_message += f"*الإغلاق السابق:* {prev_close} {currency}\n"
            response_message += f"*نطاق اليوم:* {day_range}\n"
        else:
            response_message += "لم يتم العثور على بيانات السعر الأساسية.\n"
            
        if insights_data and insights_data.get("instrumentInfo") and insights_data["instrumentInfo"].get("technicalEvents"):
            tech_events = insights_data["instrumentInfo"]["technicalEvents"]
            short_term = tech_events.get("shortTermOutlook", {}).get("stateDescription", "N/A")
            mid_term = tech_events.get("intermediateTermOutlook", {}).get("stateDescription", "N/A")
            long_term = tech_events.get("longTermOutlook", {}).get("stateDescription", "N/A")
            response_message += f"\n*التحليل الفني (Trading Central):*\n"
            response_message += f"  - قصير المدى: {short_term}\n"
            response_message += f"  - متوسط المدى: {mid_term}\n"
            response_message += f"  - طويل المدى: {long_term}\n"
            
        if insights_data and insights_data.get("recommendation"):
            recommendation = insights_data["recommendation"]
            rating = recommendation.get("rating", "N/A")
            target_price = recommendation.get("targetPrice", "N/A")
            response_message += f"\n*توصية المحللين (Yahoo Finance):*\n"
            response_message += f"  - التقييم: {rating}\n"
            response_message += f"  - السعر المستهدف: {target_price}\n"
            
        if holders_data and holders_data.get("holders"):
            insider_count = len(holders_data["holders"]) 
            response_message += f"\n*حاملو الأسهم الداخليون:* تم العثور على {insider_count} من كبار الملاك الداخليين.\n"
            # يمكن عرض تفاصيل أكثر هنا إذا لزم الأمر

        if len(response_message) > MAX_MESSAGE_LENGTH:
             parts = [response_message[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(response_message), MAX_MESSAGE_LENGTH)]
             for part in parts:
                 await update.message.reply_text(part, parse_mode="Markdown")
        else:
             await update.message.reply_text(response_message, parse_mode="Markdown")

        # إعادة حالة المستخدم إلى الوضع الافتراضي
        if user_id in self.bot.user_states:
            del self.bot.user_states[user_id]

    async def handle_linkedin_input(self, update: Update, username: str):
        """يعالج اسم مستخدم LinkedIn المدخل ويبحث عنه"""
        user_id = str(update.effective_user.id)
        await update.message.reply_text(f"🔗 جاري البحث عن ملف LinkedIn للمستخدم: {username}...")
        
        profile_data = await get_linkedin_profile(username)
        
        if profile_data:
            # تنسيق وعرض بيانات الملف الشخصي
            profile_url = profile_data.get("linkedinUrl", "غير متوفر")
            name = f"{profile_data.get('firstName', '')}" + (f" {profile_data.get('LastName', '')}" if profile_data.get("LastName") else "")
            title = profile_data.get("title", "غير متوفر")
            location = profile_data.get("location", {}).get("default", "غير متوفر")
            experience_count = len(profile_data.get("experience", []))
            education_count = len(profile_data.get("education", []))
            skills_count = len(profile_data.get("skills", []))
            
            response_message = f"👤 **ملف LinkedIn للمستخدم: {username}**\n\n"
            response_message += f"*الاسم:* {name}\n"
            response_message += f"*العنوان الوظيفي:* {title}\n"
            response_message += f"*الموقع:* {location}\n"
            response_message += f"*الرابط:* {profile_url}\n\n"
            response_message += f"*الخبرات:* {experience_count} وظيفة/منصب\n"
            response_message += f"*التعليم:* {education_count} مؤسسة تعليمية\n"
            response_message += f"*المهارات:* {skills_count} مهارة مدرجة\n"
            # يمكن إضافة المزيد من التفاصيل هنا حسب الحاجة
            
            await update.message.reply_text(response_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على ملف LinkedIn للمستخدم `{username}` أو حدث خطأ أثناء البحث.")

        # إعادة حالة المستخدم إلى الوضع الافتراضي
        if user_id in self.bot.user_states:
            del self.bot.user_states[user_id]
