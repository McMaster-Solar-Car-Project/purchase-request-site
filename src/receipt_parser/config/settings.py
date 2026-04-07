import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()

# Only set credentials if not already configured (e.g., by deployment/host)
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    # Resolve relative to project root, not current working directory
    project_root = Path(__file__).parent.parent.parent.parent
    default_creds_path = project_root / "google_ocr_credentials.json"

    if not default_creds_path.exists():
        raise FileNotFoundError(
            f"GOOGLE_APPLICATION_CREDENTIALS environment variable is not set "
            f"and default credentials file not found: {default_creds_path}\n"
            f"Please set GOOGLE_APPLICATION_CREDENTIALS to your service account key file path."
        )

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(default_creds_path)

WORD = re.compile(r"\w+")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable must be set before initializing the Gemini client."
    )
client = genai.Client(api_key=api_key)
