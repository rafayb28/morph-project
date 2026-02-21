# Morph - Real-Time Camera Vision Analysis

Morph connects to your webcam and runs YOLOv8 object detection locally — no cloud API, no credits. It draws live bounding boxes on the video feed, counts objects, and lets you set watch keywords to get alerts when specific things appear in frame.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A webcam (built-in or USB)

### 2. Install dependencies

```bash
cd morph-project
pip install -r requirements.txt
```

The first run will automatically download the YOLOv8 model weights (~6 MB for `yolov8n.pt`).

### 3. Configure (optional)

Copy the example env file if you want to change defaults:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `CAMERA_INDEX` | Webcam device index (0 = default camera) | `0` |
| `YOLO_MODEL` | YOLO model variant (see below) | `yolov8n.pt` |
| `CONFIDENCE_THRESHOLD` | Minimum detection confidence (0-1) | `0.45` |
| `DETECTION_INTERVAL` | Seconds between detection runs | `0.1` |

**Available YOLO models** (speed vs accuracy trade-off):

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `yolov8n.pt` | 6 MB | Fastest | Good |
| `yolov8s.pt` | 22 MB | Fast | Better |
| `yolov8m.pt` | 50 MB | Medium | Great |
| `yolov8l.pt` | 84 MB | Slower | Excellent |

### 4. Run

```bash
uvicorn backend.main:app --reload
```

Open **http://localhost:8000** in your browser.

## How It Works

1. **Camera capture** — OpenCV grabs frames from your webcam in a background thread.
2. **YOLO detection** — Every ~100ms a frame is fed through YOLOv8 locally on your machine. Detected objects get bounding boxes drawn directly on the frame.
3. **Annotated video stream** — The `/video_feed` endpoint serves an MJPEG stream with bounding boxes and labels already drawn, at ~30 fps.
4. **Watch keywords** — Type keywords (e.g. `person, dog, car`) in the dashboard. When YOLO detects a matching class, the bounding box turns red and an alert appears in the sidebar.
5. **WebSocket push** — Detection counts and alerts are pushed to the browser in real time via WebSocket.

## YOLO Class Names

YOLOv8 detects 80 object classes from the COCO dataset. Some useful ones for the watch list:

`person`, `bicycle`, `car`, `motorcycle`, `bus`, `truck`, `dog`, `cat`, `bird`, `horse`, `backpack`, `umbrella`, `handbag`, `suitcase`, `bottle`, `cup`, `fork`, `knife`, `spoon`, `bowl`, `banana`, `apple`, `sandwich`, `laptop`, `mouse`, `keyboard`, `cell phone`, `book`, `clock`, `scissors`, `teddy bear`, `chair`, `couch`, `bed`, `dining table`, `tv`

Full list: [COCO classes](https://docs.ultralytics.com/datasets/detect/coco/)

## Project Structure

```
morph-project/
├── backend/
│   ├── main.py          # FastAPI app — routes, MJPEG stream, WebSocket
│   ├── camera.py        # Threaded OpenCV webcam capture
│   ├── detector.py      # YOLOv8 detection + bounding box drawing
│   ├── analysis.py      # Background detection pipeline
│   ├── models.py        # Pydantic data models
│   └── config.py        # Settings loaded from .env
├── frontend/
│   ├── index.html       # Dashboard page
│   ├── styles.css       # Dark-theme styling
│   └── app.js           # WebSocket client and UI rendering
├── requirements.txt
├── .env.example
└── README.md
```
