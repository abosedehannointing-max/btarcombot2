import os
import time
import logging
import requests
import threading
from flask import Flask, jsonify

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # Make sure this is correct, not OPENAIP_API_KEY

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK WEB SERVER (for Render) ============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    """Health check endpoint - Render needs this"""
    return jsonify({
        "status": "alive",
        "bot": "running",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "openai_key_set": bool(OPENAI_API_KEY)
    }), 200

@flask_app.route('/health')
def health():
    """Alternative health check"""
    return jsonify({"status": "healthy"}), 200

def run_webserver():
    """Run Flask in a background thread"""
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting web server on port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============ TELEGRAM BOT (Polling) ============
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None
last_update_id = 0

def send_message(chat_id, text):
    """Send text message to user"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
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

def generate_thumbnail(prompt):
    """Generate thumbnail using OpenAI DALL-E"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        
        logger.info(f"Generating thumbnail for: {prompt[:50]}")
        
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"Create an eye-catching YouTube thumbnail: {prompt}. Make it vibrant, high contrast, 16:9 aspect ratio, clickable design.",
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
        
        # Check if it's a text message
        if "text" not in message:
            return
        
        text = message["text"].strip()
        logger.info(f"Processing message from {chat_id}: {text[:50]}")
        
        # Handle /start command
        if text == "/start":
            welcome_msg = (
                "🎨 **YouTube Thumbnail Generator Bot**\n\n"
                "Send me any text description, and I'll create a thumbnail!\n\n"
                "**Examples:**\n"
                "• 'Excited gamer winning tournament, red background'\n"
                "• 'Shocked face with colorful gradient background'\n"
                "• 'Cute cat with OMG text and colorful arrows'\n\n"
                "Just type your idea and I'll generate it!"
            )
            send_message(chat_id, welcome_msg)
            return
        
        # For any other text, generate a thumbnail
        send_message(chat_id, "🎨 Generating your YouTube thumbnail... (30-60 seconds)")
        
        try:
            if OPENAI_API_KEY:
                # Generate and send the thumbnail
                thumbnail_bytes = generate_thumbnail(text)
                if thumbnail_bytes:
                    caption = f"✅ Thumbnail generated for: {text[:100]}"
                    send_photo(chat_id, thumbnail_bytes, caption)
                else:
                    send_message(chat_id, "❌ Failed to generate thumbnail. Please check OpenAI API key.")
            else:
                # Echo mode if no API key (for testing)
                send_message(chat_id, f"✅ Bot is working! You said: {text}\n\n(Add OPENAI_API_KEY to generate thumbnails)")
                
        except Exception as e:
            error_msg = str(e)[:200]
            send_message(chat_id, f"❌ Error: {error_msg}\n\nPlease try a simpler prompt.")
            
    except Exception as e:
        logger.error(f"Process message error: {e}")

# ============ MAIN ============
def main():
    global last_update_id
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        return
    
    logger.info("=" * 50)
    logger.info("YouTube Thumbnail Bot Starting...")
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
            # Get new updates
            offset = last_update_id + 1 if last_update_id else None
            updates = get_updates(offset)
            
            for update in updates:
                last_update_id = update["update_id"]
                
                if "message" in update:
                    logger.info(f"New message received (ID: {last_update_id})")
                    process_message(update["message"])
            
            # Small delay to prevent hammering the API
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
