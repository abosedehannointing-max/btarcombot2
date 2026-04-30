import os
import time
import logging
import requests
import threading
from flask import Flask, jsonify

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ LANGUAGE SUPPORT ============
# Store user language preference
user_languages = {}  # {chat_id: 'en' or 'ar'}

# Translations
TEXTS = {
    'en': {
        'welcome': "🎨 **YouTube Thumbnail Generator Bot**\n\nSend me any text description, and I'll create a thumbnail!\n\n**Examples:**\n• 'Excited gamer winning tournament, red background'\n• 'Shocked face with colorful gradient'\n• 'Cute cat with OMG text and arrows'\n\nUse /language to change language",
        'generating': "🎨 Generating your YouTube thumbnail... (30-60 seconds)",
        'success': "✅ Thumbnail generated for:",
        'error': "❌ Error: {}\n\nPlease try a simpler prompt.",
        'no_api_key': "❌ Failed to generate thumbnail. Please check OpenAI API key.",
        'echo_mode': "✅ Bot is working! You said: {}\n\n(Add OPENAI_API_KEY to generate thumbnails)",
        'language_changed': "🌐 Language changed to English!\n\nSend /start to see welcome message.",
        'current_language': "🌐 Current language: English\nUse /language to switch to Arabic",
        'language_prompt': "🌐 Choose your language:\n/en - English\n/ar - العربية",
        'arabic_welcome': "🎨 **بوت إنشاء صور مصغرة لليوتيوب**\n\nأرسل لي أي وصف نصي، وسأقوم بإنشاء صورة مصغرة!\n\n**أمثلة:**\n• 'لاعب متحمس يفوز في البطولة، خلفية حمراء'\n• 'وجه مندهش مع تدرج لوني'\n• 'قطة لطيفة مع نص OMG وسهام'\n\nاستخدم /language لتغيير اللغة",
        'arabic_generating': "🎨 جاري إنشاء الصورة المصغرة... (30-60 ثانية)",
        'arabic_success': "✅ تم إنشاء الصورة المصغرة لعبارة:",
        'arabic_error': "❌ خطأ: {}\n\nيرجى المحاولة مرة أخرى بعبارة أبسط.",
        'arabic_language_changed': "🌐 تم تغيير اللغة إلى العربية!\n\nأرسل /start لرؤية رسالة الترحيب.",
        'arabic_current_language': "🌐 اللغة الحالية: العربية\nاستخدم /language للتبديل إلى الإنجليزية"
    }
}

def get_text(chat_id, key, *args):
    """Get translated text for user"""
    lang = user_languages.get(chat_id, 'en')
    text = TEXTS['en'].get(key, TEXTS['en'][key]) if lang == 'en' else TEXTS['en'].get(f'arabic_{key}', TEXTS['en'][key])
    
    # Handle Arabic special cases
    if lang == 'ar':
        arabic_keys = {
            'welcome': 'arabic_welcome',
            'generating': 'arabic_generating',
            'success': 'arabic_success',
            'error': 'arabic_error',
            'language_changed': 'arabic_language_changed',
            'current_language': 'arabic_current_language'
        }
        if key in arabic_keys:
            text = TEXTS['en'].get(arabic_keys[key], text)
    
    if args:
        return text.format(*args)
    return text

# ============ FLASK WEB SERVER ============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "alive",
        "bot": "running",
        "languages": ["English", "Arabic"],
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "openai_key_set": bool(OPENAI_API_KEY)
    }), 200

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_webserver():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting web server on port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============ TELEGRAM BOT ============
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None
last_update_id = 0

