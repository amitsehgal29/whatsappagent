"""
Application configuration loaded from environment variables.

All secrets and runtime settings are managed via a .env file and exposed
as module-level constants for import by other application modules.
"""

import os

from dotenv import load_dotenv

# Load .env from the project root (parent of app/)
load_dotenv()

# -- Anthropic / Claude -------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# -- WhatsApp Cloud API (Meta Graph API) --------------------------------------
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_WABA_ID: str = os.getenv("WHATSAPP_WABA_ID", "")
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

# -- Graph API ----------------------------------------------------------------
GRAPH_API_VERSION: str = os.getenv("GRAPH_API_VERSION", "v25.0")

# -- Model --------------------------------------------------------------------
MODEL: str = os.getenv("MODEL", "claude-sonnet-4-6")

# -- Demo ---------------------------------------------------------------------
# WhatsApp number in E.164 format WITHOUT the leading +
DEMO_MEMBER_PHONE: str = os.getenv("DEMO_MEMBER_PHONE", "")

# -- Agent --------------------------------------------------------------------
MAX_TOOL_ROUNDS: int = 15  # safety upper-bound to prevent infinite loops

# -- RAG ----------------------------------------------------------------------
TOP_K: int = 3  # number of knowledge chunks to retrieve per query
