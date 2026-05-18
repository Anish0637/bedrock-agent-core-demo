#!/bin/bash
# Deploy Bedrock Agent Core demo to AWS Lambda

set -euo pipefail

FUNCTION_NAME="bedrock-agent-core-demo"
ROLE_NAME="lambda-bedrock-agent-role"
AWS_REGION="${AWS_REGION:=us-east-1}"

echo "📦 Building deployment package..."
mkdir -p build
pip install -r requirements.txt -t build/

cp -r agent_api/ build/
cp agent_api/main.py build/lambda_handler.py

cd build
zip -r ../lambda_function.zip . -x "*.pyc"
cd ..

echo "📤 Uploading to Lambda..."

# Create or update Lambda function
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file fileb://lambda_function.zip \
  --region "$AWS_REGION" || aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.11 \
  --role "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME" \
  --handler lambda_handler.handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 60 \
  --environment "Variables={AWS_REGION=$AWS_REGION}" \
  --region "$AWS_REGION"

echo "✓ Deployed to Lambda: $FUNCTION_NAME"
echo ""
echo "To test:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME response.json"
