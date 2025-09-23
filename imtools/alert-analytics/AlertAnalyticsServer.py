from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import json

app = FastAPI()

# In-memory storage for alerts, categorized by alert name and date
alerts_storage: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

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

def initialize_storage():
    """Initialize the alerts storage"""
    global alerts_storage
    alerts_storage = {}

def categorize_alerts_by_day(alerts: List[Alert]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Categorize alerts by alert name and day
    
    Returns:
        Dict format: {alert_name: {date: [alerts]}}
    """
    categorized = {}
    
    for alert in alerts:
        # Extract alert name from labels
        alert_name = alert.labels.get('alertname', 'unknown')
        
        # Parse the start time to get the date
        try:
            start_time = datetime.fromisoformat(alert.startsAt.replace('Z', '+00:00'))
        except ValueError:
            # If parsing fails, use current time
            start_time = datetime.now()
        
        date_key = start_time.date().isoformat()
        
        # Initialize the structure if needed
        if alert_name not in categorized:
            categorized[alert_name] = {}
        
        if date_key not in categorized[alert_name]:
            categorized[alert_name][date_key] = []
        
        # Add alert to the appropriate category
        categorized[alert_name][date_key].append(alert.dict())
    
    return categorized

@app.post("/alerts")
async def receive_alerts(payload: WebhookPayload):
    """
    Receive alerts from AlertManager and categorize them by alert name and day
    """
    categorized_alerts = categorize_alerts_by_day(payload.alerts)
    
    # Merge with existing storage
    for alert_name, dates in categorized_alerts.items():
        if alert_name not in alerts_storage:
            alerts_storage[alert_name] = {}
        
        for date, alerts in dates.items():
            if date not in alerts_storage[alert_name]:
                alerts_storage[alert_name][date] = []
            
            # Process each alert to handle duplicates
            for new_alert in alerts:
                # Check if alert with same fingerprint already exists
                existing_alert_index = None
                for i, existing_alert in enumerate(alerts_storage[alert_name][date]):
                    # If fingerprint matches, it's the same alert
                    if existing_alert['fingerprint'] == new_alert['fingerprint']:
                        existing_alert_index = i
                        break
                
                # If duplicate found, update it; otherwise, add as new
                if existing_alert_index is not None:
                    # Update existing alert (might have new timestamps)
                    alerts_storage[alert_name][date][existing_alert_index] = new_alert
                else:
                    # Add new alert
                    alerts_storage[alert_name][date].append(new_alert)
    
    return {"status": "success", "message": f"Processed {len(payload.alerts)} alerts"}

@app.get("/alerts")
async def get_all_alerts():
    """
    Return all received alerts categorized by alert name and day
    """
    return alerts_storage

# Test functions
def test_receive_alerts():
    """Test function for receiving alerts"""
    # Reset storage
    initialize_storage()
    
    # Sample test payload
    test_payload = WebhookPayload(
        version="4",
        groupKey="{}:{alertname=\"TestAlert\"}",
        truncatedAlerts=0,
        status="firing",
        receiver="test_receiver",
        groupLabels={"alertname": "TestAlert"},
        commonLabels={"alertname": "TestAlert"},
        commonAnnotations={"description": "Test alert"},
        externalURL="http://localhost:9093",
        alerts=[
            Alert(
                status="firing",
                labels={"alertname": "TestAlert", "severity": "critical"},
                annotations={"description": "Test alert"},
                startsAt="2023-01-01T10:00:00Z",
                endsAt="0001-01-01T00:00:00Z",
                generatorURL="http://localhost:9090/graph?g0.expr=UP",
                fingerprint="1234567890abcdef"
            )
        ]
    )
    
    # Process the test payload
    result = categorize_alerts_by_day(test_payload.alerts)
    
    # Verify the result
    assert "TestAlert" in result
    assert "2023-01-01" in result["TestAlert"]
    assert len(result["TestAlert"]["2023-01-01"]) == 1
    
    print("test_receive_alerts passed")

def test_get_all_alerts():
    """Test function for getting all alerts"""
    # Reset storage
    initialize_storage()
    
    # Add some test data
    alerts_storage["TestAlert"] = {
        "2023-01-01": [
            {
                "status": "firing",
                "labels": {"alertname": "TestAlert", "severity": "critical"},
                "annotations": {"description": "Test alert"},
                "startsAt": "2023-01-01T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://localhost:9090/graph?g0.expr=UP",
                "fingerprint": "1234567890abcdef"
            }
        ]
    }
    
    # Get all alerts
    result = alerts_storage
    
    # Verify the result
    assert "TestAlert" in result
    assert "2023-01-01" in result["TestAlert"]
    assert len(result["TestAlert"]["2023-01-01"]) == 1
    
    print("test_get_all_alerts passed")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run tests
        test_receive_alerts()
        test_get_all_alerts()
        print("All tests passed")
    else:
        # Run the server
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)