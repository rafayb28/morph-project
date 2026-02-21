# CV Module Integration Guide

Send this to whoever is building the computer vision module. It explains exactly what the decision engine expects.

## What We Need From You (CV Module)

### Drop a folder with this structure:

```
your_cv_output/
├── scene.jpg              ← the full top-down image from the drone camera
├── detections.json        ← your detections (format below)
└── crops/                 ← zoomed-in screenshot of each suspicious object
    ├── det-001.jpg
    ├── det-002.jpg
    └── ...
```

The scene image can be `.jpg`, `.png`, or `.mp4`. Name it `scene.*` or `topdown.*`.

Crop filenames should match the `crop_filename` field in your JSON, or just name them `{object_id}.jpg`.

### detections.json format

```json
{
  "scene_id": "any-unique-id",
  "timestamp": "2026-02-20T14:00:00",
  "detections": [
    {
      "object_id": "det-001",
      "label": "suspicious_person",
      "confidence": 0.82,
      "crop_filename": "det-001.jpg",
      "bbox": [430, 340, 30, 40],
      "center": [445, 360],
      "track_id": "trk-101",
      "risk_hints": {"concealed_object": 0.7, "loitering": 0.8},
      "notes": "Individual near east barricade, hand in jacket."
    }
  ]
}
```

### Field reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `object_id` | **yes** | string | Unique ID for this detection |
| `label` | **yes** | string | What you think it is (see labels below) |
| `confidence` | **yes** | float 0-1 | How sure your model is |
| `crop_filename` | no | string | Filename of the zoomed-in crop in `crops/` |
| `bbox` | **yes** | [x, y, w, h] | Bounding box in the top-down image (pixels) |
| `center` | no | [x, y] | Center point (we'll compute from bbox if missing) |
| `track_id` | no | string | If you're tracking across frames, the track ID |
| `risk_hints` | no | dict | Extra signals your model picks up (see hints below) |
| `notes` | no | string | Free-form notes about the detection |

### Labels we understand

Use these labels so the scoring engine weights them correctly:

**High threat:**
- `weapon` / `weapon?` — confirmed or suspected weapon
- `stage_rush` — someone charging the stage/podium
- `fire` — fire or smoke
- `vip_threat` — direct threat near a VIP/speaker
- `perimeter_breach` — someone broke through security perimeter
- `rooftop_figure` — person at elevated/overwatch position
- `rushing_individual` — person running in a secured zone

**Medium threat:**
- `fight` / `confrontation` — physical altercation
- `medical_emergency` — injury, collapse, seizure
- `unauthorized_vehicle` / `approaching_vehicle` — vehicle where it shouldn't be
- `unattended_bag` / `suspicious_package` — abandoned item
- `barricade_breach` — crowd pushing through barriers
- `suspicious_person` — someone acting off
- `unauthorized_drone` — unknown drone in airspace
- `crowd_cluster` — dangerous crowd density
- `protest_group` — organized group, possibly aggressive
- `counter_surveillance` — someone surveilling the event setup

**Low threat:**
- `person` — generic person detection
- `bag` — bag with owner present
- `vehicle` — normal vehicle
- `unknown_object` — can't classify it

If your model uses a different label (like `"gun"` instead of `"weapon"`), that's fine — we'll still pick it up through keyword matching. But using the labels above gives the best scoring.

### Risk hints we understand

These are optional float values (0-1) your model can attach to boost scoring:

| Hint | What it means |
|------|---------------|
| `unattended` | Object has no owner nearby |
| `running` | Person is running |
| `aggressive` | Aggressive body language |
| `loitering` | Hanging around too long |
| `in_restricted_zone` | Inside a restricted area |
| `stationary_long` | Object hasn't moved in a while |
| `approaching_stage` | Moving toward the stage/podium |
| `breaching_perimeter` | Actively crossing security boundary |
| `concealed_object` | Hiding something under clothing |
| `erratic_movement` | Unusual movement pattern |
| `climbing` | Climbing a fence/structure |
| `near_vip` | Close to the VIP/speaker |
| `counter_flow` | Moving against the crowd |
| `obscured_face` | Face covered or hidden |
| `coordinated_movement` | Moving in sync with others |

You don't need to provide all of these — just whatever your model can detect.

## How We Run It

Once you drop your folder, we run:

```bash
python -m decision_engine.main \
    --cv-dir /path/to/your_cv_output \
    --instruction "Watch for weapons and anyone rushing the stage" \
    --priority safety \
    --drone-pos 500 400 \
    --drone-alt 150
```

The `--instruction` part is what the operator or event planner types in to tell the system what matters most for this event.

## From Python

```python
from decision_engine.cv_intake import load_cv_output
from decision_engine.main import run_pipeline, format_report

payload = load_cv_output(
    cv_dir="./your_cv_output",
    instruction_text="Watch for weapons and perimeter breaches",
    priority_mode="safety",
    drone_position_px=(500, 400),
    drone_altitude_ft=150.0,
)

output = run_pipeline(payload)
print(format_report(output))
```

## What We Give Back

A text report with:
1. **Summary** — top 3 risks ranked by score
2. **Drone actions** — MOVE (with distance in feet), HOVER, ZOOM, TRACK, ORBIT, ASCEND, DESCEND
3. **Alerts** — severity (LOW/MEDIUM/HIGH/CRITICAL), who to notify, what to do
4. **Assumptions** — anything we're guessing about (like map scale)

## Test With Our Sample

There's a working example in the repo:

```bash
python -m decision_engine.main \
    --cv-dir decision_engine/examples/sample_cv_output \
    --instruction "Watch for weapons and perimeter breaches near the stage" \
    --priority safety \
    --drone-pos 450 200 \
    --drone-alt 140
```

## Questions?

- **What coordinate system?** Pixel coords in the top-down image. (0,0) = top-left.
- **What if my model uses different labels?** Use whatever labels you want — the engine will still work, just with default scoring. Using the labels above gives the best results.
- **Do I need track_id?** No, but it helps if you're tracking objects across frames.
- **What about video?** For now just snapshot frames. Put the frame path as `scene.jpg`.
