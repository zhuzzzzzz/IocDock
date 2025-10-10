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
REPORTING_INTERVAL_DAYS = int(os.getenv("REPORTING_INTERVAL_DAYS", 1))
REPORT_EXPIRY_DAYS = int(os.getenv("REPORT_EXPIRY_DAYS", 30))  # Reports expire after 30 days
ALERTS_EXPIRY_DAYS = int(os.getenv("ALERTS_EXPIRY_DAYS", 30))  # Alerts expire after 30 days

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
# Split recipient emails by comma, remove whitespace, and filter out empty strings
RECIPIENT_EMAILS = [email.strip() for email in RECIPIENT_EMAIL.split(",") if email.strip()] if RECIPIENT_EMAIL else []
SENDER_PASSWORD_FILE = os.getenv("SENDER_PASSWORD_FILE")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# SSL configuration
SSL_KEYFILE = os.getenv("SSL_KEYFILE")
SSL_CERTFILE = os.getenv("SSL_CERTFILE")

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# Reports directory configuration
REPORTS_DIR = "reports"

# Create reports directory if it doesn't exist
os.makedirs(REPORTS_DIR, exist_ok=True)

# In-memory storage for alerts, categorized by date, alert name, and service or instance
alerts_storage: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]] = {}

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


def categorize_alerts_by_day(alerts: List[Alert]) -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
    """
    Categorize alerts by day, alert name, and either service or instance

    Returns:
        Dict format: {date: {alert_name: {service_or_instance: [alerts]}}}
    """
    categorized = {}

    for alert in alerts:
        # Extract alert name from labels
        alert_name = alert.labels.get('alertname', 'unknown')
        
        # Determine service_or_instance key based on available labels
        service = alert.labels.get('service')
        instance = alert.labels.get('instance')
        
        # Use service if available, otherwise instance, otherwise 'unknown'
        if service:
            service_or_instance = service
        elif instance:
            service_or_instance = instance
        else:
            service_or_instance = 'unknown'

        date_key = datetime.now().date().isoformat()

        # Initialize the structure if needed
        if date_key not in categorized:
            categorized[date_key] = {}

        if alert_name not in categorized[date_key]:
            categorized[date_key][alert_name] = {}

        if service_or_instance not in categorized[date_key][alert_name]:
            categorized[date_key][alert_name][service_or_instance] = []

        # Add alert to the appropriate category
        categorized[date_key][alert_name][service_or_instance].append(alert.model_dump())

    return categorized


