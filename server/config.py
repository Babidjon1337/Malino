import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Yookassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Openrouter
AI_TOKEN = os.getenv("AI_TOKEN")

# Webhook settings
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = 8000

# Taro Web
WEB_APP_URL = os.getenv("WEB_APP_URL")


AMOUNT_1 = "99"
AMOUNT_2 = "799"
