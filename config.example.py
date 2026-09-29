import os

# Telegram Bot Token from @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Secret path for your webhook endpoint (keeps attackers from spamming it)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "RANDOM_STRING_HERE")
