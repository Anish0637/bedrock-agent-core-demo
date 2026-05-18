import json
import os
import uuid

import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AGENT_ID = os.getenv("AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("AGENT_ALIAS_ID", "")

client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)


def _extract_text(response):
    text = ""
    for event in response.get("completion", []):
        if "chunk" in event and "bytes" in event["chunk"]:
            text += event["chunk"]["bytes"].decode("utf-8")
    return text


def handler(event, context):
    if not AGENT_ID or not AGENT_ALIAS_ID:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "error",
                "error": "AGENT_ID and AGENT_ALIAS_ID must be set"
            }),
        }

    try:
        raw_body = event.get("body") if isinstance(event, dict) else None
        body = json.loads(raw_body) if raw_body else {}
        message = body.get("message", "")
        session_id = body.get("session_id") or str(uuid.uuid4())

        if not message:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "error", "error": "message is required"}),
            }

        response = client.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=message,
            enableTrace=True,
        )

        output_text = _extract_text(response)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "status": "success",
                    "session_id": session_id,
                    "output": output_text,
                }
            ),
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "error", "error": str(exc)}),
        }
