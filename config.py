import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(dotenv_path: str) -> None:
    if not os.path.isfile(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                continue

            if value and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]

            os.environ.setdefault(key, value)


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return list(default)

    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def _env_json_dict(name: str, default: dict[str, int]) -> dict[str, int]:
    value = os.getenv(name)
    if value is None:
        return dict(default)

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return dict(default)

    if not isinstance(parsed, dict):
        return dict(default)

    result: dict[str, int] = {}
    for key, raw_score in parsed.items():
        try:
            result[str(key)] = int(raw_score)
        except (TypeError, ValueError):
            continue

    return result or dict(default)


def _resolve_path(path_value: str) -> str:
    if not path_value:
        return ""
    if os.path.isabs(path_value):
        return path_value
    return os.path.abspath(os.path.join(BASE_DIR, path_value))


def _env_path(name: str, default: str) -> str:
    return _resolve_path(os.getenv(name, default))


APP_NAME = os.getenv("APP_NAME", "Outreach Hub")
APP_SUBTITLE = os.getenv(
    "APP_SUBTITLE",
    "Find leads, import CSVs, and send personalized outreach.",
)

# --- AI Settings ---
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_TEMPERATURE = _env_float("GEMINI_TEMPERATURE", 0.7)

# --- App Messaging ---
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "your service")
PRODUCT_CATEGORY = os.getenv("PRODUCT_CATEGORY", "workflow automation")
PRODUCT_DESCRIPTION = os.getenv(
    "PRODUCT_DESCRIPTION",
    "A service that helps teams reduce repetitive work and move faster.",
)
PRODUCT_TARGET_ROLE = os.getenv(
    "PRODUCT_TARGET_ROLE",
    "operations, sales, or business development teams",
)
PRODUCT_PAIN_POINT = os.getenv(
    "PRODUCT_PAIN_POINT",
    "repetitive manual work and fragmented outreach processes",
)
DEFAULT_CTA = os.getenv(
    "DEFAULT_CTA",
    "If this sounds relevant, just reply and I can share a short example.",
)
DEFAULT_EMAIL_SUBJECT_TEMPLATE = os.getenv(
    "DEFAULT_EMAIL_SUBJECT_TEMPLATE",
    "Quick idea for {Company}",
)
DEFAULT_EMAIL_BODY_TEMPLATE = os.getenv(
    "DEFAULT_EMAIL_BODY_TEMPLATE",
    (
        "Hi {{Name}},\n\n"
        "{{AI_Intro}}\n\n"
        f"{PRODUCT_NAME} helps teams reduce repetitive manual work and move faster.\n\n"
        f"{DEFAULT_CTA}\n\n"
        "Best,\n"
        "{sender_name}\n"
        "{sender_title}\n"
        "{sender_company}"
    ),
)

# --- Custom AI Prompt ---
CUSTOM_EMAIL_PROMPT = os.getenv("CUSTOM_EMAIL_PROMPT", "")

# --- Pipeline Settings ---
DAILY_TARGET_COUNT = _env_int("DAILY_TARGET_COUNT", 20)
MIN_LEAD_SCORE = _env_int("MIN_LEAD_SCORE", 2)

# --- Scraper Settings ---
MAX_SCROLL_COUNT = _env_int("MAX_SCROLL_COUNT", 30)
MAX_CAPTCHA_WAIT = _env_int("MAX_CAPTCHA_WAIT", 120)
MAX_RESULTS_PER_SEARCH = _env_int("MAX_RESULTS_PER_SEARCH", 100)

# --- Sender Identity ---
SENDER_NAME = os.getenv("SENDER_NAME", "Your Name")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Your Company")
SENDER_DOMAIN = os.getenv("SENDER_DOMAIN", "example.com")
SENDER_LINKEDIN = os.getenv("SENDER_LINKEDIN", "https://www.linkedin.com")
SENDER_TAGLINE = os.getenv("SENDER_TAGLINE", "Founder")
SENDER_ADDRESS = os.getenv("SENDER_ADDRESS", "123 Main St, City, Country")
SENDER_BACKGROUND = os.getenv(
    "SENDER_BACKGROUND",
    "You work closely with teams that want to replace repetitive manual work with clearer systems.",
)

# --- Tracking ---
TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "https://t.example.com")

# --- Local Paths ---
SECRETS_DIR = _env_path("SECRETS_DIR", "secrets")
DATA_DIR = _env_path("DATA_DIR", "data")
RAW_DIR = _env_path("RAW_DIR", os.path.join("data", "raw"))
PROCESSED_DIR = _env_path("PROCESSED_DIR", os.path.join("data", "processed"))
OUTPUT_DIR = _env_path("OUTPUT_DIR", os.path.join("data", "output"))
HISTORY_DIR = _env_path("HISTORY_DIR", os.path.join("data", "history"))
LOG_DIR = _env_path("LOG_DIR", "logs")
DB_PATH = _env_path("DB_PATH", os.path.join("data", "mailing_list.db"))
GMAIL_CREDENTIALS_PATH = _env_path(
    "GMAIL_CREDENTIALS_PATH",
    os.path.join("secrets", "credentials.json"),
)
GMAIL_TOKEN_PATH = _env_path(
    "GMAIL_TOKEN_PATH",
    os.path.join("secrets", "token.json"),
)
GEMINI_API_KEY_PATH = _env_path(
    "GEMINI_API_KEY_PATH",
    os.path.join("secrets", "gemini_api.txt"),
)
MILLIONVERIFIER_API_KEY_PATH = _env_path(
    "MILLIONVERIFIER_API_KEY_PATH",
    os.path.join("secrets", "millionverifier_api_key.txt"),
)

# --- Email Validation ---
VALIDATE_EMAILS = _env_bool("VALIDATE_EMAILS", True)
MILLIONVERIFIER_API_KEY = os.getenv("MILLIONVERIFIER_API_KEY", "")
if not MILLIONVERIFIER_API_KEY and os.path.isfile(MILLIONVERIFIER_API_KEY_PATH):
    with open(MILLIONVERIFIER_API_KEY_PATH, "r", encoding="utf-8") as handle:
        MILLIONVERIFIER_API_KEY = handle.read().strip()
MILLIONVERIFIER_API_URL = "https://api.millionverifier.com/api/v3/"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY and os.path.isfile(GEMINI_API_KEY_PATH):
    with open(GEMINI_API_KEY_PATH, "r", encoding="utf-8") as handle:
        GEMINI_API_KEY = handle.read().strip()

# --- Blacklist ---
DEFAULT_BLACKLIST = [
    "yelp",
    "wikipedia",
    "glassdoor",
    "indeed",
    "linkedin.com/company",
    "facebook",
    "twitter",
    "instagram",
    "yellowpages",
    "bbb.org",
    "mapquest",
    "manta",
    "crunchbase",
    "zoominfo",
    "houzz",
    "angieslist",
]

# --- Scoring Keywords ---
_DEFAULT_SCORE_KEYWORDS = {
    "automation": 2,
    "consult": 2,
    "engineering": 1,
    "energy": 1,
    "service": 1,
    "software": 1,
    "solution": 1,
    "sustainab": 1,
}
SCORE_KEYWORDS = _env_json_dict("SCORE_KEYWORDS_JSON", _DEFAULT_SCORE_KEYWORDS)
