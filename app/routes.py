from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .intent_handler import interpret_intent, execute_intent

router = APIRouter()

class Query(BaseModel):
    prompt: str

@router.get("/healthz")
def healthz():
    return {"status": "ok"}

@router.post("/query")
def handle_query(q: Query):
    user_prompt = q.prompt or ""
    if not user_prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    intent = interpret_intent(user_prompt)
    result = execute_intent(intent)
    return {"intent": intent, "result": result}
