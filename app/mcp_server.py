
import asyncio
import json
import sys
from typing import Any, Dict

# Minimal MCP over stdio using asyncio streams.
# Requires `mcp` python package (modelcontextprotocol)

from mcp.server import Server
from mcp.types import Tool, ToolInputSchema, CallToolResult
from pydantic import BaseModel, Field

# Import our intent executor
from app.intent_handler import interpret_intent, execute_intent

server = Server("mcp-k8s")

class QueryInput(BaseModel):
    prompt: str = Field(..., description="Natural language request, e.g. 'list pods in kube-system'.")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="k8s_query",
            description="Parse a natural language Kubernetes request and execute it against the cluster.",
            inputSchema=ToolInputSchema.json_schema(QueryInput.schema())
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    if name != "k8s_query":
        return CallToolResult(content=[{"type":"text","text": json.dumps({"error":"unknown tool"})}])
    try:
        q = QueryInput(**arguments)
    except Exception as e:
        return CallToolResult(content=[{"type":"text","text": json.dumps({"error":str(e)})}])
    intent = interpret_intent(q.prompt)
    result = execute_intent(intent)
    return CallToolResult(
        content=[{"type":"text","text": json.dumps({"intent":intent,"result":result})}]
    )

async def main():
    await server.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())
