import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


langchain_config = {
    "llm": "Gemini",
    "api_key": GEMINI_API_KEY,
  
}
