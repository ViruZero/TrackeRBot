import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("trackerbot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler("trackerbot.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

class MockOllamaResponse:
    def __init__(self, text: str, status_code: int = 200):
        self._text = text
        self.status_code = status_code

    def json(self):
        return {"response": self._text}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error {self.status_code}")

def smart_ai_post(url: str, json: dict = None, timeout: int = 20, **kwargs):
    payload = json or {}
    local_url = os.getenv("LOCAL_OLLAMA_URL", url).strip()

    # Tier 1: Try Local PC Ollama first (3s connect timeout, 25s read timeout)
    try:
        resp = requests.post(local_url, json=payload, timeout=(3.0, 25.0))
        if resp.status_code == 200:
            print("[AI Router] Answered by Local PC (Ollama)")
            return resp
        logger.error(f"[AI Router] Local PC (Ollama) returned status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.exception("[AI Router] Local PC (Ollama) tier failed")
        print(f"[AI Router] Local PC unreachable ({type(e).__name__}), switching to Groq Cloud AI...")

    # Tier 2: Fallback to Groq Free Cloud API (openai/gpt-oss-120b)
    prompt = payload.get("prompt", "")
    options = payload.get("options", {})
    temperature = options.get("temperature", 0.85)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    try:
        if not groq_key:
            raise RuntimeError("GROQ_API_KEY is missing in .env")

        groq_payload = {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        # Preserve strict JSON output mode for tracker_image.py price extraction
        if payload.get("format") == "json":
            groq_payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
            "User-Agent": "TrackerBot/1.0"
        }

        groq_resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=groq_payload,
            timeout=25
        )
        groq_resp.raise_for_status()
        data = groq_resp.json()
        answer = data["choices"][0]["message"]["content"] or ""
        print("[AI Router] Answered by Groq Cloud AI (openai/gpt-oss-120b)")
        return MockOllamaResponse(answer, 200)
    except Exception:
        logger.exception("[AI Router] Groq Cloud AI tier failed")
        print("[AI Router] Groq Cloud AI failed, switching to Gemini...")

    # Tier 3: Fallback to Google Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        logger.error("[AI Router] Gemini tier failed: GEMINI_API_KEY is missing in .env")
        raise RuntimeError("Local AI is offline, Groq Cloud AI failed, and GEMINI_API_KEY is missing in .env")

    generation_config = {"temperature": temperature}
    if payload.get("format") == "json":
        generation_config["response_mime_type"] = "application/json"

    gemini_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config
    }

    try:
        gemini_resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            json=gemini_payload,
            timeout=25
        )
        gemini_resp.raise_for_status()
        data = gemini_resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"]
        print("[AI Router] Answered by Gemini")
        return MockOllamaResponse(answer, 200)
    except Exception as e:
        logger.exception("[AI Router] Gemini tier failed")
        raise RuntimeError(f"Local AI is offline, Groq Cloud AI failed, and Gemini failed: {e}") from e
