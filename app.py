import os
import sys
import json
import logging
import requests
from flask import Flask, request, jsonify
from io import BytesIO
import time

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# Check for missing variables
missing_vars = []
if not TELEGRAM_TOKEN:
    missing_vars.append("TELEGRAM_TOKEN")
if not OPENAI_API_KEY:
    missing_vars.append("OPENAI_API_KEY")
if not RENDER_EXTERNAL_URL:
    missing_vars.append("RENDER_EXTERNAL_URL")

if missing_vars:
    error_msg = f"Missing environment variables: {', '.join(missing_vars)}"
    print(f"ERROR: {error_msg}")
    # Don't exit, just log for now

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
flask_app = Flask(__name__)

# Telegram API URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None

# ============ TELEGRAM HELPERS ============
def send_message(chat_id, text):
    """Send a simple text message"""
    if not TELEGRAM_API_URL:
        return None
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        response = requests.post(url, json=data, timeout=10)
        logger.info(f"Sent message to {chat_id}: {text[:50]}")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

def send_photo(chat_id, photo_bytes, caption=""):
    """Send a photo"""
    if not TELEGRAM_API_URL:
        return None
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        files = {"photo": ("thumbnail.jpg", photo_bytes, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption[:200]}
        response = requests.post(url, data=data, files=files, timeout=30)
        logger.info(f"Sent photo to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return None

def send_typing(chat_id):
    """Show typing indicator"""
    if not TELEGRAM_API_URL:
        return
    try:
        url = f"{TELEGRAM_API_URL}/sendChatAction"
        data = {"chat_id": chat_id, "action": "upload_photo"}
        requests.post(url, json=data, timeout=5)
    except:
        pass

# ============ IMAGE GENERATION ============
def generate_thumbnail(prompt):
    """Generate thumbnail using OpenAI DALL-E"""
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        
        logger.info(f"Generating image for: {prompt[:100]}")
        
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"YouTube thumbnail, eye-catching, high contrast, 16:9 ratio: {prompt}",
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = response.data[0].url
        logger.info(f"Image URL: {image_url[:100]}")
        
        img_response = requests.get(image_url, timeout=30)
        return img_response.content
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise e

# ============ PROCESS MESSAGES ============
def process_update(update):
    """Process incoming Telegram update"""
    try:
        # Check if it's a message
        if "message" not in update:
            return
        
        message = update["message"]
        chat_id = message["chat"]["id"]
        
        # Handle /start command
        if "text" in message and message["text"] == "/start":
            send_message(chat_id, 
                "🎨 *YouTube Thumbnail Generator Bot*\n\n"
                "Send me any text description, and I'll create a thumbnail!\n\n"
                "*Examples:*\n"
                "• 'Excited gamer winning tournament'\n"
                "• 'Shocked face with colorful background'\n"
                "• 'Cute cat with OMG text and arrows'")
            return
        
        # Handle text messages
        if "text" in message:
            prompt = message["text"]
            
            # Don't process empty messages
            if not prompt or len(prompt.strip()) == 0:
                return
            
            # Send acknowledgment
            send_message(chat_id, "🎨 Generating your YouTube thumbnail... (30-60 seconds)")
            
            try:
                # Generate thumbnail
                thumbnail_bytes = generate_thumbnail(prompt)
                
                # Send the thumbnail
                send_photo(chat_id, BytesIO(thumbnail_bytes).getvalue(), 
                          caption=f"✅ Generated from: {prompt[:100]}")
                
            except Exception as e:
                error_msg = str(e)[:200]
                send_message(chat_id, f"❌ Error: {error_msg}\n\nPlease try again with a simpler prompt.")
                
    except Exception as e:
        logger.error(f"Process error: {e}")

# ============ FLASK ROUTES ============
@flask_app.route("/", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "alive", 
        "bot": "running",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "openai_key_set": bool(OPENAI_API_KEY),
        "webhook_url_set": bool(RENDER_EXTERNAL_URL)
    }), 200

@flask_app.route("/webhook", methods=["POST"])
@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Handle Telegram webhook"""
    try:
        update = request.get_json()
        if update:
            logger.info(f"Received update: {update.get('message', {}).get('text', 'no text')}")
            # Process in background
            import threading
            thread = threading.Thread(target=process_update, args=(update,))
            thread.start()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

# ============ SET WEBHOOK ============
def set_webhook():
    """Set the webhook URL for the bot"""
    if not TELEGRAM_TOKEN or not RENDER_EXTERNAL_URL:
        logger.warning("Cannot set webhook: Missing token or URL")
        return False
    
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{TELEGRAM_TOKEN}"
    
    try:
        # Remove any existing webhook
        requests.post(f"{TELEGRAM_API_URL}/deleteWebhook", json={"drop_pending_updates": True})
        
        # Set new webhook
        response = requests.post(
            f"{TELEGRAM_API_URL}/setWebhook",
            json={"url": webhook_url},
            timeout=10
        )
        
        if response.json().get("ok"):
            logger.info(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            logger.error(f"❌ Failed to set webhook: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"Webhook setup error: {e}")
        return False

# ============ MAIN ============
if __name__ == "__main__":
    print("=" * 50)
    print("Starting YouTube Thumbnail Bot")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"TELEGRAM_TOKEN set: {bool(TELEGRAM_TOKEN)}")
    print(f"OPENAI_API_KEY set: {bool(OPENAI_API_KEY)}")
    print(f"RENDER_EXTERNAL_URL: {RENDER_EXTERNAL_URL}")
    print("=" * 50)
    
    # Set webhook
    if TELEGRAM_TOKEN and RENDER_EXTERNAL_URL:
        set_webhook()
    else:
        print("⚠️ Cannot set webhook - missing environment variables")
    
    # Start Flask server
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}")
    print(f"Health check: https://btarcombot2.onrender.com/")
    
    # Run with debug=False for production
    flask_app.run(host="0.0.0.0", port=port, debug=False)
