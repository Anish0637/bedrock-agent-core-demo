#!/bin/bash
set -euo pipefail

: "${AWS_PROFILE:=default}"
: "${AWS_REGION:=us-east-1}"
: "${PORT:=8080}"

export AWS_PROFILE AWS_REGION

python3 -m uvicorn agent_api.main:app --host 127.0.0.1 --port "$PORT" --reload
