"""
FastAPI application for Bedrock Agent Core demo.
Exposes /invoke and /health endpoints.
"""

import os
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from agent_api.bedrock_client import BedrockAgentClient
from agent_api.models import InvokeRequest, InvokeResponse, HealthResponse, SessionHistoryRequest, SessionMessage

# Load .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Bedrock Agent Core Demo",
    version="0.1.0",
    description="AWS Bedrock Agent Core demo with REST API",
)

# Bedrock client
BEDROCK_AGENT_ID = os.getenv("BEDROCK_AGENT_ID")
BEDROCK_AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID", "LFTSTCNFEW")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not BEDROCK_AGENT_ID:
    logger.warning("BEDROCK_AGENT_ID not set. Run `python3 scripts/create_agent.py` first.")
    bedrock_client = None
else:
    try:
        bedrock_client = BedrockAgentClient(
            agent_id=BEDROCK_AGENT_ID,
            agent_alias_id=BEDROCK_AGENT_ALIAS_ID,
            region=AWS_REGION,
        )
        logger.info(f"Initialized Bedrock Agent: {BEDROCK_AGENT_ID}")
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {e}")
        bedrock_client = None


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok" if bedrock_client else "degraded",
        agent_id=BEDROCK_AGENT_ID or "not-configured",
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke_agent(request: InvokeRequest):
    """Invoke the Bedrock Agent Core with a user message."""
    if not bedrock_client:
        return InvokeResponse(
            output="Agent not initialized. Run `python3 scripts/create_agent.py` first.",
            session_id=request.session_id or "none",
            trace_id="none",
            status="error",
            duration_seconds=0.0,
            error="Agent not configured",
        )
    
    try:
        logger.info(f"Processing request: {request.message[:50]}...")
        result = bedrock_client.invoke(
            message=request.message,
            session_id=request.session_id,
            max_iterations=request.max_iterations,
        )
        
        # Ensure all required fields are present
        result.setdefault("duration_seconds", 0.0)
        return InvokeResponse(**result)
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        return InvokeResponse(
            output=f"Internal error: {str(e)}",
            session_id=request.session_id or "unknown",
            trace_id="error",
            status="error",
            duration_seconds=0.0,
            error=str(e),
        )


@app.post("/session-history")
async def get_session_history(request: SessionHistoryRequest):
    """Retrieve conversation history for a session."""
    if not bedrock_client:
        return JSONResponse(status_code=503, content={"error": "Agent not configured"})
    
    history = bedrock_client.get_session_history(request.session_id, request.limit)
    return {"session_id": request.session_id, "messages": history}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="127.0.0.1", port=port)
