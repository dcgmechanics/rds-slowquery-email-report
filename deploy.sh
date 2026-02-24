#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-rds-slow-query-report}"
REGION="${2:-ap-south-1}"
PARAMS_FILE="parameters.json"

echo "============================================="
echo " RDS Slow Query Report - CloudFormation Deploy"
echo "============================================="
echo "Stack Name : ${STACK_NAME}"
echo "Region     : ${REGION}"
echo "Parameters : ${PARAMS_FILE}"
echo ""

if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed. Install it first."
    exit 1
fi

echo "Validating template..."
aws cloudformation validate-template \
    --template-body file://template.yaml \
    --region "${REGION}" > /dev/null

echo "Template is valid."
echo ""

echo "Deploying stack '${STACK_NAME}'..."
aws cloudformation deploy \
    --template-file template.yaml \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides file://${PARAMS_FILE} \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --no-fail-on-empty-changeset

echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs" \
    --output table

echo ""
echo "Deployment complete."
echo ""
echo "To test the Lambda manually:"
echo "  aws lambda invoke --function-name ${STACK_NAME}-reporter --region ${REGION} /dev/stdout"
