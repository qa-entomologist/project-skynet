import os
from dotenv import load_dotenv

load_dotenv()

AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-west-2")

DD_API_KEY = os.getenv("DD_API_KEY", "")
DD_SITE = os.getenv("DD_SITE", "datadoghq.com")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

MAX_DEPTH = int(os.getenv("MAX_DEPTH", "5"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "50"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

OTLP_ENDPOINT_MAP = {
    "datadoghq.com": "https://api.datadoghq.com/api/intake/otlp/v1/traces",
    "us3.datadoghq.com": "https://api.us3.datadoghq.com/api/intake/otlp/v1/traces",
    "us5.datadoghq.com": "https://api.us5.datadoghq.com/api/intake/otlp/v1/traces",
    "datadoghq.eu": "https://api.datadoghq.eu/api/intake/otlp/v1/traces",
    "ap1.datadoghq.com": "https://api.ap1.datadoghq.com/api/intake/otlp/v1/traces",
}

def get_otlp_endpoint():
    return OTLP_ENDPOINT_MAP.get(DD_SITE, OTLP_ENDPOINT_MAP["datadoghq.com"])
