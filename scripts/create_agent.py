"""
Create a new Bedrock Agent Core agent (one-time setup).
Saves agent ID and alias to .env file.
"""

import json
import os
import sys
import time
import boto3
from pathlib import Path
from dotenv import load_dotenv

# Load existing .env if present
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")

# Initialize clients
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
bedrock_agent_client = session.client("bedrock-agent")

def create_agent():
    """Create a new Bedrock Agent Core agent (or use existing one)."""
    
    print("🚀 Bedrock Agent Core setup...")
    print(f"   Region: {AWS_REGION}")
    print(f"   Profile: {AWS_PROFILE}\n")
    
    # Agent definition with tools
    agent_name = "bedrock-agent-core-demo"
    agent_description = "Demo agent using Bedrock Agent Core for managing tool execution"
    
    # Get current AWS account ID
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    role_arn = f"arn:aws:iam::{account_id}:role/bedrock-agent-role"
    
    # Check if role exists; if not, create it
    iam = session.client("iam")
    try:
        iam.get_role(RoleName="bedrock-agent-role")
        print("✓ Using existing IAM role: bedrock-agent-role")
    except iam.exceptions.NoSuchEntityException:
        print("⚠ Creating IAM role: bedrock-agent-role")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        iam.create_role(
            RoleName="bedrock-agent-role",
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for Bedrock Agent Core",
        )
        
        # Attach permissions
        iam.attach_role_policy(
            RoleName="bedrock-agent-role",
            PolicyArn="arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        )
    
    # Check if agent already exists
    try:
        agents_response = bedrock_agent_client.list_agents()
        existing_agent = next(
            (a for a in agents_response.get("agentSummaries", []) if a["agentName"] == agent_name),
            None
        )
        if existing_agent:
            agent_id = existing_agent["agentId"]
            print(f"✓ Using existing agent: {agent_id}")
            alias_id = "LFTSTCNFEW"  # Default alias
        else:
            raise KeyError("Not found")
    except (KeyError, IndexError):
        # Agent doesn't exist, create it
        print(f"Creating new agent: {agent_name}")
        try:
            response = bedrock_agent_client.create_agent(
                agentName=agent_name,
                description=agent_description,
                agentResourceRoleArn=role_arn,
                idleSessionTTLInSeconds=900,  # 15 minutes
                foundationModel="anthropic.claude-3-5-sonnet-20241022",
                instruction="You are a helpful assistant with access to tools. Use tools to help answer user questions. Always be clear about what you're doing.",
            )
            
            agent_id = response["agent"]["agentId"]
            print(f"✓ Agent created: {agent_id}")
            print(f"⏳ Waiting for agent to be ready...")
            
            # Wait for agent to be in PREPARED state
            max_wait = 30
            wait_interval = 2
            elapsed = 0
            while elapsed < max_wait:
                try:
                    agent_response = bedrock_agent_client.get_agent(agentId=agent_id)
                    agent_status = agent_response.get("agent", {}).get("agentStatus")
                    if agent_status == "PREPARED":
                        print(f"✓ Agent ready (status: {agent_status})\n")
                        break
                    else:
                        print(f"  Status: {agent_status} (waiting...)")
                        time.sleep(wait_interval)
                        elapsed += wait_interval
                except Exception:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
            
            # Create agent alias (for deployment)
            try:
                alias_response = bedrock_agent_client.create_agent_alias(
                    agentId=agent_id,
                    agentAliasName="DRAFT",
                    description="Draft version for testing",
                )
                alias_id = alias_response["agentAlias"]["agentAliasId"]
                print(f"✓ Agent alias created: {alias_id}\n")
            except Exception as e:
                print(f"⚠ Could not create alias: {e}")
                print(f"  Using default alias\n")
                alias_id = "LFTSTCNFEW"  # Default alias
        except Exception as e:
            print(f"❌ Error creating agent: {e}")
            sys.exit(1)
        
        # Save to .env
        with open(env_path, "a") as f:
            f.write(f"\nBEDROCK_AGENT_ID={agent_id}\n")
            f.write(f"BEDROCK_AGENT_ALIAS_ID={alias_id}\n")
        
        print(f"✓ Saved to .env:")
        print(f"  BEDROCK_AGENT_ID={agent_id}")
        print(f"  BEDROCK_AGENT_ALIAS_ID={alias_id}\n")
        
        print("🎉 Agent ready! Run: python3 -m uvicorn agent_api.main:app --reload")
        return agent_id, alias_id
    
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_agent()
