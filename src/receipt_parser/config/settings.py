import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "ocr_demo_key.json"

WORD = re.compile(r"\w+")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable must be set before initializing the Gemini client."
    )
client = genai.Client(api_key=api_key)