@app.post("/alerts")
async def receive_alerts(payload: WebhookPayload):
    """
    Receive alerts from AlertManager and categorize them by day, alert name, and service or instance

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
          "labels": {"alertname": "...", "service": "...", "instance": "...", "key": "value"},
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

    # Merge with existing storage - simply append all alerts, no deduplication
    for date, alert_names in categorized_alerts.items():
        if date not in alerts_storage:
            alerts_storage[date] = {}

        for alert_name, service_or_instances in alert_names.items():
            if alert_name not in alerts_storage[date]:
                alerts_storage[date][alert_name] = {}

            for service_or_instance, alerts in service_or_instances.items():
                if service_or_instance not in alerts_storage[date][alert_name]:
                    alerts_storage[date][alert_name][service_or_instance] = []

                # Add all alerts without checking for duplicates
                # This allows us to count occurrences of the same alert
                for new_alert in alerts:
                    alerts_storage[date][alert_name][service_or_instance].append(new_alert)

    if DEBUG_LEVEL >= 1:
        print(f"Successfully processed {len(payload.alerts)} alerts")

    return {"status": "success", "message": f"Processed {len(payload.alerts)} alerts"}


@app.get("/alerts")
async def get_all_alerts():
    """
    Return all received alerts categorized by date, alert name, and service or instance

    Returns alerts in the following structure:
    {
      "date": {
        "alert_name": {
          "service_or_instance": [alert_objects]
        }
      }
    }

    Example response:
    {
      "2023-05-15": {
        "HighCPULoad": {
          "service1": [
            {
              "status": "firing",
              "labels": {"alertname": "HighCPULoad", "service": "service1", "severity": "warning"},
              "annotations": {"description": "CPU load is high"},
              "startsAt": "2023-05-15T10:00:00Z",
              "endsAt": "0001-01-01T00:00:00Z",
              "generatorURL": "http://prometheus/graph...",
              "fingerprint": "abc123..."
            }
          ]
        }
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
    alert_names = ["AlertOne", "AlertTwo", "AlertThree"]
    components = ["ioc", "container", "node"]
    severities = ["info", "warning", "critical"]

    # Define instances and services separately
    instances = ["node0", "node1", "node2"]
    services = ["service1", "service2", "service3"]

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        alerts_storage[date] = {}

        # Generate different number of alerts for each day (0, 1, or 10)
        # Randomly select from 0, 1, 10 alerts per day
        alert_count = random.choice([10])

        # Generate random alerts for this date
        for j in range(alert_count):
            # Randomly select alert attributes
            alert_name = random.choice(alert_names)
            component = random.choice(components)
            severity = random.choice(severities)

            # Select instance and service independently
            instance = random.choice(instances)
            service = random.choice(services)
            
            # Randomly decide whether to use service, instance, or both
            use_service = random.choice([True, False])
            use_instance = random.choice([True, False])

            # Initialize alert name group if not exists
            if alert_name not in alerts_storage[date]:
                alerts_storage[date][alert_name] = {}

            # Determine the service_or_instance key
            if use_service:
                service_or_instance = service
            elif use_instance:
                service_or_instance = instance
            else:
                service_or_instance = 'unknown'
                
            # Initialize service_or_instance group if not exists
            if service_or_instance not in alerts_storage[date][alert_name]:
                alerts_storage[date][alert_name][service_or_instance] = []

            # Create alert with the specified format
            labels = {
                "alertname": alert_name,
                "component": component,
                "severity": severity
            }
            
            # Add service and/or instance labels based on what we're using
            if use_service:
                labels["service"] = service
            if use_instance:
                labels["instance"] = instance

            alert = {
                "status": "firing",
                "labels": labels,
                "annotations": {
                    "description": f"{component.upper()} {service} running on {instance} has encountered issues.",
                    "summary": f"Issues detected in {component} logs"
                },
                "startsAt": (datetime.now() - timedelta(days=i, hours=random.randint(0, 23))).isoformat() + "Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "example.com",
                "fingerprint": f"{random.randint(0, 0xffffffff):016x}"
            }
            alerts_storage[date][alert_name][service_or_instance].append(alert)

    return {"status": "success", "message": f"Generated test data for {days} days"}


@app.get("/generate-report")
async def manual_generate_report(period_days: int = None):
    """
    Manually trigger report generation with configurable period.

    Args:
        period_days (int): Number of days to include in report (default: uses REPORTING_INTERVAL_DAYS)

    Returns:
        Dict with status and filepath of generated report

    Example:
        GET /generate-report?period_days=7

        Response:
        {
            "status": "success", 
            "report_file": "/path/to/alert_report_2023-05-01_to_2023-05-07.txt"
        }

    This endpoint generates a statistical report for the specified period (or default period if not specified).
    The report file is saved in the reports directory with a name indicating the period covered.
    """
    # Use provided period or default to configured interval
    days_to_report = period_days if period_days is not None else REPORTING_INTERVAL_DAYS
    # Generate report with specified parameters
    filepath, content = await generate_report_with_period(days_to_report)

    # Send email with the generated report
    await send_report_email(content)

    return {"status": "success", "report_file": filepath}


@app.get("/generate-today-report")
async def manual_generate_today_report():
    """
    Manually trigger today's alert statistics report generation.

    Returns:
        Dict with status and filepath of today's report

    This endpoint generates a statistical report for today's alerts only.
    It is separate from the historical reporting functionality.
    """
    # Generate today's report
    filepath, content = await generate_today_report()

    # Send email with today's report
    await send_report_email(content)

    return {"status": "success", "report_file": filepath}


async def generate_today_report():
    """Generate statistical report for today's alerts only"""
    global alerts_storage

    # Get today's date
    today_date = datetime.now().date().isoformat()

    # Get today's alerts if they exist
    today_alerts = alerts_storage.get(today_date, {})
    
    # Data structure for service/instance statistics
    service_instance_stats = defaultdict(int)

    # Generate report content for today
    report_content = f"Today's Alert Analytics Report ({today_date})\n"
    report_content += "=" * 50 + "\n"

    total_alerts = 0

    if today_alerts:
        report_content += f"\nDate: {today_date}\n"
        # Process alerts organized by alert name and service_or_instance
        for alert_name, service_or_instances in today_alerts.items():
            report_content += f"    Alert: {alert_name}\n"
            alert_total = 0            
            for service_or_instance, alerts in service_or_instances.items():
                count = len(alerts)
                report_content += f"        {service_or_instance}: {count}\n"
                alert_total += count
                total_alerts += count
                # Track service/instance totals
                service_instance_stats[service_or_instance] += count                
            report_content += f"        Alert Total: {alert_total}\n"
        report_content += f"    Daily Total: {total_alerts} alerts\n"
    else:
        report_content += f"\nDate: {today_date}\n"
        report_content += f"    Daily Total: 0 alerts\n"

    # Add service/instance statistics
    if service_instance_stats:
        report_content += f"\nService/Instance Statistics:\n"
        # Sort by count (descending)
        sorted_stats = sorted(service_instance_stats.items(), key=lambda x: x[1], reverse=True)
        for service_or_instance, count in sorted_stats:
            percentage = (count / total_alerts * 100) if total_alerts > 0 else 0
            report_content += f"    {service_or_instance}: {count} ({percentage:.1f}%)\n"

    report_content += f"\nOverall Total: {total_alerts} alerts\n"

    # Write report to file in reports directory
    report_filename = f"alert_report_{today_date}.txt"
    report_filepath = os.path.join(REPORTS_DIR, report_filename)
    with open(report_filepath, "w") as f:
        f.write(report_content)

    print(f"Today's report generated: {report_filepath}")

    return report_filepath, report_content


async def generate_report_with_period(period_days):
    """Generate statistical report for specified period"""
    global alerts_storage

    # Calculate the date range for the report (excluding today)
    end_date = datetime.now().date()  # Today (excluded)
    # Start of reporting period
    start_date = end_date - timedelta(days=period_days)

    # Filter alerts within the reporting period (excluding today)
    # Organize report data by date, alert name, and service or instance
    report_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    # Additional data structure for service/instance statistics
    service_instance_stats = defaultdict(int)

    for date_str, alerts_by_name in alerts_storage.items():
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Include data from start_date up to but not including end_date (today)
        if start_date <= date_obj < end_date:
            # Count alerts by alert name and service_or_instance for this date
            for alert_name, service_or_instances in alerts_by_name.items():
                for service_or_instance, alerts in service_or_instances.items():
                    count = len(alerts)
                    report_data[date_str][alert_name][service_or_instance] = count
                    # Also track service/instance totals
                    service_instance_stats[service_or_instance] += count

    # Generate report content
    if period_days == 1:
        # For single day reports, show just that date
        report_date = (end_date - timedelta(days=1)).isoformat()
        report_content = f"Alert Analytics Report ({report_date})\n"
        report_filename = f"alert_report_{report_date}.txt"
    else:
        # For multi-day reports, show the range
        report_content = f"Alert Analytics Report ({start_date} to {end_date - timedelta(days=1)})\n"
        report_filename = f"alert_report_from_{start_date}_to_{end_date - timedelta(days=1)}.txt"
    report_content += "=" * 50 + "\n"

    total_alerts = 0

    for single_date in (start_date + timedelta(n) for n in range(period_days)):
        date_str = single_date.isoformat()
        if date_str in report_data:
            # Date has data
            report_content += f"\nDate: {date_str}\n"
            daily_total = 0
            # Group by alert name first
            for alert_name in sorted(report_data[date_str].keys()):
                report_content += f"    Alert: {alert_name}\n"
                alert_total = 0                
                # Then by service_or_instance
                for service_or_instance, count in report_data[date_str][alert_name].items():
                    report_content += f"        {service_or_instance}: {count}\n"
                    alert_total += count
                    daily_total += count                    
                report_content += f"        Alert Total: {alert_total}\n"
            report_content += f"    Daily Total: {daily_total}\n"
            total_alerts += daily_total
        else:
            # Date has no data
            report_content += f"\nDate: {date_str}\n"
            report_content += f"    Daily Total: 0\n"

    # Add service/instance statistics
    if service_instance_stats:
        report_content += f"\nService/Instance Statistics:\n"
        # Sort by count (descending)
        sorted_stats = sorted(service_instance_stats.items(), key=lambda x: x[1], reverse=True)
        for service_or_instance, count in sorted_stats:
            percentage = (count / total_alerts * 100) if total_alerts > 0 else 0
            report_content += f"    {service_or_instance}: {count} ({percentage:.1f}%)\n"

    report_content += f"\nOverall Total: {total_alerts} alerts\n"

    # Write report to file in reports directory
    report_filepath = os.path.join(REPORTS_DIR, report_filename)
    with open(report_filepath, "w") as f:
        f.write(report_content)

    print(f"Report generated: {report_filepath}")

    return report_filepath, report_content


async def send_report_email(report_content: str):
    """Send email with report attachment"""
    # Get email configuration from environment variables
    smtp_server = SMTP_SERVER
    smtp_port = SMTP_PORT
    sender_email = SENDER_EMAIL
    recipient_emails = RECIPIENT_EMAILS
    key_file = SENDER_PASSWORD_FILE

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
    if not recipient_emails:
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
        message["To"] = ", ".join(recipient_emails)
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
        
        # Send email to all recipients
        for recipient_email in recipient_emails:
            server.sendmail(sender_email, recipient_email, message.as_string())
            print(f"Report email sent successfully to {recipient_email}")

        server.quit()

    except Exception as e:
        print(f"Failed to send email: {str(e)}")


async def cleanup_expired_reports():
    """Clean up expired report files"""
    if not os.path.exists(REPORTS_DIR):
        print(f"Reports directory {REPORTS_DIR} does not exist")
        return

    # Calculate the cutoff date for expiration
    cutoff_date = datetime.now() - timedelta(days=REPORT_EXPIRY_DAYS)
    
    deleted_files = []
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.txt') and filename.startswith('alert_report'):
            file_path = os.path.join(REPORTS_DIR, filename)
            
            # Get file modification time
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # If file is older than cutoff date, delete it
            if mod_time < cutoff_date:
                try:
                    os.remove(file_path)
                    deleted_files.append(filename)
                except Exception as e:
                    print(f"Failed to delete report {file_path}: {str(e)}")
    
    if deleted_files:
        print(f"Cleaned up {len(deleted_files)} expired reports:")
        for filename in deleted_files:
            print(f"  - {filename}")


async def cleanup_expired_alerts():
    """Clean up expired alert data from memory storage"""
    global alerts_storage
    
    # Calculate the cutoff date for expiration using ALERTS_EXPIRY_DAYS
    cutoff_date = datetime.now().date() - timedelta(days=ALERTS_EXPIRY_DAYS)
    
    dates_to_remove = []
    
    # Find expired dates
    for date_str in alerts_storage.keys():
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            # If alert date is older than cutoff date, mark for deletion
            if date_obj < cutoff_date:
                dates_to_remove.append(date_str)
        except ValueError:
            # If date parsing fails, skip this entry
            print(f"Skipping invalid date format: {date_str}")
            continue
    
    # Remove expired data
    for date_str in dates_to_remove:
        del alerts_storage[date_str]
    
    if dates_to_remove:
        print(f"Cleaned up {len(dates_to_remove)} days of expired alert data from memory:")
        for date_str in sorted(dates_to_remove):
            print(f"  - {date_str}")


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
            _, content = await generate_report_with_period(REPORTING_INTERVAL_DAYS)
            # Send email with report
            await send_report_email(content)
        except Exception as e:
            print(f"Failed to generate or send report: {str(e)}")


async def scheduled_cleanup_task():
    """Run the cleanup task daily at 10 AM"""
    while True:
        # Calculate seconds until next 10 AM
        now = datetime.now()
        next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)

        # If it's already past 10 AM today, schedule for tomorrow
        if now > next_run:
            next_run += timedelta(days=1)

        # Calculate delay until next run
        delay = (next_run - now).total_seconds()

        print(f"Next cleanup scheduled in {delay} seconds (at {next_run})")
        await asyncio.sleep(delay)

        try:
            # Clean up expired reports
            await cleanup_expired_reports()
            # Clean up expired alert data from memory
            await cleanup_expired_alerts()
        except Exception as e:
            print(f"Failed to clean up expired reports: {str(e)}")


def start_scheduled_tasks():
    """Start the scheduled reporting and cleanup tasks"""
    loop = asyncio.get_event_loop()
    loop.create_task(scheduled_report_task())
    loop.create_task(scheduled_cleanup_task())


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

    # Start the scheduled reporting and cleanup tasks
    start_scheduled_tasks()

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
