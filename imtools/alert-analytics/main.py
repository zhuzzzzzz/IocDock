from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta, date
import json
import time
import threading
import atexit
import asyncio

app = FastAPI(title="Alert Analytics Server", 
              description="API for receiving alerts and generating daily reports")

# In-memory storage for alerts and statistics
alerts_storage = defaultdict(list)
daily_stats = defaultdict(Counter)

class AlertLabels(BaseModel):
    alertname: str
    severity: str
    instance: str

class AlertAnnotations(BaseModel):
    summary: str

class Alert(BaseModel):
    labels: Dict[str, str]
    annotations: Dict[str, str]

class AlertPayload(BaseModel):
    alerts: List[Alert]

class AlertEntry(BaseModel):
    timestamp: datetime
    alert: Alert

class CategoryInfo(BaseModel):
    labels: Dict[str, str]
    count: int
    timestamps: List[str]

class ReportData(BaseModel):
    date: str
    total_alerts: int
    categories: List[CategoryInfo]

class AlertAnalyticsServer:
    def __init__(self):
        self.storage = alerts_storage
        self.stats = daily_stats
        self.lock = threading.Lock()
        
    def categorize_alert(self, alert: Alert):
        """
        Categorize alert based on its labels
        """
        labels = alert.labels
        # Create a category key from sorted label items
        category_key = tuple(sorted(labels.items()))
        return category_key
    
    def record_alert(self, alert: Alert):
        """
        Record incoming alert with timestamp
        """
        with self.lock:
            category = self.categorize_alert(alert)
            timestamp = datetime.now()
            alert_entry = {
                'timestamp': timestamp,
                'alert': alert.dict()
            }
            self.storage[category].append(alert_entry)
            
            # Update daily statistics
            day_key = timestamp.date()
            self.stats[day_key][category] += 1
    
    def generate_daily_report(self, target_date: Optional[date] = None):
        """
        Generate daily statistical report
        """
        with self.lock:
            today = datetime.now().date()
            
            # If no target date specified, use yesterday
            if target_date is None:
                target_date = today - timedelta(days=1)
            
            if target_date in self.stats:
                report_data = {
                    'date': target_date.isoformat(),
                    'total_alerts': sum(self.stats[target_date].values()),
                    'categories': []
                }
                
                for category, count in self.stats[target_date].items():
                    # Find timestamps for this category
                    timestamps = []
                    for alert_entry in self.storage[category]:
                        if alert_entry['timestamp'].date() == target_date:
                            timestamps.append(alert_entry['timestamp'].isoformat())
                    
                    category_info = {
                        'labels': dict(category),
                        'count': count,
                        'timestamps': timestamps
                    }
                    report_data['categories'].append(category_info)
                
                # Clear old data (older than 2 days)
                self.cleanup_old_data()
                
                return report_data
            else:
                return {
                    'date': target_date.isoformat(),
                    'total_alerts': 0,
                    'categories': []
                }
    
    def cleanup_old_data(self):
        """
        Remove data older than 2 days to prevent memory overflow
        """
        cutoff_date = datetime.now().date() - timedelta(days=2)
        
        # Clean storage
        categories_to_remove = []
        for category, alerts in self.storage.items():
            # Keep only recent alerts
            recent_alerts = [
                alert for alert in alerts 
                if alert['timestamp'].date() > cutoff_date
            ]
            if recent_alerts:
                self.storage[category] = recent_alerts
            else:
                categories_to_remove.append(category)
        
        for category in categories_to_remove:
            del self.storage[category]
        
        # Clean stats
        dates_to_remove = [
            date_key for date_key in self.stats.keys() 
            if date_key < cutoff_date
        ]
        for date_key in dates_to_remove:
            del self.stats[date_key]

# Initialize the analytics server
analytics_server = AlertAnalyticsServer()

@app.post("/alerts", 
          summary="Receive alerts",
          description="Receive alerts from alertmanager")
