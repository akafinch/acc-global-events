import os
import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace
from prometheus_client import Counter, Histogram
import logging
from pythonjsonlogger import jsonlogger

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

app = FastAPI(title="Event Generator Service")

# Metrics
events_generated = Counter('events_generated_total', 'Total events generated', ['region', 'type'])
generation_time = Histogram('event_generation_seconds', 'Time spent generating events')

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

async def send_event_to_zuplo(event: Event):
    zuplo_url = os.getenv("ZUPLO_API_URL")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{zuplo_url}/events", json=event.dict()) as response:
                if response.status != 200:
                    logger.error(f"Failed to send event to Zuplo: {await response.text()}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Error sending event to Zuplo: {str(e)}")
            return False

@app.post("/generate")
async def generate_event(event_type: str):
    try:
        with generation_time.time():
            event = Event(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat(),
                type=event_type,
                source={
                    "region": os.getenv("REGION", "unknown"),
                    "instance": os.getenv("HOSTNAME", "unknown")
                },
                payload=EventPayload(
                    type=event_type,
                    properties={
                        "timestamp": datetime.utcnow().isoformat(),
                        "value": 100  # Example value
                    }
                ),
                metadata={
                    "version": "1.0",
                    "priority": 1,
                    "tags": ["test"]
                }
            )
            
            success = await send_event_to_zuplo(event)
            if success:
                events_generated.labels(
                    region=event.source["region"],
                    type=event_type
                ).inc()
                return {"status": "success", "event_id": event.id}
            else:
                raise HTTPException(status_code=500, detail="Failed to send event to Zuplo")
    except Exception as e:
        logger.error(f"Error generating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
