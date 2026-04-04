import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "ocr_demo_key.json"

WORD = re.compile(r"\w+")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
