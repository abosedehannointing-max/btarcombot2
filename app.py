import os
import logging
from flask import Flask, request, jsonify
import requests

# Setup
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

# Telegram API
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_message(chat_id, text):
    """Send a message"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        response = requests.post(url, json=data, timeout=10)
        logger.info(f"Message sent to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "alive", "message": "Bot is running"}), 200

@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Handle incoming messages"""
    try:
        update = request.get_json()
        logger.info(f"Received: {update}")
        
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")
            
            if text == "/start":
                send_message(chat_id, "🎨 Bot is working! Send me any text for a thumbnail (coming soon)")
            else:
                send_message(chat_id, f"✅ I received: {text}\n\nThumbnail generation will be added next!")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    # Set webhook
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{TELEGRAM_TOKEN}"
    requests.post(f"{TELEGRAM_API_URL}/deleteWebhook")
    response = requests.post(
        f"{TELEGRAM_API_URL}/setWebhook",
        json={"url": webhook_url}
    )
    logger.info(f"Webhook set to {webhook_url}: {response.json()}")
    
    # Start server
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False)
