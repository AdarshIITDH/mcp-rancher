
import json
import re
from .gemini_client import query_gemini
from . import k8s_client

SYSTEM_PROMPT = """
You are an intent extractor for Kubernetes ops.
Return ONLY valid JSON (no code fences), following exactly this schema:

{
  "action": "list_pods" | "top_pods" | "scale_resources",
  "params": {
    "namespace": "default",
    "resource_name": "string",
    "percentage": 30,
    "operation": "decrease" | "increase"
  }
}
Do not include any other keys. Do not include markdown or comments.
"""

def _regex_fallback(user_prompt: str) -> dict:
    p = user_prompt.strip().lower()

    # list pods
    if "list" in p and "pod" in p:
        ns = "default"
        m = re.search(r"(?:in|from)\s+([a-z0-9-]+)\s+namespace", p)
        if m:
            ns = m.group(1)
        return {"action": "list_pods", "params": {"namespace": ns}}

    # top pods
    if ("top" in p or "most" in p) and "pod" in p:
        ns = "default"
        m = re.search(r"(?:in|from)\s+([a-z0-9-]+)\s+namespace", p)
        if m:
            ns = m.group(1)
        return {"action": "top_pods", "params": {"namespace": ns}}

    # scale / optimize
    if any(x in p for x in ["scale", "optimise", "optimize", "reduce", "increase"]):
        tokens = re.findall(r"[a-z0-9-]+", p)
        resource_name = tokens[-1] if tokens else None
        percent = 30
        m = re.search(r"(\d+)\s*%+", p)
        if m:
            percent = int(m.group(1))
        operation = "decrease"
        if "increase" in p:
            operation = "increase"
        return {
            "action": "scale_resources",
            "params": {
                "resource_name": resource_name,
                "percentage": percent,
                "operation": operation,
                "namespace": "default"
            }
        }

    return {"action": "unknown", "params": {}}

def _cleanup_gemini(raw: str) -> str:
    cleaned = raw.strip()
    # Strip triple backticks & language tag if any
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned

def _normalize_intent(intent: dict) -> dict:
    action = intent.get("action", "unknown")
    params = intent.get("params", {}) or {}
    ns = params.get("namespace") or "default"
    params["namespace"] = ns
    if action == "scale_resources":
        params["percentage"] = int(params.get("percentage", 30) or 30)
        op = params.get("operation") or "decrease"
        if op not in ["decrease", "increase"]:
            op = "decrease"
        params["operation"] = op
    return {"action": action, "params": params}

def interpret_intent(user_prompt: str) -> dict:
    # Ask Gemini with a strict preamble
    raw = query_gemini(f"{SYSTEM_PROMPT}\nUser: {user_prompt}")
    cleaned = _cleanup_gemini(raw)
    try:
        intent = json.loads(cleaned)
        return _normalize_intent(intent)
    except Exception:
        # Fall back to regex
        return _regex_fallback(user_prompt)

def execute_intent(intent: dict):
    action = intent.get("action")
    params = intent.get("params", {}) or {}
    ns = params.get("namespace", "default")

    if action == "list_pods":
        return k8s_client.list_pods(namespace=ns)

    elif action == "top_pods":
        return k8s_client.top_pods(namespace=ns)

    elif action == "scale_resources":
        resource_name = params.get("resource_name")
        if not resource_name:
            return {"error": "resource_name missing", "intent": intent}
        return k8s_client.scale_resources(
            resource_name=resource_name,
            namespace=ns,
            percentage=params.get("percentage", 30),
            operation=params.get("operation", "decrease"),
        )

    else:
        return {"error": "Unknown action", "details": intent}
