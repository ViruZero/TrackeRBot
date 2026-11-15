import os
import requests
from dotenv import load_dotenv

load_dotenv()

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
    except Exception as e:
        print(f"[AI Router] Local PC unreachable ({type(e).__name__}), switching to Groq Cloud AI...")

    # Tier 2: Fallback to Groq Free Cloud API (openai/gpt-oss-120b)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise RuntimeError("Local AI is offline and GROQ_API_KEY is missing in .env")

    prompt = payload.get("prompt", "")
    options = payload.get("options", {})
    temperature = options.get("temperature", 0.85)

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
