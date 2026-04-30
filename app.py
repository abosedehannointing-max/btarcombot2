import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import openai
import requests
from io import BytesIO

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ BOT HANDLERS ============
async def start(update: Update, context):
    await update.message.reply_text(
        "🎨 Send me any text, and I'll generate a YouTube thumbnail!\n\n"
        "Example: 'Excited cat, red background, WOW text'"
    )

async def generate_thumbnail(update: Update, context):
    prompt = update.message.text
    
    # Send typing indicator
    await update.message.chat.send_action(action="upload_photo")
    
    # Acknowledge
    status_msg = await update.message.reply_text("🎨 Generating thumbnail...")
    
    try:
        # Generate image with DALL-E
        response = openai.images.generate(
            model="dall-e-3",
            prompt=f"YouTube thumbnail: {prompt}. Eye-catching, high contrast, 16:9 aspect ratio.",
            size="1024x1024",
            quality="hd",
            n=1
        )
        
        # Download and send image
        image_url = response.data[0].url
        img_response = requests.get(image_url)
        img_bytes = BytesIO(img_response.content)
        
        await update.message.reply_photo(
            photo=img_bytes,
            caption=f"✅ Thumbnail ready!\nPrompt: {prompt[:100]}"
        )
        
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("❌ Error generating thumbnail. Please try again.")

# ============ MAIN ============
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_thumbnail))
    
    logger.info("Bot started...")
    app.run_polling()  # Polling works fine on Render free tier

if __name__ == "__main__":
    main()
