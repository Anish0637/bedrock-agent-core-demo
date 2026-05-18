"""
Bedrock Agent Core wrapper for managing agent invocations.
Handles session state and tool execution orchestration.
"""

import boto3
import logging
import json
import os
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)

class BedrockAgentClient:
    def __init__(self, agent_id: str, agent_alias_id: str = "LFTSTCNFEW", region: str = "us-east-1"):
        """
        Initialize Bedrock Agent Core client.
        
        Args:
            agent_id: The Bedrock Agent ID (from console or create_agent.py)
            agent_alias_id: The agent alias ID (default: LFTSTCNFEW = latest alias)
            region: AWS region
        """
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.region = region
        self.client = boto3.client("bedrock-agent-runtime", region_name=region)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.session_table_name = "bedrock-agent-sessions"
        self._ensure_session_table()
    
    def _ensure_session_table(self):
        """Create DynamoDB table for session state if it doesn't exist."""
        try:
            self.dynamodb.create_table(
                TableName=self.session_table_name,
                KeySchema=[
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
                TimeToLiveSpecification={
                    "AttributeName": "ttl",
                    "Enabled": True,
                },
            )
            logger.info(f"Created DynamoDB table: {self.session_table_name}")
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            logger.debug(f"Table {self.session_table_name} already exists")
        except Exception as e:
            logger.warning(f"Could not create session table: {e}. Session state may not persist.")
    
    def invoke(
        self,
        message: str,
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Invoke the Bedrock Agent Core.
        
        Args:
            message: User query/prompt
            session_id: Conversation session ID (auto-generated if not provided)
            max_iterations: Max agent reasoning loops
            timeout_seconds: Invocation timeout
            
        Returns:
            Response dict with output, trace_id, status
        """
        if not session_id:
            session_id = str(uuid4())
        
        trace_id = str(uuid4())
        invocation_started = datetime.utcnow()
        
        try:
            logger.info(f"Invoking agent {self.agent_id} with message: {message[:100]}")
            
            # Invoke Bedrock Agent Core
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=message,
                sessionState={
                    "sessionAttributes": {
                        "trace_id": trace_id,
                        "invoked_at": invocation_started.isoformat(),
                    }
                },
                enableTrace=True,
            )
            
            # Parse streaming response
            output_text = ""
            # The response is an event stream - collect completion events
            for event in response.get("completion", []):
                if isinstance(event, dict):
                    if "text" in event:
                        output_text += event.get("text", "")
                    elif "chunk" in event:
                        chunk = event["chunk"]
                        if "bytes" in chunk:
                            output_text += chunk["bytes"].decode("utf-8")
            
            # If no text found, try to get from response body
            if not output_text and "body" in response:
                import json
                body = response["body"].read()
                try:
                    body_data = json.loads(body)
                    output_text = body_data.get("output", "").get("text", "")
                except Exception:
                    pass  # If parsing fails, use empty output
            
            invocation_duration = (datetime.utcnow() - invocation_started).total_seconds()
            
            # Store session state
            self._save_session_state(session_id, message, output_text, trace_id, invocation_duration)
            
            return {
                "output": output_text or "No response from agent.",
                "session_id": session_id,
                "trace_id": trace_id,
                "status": "success",
                "duration_seconds": invocation_duration,
            }
        
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}", exc_info=True)
            return {
                "output": f"Error: {str(e)}",
                "session_id": session_id,
                "trace_id": trace_id,
                "status": "error",
                "error": str(e),
            }
    
    def _save_session_state(
        self,
        session_id: str,
        message: str,
        output: str,
        trace_id: str,
        duration: float,
    ):
        """Save conversation to DynamoDB for audit trail."""
        try:
            table = self.dynamodb.Table(self.session_table_name)
            now = datetime.utcnow()
            ttl_timestamp = int((now + timedelta(days=30)).timestamp())
            
            table.put_item(
                Item={
                    "session_id": session_id,
                    "timestamp": now.isoformat(),
                    "message": message,
                    "output": output,
                    "trace_id": trace_id,
                    "duration_seconds": duration,
                    "ttl": ttl_timestamp,
                }
            )
            logger.debug(f"Saved session state for {session_id}")
        except Exception as e:
            logger.warning(f"Failed to save session state: {e}")
    
    def get_session_history(self, session_id: str, limit: int = 10) -> list:
        """Retrieve conversation history for a session."""
        try:
            table = self.dynamodb.Table(self.session_table_name)
            response = table.query(
                KeyConditionExpression="session_id = :sid",
                ExpressionAttributeValues={":sid": session_id},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            return response.get("Items", [])
        except Exception as e:
            logger.warning(f"Failed to retrieve session history: {e}")
            return []
