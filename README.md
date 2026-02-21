# Drone Decision & Alert Engine (Post-CV)

A local, offline-friendly module that takes computer-vision detections and operator instructions and produces **ranked drone action recommendations** and **security alerts** as plain text.

Built as the "decision & action" layer of a drone surveillance system for event planners. The companion CV module (built separately) feeds object detections into this engine.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the demo
python -m decision_engine.main --input decision_engine/examples/sample_input.json
```

## Architecture

```
Operator Instruction ─┐
                      ├─→ Decision Engine ─→ Text Report
CV Object Detections ─┘        │
                               ├── instruction_parser.py  (Step A)
                               ├── risk_scoring.py        (Step B)
                               ├── action_planner.py      (Step C)
                               └── alerting.py            (Step D)
```

### Pipeline Steps

| Step | Module | What it does |
|------|--------|-------------|
| A | `instruction_parser.py` | Parses free-form operator text into structured watchlist rules with urgency weights |
| B | `risk_scoring.py` | Scores each detected object using label weight, confidence, proximity, risk hints, and instruction match |
| C | `action_planner.py` | Generates sequenced drone commands (MOVE, HOVER, ZOOM, TRACK, ORBIT, ASCEND, DESCEND) in feet |
| D | `alerting.py` | Creates severity-tagged alerts with notification routing and next-step guidance |

## Input Format

The engine accepts a single JSON payload with three sections:

### `scene` — Scene Context
| Field | Type | Description |
|-------|------|-------------|
| `scene_id` | string | Unique scene identifier |
| `topdown_media_path` | string | Path to top-down image/video (consumed by CV module) |
| `timestamp` | ISO datetime | When the frame was captured |
| `venue_map_scale_ft_per_px` | float or null | Venue scale for pixel→feet conversion. If null, defaults to 0.5 ft/px |
| `restricted_zones` | list of polygons or null | Restricted area boundaries (for future use) |
| `drone_state` | object | Current drone position, altitude, heading, zoom |

### `objects` — CV Detections
Each object from the CV module:
| Field | Type | Description |
|-------|------|-------------|
| `object_id` | string | Unique ID from CV tracker |
| `label` | string | Classification label (e.g. `"weapon?"`, `"fight"`, `"unattended_bag"`) |
| `confidence` | float 0–1 | CV model confidence |
| `crop_media_path` | string | Path to zoomed-in crop |
| `topdown_bbox` | [x, y, w, h] | Bounding box in top-down pixel coords |
| `topdown_center` | [x, y] | Center point in top-down coords |
| `risk_hints` | dict | Optional CV-provided hints (e.g. `{"unattended": 0.9}`) |

### `instruction` — Operator Input
| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Free-form instruction text |
| `priority_mode` | enum | One of: `safety`, `crowd`, `theft`, `general` |

See `decision_engine/examples/sample_input.json` for a complete example.

## Output

The engine prints a formatted text report with four sections:

1. **Summary** — Top 1–3 risks with severity, label, confidence, and score
2. **Recommended Drone Actions** — Ranked, sequenced commands with parameters in feet and rationale
3. **Alerts** — Severity-tagged notifications with routing (staff / security / authorities) and next steps
4. **Assumptions / Uncertainties** — Scale defaults, low-confidence flags, human confirmation requests

## How to Extend

### Adding new labels/weights
Edit `decision_engine/config.py`:
- `LABEL_BASE_WEIGHTS` — add new labels with a 0–10 risk weight
- `HINT_WEIGHTS` — add new risk hint categories
- `WATCHLIST_KEYWORDS` — add synonyms so the instruction parser recognizes new threats

### Movement conversion
All drone movements are output in **feet**. The conversion uses `venue_map_scale_ft_per_px` from the scene context. If not provided, the engine assumes **0.5 ft/px** and flags this in the assumptions section.

To change the default: edit `DEFAULT_SCALE_FT_PER_PX` in `config.py`.

### Plugging in the CV module
The CV module should produce `ObjectOfInterest` objects matching the schema in `models.py`. The simplest integration:

```python
from decision_engine.models import DecisionInput, ObjectOfInterest, SceneContext
from decision_engine.main import run_pipeline, format_report

payload = DecisionInput(
    scene=your_scene_context,
    objects=your_cv_detections,
    instruction=operator_instruction,
)
output = run_pipeline(payload)
print(format_report(output))
```

## Optional: FastAPI Endpoint

```bash
uvicorn decision_engine.api:app --reload --port 8000
```

Then POST to `/recommend`:
```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d @decision_engine/examples/sample_input.json
```

Add `Accept: text/plain` header for the formatted text report instead of JSON.

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
decision_engine/
├── __init__.py
├── models.py              # Pydantic data contracts (input + output)
├── config.py              # Weights, thresholds, defaults
├── instruction_parser.py  # Step A: parse operator text → watchlist rules
├── risk_scoring.py        # Step B: score objects by risk
├── action_planner.py      # Step C: generate drone action commands
├── alerting.py            # Step D: generate severity alerts
├── main.py                # CLI entry point + text report formatter
├── api.py                 # Optional FastAPI endpoint
└── examples/
    ├── sample_input.json  # Demo payload with 8 objects
    └── run_demo.py        # Standalone demo runner
tests/
├── test_instruction_parser.py
└── test_risk_scoring.py
requirements.txt
README.md
```

## Tech Stack

- Python 3.11+
- Pydantic v2 (validation & serialization)
- FastAPI + Uvicorn (optional REST endpoint)
- No external paid services — fully offline
