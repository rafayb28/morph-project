"""Main CLI entry point for the drone decision engine.

Loads a JSON input file, runs the full pipeline (parse → score → plan → alert),
and prints a formatted text report.

Two ways to use:

1) From a pre-built JSON file:
    python -m decision_engine.main --input examples/sample_input.json

2) From a CV output folder + operator instructions:
    python -m decision_engine.main \\
        --cv-dir /path/to/cv_output \\
        --instruction "Watch for weapons and anyone near the stage" \\
        --drone-pos 500 400 \\
        --drone-alt 150
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from textwrap import indent

from decision_engine.action_planner import plan_actions
from decision_engine.alerting import generate_alerts
from decision_engine.instruction_parser import parse_instruction
from decision_engine.models import DecisionInput, DecisionOutput
from decision_engine.risk_scoring import score_all_objects


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(payload: DecisionInput) -> DecisionOutput:
    """Execute the full decision engine pipeline and return structured output."""
    # Step A: Parse operator instruction
    parsed = parse_instruction(payload.instruction.text)

    # Step B: Score all objects
    scored = score_all_objects(payload.objects, payload.scene, parsed)

    # Step C: Generate actions
    actions, assumptions = plan_actions(scored, payload.scene)

    # Step D: Generate alerts
    alerts = generate_alerts(scored)

    # Build summary from top risks
    summary_lines: list[str] = []
    for so in scored[:3]:
        sev = "HIGH" if so.risk_score >= 10 else ("MEDIUM" if so.risk_score >= 5 else "LOW")
        summary_lines.append(
            f"[{sev}] '{so.object.label}' (id={so.object.object_id}, "
            f"confidence={so.object.confidence:.0%}, score={so.risk_score})"
        )

    return DecisionOutput(
        summary=summary_lines,
        actions=actions,
        alerts=alerts,
        assumptions=assumptions,
    )


# ── Text report formatter ────────────────────────────────────────────────────

SEPARATOR = "=" * 72

def format_report(output: DecisionOutput) -> str:
    lines: list[str] = []

    lines.append(SEPARATOR)
    lines.append("  DRONE DECISION ENGINE — SITUATION REPORT")
    lines.append(SEPARATOR)
    lines.append("")

    # Summary
    lines.append(">> SUMMARY")
    lines.append("-" * 40)
    if output.summary:
        for s in output.summary:
            lines.append(f"  {s}")
    else:
        lines.append("  No significant risks detected.")
    lines.append("")

    # Actions
    lines.append(">> RECOMMENDED DRONE ACTIONS")
    lines.append("-" * 40)
    if output.actions:
        for a in output.actions:
            target = f" → {a.target_object_id}" if a.target_object_id else ""
            lines.append(f"  #{a.rank}  [{a.action_type.value}]{target}")
            lines.append(f"        {a.parameters}")
            lines.append(f"        Rationale: {a.rationale}")
            lines.append("")
    else:
        lines.append("  No actions recommended at this time.")
        lines.append("")

    # Alerts
    lines.append(">> ALERTS")
    lines.append("-" * 40)
    if output.alerts:
        for al in output.alerts:
            notify_str = ", ".join(n.value for n in al.notify)
            lines.append(f"  [{al.severity.value}] Object: {al.object_id or 'N/A'}")
            lines.append(f"        Notify: {notify_str}")
            lines.append(f"        Reason: {al.reason}")
            lines.append(f"        Action: {al.next_steps}")
            lines.append("")
    else:
        lines.append("  No alerts.")
        lines.append("")

    # Assumptions
    lines.append(">> ASSUMPTIONS / UNCERTAINTIES")
    lines.append("-" * 40)
    if output.assumptions:
        for asn in output.assumptions:
            lines.append(f"  • {asn.text}")
    else:
        lines.append("  None.")
    lines.append("")
    lines.append(SEPARATOR)

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drone Decision Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # From a JSON file:
  python -m decision_engine.main --input examples/sample_input.json

  # From your friend's CV output folder + your instructions:
  python -m decision_engine.main \\
      --cv-dir ./cv_output \\
      --instruction "Watch for weapons, suspicious people near the stage, and perimeter breaches" \\
      --drone-pos 500 400 \\
      --drone-alt 150 \\
      --priority safety
        """,
    )

    # Option 1: pre-built JSON
    parser.add_argument(
        "--input", "-i",
        help="Path to JSON input file (DecisionInput payload)",
    )

    # Option 2: CV folder + instructions
    parser.add_argument(
        "--cv-dir",
        help="Path to CV module output folder (contains scene image + detections.json + crops/)",
    )
    parser.add_argument(
        "--instruction",
        help="What to watch for — from the operator or event planner (free-form text)",
    )
    parser.add_argument(
        "--priority",
        choices=["safety", "crowd", "theft", "general"],
        default="general",
        help="Priority mode (default: general)",
    )
    parser.add_argument(
        "--drone-pos",
        nargs=2, type=int, metavar=("X", "Y"),
        default=[500, 500],
        help="Drone position in top-down pixel coords (default: 500 500)",
    )
    parser.add_argument(
        "--drone-alt",
        type=float, default=150.0,
        help="Drone altitude in feet (default: 150)",
    )
    parser.add_argument(
        "--drone-heading",
        type=float, default=0.0,
        help="Drone heading in degrees (default: 0)",
    )
    parser.add_argument(
        "--drone-zoom",
        type=float, default=1.0,
        help="Drone camera zoom level (default: 1.0)",
    )
    parser.add_argument(
        "--scale",
        type=float, default=None,
        help="Venue scale in feet per pixel (default: auto 0.5 ft/px)",
    )

    # Output format
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print raw JSON output instead of formatted report",
    )
    args = parser.parse_args()

    # Determine input mode
    if args.input and args.cv_dir:
        print("Error: use --input OR --cv-dir, not both.", file=sys.stderr)
        sys.exit(1)

    if not args.input and not args.cv_dir:
        print("Error: provide --input <file.json> or --cv-dir <folder> --instruction <text>", file=sys.stderr)
        sys.exit(1)

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        with open(input_path) as f:
            raw = json.load(f)
        payload = DecisionInput.model_validate(raw)

    else:
        if not args.instruction:
            print("Error: --instruction is required with --cv-dir", file=sys.stderr)
            sys.exit(1)

        from decision_engine.cv_intake import load_cv_output

        cv_path = Path(args.cv_dir)
        if not cv_path.is_dir():
            print(f"Error: CV directory not found: {cv_path}", file=sys.stderr)
            sys.exit(1)

        payload = load_cv_output(
            cv_dir=cv_path,
            instruction_text=args.instruction,
            priority_mode=args.priority,
            drone_position_px=tuple(args.drone_pos),
            drone_altitude_ft=args.drone_alt,
            drone_heading_deg=args.drone_heading,
            drone_zoom=args.drone_zoom,
            venue_scale_ft_per_px=args.scale,
        )

    output = run_pipeline(payload)

    if args.json_output:
        print(output.model_dump_json(indent=2))
    else:
        print(format_report(output))


if __name__ == "__main__":
    main()