async def receive_alerts(payload: AlertPayload):
    try:
        alerts = payload.alerts
        for alert in alerts:
            analytics_server.record_alert(alert)
            
        return {"status": "success", "received": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report", 
         response_model=ReportData,
         summary="Get daily report",
         description="Generate and return the daily report")
async def get_report(target_date: Optional[str] = Query(None, description="Target date in YYYY-MM-DD format")):
    try:
        date_obj = None
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        report = analytics_server.generate_daily_report(date_obj)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate-report", 
         summary="Generate report manually",
         description="Manually trigger report generation (for testing purposes)")
async def generate_report(target_date: Optional[str] = Query(None, description="Target date in YYYY-MM-DD format")):
    try:
        date_obj = None
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        report = analytics_server.generate_daily_report(date_obj)
        # 保存报告到文件以便查看
        report_file = f"/home/zhu/docker/IocDock/imtools/alert-analytics/report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        return {"message": "Report generated", "report": report, "saved_to": report_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/add-sample-alerts", 
         summary="Add sample alerts",
         description="Add sample alerts for testing purposes")
async def add_sample_alerts(from_yesterday: bool = Query(False, description="If true, add alerts with yesterday's timestamp")):
    sample_alerts = [
        {
            "labels": {
                "alertname": "HighCPU",
                "severity": "warning",
                "instance": "server01"
            },
            "annotations": {
                "summary": "High CPU usage detected"
            }
        },
        {
            "labels": {
                "alertname": "DiskFull",
                "severity": "critical",
                "instance": "server02"
            },
            "annotations": {
                "summary": "Disk space is almost full"
            }
        },
        {
            "labels": {
                "alertname": "HighCPU",
                "severity": "warning",
                "instance": "server01"
            },
            "annotations": {
                "summary": "High CPU usage detected"
            }
        }
    ]
    
    # Temporarily modify the analytics server to record alerts with yesterday's date if requested
    original_record_alert = analytics_server.record_alert
    
    if from_yesterday:
        def record_alert_yesterday(alert):
            with analytics_server.lock:
                category = analytics_server.categorize_alert(alert)
                # Set timestamp to yesterday
                timestamp = datetime.now() - timedelta(days=1)
                alert_entry = {
                    'timestamp': timestamp,
                    'alert': alert.dict()
                }
                analytics_server.storage[category].append(alert_entry)
                
                # Update daily statistics
                day_key = timestamp.date()
                analytics_server.stats[day_key][category] += 1
        
        analytics_server.record_alert = record_alert_yesterday
    
    try:
        for alert_data in sample_alerts:
            alert = Alert(**alert_data)
            analytics_server.record_alert(alert)
    finally:
        # Restore original method
        analytics_server.record_alert = original_record_alert
    
    return {"message": "Sample alerts added", "count": len(sample_alerts)}

# Background task for daily report generation
async def daily_report_scheduler():
    """
    Scheduler to generate daily reports
    """
    while True:
        now = datetime.now()
        # Calculate time until next midnight
        tomorrow = now + timedelta(days=1)
        next_midnight = datetime(
            year=tomorrow.year,
            month=tomorrow.month,
            day=tomorrow.day,
            hour=0,
            minute=0,
            second=0
        )
        
        # Wait until next midnight
        time_to_wait = (next_midnight - now).total_seconds()
        await asyncio.sleep(time_to_wait)
        
        # Generate report
        report = analytics_server.generate_daily_report()
        
        # Here you could save the report to a file or send it via email
        # For now, we'll just print it
        print(f"Daily Report Generated: {json.dumps(report, indent=2)}")

# Start the daily report scheduler
@app.on_event("startup")
async def startup_event():
    # Start the daily report scheduler in a separate thread
    loop = asyncio.get_event_loop()
    loop.create_task(daily_report_scheduler())

# Register exit handler to generate final report
@app.on_event("shutdown")
async def shutdown_event():
    print("Server shutting down. Final report:", 
          json.dumps(analytics_server.generate_daily_report(), indent=2))