import os
from dotenv 
import load_dotenv

load_dotenv()

SITE_URL = os.getenv("SITE_URL", "http://51.75.144.178/ints")
USERNAME = os.getenv("nutsdev98")
PASSWORD = os.getenv("nutsdev98")

# Endpoint
LOGIN_URL  = f"{SITE_URL}/login"
OTP_URL    = f"{SITE_URL}/agent/MySMSNumbers"

# Path
SESSION_DIR   = "session"
DOWNLOAD_DIR  = "downloads"
