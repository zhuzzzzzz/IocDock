from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json
import os
import asyncio
from collections import defaultdict
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import make_msgid

# Configuration parameters
DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", 0))
DEBUG_LEVEL = 3
REPORTING_INTERVAL_DAYS = int(os.getenv("REPORTING_INTERVAL_DAYS", 1))

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qiye.aliyun.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "zhujunhua@mail.iasf.ac.cn")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "1728831951@qq.com")
EMAIL_KEY_FILE = os.getenv("SENDER_PASSWORD_FILE")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# SSL configuration
SSL_KEYFILE = os.getenv("SSL_KEYFILE")
SSL_CERTFILE = os.getenv("SSL_CERTFILE")

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# In-memory storage for alerts, categorized by date and alert name
alerts_storage: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

app = FastAPI()


class Alert(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: str
    endsAt: str
    generatorURL: str
    fingerprint: str


class WebhookPayload(BaseModel):
    version: str
    groupKey: str
    truncatedAlerts: int
    status: str
    receiver: str
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Dict[str, str]
    externalURL: str
    alerts: List[Alert]


def categorize_alerts_by_day(alerts: List[Alert]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Categorize alerts by day and alert name

    Returns:
        Dict format: {date: {alert_name: [alerts]}}
    """
    categorized = {}

    for alert in alerts:
        # Extract alert name from labels
        alert_name = alert.labels.get('alertname', 'unknown')

        # Parse the start time to get the date
        try:
            start_time = datetime.fromisoformat(
                alert.startsAt.replace('Z', '+00:00'))
        except ValueError:
            # If parsing fails, use current time
            start_time = datetime.now()

        date_key = start_time.date().isoformat()

        # Initialize the structure if needed
        if date_key not in categorized:
            categorized[date_key] = {}

        if alert_name not in categorized[date_key]:
            categorized[date_key][alert_name] = []

        # Add alert to the appropriate category
        categorized[date_key][alert_name].append(alert.model_dump())

    return categorized


@app.post("/alerts")
async def receive_alerts(payload: WebhookPayload):
    """
    Receive alerts from AlertManager and categorize them by day and alert name

    This endpoint accepts POST requests from AlertManager webhook configuration.
    AlertManager sends alerts in JSON format to this endpoint.

    Expected data format:
    {
      "version": "4",
      "groupKey": "...",
      "truncatedAlerts": 0,
      "status": "firing|resolved",
      "receiver": "...",
      "groupLabels": {"key": "value"},
      "commonLabels": {"key": "value"},
      "commonAnnotations": {"key": "value"},
      "externalURL": "...",
      "alerts": [
        {
          "status": "firing|resolved",
          "labels": {"alertname": "...", "key": "value"},
          "annotations": {"key": "value"},
          "startsAt": "YYYY-MM-DDTHH:MM:SSZ",
          "endsAt": "YYYY-MM-DDTHH:MM:SSZ",
          "generatorURL": "...",
          "fingerprint": "..."
        }
      ]
    }

    To configure AlertManager to send alerts to this service, add a webhook_configs
    receiver in your alertmanager.yml:

    receivers:
    - name: 'alert-analytics'
      webhook_configs:
      - url: 'https://<server-ip>:8000/alerts'
        send_resolved: true

    route:
      receiver: 'alert-analytics'
    """
    # Multi-level debug logging
    if DEBUG_LEVEL >= 3:
        print(f"Received POST request to /alerts")
        print(f"Full payload: {payload.model_dump_json(indent=2)}")
    elif DEBUG_LEVEL >= 2:
        print(f"Received {len(payload.alerts)} alerts:")
        for i, alert in enumerate(payload.alerts):
            print(
                f"  Alert {i+1}: {alert.labels.get('alertname', 'unknown')} - {alert.status}")

    if DEBUG_LEVEL >= 3:
        print(f"Alert details:")
        for i, alert in enumerate(payload.alerts):
            print(f"  Alert {i+1}: {json.dumps(alert.model_dump(), indent=2)}")

    categorized_alerts = categorize_alerts_by_day(payload.alerts)

    # Merge with existing storage
    for date, alert_names in categorized_alerts.items():
        if date not in alerts_storage:
            alerts_storage[date] = {}

        for alert_name, alerts in alert_names.items():
            if alert_name not in alerts_storage[date]:
                alerts_storage[date][alert_name] = []

            # Process each alert to handle duplicates
            for new_alert in alerts:
                # Check if alert with same fingerprint already exists
                existing_alert_index = None
                for i, existing_alert in enumerate(alerts_storage[date][alert_name]):
                    # If fingerprint matches, it's the same alert
                    if existing_alert['fingerprint'] == new_alert['fingerprint']:
                        existing_alert_index = i
                        break

                # If duplicate found, update it; otherwise, add as new
                if existing_alert_index is not None:
                    # Update existing alert (might have new timestamps)
                    alerts_storage[date][alert_name][existing_alert_index] = new_alert
                else:
                    # Add new alert
                    alerts_storage[date][alert_name].append(new_alert)

    if DEBUG_LEVEL >= 1:
        print(f"Successfully processed {len(payload.alerts)} alerts")

    return {"status": "success", "message": f"Processed {len(payload.alerts)} alerts"}


@app.get("/alerts")
async def get_all_alerts():
    """
    Return all received alerts categorized by date and alert name

    Returns alerts in the following structure:
    {
      "date": {
        "alert_name": [alert_objects]
      }
    }

    Example response:
    {
      "2023-05-15": {
        "HighCPULoad": [
          {
            "status": "firing",
            "labels": {"alertname": "HighCPULoad", "severity": "warning"},
            "annotations": {"description": "CPU load is high"},
            "startsAt": "2023-05-15T10:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus/graph...",
            "fingerprint": "abc123..."
          }
        ]
      }
    }
    """
    return alerts_storage


@app.get("/generate-test-data")
async def generate_test_data(days: int = 7):
    """
    Generate test alert data for the past N days for debugging purposes.

    Args:
        days (int): Number of past days to generate test data for (default: 7)

    Returns:
        Dict with status and message

    Example:
        GET /generate-test-data?days=5

        Response:
        {
            "status": "success", 
            "message": "Generated test data for 5 days"
        }

    This will populate the alerts_storage with random alert data for the past 5 days.
    Each day will have 10 randomly generated alerts with various alert names, 
    components, services, and instances.
    """
    global alerts_storage

    # Define possible values for random combinations
    alert_names = ["TestAlertOne", "TestAlertTwo", "TestAlertThree"]
    components = ["ioc", "container", "node"]
    severities = ["info", "warning", "critical"]

    # Define instances and services separately
    instances = ["test-node0", "test-node1", "test-node2"]
    services = ["test_service_1", "test_service_2", "test_service_3"]

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        alerts_storage[date] = {}

        # Generate different number of alerts for each day (0, 1, or 10)
        # Randomly select from 0, 1, 10 alerts per day
        alert_count = random.choice([0, 1, 10])

        # Generate random alerts for this date
        for j in range(alert_count):
            # Randomly select alert attributes
            alert_name = random.choice(alert_names)
            component = random.choice(components)
            severity = random.choice(severities)

            # Initialize alert name group if not exists
            if alert_name not in alerts_storage[date]:
                alerts_storage[date][alert_name] = []

            # Select instance and service independently
            instance = random.choice(instances)
            service = random.choice(services)

            # Create alert with the specified format
            alert = {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "component": component,
                    "instance": instance,
                    "service": service,
                    "severity": severity
                },
                "annotations": {
                    "description": f"{component.upper()} {service} running on {instance} has encountered issues.",
                    "summary": f"Issues detected in {component} logs"
                },
                "startsAt": (datetime.now() - timedelta(days=i, hours=random.randint(0, 23))).isoformat() + "Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "example.com",
                "fingerprint": f"{random.randint(0, 0xffffffff):016x}"
            }
            alerts_storage[date][alert_name].append(alert)

    return {"status": "success", "message": f"Generated test data for {days} days"}


@app.get("/generate-report")
async def manual_generate_report(period_days: int = None, clear_data: bool = False):
    """
    Manually trigger report generation with configurable period and data clearing option.

    Args:
        period_days (int): Number of days to include in report (default: uses REPORTING_INTERVAL_DAYS)
        clear_data (bool): Whether to clear data after generating report (default: False)

    Returns:
        Dict with status and filename of generated report

    Example:
        GET /generate-report?period_days=7&clear_data=true

        Response:
        {
            "status": "success", 
            "report_file": "alert_report_2023-05-01_to_2023-05-07.txt"
        }

    This endpoint generates a statistical report for the specified period (or default period if not specified).
    If clear_data is set to true, it will remove the data used in the report from storage after generating 
    the report. The report file is saved in the current directory with a name indicating the period covered.
    """
    # Use provided period or default to configured interval
    days_to_report = period_days if period_days is not None else REPORTING_INTERVAL_DAYS
    # Generate report with specified parameters
    filename, content = await generate_report_with_period(days_to_report, clear_data=clear_data)

    # Send email with the generated report
    await send_report_email(content)

    return {"status": "success", "report_file": filename}


@app.get("/generate-today-report")
async def manual_generate_today_report():
    """
    Manually trigger today's alert statistics report generation.

    Returns:
        Dict with status and content of today's report

    This endpoint generates a statistical report for today's alerts only.
    It is separate from the historical reporting functionality.
    """
    # Generate today's report
    filename, content = await generate_today_report()

    # Send email with today's report
    await send_report_email(content)

    return {"status": "success", "report_file": filename}


async def generate_today_report():
    """Generate statistical report for today's alerts only"""
    global alerts_storage

    # Get today's date
    today_date = datetime.now().date().isoformat()

    # Get today's alerts if they exist
    today_alerts = alerts_storage.get(today_date, {})

    # Generate report content for today
    report_content = f"Today's Alert Analytics Report ({today_date})\n"
    report_content += "=" * 50 + "\n"

    total_alerts = 0

    if today_alerts:
        report_content += f"\nDate: {today_date}\n"

        # Group by service first
        service_data = defaultdict(lambda: defaultdict(int))
        for alert_name, alerts in today_alerts.items():
            for alert in alerts:
                # Get service from labels, default to 'unknown' if not present
                service = alert.get('labels', {}).get('service', 'unknown')
                service_data[service][alert_name] += 1

        # Then by alert name
        for service in sorted(service_data.keys()):
            report_content += f"  Service: {service}\n"
            service_total = 0

            for alert_name, count in service_data[service].items():
                report_content += f"    {alert_name}: {count}\n"
                service_total += count
                total_alerts += count

            report_content += f"    Service Total: {service_total}\n"

        report_content += f"  Daily Total: {total_alerts} alerts\n"
    else:
        report_content += f"\nDate: {today_date}\n"
        report_content += f"  Daily Total: 0 alerts\n"

    report_content += f"\nOverall Total: {total_alerts} alerts\n"

    # Write report to file
    report_filename = f"alert_report_{today_date}.txt"
    with open(report_filename, "w") as f:
        f.write(report_content)

    print(f"Today's report generated: {report_filename}")

    return report_filename, report_content


async def generate_report_with_period(period_days, clear_data=False):
    """Generate statistical report for specified period and optionally clear data"""
    global alerts_storage

    # Calculate the date range for the report (excluding today)
    end_date = datetime.now().date()  # Today (excluded)
    # Start of reporting period
    start_date = end_date - timedelta(days=period_days)

    # Filter alerts within the reporting period (excluding today)
    # Change report_data structure to be organized by service first
    report_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    dates_to_remove = []

    for date_str, alerts_by_name in alerts_storage.items():
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Include data from start_date up to but not including end_date (today)
        if start_date <= date_obj < end_date:
            # Count alerts by service and name for this date
            for alert_name, alerts in alerts_by_name.items():
                for alert in alerts:
                    # Get service from labels, default to 'unknown' if not present
                    service = alert.get('labels', {}).get('service', 'unknown')
                    report_data[date_str][service][alert_name] += 1
            if clear_data:  # Only mark for removal if clear_data is True
                dates_to_remove.append(date_str)

    # Generate report content
    if period_days == 1:
        # For single day reports, show just that date
        report_date = (end_date - timedelta(days=1)).isoformat()
        report_content = f"Alert Analytics Report ({report_date})\n"
    else:
        # For multi-day reports, show the range
        report_content = f"Alert Analytics Report ({start_date} to {end_date - timedelta(days=1)})\n"
    report_content += "=" * 50 + "\n"

    total_alerts = 0
    # Fix: Iterate through all dates in the range, not just dates with data
    for single_date in (start_date + timedelta(n) for n in range(period_days)):
        date_str = single_date.isoformat()
        if date_str in report_data:
            # Date has data
            report_content += f"\nDate: {date_str}\n"
            daily_total = 0

            # Group by service first
            for service in sorted(report_data[date_str].keys()):
                report_content += f"  Service: {service}\n"
                service_total = 0

                # Then by alert name
                for alert_name, count in report_data[date_str][service].items():
                    report_content += f"    {alert_name}: {count}\n"
                    service_total += count
                    daily_total += count

                report_content += f"    Service Total: {service_total}\n"

            report_content += f"  Daily Total: {daily_total}\n"
            total_alerts += daily_total
        else:
            # Date has no data
            report_content += f"\nDate: {date_str}\n"
            report_content += f"  Daily Total: 0\n"

    report_content += f"\nOverall Total: {total_alerts} alerts\n"

    # Generate filename based on period
    if period_days == 1:
        # For single day reports, use just that date
        report_date = (end_date - timedelta(days=1)).isoformat()
        report_filename = f"alert_report_{report_date}.txt"
    else:
        # For multi-day reports, use from/to format
        report_filename = f"alert_report_from_{start_date}_to_{end_date - timedelta(days=1)}.txt"

    with open(report_filename, "w") as f:
        f.write(report_content)

    print(f"Report generated: {report_filename}")

    # Clear the data for the reported period only if requested
    if clear_data:
        for date_str in dates_to_remove:
            del alerts_storage[date_str]
        print(f"Cleared data for {len(dates_to_remove)} days")

    return report_filename, report_content


async def send_report_email(report_content: str):
    """Send email with report attachment"""
    # Get email configuration from environment variables
    smtp_server = SMTP_SERVER
    smtp_port = SMTP_PORT
    sender_email = SENDER_EMAIL
    recipient_email = RECIPIENT_EMAIL
    key_file = EMAIL_KEY_FILE

    # If no key file specified, try to get password directly
    if key_file and os.path.exists(key_file):
        with open(key_file, 'r') as f:
            password = f.read().strip()
    else:
        password = SENDER_PASSWORD

    # Check each configuration item and report which ones are missing
    missing_configs = []
    if not smtp_server:
        missing_configs.append("SMTP_SERVER")
    if not sender_email:
        missing_configs.append("SENDER_EMAIL")
    if not recipient_email:
        missing_configs.append("RECIPIENT_EMAIL")
    if not password:
        missing_configs.append(
            "SENDER_PASSWORD or EMAIL_KEY_FILE with valid file")
    if missing_configs:
        print(
            f"Email configuration incomplete. Missing items: {', '.join(missing_configs)}")
        return

    try:
        # Create message
        message = MIMEMultipart('alternative')
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = Header("Alert Analytics Report")
        message["Return-Path"] = sender_email
        message['Message-id'] = make_msgid()

        # Add body to email
        message.attach(
            MIMEText(report_content, _subtype="plain", _charset="utf-8"))

        # Create SMTP session
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        # server.starttls()  # Enable security
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, message.as_string())

        server.quit()

        print(f"Report email sent successfully to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

# Add new functionality for scheduled reporting


async def scheduled_report_task():
    """Run the reporting task daily at 9 AM"""
    while True:
        # Calculate seconds until next 9 AM
        now = datetime.now()
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)

        # If it's already past 9 AM today, schedule for tomorrow
        if now > next_run:
            next_run += timedelta(days=1)

        # Calculate delay until next run
        delay = (next_run - now).total_seconds()

        print(f"Next report scheduled in {delay} seconds (at {next_run})")
        await asyncio.sleep(delay)

        try:
            # Generate report
            _, content = await generate_report_with_period(REPORTING_INTERVAL_DAYS, clear_data=True)
            # Send email with report
            await send_report_email(content)
        except Exception as e:
            print(f"Failed to generate or send report: {str(e)}")


def start_scheduled_task():
    """Start the scheduled reporting task"""
    loop = asyncio.get_event_loop()
    loop.create_task(scheduled_report_task())


if __name__ == "__main__":
    # Run the server
    import uvicorn
    # Configure uvicorn log level based on DEBUG_LEVEL
    if DEBUG_LEVEL == 0:
        log_level = "warning"
    elif DEBUG_LEVEL >= 1:
        log_level = "info"
    else:
        log_level = "info"

    # Start the scheduled reporting task
    start_scheduled_task()

    # Check if HTTPS is enabled via environment variables
    ssl_keyfile = SSL_KEYFILE
    ssl_certfile = SSL_CERTFILE

    if ssl_keyfile and ssl_certfile:
        # Run with HTTPS
        uvicorn.run(
            app,
            host=SERVER_HOST,
            port=SERVER_PORT,
            log_level=log_level,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile
        )
    else:
        # Run with HTTP (default)
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level=log_level)
