import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from prometheus_client import Counter, Histogram, Gauge
import logging
from pythonjsonlogger import jsonlogger

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
    # Implementation for sending metrics to TrafficPeak
    # This would be implemented based on TrafficPeak's API specifications
    pass

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
