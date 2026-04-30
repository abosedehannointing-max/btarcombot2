import os
import time
import logging
import requests
import threading
from flask import Flask

# -------------------- Setup --------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- Flask Web Server (for Render) --------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot is running!", 200

def run_webserver():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host='0.0.0.0', port=port, debug=False)

# -------------------- Telegram Bot (Polling) --------------------
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
last_update_id = 0

def send_message(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"Send error: {e}")

def get_updates(offset=None):
    try:
        url = f"{TELEGRAM_API_URL}/getUpdates"
        params = {"timeout": 30, "offset": offset} if offset else {"timeout": 30}
        response = requests.get(url, params=params, timeout=35)
        return response.json().get("result", [])
    except Exception as e:
        logger.error(f"Get updates error: {e}")
        return []

def process_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if text == "/start":
        send_message(chat_id, "🎨 Send me any text and I'll make a YouTube thumbnail!")
    else:
        send_message(chat_id, f"✅ Bot works! You said: {text}\n(Thumbnail generation coming soon)")

# -------------------- Main --------------------
def main():
    global last_update_id
    
    # Start web server in background
    threading.Thread(target=run_webserver, daemon=True).start()
    
    logger.info("Bot started! Polling for messages...")
    
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                if "message" in update:
                    process_message(update["message"])
            time.sleep(1)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
