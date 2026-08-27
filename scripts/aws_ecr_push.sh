#!/usr/bin/env bash
# Helper steps for ECR push + ECS Express Mode (explanations live in the chat / README).
# Requires: aws CLI configured, docker logged in capability.
#
# Usage examples:
#   export AWS_REGION=us-west-2
#   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
#   ./scripts/aws_ecr_push.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AWS_REGION="${AWS_REGION:-us-west-2}"
REPO_NAME="${REPO_NAME:-fin-rag-lab}"
LOCAL_TAG="${LOCAL_TAG:-fin-rag-lab:cloud}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

command -v aws >/dev/null || { echo "Install AWS CLI first"; exit 1; }
DOCKER="${DOCKER:-docker}"
if ! command -v "$DOCKER" >/dev/null 2>&1; then
  DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}"

echo "Account:  $ACCOUNT_ID"
echo "Region:   $AWS_REGION"
echo "ECR repo: $ECR_URI:$IMAGE_TAG"

# Create repo if missing
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository \
       --repository-name "$REPO_NAME" \
       --region "$AWS_REGION" \
       --image-scanning-configuration scanOnPush=true \
       --encryption-configuration encryptionType=AES256

echo "Logging in to ECR…"
aws ecr get-login-password --region "$AWS_REGION" \
  | "$DOCKER" login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Tagging and pushing…"
"$DOCKER" tag "$LOCAL_TAG" "${ECR_URI}:${IMAGE_TAG}"
"$DOCKER" push "${ECR_URI}:${IMAGE_TAG}"

echo
echo "Pushed: ${ECR_URI}:${IMAGE_TAG}"
echo "Next: create Secrets Manager secret + ECS Express Mode service (see deploy guide)."
