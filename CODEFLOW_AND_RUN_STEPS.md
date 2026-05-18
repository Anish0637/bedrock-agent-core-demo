# Bedrock Agent Core Demo: Code Flow and Run Steps

## 1. Project Overview

This project exposes a FastAPI API that forwards user requests to an AWS Bedrock Agent, stores session records in DynamoDB, and returns structured responses.

Core entrypoint:
- API app: `agent_api/main.py`
- Bedrock + DynamoDB client wrapper: `agent_api/bedrock_client.py`
- Data models: `agent_api/models.py`

---

## 2. Code Flow (Request Lifecycle)

### Step A: Server startup

When you run Uvicorn with `agent_api.main:app`:
1. `.env` is loaded in `agent_api/main.py`.
2. `BEDROCK_AGENT_ID`, `BEDROCK_AGENT_ALIAS_ID`, and `AWS_REGION` are read.
3. `BedrockAgentClient(...)` is initialized.
4. During init, `_ensure_session_table()` runs:
   - Creates DynamoDB table `bedrock-agent-sessions` if missing.
   - Ensures TTL is enabled on attribute `ttl`.

### Step B: Health check

`GET /health` returns:
- `status = ok` when Bedrock client is initialized.
- `agent_id` currently configured in env.

### Step C: Invoke request

For `POST /invoke`:
1. FastAPI validates request body using `InvokeRequest`.
2. `main.py` calls `bedrock_client.invoke(...)`.
3. `bedrock_client.py` sends `invoke_agent` to Bedrock with:
   - `agentId`
   - `agentAliasId`
   - `sessionId`
   - `inputText`
   - `sessionState.sessionAttributes` (`trace_id`, `invoked_at`)
   - `enableTrace=True`
4. Response stream is parsed into `output_text`.
5. Session record is persisted in DynamoDB via `_save_session_state(...)`.
6. API returns `InvokeResponse` with:
   - `output`
   - `session_id`
   - `trace_id`
   - `status`
   - `duration_seconds`

### Step D: Session history

For `POST /session-history`:
1. API reads `session_id` + `limit`.
2. `get_session_history(...)` queries DynamoDB by partition key `session_id`.
3. Returns recent messages for that session.

---

## 3. Architecture in Practice

1. Client sends HTTP request to FastAPI.
2. FastAPI invokes Bedrock Agent Runtime.
3. Bedrock Agent (Nova Micro model) generates response.
4. App writes interaction record to DynamoDB.
5. Client can fetch conversation history via `/session-history`.

---

## 4. Prerequisites

- Python 3.11+
- AWS account with Bedrock Agent access
- Valid AWS profile (working in this setup: `anish0637`)
- Region: `us-east-1`

Install dependencies:

```bash
cd /tmp/bedrock-agent-core-demo
pip install -r requirements.txt
```

If `aws-lambda-wsgi` install fails, use:

```bash
pip install boto3 fastapi "uvicorn[standard]" pydantic python-dotenv
```

---

## 5. Environment Setup

Create env file:

```bash
cp .env.example .env
```

Set values (important):

```env
AWS_PROFILE=anish0637
AWS_REGION=us-east-1
BEDROCK_AGENT_ID=WBXFYNOUAH
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
PORT=8082
LOG_LEVEL=INFO
```

---

## 6. Run the API

```bash
cd /tmp/bedrock-agent-core-demo
AWS_PROFILE=anish0637 AWS_REGION=us-east-1 BEDROCK_AGENT_ALIAS_ID=TSTALIASID \
PYTHONPATH=/tmp/bedrock-agent-core-demo \
python3 -m uvicorn agent_api.main:app --host 127.0.0.1 --port 8082
```

---

## 7. Test Endpoints (Examples)

### Health

```bash
curl -s http://127.0.0.1:8082/health | python3 -m json.tool
```

Expected shape:

```json
{
  "status": "ok",
  "agent_id": "WBXFYNOUAH",
  "timestamp": "..."
}
```

### Invoke

```bash
curl -s -X POST http://127.0.0.1:8082/invoke \
  -H "Content-Type: application/json" \
  -d '{"message":"What is 8 + 9?","session_id":"demo-mem-4"}' | python3 -m json.tool
```

Example success response:

```json
{
  "output": "The result of 8 + 9 is 17.",
  "session_id": "demo-mem-4",
  "trace_id": "...",
  "status": "success",
  "duration_seconds": 2.0,
  "error": null
}
```

### Session history

```bash
curl -s -X POST http://127.0.0.1:8082/session-history \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-mem-4","limit":5}' | python3 -m json.tool
```

Example:

```json
{
  "session_id": "demo-mem-4",
  "messages": [
    {
      "message": "What is 8 + 9?",
      "output": "The result of 8 + 9 is 17.",
      "trace_id": "..."
    }
  ]
}
```

---

## 8. Verify DynamoDB Persistence Directly

```bash
AWS_PAGER="" aws dynamodb query \
  --table-name bedrock-agent-sessions \
  --key-condition-expression 'session_id = :sid' \
  --expression-attribute-values '{":sid":{"S":"demo-mem-4"}}' \
  --region us-east-1 \
  --profile anish0637 \
  --output json
```

If records exist, memory persistence is working.

---

## 9. Troubleshooting

### `address already in use`
Use a different port (e.g. `8082`).

### Bedrock invoke model errors
Confirm:
- Agent model is `amazon.nova-micro-v1:0`
- Agent is `PREPARED`
- Alias is valid (`TSTALIASID`)
- Model access is enabled in Bedrock console

### `InvalidClientTokenId` / token errors
Re-auth the profile:

```bash
aws sts get-caller-identity --profile anish0637
```

If needed, refresh login/credentials for that profile.

---

## 10. Useful Commands

Check agent:

```bash
AWS_PAGER="" aws bedrock-agent get-agent \
  --agent-id WBXFYNOUAH \
  --region us-east-1 \
  --profile anish0637
```

List aliases:

```bash
AWS_PAGER="" aws bedrock-agent list-agent-aliases \
  --agent-id WBXFYNOUAH \
  --region us-east-1 \
  --profile anish0637
```

Check TTL:

```bash
AWS_PAGER="" aws dynamodb describe-time-to-live \
  --table-name bedrock-agent-sessions \
  --region us-east-1 \
  --profile anish0637
```
