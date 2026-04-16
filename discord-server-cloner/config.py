import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))

# Webhook Logging (for scrape command token collection)
WEBHOOK_LOG_CHANNEL_ID = int(os.getenv('WEBHOOK_LOG_CHANNEL_ID', 0))  # Channel to send token logs

# Rate Limiting (seconds between operations)
ROLE_DELAY = 0.5
CHANNEL_DELAY = 0.5
PERMISSION_DELAY = 0.3