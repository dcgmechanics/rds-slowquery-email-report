import boto3
import time
import os
from datetime import datetime, timedelta, timezone


logs_client = boto3.client("logs")
ses_client = boto3.client("ses", region_name=os.environ["SES_REGION"])

LOG_GROUP = os.environ["LOG_GROUP_NAME"]
SOURCE_EMAIL = os.environ["SOURCE_EMAIL"]
DESTINATION_EMAILS = os.environ["DESTINATION_EMAILS"].split(",")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))
QUERY_LIMIT = int(os.environ.get("QUERY_LIMIT", "20"))

INSIGHTS_QUERY = """
    filter @message like "Query_time"
    | parse @message "# User@Host: *[*] @  [*]  Id: *\\n# Query_time: *  Lock_time: * Rows_sent: *  Rows_examined: *\\n*" as user, temp1, client_ip, id, query_time, lock_time, rows_sent, rows_examined, query_block
    | sort query_time desc
    | display query_time, lock_time, rows_examined, rows_sent, user, client_ip, query_block
    | limit {limit}
"""


def run_insights_query(log_group, query, start_time, end_time):
    """Start a CloudWatch Logs Insights query and poll until complete."""
    response = logs_client.start_query(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        queryString=query,
    )
    query_id = response["queryId"]

    max_attempts = 10
    for _ in range(max_attempts):
        time.sleep(2)
        result = logs_client.get_query_results(queryId=query_id)
        if result["status"] not in ("Running", "Scheduled"):
            return result
    raise TimeoutError(f"Insights query {query_id} did not complete within {max_attempts * 2}s")


def build_html_report(results, start_dt, end_dt):
    """Convert Insights query results into a styled HTML email body."""
    period = f"{start_dt.strftime('%b %d, %Y')} &ndash; {end_dt.strftime('%b %d, %Y')}"

    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; padding: 20px; }}
        h2 {{ color: #d63031; }}
        .meta {{ color: #636e72; font-size: 14px; margin-bottom: 16px; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
        th {{ background-color: #2d3436; color: #ffffff; padding: 10px 12px; text-align: left; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #dfe6e9; vertical-align: top; }}
        tr:nth-child(even) {{ background-color: #f5f6fa; }}
        tr:hover {{ background-color: #dfe6e9; }}
        code {{ background: #ffeaa7; padding: 2px 6px; border-radius: 3px; font-size: 12px; word-break: break-all; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #b2bec3; }}
    </style>
    </head>
    <body>
    <h2>Weekly RDS Slow Query Report</h2>
    <p class="meta">
        <strong>Log Group:</strong> {LOG_GROUP}<br>
        <strong>Period:</strong> {period}<br>
        <strong>Top {QUERY_LIMIT} slowest queries</strong>
    </p>
    """

    if not results:
        html += "<p><strong>No slow queries found for this period.</strong></p>"
    else:
        html += """
        <table>
            <tr>
                <th>#</th>
                <th>Query Time (s)</th>
                <th>Lock Time (s)</th>
                <th>Rows Examined</th>
                <th>Rows Sent</th>
                <th>User</th>
                <th>Client IP</th>
                <th>Query</th>
            </tr>
        """
        for idx, row in enumerate(results, 1):
            data = {field["field"]: field["value"] for field in row if not field["field"].startswith("@")}
            html += f"""
            <tr>
                <td>{idx}</td>
                <td>{data.get('query_time', 'N/A')}</td>
                <td>{data.get('lock_time', 'N/A')}</td>
                <td>{data.get('rows_examined', 'N/A')}</td>
                <td>{data.get('rows_sent', 'N/A')}</td>
                <td>{data.get('user', 'N/A')}</td>
                <td>{data.get('client_ip', 'N/A')}</td>
                <td><code>{data.get('query_block', 'N/A')}</code></td>
            </tr>
            """
        html += "</table>"

    html += f"""
    <p class="footer">
        Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC by RDS Slow Query Reporter Lambda.
    </p>
    </body></html>
    """
    return html


def lambda_handler(event, context):
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    end_epoch = int(end_dt.timestamp())
    start_epoch = int(start_dt.timestamp())

    query = INSIGHTS_QUERY.format(limit=QUERY_LIMIT)

    print(f"Running Insights query on {LOG_GROUP} from {start_dt} to {end_dt}")
    result = run_insights_query(LOG_GROUP, query, start_epoch, end_epoch)
    print(f"Query status: {result['status']}, rows returned: {len(result.get('results', []))}")

    html_body = build_html_report(result.get("results", []), start_dt, end_dt)

    subject = f"Weekly RDS Slow Query Report | {start_dt.strftime('%b %d')} - {end_dt.strftime('%b %d, %Y')}"

    ses_client.send_email(
        Source=SOURCE_EMAIL,
        Destination={"ToAddresses": DESTINATION_EMAILS},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
        },
    )
    print(f"Report emailed to {DESTINATION_EMAILS}")

    return {"statusCode": 200, "body": "Report sent successfully!"}
