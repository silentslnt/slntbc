import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))

# Rate Limiting (seconds between operations)
ROLE_DELAY = 0.5
CHANNEL_DELAY = 0.5
PERMISSION_DELAY = 0.3