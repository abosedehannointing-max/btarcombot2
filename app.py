import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest
import openai
import requests
from io import BytesIO
from flask import Flask, request, jsonify
import asyncio

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Your Render app URL

# If RENDER_EXTERNAL_URL not set, try to build it from environment
if not RENDER_URL:
    render_service_name = os.environ.get("RENDER_SERVICE_NAME", "your-app")
    RENDER_URL = f"https://{render_service_name}.onrender.com"

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global bot instance
bot_app = None
flask_app = Flask(__name__)

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context):
    await update.message.reply_text(
        "🎨 Send me text, get a YouTube thumbnail!\n\n"
        "Example: 'Excited cat, red background, WOW text'"
    )

async def generate_thumbnail(update: Update, context):
    prompt = update.message.text
    await update.message.chat.send_action(action="upload_photo")
    status_msg = await update.message.reply_text("🎨 Generating...")
    
    try:
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"YouTube thumbnail: {prompt}. Eye-catching, 16:9 aspect ratio.",
            size="1024x1024",
            quality="hd",
            n=1
        )
        
        image_url = response.data[0].url
        img_response = requests.get(image_url)
        img_bytes = BytesIO(img_response.content)
        
        await update.message.reply_photo(
            photo=img_bytes,
            caption=f"✅ Done!\nPrompt: {prompt[:100]}"
        )
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("❌ Error. Please try again.")

# ============ FLASK WEBHOOK ============
@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

@flask_app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        asyncio.create_task(bot_app.process_update(update))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# ============ MAIN ============
if __name__ == "__main__":
    # Setup bot
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_thumbnail))
    
    # Set webhook
    webhook_url = f"{RENDER_URL}/webhook/{TELEGRAM_TOKEN}"
    async def set_webhook():
        await bot_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    
    asyncio.run(set_webhook())
    
    # Start Flask
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
