#!/usr/bin/env bash
set -euo pipefail

: "${AWS_PROFILE:=anish0637}"
: "${AWS_REGION:=us-east-1}"
: "${FUNCTION_NAME:=bedrock-agent-core-demo-lambda}"
: "${ROLE_NAME:=bedrock-agent-lambda-role}"
: "${AGENT_ID:=WBXFYNOUAH}"
: "${AGENT_ALIAS_ID:=TSTALIASID}"

export AWS_PROFILE AWS_REGION
AWS="aws --profile ${AWS_PROFILE} --region ${AWS_REGION}"

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP_PATH="${WORKDIR}/lambda_function.zip"

echo "Packaging Lambda..."
cd "${WORKDIR}/lambda"
rm -f "${ZIP_PATH}"
zip -q "${ZIP_PATH}" handler.py

ACCOUNT_ID="$(${AWS} sts get-caller-identity --query Account --output text)"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

if ! ${AWS} iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  echo "Creating IAM role ${ROLE_NAME}..."
  cat > /tmp/lambda-trust.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
  ${AWS} iam create-role --role-name "${ROLE_NAME}" --assume-role-policy-document file:///tmp/lambda-trust.json >/dev/null
  ${AWS} iam attach-role-policy --role-name "${ROLE_NAME}" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  ${AWS} iam attach-role-policy --role-name "${ROLE_NAME}" --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
  echo "Waiting for IAM role propagation..."
  sleep 10
fi

if ${AWS} lambda get-function --function-name "${FUNCTION_NAME}" >/dev/null 2>&1; then
  echo "Updating existing Lambda function..."
  ${AWS} lambda update-function-code --function-name "${FUNCTION_NAME}" --zip-file "fileb://${ZIP_PATH}" >/dev/null
  ${AWS} lambda update-function-configuration \
    --function-name "${FUNCTION_NAME}" \
    --runtime python3.11 \
    --handler handler.handler \
    --timeout 30 \
      --environment "Variables={AGENT_ID=${AGENT_ID},AGENT_ALIAS_ID=${AGENT_ALIAS_ID}}" >/dev/null
else
  echo "Creating Lambda function..."
  ${AWS} lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --runtime python3.11 \
    --role "${ROLE_ARN}" \
    --handler handler.handler \
    --zip-file "fileb://${ZIP_PATH}" \
    --timeout 30 \
      --environment "Variables={AGENT_ID=${AGENT_ID},AGENT_ALIAS_ID=${AGENT_ALIAS_ID}}" >/dev/null
fi

API_ID="$(${AWS} apigatewayv2 get-apis --query "Items[?Name=='${FUNCTION_NAME}-api'].ApiId | [0]" --output text)"
if [[ "${API_ID}" == "None" || -z "${API_ID}" ]]; then
  echo "Creating HTTP API..."
  API_ID="$(${AWS} apigatewayv2 create-api --name "${FUNCTION_NAME}-api" --protocol-type HTTP --target "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}" --query ApiId --output text)"
fi

API_ENDPOINT="$(${AWS} apigatewayv2 get-api --api-id "${API_ID}" --query ApiEndpoint --output text)"

ROUTE_ID="$(${AWS} apigatewayv2 get-routes --api-id "${API_ID}" --query "Items[?RouteKey=='POST /invoke'].RouteId | [0]" --output text)"
if [[ "${ROUTE_ID}" == "None" || -z "${ROUTE_ID}" ]]; then
  INTEGRATION_ID="$(${AWS} apigatewayv2 get-integrations --api-id "${API_ID}" --query "Items[0].IntegrationId" --output text)"
  ${AWS} apigatewayv2 create-route \
    --api-id "${API_ID}" \
    --route-key 'POST /invoke' \
    --target "integrations/${INTEGRATION_ID}" >/dev/null
fi

if ! ${AWS} lambda get-policy --function-name "${FUNCTION_NAME}" 2>/dev/null | grep -q "apigateway.amazonaws.com"; then
  ${AWS} lambda add-permission \
    --function-name "${FUNCTION_NAME}" \
    --statement-id "apigw-invoke-$(date +%s)" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*/*" >/dev/null
fi

echo "Done. Invoke endpoint:"
echo "${API_ENDPOINT}/invoke"
echo
echo "Test with:"
echo "curl -s -X POST '${API_ENDPOINT}/invoke' -H 'content-type: application/json' -d '{\"message\":\"What is 2 + 2?\",\"session_id\":\"demo-api\"}'"
