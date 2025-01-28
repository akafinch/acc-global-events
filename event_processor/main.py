import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
import redis
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from prometheus_client import Counter, Histogram, Gauge
import logging
from pythonjsonlogger import jsonlogger
from base64 import b64encode

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

app = FastAPI(title="Event Processor Service")

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# Metrics
events_processed = Counter('events_processed_total', 'Total events processed', ['region', 'type'])
processing_time = Histogram('event_processing_seconds', 'Time spent processing events')
queue_depth = Gauge('event_queue_depth', 'Current event queue depth')

# TrafficPeak Configuration
TRAFFICPEAK_URL = os.getenv("TRAFFICPEAK_URL", "https://api.trafficpeak.com/v1/metrics")
TRAFFICPEAK_TOKEN = os.getenv("TRAFFICPEAK_TOKEN")
TRAFFICPEAK_TABLE = os.getenv("TRAFFICPEAK_TABLE", "event_metrics")
TRAFFICPEAK_USERNAME = os.getenv("TRAFFICPEAK_USERNAME")
TRAFFICPEAK_PASSWORD = os.getenv("TRAFFICPEAK_PASSWORD")

class EventPayload(BaseModel):
    type: str
    properties: Dict[str, Any]

class Event(BaseModel):
    id: str
    timestamp: str
    type: str
    source: Dict[str, str]
    payload: EventPayload
    metadata: Dict[str, Any]

class Metrics(BaseModel):
    timestamp: str
    region: str
    metrics: Dict[str, float]
    tags: Dict[str, str]

async def send_metrics_to_trafficpeak(metrics: Metrics):
    if not all([TRAFFICPEAK_USERNAME, TRAFFICPEAK_PASSWORD, TRAFFICPEAK_TOKEN]):
        logger.error("TrafficPeak credentials not configured")
        return False

    try:
        # Create basic auth header
        auth_string = f"{TRAFFICPEAK_USERNAME}:{TRAFFICPEAK_PASSWORD}"
        auth_bytes = auth_string.encode('ascii')
        base64_auth = b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {base64_auth}",
            "Content-Type": "application/json",
            "X-API-Token": TRAFFICPEAK_TOKEN
        }

        payload = {
            "table_name": TRAFFICPEAK_TABLE,
            "timestamp": metrics.timestamp,
            "region": metrics.region,
            "metrics": metrics.metrics,
            "tags": metrics.tags
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TRAFFICPEAK_URL,
                json=payload,
                headers=headers,
                timeout=10  # 10 seconds timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to send metrics to TrafficPeak: {error_text}")
                    return False
                    
                logger.info(f"Successfully sent metrics to TrafficPeak for region {metrics.region}")
                return True

    except asyncio.TimeoutError:
        logger.error("Timeout while sending metrics to TrafficPeak")
        return False
    except Exception as e:
        logger.error(f"Error sending metrics to TrafficPeak: {str(e)}")
        return False

@app.post("/process")
async def process_event(event: Event):
    try:
        with processing_time.time():
            # Store event in Redis for potential replay
            redis_client.setex(
                f"event:{event.id}",
                3600,  # 1 hour TTL
                json.dumps(event.dict())
            )

            # Process the event (example processing)
            processed_data = {
                "event_id": event.id,
                "processed_timestamp": datetime.utcnow().isoformat(),
                "processing_result": "success"
            }

            # Generate metrics
            metrics = Metrics(
                timestamp=datetime.utcnow().isoformat(),
                region=event.source["region"],
                metrics={
                    "processing_time": processing_time._sum.get(),
                    "queue_depth": queue_depth._value.get(),
                    "error_rate": 0.0  # Example metric
                },
                tags={
                    "environment": os.getenv("ENVIRONMENT", "production"),
                    "service": "event_processor",
                    "version": "1.0"
                }
            )

            # Send metrics to TrafficPeak
            await send_metrics_to_trafficpeak(metrics)

            # Update metrics
            events_processed.labels(
                region=event.source["region"],
                type=event.type
            ).inc()

            return processed_data
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        # Check Redis connection
        redis_client.ping()
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service unhealthy")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
