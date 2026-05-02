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
user_languages = {}  # {chat_id: 'en', 'ar', or 'tr'}

# Translations for all three languages
TEXTS = {
    'en': {
        'welcome': "🎨 **YouTube Thumbnail Generator Bot**\n\nSend me any text description, and I'll create a thumbnail!\n\n**Examples:**\n• 'Excited gamer winning tournament, red background'\n• 'Shocked face with colorful gradient'\n• 'Cute cat with OMG text and arrows'\n\nUse /language to change language",
        'generating': "🎨 Generating your YouTube thumbnail... (30-60 seconds)",
        'success': "✅ Thumbnail generated for:",
        'error': "❌ Error: {}\n\nPlease try a simpler prompt.",
        'no_api_key': "❌ Failed to generate thumbnail. Please check OpenAI API key.",
        'echo_mode': "✅ Bot is working! You said: {}\n\n(Add OPENAI_API_KEY to generate thumbnails)",
        'language_changed': "🌐 Language changed to English!\n\nSend /start to see welcome message.",
        'current_language': "🌐 Current language: English\nUse /language to change language",
        'language_prompt': "🌐 Choose your language:\n/en - English\n/ar - العربية\n/tr - Türkçe",
        # Arabic translations
        'arabic_welcome': "🎨 **بوت إنشاء صور مصغرة لليوتيوب**\n\nأرسل لي أي وصف نصي، وسأقوم بإنشاء صورة مصغرة!\n\n**أمثلة:**\n• 'لاعب متحمس يفوز في البطولة، خلفية حمراء'\n• 'وجه مندهش مع تدرج لوني'\n• 'قطة لطيفة مع نص OMG وسهام'\n\nاستخدم /language لتغيير اللغة",
        'arabic_generating': "🎨 جاري إنشاء الصورة المصغرة... (30-60 ثانية)",
        'arabic_success': "✅ تم إنشاء الصورة المصغرة لعبارة:",
        'arabic_error': "❌ خطأ: {}\n\nيرجى المحاولة مرة أخرى بعبارة أبسط.",
        'arabic_language_changed': "🌐 تم تغيير اللغة إلى العربية!\n\nأرسل /start لرؤية رسالة الترحيب.",
        'arabic_current_language': "🌐 اللغة الحالية: العربية\nاستخدم /language لتغيير اللغة",
        'arabic_language_prompt': "🌐 اختر لغتك:\n/en - الإنجليزية\n/ar - العربية\n/tr - التركية",
        # Turkish translations
        'turkish_welcome': "🎨 **YouTube Küçük Resim Oluşturma Botu**\n\nBana herhangi bir metin açıklaması gönderin, bir küçük resim oluşturayım!\n\n**Örnekler:**\n• 'Turnuva kazanan heyecanlı oyuncu, kırmızı arka plan'\n• 'Renkli geçişli şaşkın yüz'\n• 'OMG metni ve okları olan sevimli kedi'\n\nDil değiştirmek için /language kullanın",
        'turkish_generating': "🎨 YouTube küçük resminiz oluşturuluyor... (30-60 saniye)",
        'turkish_success': "✅ Şunun için küçük resim oluşturuldu:",
        'turkish_error': "❌ Hata: {}\n\nLütfen daha basit bir ifade deneyin.",
        'turkish_language_changed': "🌐 Dil Türkçe olarak değiştirildi!\n\nHoşgeldiniz mesajını görmek için /start gönderin.",
        'turkish_current_language': "🌐 Mevcut dil: Türkçe\nDil değiştirmek için /language kullanın",
        'turkish_language_prompt': "🌐 Dilinizi seçin:\n/en - İngilizce\n/ar - Arapça\n/tr - Türkçe"
    }
}

