"""Optional FastAPI endpoint for the decision engine.

Run with:
    uvicorn decision_engine.api:app --reload --port 8000

POST /recommend with a JSON body matching DecisionInput schema.
Returns either plain text (Accept: text/plain) or JSON.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from decision_engine.main import format_report, run_pipeline
from decision_engine.models import DecisionInput

app = FastAPI(
    title="Drone Decision Engine",
    version="0.1.0",
    description="Accepts CV detections + operator instructions, returns ranked drone actions and alerts.",
)


@app.post("/recommend")
async def recommend(payload: DecisionInput, request: Request):
    output = run_pipeline(payload)

    accept = request.headers.get("accept", "application/json")
    if "text/plain" in accept:
        return PlainTextResponse(format_report(output))

    return JSONResponse(content=output.model_dump(mode="json"))


@app.get("/health")
async def health():
    return {"status": "ok"}
