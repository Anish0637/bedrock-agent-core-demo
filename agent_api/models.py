"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime


class InvokeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User query")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    max_iterations: int = Field(10, ge=1, le=20, description="Max agent loops")


class InvokeResponse(BaseModel):
    output: str
    session_id: str
    trace_id: str
    status: str  # "success" or "error"
    duration_seconds: float
    error: Optional[str] = None


class SessionHistoryRequest(BaseModel):
    session_id: str
    limit: int = Field(10, ge=1, le=100)


class SessionMessage(BaseModel):
    timestamp: str
    message: str
    output: str
    trace_id: str
    duration_seconds: float


class HealthResponse(BaseModel):
    status: str
    agent_id: str
    timestamp: str
