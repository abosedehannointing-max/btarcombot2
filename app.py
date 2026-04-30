import os
import time
import json
import logging
import requests
from flask import Flask, request, jsonify
import threading

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram API URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Flask app
flask_app = Flask(__name__)

# ============ TELEGRAM HELPERS ============
def send_message(chat_id, text):
    """Send a simple text message"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

def send_photo(chat_id, photo_bytes, caption=""):
    """Send a photo"""
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        files = {"photo": ("thumbnail.jpg", photo_bytes, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}
        response = requests.post(url, data=data, files=files, timeout=30)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return None

def send_typing(chat_id):
    """Show typing indicator"""
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
        
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"YouTube thumbnail, eye-catching, high contrast, 16:9 ratio: {prompt}",
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
                "🎨 **YouTube Thumbnail Generator Bot**\n\n"
                "Send me any text description, and I'll create a thumbnail!\n\n"
                "**Examples:**\n"
                "- 'Excited gamer winning tournament'\n"
                "- 'Shocked face with colorful background'\n"
                "- 'Cute cat with OMG text and arrows'")
            return
        
        # Handle text messages
        if "text" in message:
            prompt = message["text"]
            
            # Send typing indicator and acknowledgment
            send_typing(chat_id)
            send_message(chat_id, "🎨 Generating your YouTube thumbnail... (30-60 seconds)")
            
            try:
                # Generate thumbnail
                thumbnail_bytes = generate_thumbnail(prompt)
                
                # Send the thumbnail
                from io import BytesIO
                send_photo(chat_id, BytesIO(thumbnail_bytes).getvalue(), 
                          caption=f"✅ Generated from: {prompt[:100]}")
                
            except Exception as e:
                send_message(chat_id, f"❌ Error: {str(e)[:200]}\n\nPlease try again with a simpler prompt.")
                
    except Exception as e:
        logger.error(f"Process error: {e}")

# ============ FLASK WEBHOOK HANDLER ============
@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "alive", "bot": "running"}), 200

@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Handle Telegram webhook"""
    try:
        update = request.get_json()
        logger.info(f"Received update: {update.get('message', {}).get('text', 'no text')}")
        
        # Process in background thread to not block
        thread = threading.Thread(target=process_update, args=(update,))
        thread.start()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# ============ SET WEBHOOK ============
def set_webhook():
    """Set the webhook URL for the bot"""
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        # Try to detect from environment
        render_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'unknown')}.onrender.com"
    
    webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
    
    # Remove any existing webhook
    requests.post(f"{TELEGRAM_API_URL}/deleteWebhook", json={"drop_pending_updates": True})
    
    # Set new webhook
    response = requests.post(
        f"{TELEGRAM_API_URL}/setWebhook",
        json={"url": webhook_url}
    )
    
    if response.json().get("ok"):
        logger.info(f"✅ Webhook set to: {webhook_url}")
        return True
    else:
        logger.error(f"❌ Failed to set webhook: {response.json()}")
        return False

# ============ MAIN ============
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting YouTube Thumbnail Bot")
    logger.info("=" * 50)
    
    # Set webhook
    set_webhook()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask server on port {port}")
    flask_app.run(host="0.0.0.0", port=port)
