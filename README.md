# Bedrock Agent Core Demo

Minimal demo agent using **AWS Bedrock Agent Core** — AWS's managed agentic service that handles ReAct loops internally.

## What It Does

- Accepts user queries via REST API
- Uses **Bedrock Agent Core** (managed service) to reason and plan
- Calls tools like math, time, and AWS operations
- Returns results with full auditability

## Key Differences from LangGraph

| Aspect | LangGraph | Bedrock Agent Core |
|--------|-----------|-------------------|
| Agentic loop | Custom in code | Managed by AWS |
| Tool calling | Via LangChain | Via Agent Core API |
| Model failover | Custom logic | Built-in |
| Pricing | Pay per model call | Pay per agent invocation |
| Deployment | ECS/Lambda | Managed service |
| Observability | Custom spans + CloudWatch | Agent Core logs + CloudWatch |

## Quick Start

### 1. Prerequisites

```bash
pip install -r requirements.txt
```

### 2. Configure AWS Credentials

```bash
export AWS_PROFILE=your_profile
export AWS_REGION=us-east-1
```

### 3. Create Agent (One-time)

```bash
python3 scripts/create_agent.py
```

Saves agent ID to `.env`:
```
BEDROCK_AGENT_ID=XXXXX
BEDROCK_AGENT_ALIAS_ID=XXXXX
```

### 4. Run API Server

```bash
python3 -m uvicorn agent_api.main:app --host 127.0.0.1 --port 8080
```

### 5. Send Request

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is 15 + 25?",
    "session_id": "demo-1"
  }'
```

Response:
```json
{
  "output": "15 + 25 = 40",
  "session_id": "demo-1",
  "trace_id": "abc123...",
  "status": "success"
}
```

## Project Structure

```
bedrock-agent-core-demo/
├── agent_api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with /invoke endpoint
│   ├── bedrock_client.py    # Bedrock Agent Core wrapper
│   └── models.py            # Pydantic models
├── scripts/
│   ├── create_agent.py      # One-time agent creation
│   └── deploy_lambda.py     # AWS Lambda deployment helper
├── tests/
│   ├── test_agent_api.py
│   └── test_bedrock_client.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── README.md
└── .gitignore
```

## Architecture

```
Client
  ↓
FastAPI /invoke
  ↓
Bedrock Agent Core (managed)
  ├─ Model: Claude 3.5 Sonnet
  ├─ Tools: add_numbers, get_utc_time, get_aws_identity
  ├─ ReAct loop (automatic)
  └─ CloudWatch logs
  ↓
DynamoDB (session state)
  ↓
Response JSON
```

## Tools Available

1. **add_numbers(a: float, b: float) → float**
   - Adds two numbers deterministically

2. **get_utc_time() → string**
   - Returns current UTC timestamp

3. **get_aws_identity() → dict**
   - Returns caller's AWS account ID (via STS)

## Deployment

### Option 0: No Docker, No EC2 (API Gateway + Lambda)

This is the simplest managed deployment path.

```bash
AWS_PROFILE=anish0637 \
AWS_REGION=us-east-1 \
AGENT_ID=WBXFYNOUAH \
AGENT_ALIAS_ID=TSTALIASID \
./scripts/deploy_lambda_apigw.sh
```

The script creates/updates:
- Lambda function (`bedrock-agent-core-demo-lambda`)
- IAM role for Lambda execution
- HTTP API Gateway endpoint with `POST /invoke`

### Option 1: ECS (Recommended for prod)

```bash
./scripts/deploy_ecs.sh
```

### Option 2: AWS Lambda (Serverless)

```bash
./scripts/deploy_lambda_apigw.sh
```

### Option 3: Local Docker

```bash
docker build -t bedrock-agent-core-demo .
docker run -p 8080:8080 bedrock-agent-core-demo
```

## Observability

### CloudWatch Logs

Agent Core logs go to:
```
/aws/bedrock/agent-core/demo-agent
```

Query all invocations:
```bash
aws logs tail /aws/bedrock/agent-core/demo-agent --follow
```

### Metrics

Track in CloudWatch:
- `AgentInvocations` (count)
- `ToolCallCount` (per tool)
- `AverageLatency` (ms)

## Next Steps

1. **Add more tools** — Extend `agent_api/bedrock_client.py` with custom actions
2. **Add auth** — API key / IAM validation
3. **Add caching** — DynamoDB session caching
4. **Monitor cost** — CloudWatch cost allocation tags
5. **Multi-agent** — Agent discovery + routing

## Cost Estimate (Monthly)

Assuming 10K invocations/month:
- Bedrock Agent Core: ~$0.025/invocation = **$250/month**
- DynamoDB (on-demand): ~$5/month
- CloudWatch: ~$10/month
- **Total: ~$265/month**

(Varies by region and model choice)

## Troubleshooting

**"Agent not found"**
- Run `python3 scripts/create_agent.py` first

**"Tool execution failed"**
- Check CloudWatch logs for Bedrock Agent Core errors
- Verify IAM role has Bedrock permissions

**"Session state expired"**
- DynamoDB TTL is set to 24h; increase in `bedrock_client.py` if needed

## References

- [AWS Bedrock Agent Core Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Agent Definitions and Tools](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-step-by-step.html)
- [CloudWatch Logs for Agents](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-monitor.html)
