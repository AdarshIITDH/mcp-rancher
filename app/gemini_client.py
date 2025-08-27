import os
import json
import requests
from .config import settings

GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_URL = settings.GEMINI_URL

def _extract_text(resp_json: dict) -> str:
    # Gemini REST v1beta response shape: candidates[0].content.parts[].text
    try:
        cands = resp_json.get("candidates") or []
        if not cands:
            return ""
        parts = cands[0].get("content", {}).get("parts", []) or []
        texts = []
        for p in parts:
            t = p.get("text", "")
            if t:
                texts.append(t)
        return "\n".join(texts).strip()
    except Exception:
        return ""

def query_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return '{"action":"unknown","params":{"error":"GEMINI_API_KEY not set"}}'

    headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(GEMINI_URL, headers=headers, data=json.dumps(body), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return '{"action":"unknown","params":{"error":"Gemini request failed","details":"%s"}}' % str(e).replace('"','\"')
    except ValueError:
        return '{"action":"unknown","params":{"error":"Gemini returned non-JSON"}}'

    text = _extract_text(data)
    # Ensure we return *some* string; intent_handler will sanitize/validate
    return text or '{"action":"unknown","params":{}}'
