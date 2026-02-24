# RDS Slow Query Report — Automated Weekly Email

Deploys a serverless pipeline that automatically queries your RDS slow query logs every week, builds a styled HTML report of the **Top N slowest queries**, and emails it via Amazon SES.

## Architecture

```
EventBridge (cron) ──> Lambda (Python 3.12) ──> CloudWatch Logs Insights
                                │                        │
                                │     query results ◄────┘
                                │
                                └──> SES ──> Email Recipients
```

## What Gets Deployed (CloudFormation)

| Resource | Type | Purpose |
|---|---|---|
| IAM Role | `AWS::IAM::Role` | Lambda execution role with CW Logs + SES permissions |
| Lambda Function | `AWS::Lambda::Function` | Runs the Insights query, builds HTML, sends email |
| EventBridge Rule | `AWS::Events::Rule` | Weekly cron trigger (default: Mon 10:00 AM IST) |
| Lambda Permission | `AWS::Lambda::Permission` | Allows EventBridge to invoke the Lambda |
| CloudWatch Log Group | `AWS::Logs::LogGroup` | Stores Lambda execution logs (14-day retention) |

## Prerequisites

1. **AWS CLI** configured with appropriate credentials.
2. **SES verified identities** — the sender email (`SourceEmail`) must be verified in the SES region. If SES is in sandbox mode, recipient emails must also be verified.
3. **RDS slow query log** enabled and publishing to CloudWatch Logs.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `LogGroupName` | `/aws/rds/instance/spyne-prod-rds/slowquery` | CW Logs log group for slow queries |
| `SourceEmail` | *(required)* | Verified SES sender address |
| `DestinationEmails` | *(required)* | Comma-separated recipient list |
| `SESRegion` | `us-east-1` | Region where SES sender is verified |
| `ScheduleExpression` | `cron(30 4 ? * MON *)` | EventBridge cron (04:30 UTC = 10:00 IST) |
| `LookbackDays` | `7` | Days of slow query history to analyze |
| `QueryLimit` | `20` | Max queries in the report |
| `LambdaMemorySize` | `256` | Lambda memory (MB) |
| `LambdaTimeout` | `120` | Lambda timeout (seconds) |

## Quick Start

### 1. Edit parameters

Update `parameters.json` with your actual values:

```json
[
  { "ParameterKey": "SourceEmail",       "ParameterValue": "devops@yourcompany.com" },
  { "ParameterKey": "DestinationEmails", "ParameterValue": "team@yourcompany.com" },
  { "ParameterKey": "LogGroupName",      "ParameterValue": "/aws/rds/instance/YOUR-INSTANCE/slowquery" }
]
```

### 2. Deploy

```bash
# Using the deploy script (recommended)
./deploy.sh <stack-name> <region>
./deploy.sh rds-slow-query-report ap-south-1

# Or using AWS CLI directly
aws cloudformation deploy \
    --template-file template.yaml \
    --stack-name rds-slow-query-report \
    --parameter-overrides file://parameters.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ap-south-1
```

### 3. Test manually

```bash
aws lambda invoke \
    --function-name rds-slow-query-report-reporter \
    --region ap-south-1 \
    /dev/stdout
```

## Tearing Down

```bash
aws cloudformation delete-stack \
    --stack-name rds-slow-query-report \
    --region ap-south-1
```

## File Structure

```
.
├── template.yaml          # CloudFormation template (all resources + inline Lambda code)
├── parameters.json        # Deployment parameters (edit before deploying)
├── deploy.sh              # One-command deploy script
├── lambda/
│   └── slow_query_report.py   # Lambda source (readable reference copy)
└── README.md
```

## IST Schedule Reference

| IST Time | UTC Cron Expression |
|---|---|
| Monday 10:00 AM | `cron(30 4 ? * MON *)` |
| Monday 9:00 AM | `cron(30 3 ? * MON *)` |
| Daily 10:00 AM | `cron(30 4 ? * * *)` |
| Daily 6:00 PM | `cron(30 12 ? * * *)` |