def get_text(chat_id, key, *args):
    """Get translated text based on user's language preference"""
    lang = user_languages.get(chat_id, 'en')
    
    # Default to English text
    text = TEXTS['en'].get(key, TEXTS['en'][key])
    
    # Handle language-specific overrides
    if lang == 'ar':
        arabic_keys = {
            'welcome': 'arabic_welcome',
            'generating': 'arabic_generating',
            'success': 'arabic_success',
            'error': 'arabic_error',
            'language_changed': 'arabic_language_changed',
            'current_language': 'arabic_current_language',
            'language_prompt': 'arabic_language_prompt'
        }
        if key in arabic_keys:
            text = TEXTS['en'].get(arabic_keys[key], text)
    
    elif lang == 'tr':
        turkish_keys = {
            'welcome': 'turkish_welcome',
            'generating': 'turkish_generating',
            'success': 'turkish_success',
            'error': 'turkish_error',
            'language_changed': 'turkish_language_changed',
            'current_language': 'turkish_current_language',
            'language_prompt': 'turkish_language_prompt'
        }
        if key in turkish_keys:
            text = TEXTS['en'].get(turkish_keys[key], text)
    
    # Format with arguments if provided
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
        "languages": ["English", "Arabic", "Turkish"],
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
        requests.post(url, json=data, timeout=10)
        logger.info(f"Message sent to {chat_id}")
    except Exception as e:
        logger.error(f"Send message error: {e}")

def send_photo(chat_id, photo_bytes, caption=""):
    """Send photo to user"""
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        files = {"photo": ("thumb.jpg", photo_bytes, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}
        requests.post(url, data=data, files=files, timeout=30)
        logger.info(f"Photo sent to {chat_id}")
    except Exception as e:
        logger.error(f"Send photo error: {e}")

def generate_thumbnail(prompt, lang='en'):
    """Generate thumbnail using OpenAI DALL-E with language support"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        
        # Customize prompt based on language
        if lang == 'ar':
            full_prompt = f"Create an eye-catching YouTube thumbnail based on this Arabic description: {prompt}. Make it vibrant, high contrast, 16:9 aspect ratio, clickable design."
        elif lang == 'tr':
            full_prompt = f"Create an eye-catching YouTube thumbnail based on this Turkish description: {prompt}. Make it vibrant, high contrast, 16:9 aspect ratio, clickable design."
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
        params = {"timeout": 30, "allowed_updates": ["message"]}
        if offset:
            params["offset"] = offset
        response = requests.get(url, params=params, timeout=35)
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", [])
        elif data.get("error_code") == 409:
            logger.warning("Conflict detected, waiting 5 seconds...")
            time.sleep(5)
            return []
        else:
            logger.error(f"Telegram API error: {data}")
            return []
            
    except Exception as e:
        logger.error(f"Get updates error: {e}")
        return []

def process_message(message):
    """Process incoming message"""
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
            send_message(chat_id, get_text(chat_id, 'welcome'), parse_mode="Markdown")
            return
        
        # Handle /language command
        if text == "/language":
            send_message(chat_id, get_text(chat_id, 'language_prompt'))
            return
        
        # Handle language switch commands
        if text == "/en":
            user_languages[chat_id] = 'en'
            send_message(chat_id, get_text(chat_id, 'language_changed'))
            return
        
        if text == "/ar":
            user_languages[chat_id] = 'ar'
            send_message(chat_id, get_text(chat_id, 'language_changed'))
            return
        
        if text == "/tr":
            user_languages[chat_id] = 'tr'
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
    logger.info("YouTube Thumbnail Bot Starting (Tri-lingual: EN/AR/TR)...")
    logger.info(f"TELEGRAM_TOKEN: {'✓' if TELEGRAM_TOKEN else '✗'}")
    logger.info(f"OPENAI_API_KEY: {'✓' if OPENAI_API_KEY else '✗'}")
    logger.info("=" * 50)
    
    # Clear previous sessions
    try:
        requests.post(f"{TELEGRAM_API_URL}/deleteWebhook", json={"drop_pending_updates": True})
        time.sleep(1)
        requests.get(f"{TELEGRAM_API_URL}/getUpdates", params={"offset": -1, "timeout": 1})
        time.sleep(1)
        logger.info("Cleared previous bot sessions")
    except Exception as e:
        logger.warning(f"Clear session warning: {e}")
    
    # Start web server in background thread
    webserver_thread = threading.Thread(target=run_webserver, daemon=True)
    webserver_thread.start()
    logger.info("Web server thread started")
    
    time.sleep(2)
    
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
