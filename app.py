import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import openai
import requests
from io import BytesIO
from flask import Flask, jsonify
import threading
import time

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Validate required environment variables
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for Render health checks
flask_app = Flask(__name__)

@flask_app.route("/")
def health_check():
    return jsonify({"status": "alive", "message": "Bot is running"}), 200

def run_flask():
    """Run Flask server for Render health checks"""
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask server on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ============ BOT HANDLERS ============
async def start(update: Update, context):
    await update.message.reply_text(
        "🎨 YouTube Thumbnail Generator Bot\n\n"
        "Send me any text description, and I'll generate a thumbnail!\n\n"
        "Examples:\n"
        "- 'Excited gamer winning tournament, red background'\n"
        "- 'Shocked face with colorful gradient background'\n"
        "- 'Cute cat with 'OMG' text and colorful arrows'"
    )

async def generate_thumbnail(update: Update, context):
    prompt = update.message.text
    logger.info(f"Generating thumbnail for: {prompt[:50]}...")
    
    # Send acknowledgment
    status_msg = await update.message.reply_text("🎨 Generating your YouTube thumbnail... (30-60 seconds)")
    
    try:
        # Generate image with DALL-E 3
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"""Create an eye-catching YouTube thumbnail based on this description: {prompt}
            
            Requirements:
            - YouTube thumbnail style, 16:9 aspect ratio
            - High contrast, vibrant colors
            - Bold, clickable design
            - Suitable for YouTube video thumbnail""",
            size="1024x1024",
            quality="standard",  # Use 'standard' for faster/cheaper generation
            n=1
        )
        
        # Get the image URL
        image_url = response.data[0].url
        
        # Download the image
        img_response = requests.get(image_url, timeout=30)
        img_bytes = BytesIO(img_response.content)
        
        # Send the thumbnail back to user
        await update.message.reply_photo(
            photo=img_bytes,
            caption=f"✅ Thumbnail generated!\n\n📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n\n💡 Tip: Add text overlay using Canva for best results!"
        )
        
        # Delete the status message
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        await status_msg.edit_text(
            f"❌ Sorry, something went wrong.\n\nError: {str(e)[:200]}\n\nPlease try again with a simpler prompt."
        )

# ============ MAIN ============
def main():
    logger.info("=" * 50)
    logger.info("Starting YouTube Thumbnail Bot on Render")
    logger.info("=" * 50)
    
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask health check server started")
    
    # Give Flask a moment to start
    time.sleep(2)
    
    # Build and run the Telegram bot
    logger.info("Initializing Telegram bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_thumbnail))
    
    logger.info("Bot is ready! Starting polling...")
    
    # Start the bot with polling (simpler for Render)
    app.run_polling(allowed_updates=None)
    
if __name__ == "__main__":
    main()
