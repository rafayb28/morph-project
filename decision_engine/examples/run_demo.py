"""Quick demo script — runs the decision engine on sample_input.json.

Usage:
    python decision_engine/examples/run_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from decision_engine.main import format_report, run_pipeline
from decision_engine.models import DecisionInput


def main() -> None:
    sample_path = Path(__file__).resolve().parent / "sample_input.json"
    if not sample_path.exists():
        print(f"Sample input not found at {sample_path}", file=sys.stderr)
        sys.exit(1)

    with open(sample_path) as f:
        raw = json.load(f)

    payload = DecisionInput.model_validate(raw)
    output = run_pipeline(payload)
    print(format_report(output))


if __name__ == "__main__":
    main()
