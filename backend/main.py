from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.analysis import pipeline
from backend.camera import camera
from backend.models import WSMessageType, WSOutgoing

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-20s  %(message)s")
log = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    camera.start()
    log.info("Camera started")
    pipeline.start()
    log.info("Detection pipeline started")
    yield
    pipeline.stop()
    camera.stop()
    log.info("Shutdown complete")


app = FastAPI(title="Morph Vision", lifespan=lifespan)


# -- MJPEG video stream (shows annotated frames with bounding boxes) ------

async def _mjpeg_generator():
    while True:
        frame = camera.get_display_jpeg()
        if frame is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        await asyncio.sleep(0.033)  # ~30 fps


@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# -- WebSocket ------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    pipeline.register(ws)
    log.info("WebSocket client connected")

    if pipeline.last_result is not None:
        init = WSOutgoing(
            type=WSMessageType.DETECTION_RESULT,
            payload=pipeline.last_result.model_dump(mode="json"),
        )
        await ws.send_text(init.model_dump_json())

    await ws.send_text(
        WSOutgoing(
            type=WSMessageType.STATUS,
            payload={"prompt": pipeline.prompt, "connected": True},
        ).model_dump_json()
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == WSMessageType.SET_PROMPT:
                new_prompt = data.get("payload", {}).get("prompt", "")
                pipeline.prompt = new_prompt
                log.info("Prompt updated: %s", new_prompt[:80])
                await ws.send_text(
                    WSOutgoing(
                        type=WSMessageType.STATUS,
                        payload={"prompt": pipeline.prompt},
                    ).model_dump_json()
                )
    except WebSocketDisconnect:
        pass
    finally:
        pipeline.unregister(ws)
        log.info("WebSocket client disconnected")


# -- Static frontend ------------------------------------------------------

@app.get("/")
async def root():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(index.read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