def send_message(chat_id, text, parse_mode=None):
    """Send text message to user"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        response = requests.post(url, json=data, timeout=10)
        logger.info(f"Message sent to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return None

def send_photo(chat_id, photo_bytes, caption=""):
    """Send photo to user"""
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        files = {"photo": ("thumb.jpg", photo_bytes, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}
        response = requests.post(url, data=data, files=files, timeout=30)
        logger.info(f"Photo sent to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Send photo error: {e}")
        return None

def generate_thumbnail(prompt, lang='en'):
    """Generate thumbnail using OpenAI DALL-E"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        
        # Add language instruction for better results
        if lang == 'ar':
            full_prompt = f"Create an eye-catching YouTube thumbnail based on this Arabic description: {prompt}. Make it vibrant, high contrast, 16:9 aspect ratio, clickable design."
        else:
            full_prompt = f"Create an eye-catching YouTube thumbnail: {prompt}. Make it vibrant, high contrast, 16:9 aspect ratio, clickable design."
        
        logger.info(f"Generating thumbnail for: {prompt[:50]} (lang: {lang})")
        
        response = openai.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = response.data[0].url
        img_response = requests.get(image_url, timeout=30)
        return img_response.content
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise e

def get_updates(offset=None):
    """Get new messages from Telegram"""
    try:
        url = f"{TELEGRAM_API_URL}/getUpdates"
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        response = requests.get(url, params=params, timeout=35)
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", [])
        else:
            logger.error(f"Telegram API error: {data}")
            return []
            
    except Exception as e:
        logger.error(f"Get updates error: {e}")
        return []

def process_message(message):
    """Process a single message from user"""
    try:
        chat_id = message["chat"]["id"]
        
        # Initialize language for new users
        if chat_id not in user_languages:
            user_languages[chat_id] = 'en'
        
        # Check if it's a text message
        if "text" not in message:
            return
        
        text = message["text"].strip()
        logger.info(f"Processing message from {chat_id}: {text[:50]}")
        
        # Handle /start command
        if text == "/start":
            welcome = get_text(chat_id, 'welcome')
            send_message(chat_id, welcome, parse_mode="Markdown")
            return
        
        # Handle /language command
        if text == "/language":
            lang_prompt = "🌐 Choose your language:\n/en - English\n/ar - العربية"
            send_message(chat_id, lang_prompt)
            return
        
        # Handle /en command
        if text == "/en":
            user_languages[chat_id] = 'en'
            send_message(chat_id, get_text(chat_id, 'language_changed'))
            return
        
        # Handle /ar command
        if text == "/ar":
            user_languages[chat_id] = 'ar'
            send_message(chat_id, get_text(chat_id, 'language_changed'))
            return
        
        # For any other text, generate a thumbnail
        send_message(chat_id, get_text(chat_id, 'generating'))
        
        try:
            if OPENAI_API_KEY:
                # Generate and send the thumbnail
                thumbnail_bytes = generate_thumbnail(text, user_languages[chat_id])
                if thumbnail_bytes:
                    caption = f"{get_text(chat_id, 'success')} {text[:100]}"
                    send_photo(chat_id, thumbnail_bytes, caption)
                else:
                    send_message(chat_id, get_text(chat_id, 'no_api_key'))
            else:
                # Echo mode if no API key
                send_message(chat_id, get_text(chat_id, 'echo_mode').format(text))
                
        except Exception as e:
            error_msg = str(e)[:200]
            send_message(chat_id, get_text(chat_id, 'error').format(error_msg))
            
    except Exception as e:
        logger.error(f"Process message error: {e}")

# ============ MAIN ============
def main():
    global last_update_id
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        return
    
    logger.info("=" * 50)
    logger.info("YouTube Thumbnail Bot Starting (Bilingual: EN/AR)...")
    logger.info(f"TELEGRAM_TOKEN: {'✓' if TELEGRAM_TOKEN else '✗'}")
    logger.info(f"OPENAI_API_KEY: {'✓' if OPENAI_API_KEY else '✗ (echo mode only)'}")
    logger.info("=" * 50)
    
    # Start web server in background thread
    webserver_thread = threading.Thread(target=run_webserver, daemon=True)
    webserver_thread.start()
    logger.info("Web server thread started")
    
    # Give the web server a moment to start
    time.sleep(2)
    
    # Clear old updates
    get_updates()
    logger.info("Starting polling loop...")
    
    # Main polling loop
    while True:
        try:
            offset = last_update_id + 1 if last_update_id else None
            updates = get_updates(offset)
            
            for update in updates:
                last_update_id = update["update_id"]
                
                if "message" in update:
                    logger.info(f"New message received (ID: {last_update_id})")
                    process_message(update["message"])
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
