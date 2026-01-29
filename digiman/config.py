"""Configuration loader for Digiman."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "todos.db"))

# Granola
GRANOLA_CACHE_PATH = os.path.expanduser(
    os.getenv("GRANOLA_CACHE_PATH", "~/Library/Application Support/Granola/cache-v3.json")
)

# Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_USER_ID = os.getenv("SLACK_USER_ID")

# Flask
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
