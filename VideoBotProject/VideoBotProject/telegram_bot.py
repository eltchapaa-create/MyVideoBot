import httpx
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- الإعدادات المحدثة ---
BOT_TOKEN = '7694598160:AAEQ_B1hPM3IgyVdMJqkcL6dCn71n1ily6k'
BACKEND_URL = 'https://myvideobot-8cr6.onrender.com'
FORCED_JOIN_CHANNEL = '@VidGrabChannel' 

# --- دوال مساعدة ---
async def check_user_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    للتحقق مما إذا كان المستخدم عضواً في القناة.
    """
    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception: return False

# --- معالجات الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يتم استدعاؤها عند إرسال المستخدم للأمر /start
    """
    await update.message.reply_text('أهلاً بك! أرسل لي رابط أي فيديو وسأقوم بتحميله لك.')

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    تتعامل مع الروابط التي يرسلها المستخدم.
    """
    url = update.message.text
    msg = await update.message.reply_text('⏳ جاري تحليل الرابط...')

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(f'{BACKEND_URL}/get_info', params={'url': url})
            response.raise_for_status()
            data = response.json()
            
            context.user_data['original_url'] = url
            
            keyboard = []
            for f in data.get('formats', []):
                res = f.get('resolution', 'N/A')
                # نستخدم الدقة كمفتاح للميزة
                feature_key = res.lower()
                text = f"تحميل {res} ({f.get('ext')})"
                callback_data = f"feature_{feature_key}_{f.get('format_id')}"
                keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
            
            keyboard.append([InlineKeyboardButton("🎵 تحويل إلى MP3", callback_data="feature_mp3_")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(f"اختر الجودة المطلوبة لـ:\n*{data.get('title')}*", reply_markup=reply_markup, parse_mode='Markdown')

        except Exception as e:
            await msg.edit_text(f'حدث خطأ: {e}')

async def feature_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يتم استدعاؤها عند الضغط على زر الجودة، وتعرض واجهة الإعلان.
    """
    query = update.callback_query
    await query.answer()
    
    _, feature, format_id = query.data.split('_', 2)
    context.user_data['selected_feature'] = feature
    context.user_data['selected_format_id'] = format_id

    # رابط صفحة الإعلان أصبح يشير إلى الخادم الخلفي مباشرة
    ad_page_url = f"{BACKEND_URL}/show_ad_page?feature={feature}"

    keyboard = [
        [InlineKeyboardButton("👁️ مشاهدة الإعلان (انتظر 30 ثانية)", web_app=WebAppInfo(url=ad_page_url))],
        [InlineKeyboardButton("✅ لقد شاهدت، متابعة", callback_data="proceed_download")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text('الخطوة 1: شاهد الإعلان. \nالخطوة 2: اضغط متابعة.', reply_markup=reply_markup)

async def proceed_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يتم استدعاؤها بعد "مشاهدة" الإعلان، للتحقق من الانضمام والبدء بالتحميل.
    """
    query = update.callback_query
    await query.answer()
    
    if not await check_user_membership(query.from_user.id, context):
        await query.message.reply_text(f'يجب عليك الانضمام إلى القناة أولاً: {FORCED_JOIN_CHANNEL}')
        return

    feature = context.user_data.get('selected_feature')
    format_id = context.user_data.get('selected_format_id')
    original_url = context.user_data.get('original_url')
    
    if not original_url or not feature:
        await query.message.edit_text('حدث خطأ، يرجى إرسال الرابط مرة أخرى.')
        return

    await query.message.edit_text('✅ تم التحقق. جاري المعالجة الآن...')
    
    endpoint = ""
    params = {'url': original_url}
    
    if feature == 'mp3':
        endpoint = "/convert_to_mp3"
    else:
        endpoint = "/download"
        params['format_id'] = format_id

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.get(f'{BACKEND_URL}{endpoint}', params=params)
            response.raise_for_status()
            file_path = response.json().get('file_path')

            if feature == 'mp3':
                await query.message.reply_audio(audio=open(file_path, 'rb'))
            else:
                await query.message.reply_video(video=open(file_path, 'rb'), supports_streaming=True)
            
            os.remove(file_path)
            
        except Exception as e:
            await query.message.edit_text(f'فشل الطلب: {e}')

def main() -> None:
    """
    الدالة الرئيسية لتشغيل البوت.
    """
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(feature_button_callback, pattern='^feature_'))
    application.add_handler(CallbackQueryHandler(proceed_download_callback, pattern='^proceed_download$'))

    print("البوت قيد التشغيل...")
    application.run_polling()

if __name__ == '__main__':
    main()
