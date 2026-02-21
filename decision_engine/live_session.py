"""Live operator session for the drone decision engine.

Simulates a running surveillance feed where:
- CV detections update each cycle (from a folder that gets refreshed, or from JSON)
- The operator can type new instructions mid-session that stack on previous ones
- Each cycle re-runs the full pipeline with the combined instruction set

Usage:
    python -m decision_engine.live_session --cv-dir ./cv_output --drone-pos 500 400

    # Or with a JSON file as the base detections:
    python -m decision_engine.live_session --input examples/political_rally.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from decision_engine.instruction_parser import (
    ParsedInstruction,
    merge_instructions,
    parse_instruction,
)
from decision_engine.main import format_report, run_pipeline
from decision_engine.models import DecisionInput, OperatorInstruction, PriorityMode


BANNER = """
╔══════════════════════════════════════════════════════════════════════╗
║              DRONE DECISION ENGINE — LIVE SESSION                  ║
║                                                                    ║
║  Type new instructions anytime. They stack on top of previous      ║
║  ones and take effect on the next cycle.                           ║
║                                                                    ║
║  Commands:                                                         ║
║    <any text>          → add instruction (e.g. "also watch for     ║
║                          alcohol" or "ignore the protest group")    ║
║    /status             → show current active instructions          ║
║    /clear              → reset instructions to just the original   ║
║    /run                → force an immediate re-evaluation          ║
║    /interval <secs>    → change auto-cycle interval (0 = manual)   ║
║    /quit               → exit live session                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""


class LiveSession:
    """Manages a live operator session with stacking instructions."""

    def __init__(
        self,
        base_payload: DecisionInput,
        cycle_interval: float = 0.0,
    ):
        self.base_payload = base_payload
        self.cycle_interval = cycle_interval

        self.base_instruction_text = base_payload.instruction.text
        self.instruction_history: list[tuple[str, str]] = [
            (datetime.now().strftime("%H:%M:%S"), self.base_instruction_text),
        ]

        self._parsed_base = parse_instruction(self.base_instruction_text)
        self._parsed_combined = self._parsed_base
        self._combined_text = self.base_instruction_text

        self._running = False
        self._cycle_count = 0

    def add_instruction(self, text: str) -> None:
        """Layer a new operator instruction on top of existing ones."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.instruction_history.append((timestamp, text))
        new_parsed = parse_instruction(text)
        self._parsed_combined = merge_instructions(self._parsed_combined, new_parsed)
        self._combined_text = self._parsed_combined.raw_text

        new_cats = {r.category for r in new_parsed.rules}
        print(f"\n  [{timestamp}] Instruction added: \"{text}\"")
        if new_cats:
            print(f"  Watchlist updated: +{', '.join(new_cats)}")
        else:
            print(f"  (no new keyword categories detected — instruction still recorded)")
        print(f"  Active rules: {len(self._parsed_combined.rules)} categories, "
              f"urgency={self._parsed_combined.global_urgency:.1f}")
        print()

    def clear_instructions(self) -> None:
        """Reset to only the original instruction."""
        self.instruction_history = [self.instruction_history[0]]
        self._parsed_combined = self._parsed_base
        self._combined_text = self.base_instruction_text
        print("\n  Instructions cleared. Back to original briefing only.\n")

    def show_status(self) -> None:
        """Print all active instructions."""
        print("\n  ── ACTIVE INSTRUCTIONS ──")
        for ts, text in self.instruction_history:
            print(f"  [{ts}] {text}")
        print(f"\n  Combined watchlist categories: "
              f"{', '.join(r.category for r in self._parsed_combined.rules) or '(none)'}")
        print(f"  Global urgency: {self._parsed_combined.global_urgency:.1f}")
        print(f"  Cycles completed: {self._cycle_count}\n")

    def run_cycle(self) -> None:
        """Run one decision cycle with the current combined instructions."""
        self._cycle_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        payload = self.base_payload.model_copy(deep=True)
        payload.instruction = OperatorInstruction(
            text=self._combined_text,
            priority_mode=payload.instruction.priority_mode,
        )

        output = run_pipeline(payload)
        report = format_report(output)

        print(f"\n  ── CYCLE #{self._cycle_count} at {timestamp} ──")
        print(report)

    def run_interactive(self) -> None:
        """Main interactive loop."""
        print(BANNER)
        print(f"  Base instruction: \"{self.base_instruction_text}\"")
        print(f"  Watchlist: {', '.join(r.category for r in self._parsed_combined.rules)}")
        if self.cycle_interval > 0:
            print(f"  Auto-cycle every {self.cycle_interval:.0f}s (type /interval 0 for manual)")
        else:
            print(f"  Manual mode — type /run to evaluate (or /interval 10 for auto)")
        print()

        # Run initial cycle
        self.run_cycle()

        self._running = True
        auto_thread = None
        if self.cycle_interval > 0:
            auto_thread = threading.Thread(target=self._auto_cycle_loop, daemon=True)
            auto_thread.start()

        try:
            while self._running:
                try:
                    line = input("operator> ").strip()
                except EOFError:
                    break

                if not line:
                    continue

                if line.lower() == "/quit":
                    print("\n  Ending live session.")
                    break
                elif line.lower() == "/status":
                    self.show_status()
                elif line.lower() == "/clear":
                    self.clear_instructions()
                elif line.lower() == "/run":
                    self.run_cycle()
                elif line.lower().startswith("/interval"):
                    parts = line.split()
                    if len(parts) == 2:
                        try:
                            self.cycle_interval = float(parts[1])
                            if self.cycle_interval > 0:
                                print(f"\n  Auto-cycle set to {self.cycle_interval:.0f}s\n")
                                if auto_thread is None or not auto_thread.is_alive():
                                    auto_thread = threading.Thread(
                                        target=self._auto_cycle_loop, daemon=True,
                                    )
                                    auto_thread.start()
                            else:
                                print("\n  Switched to manual mode. Type /run to evaluate.\n")
                        except ValueError:
                            print("  Usage: /interval <seconds>")
                    else:
                        print("  Usage: /interval <seconds>")
                elif line.startswith("/"):
                    print(f"  Unknown command: {line}. Type /quit to exit.")
                else:
                    self.add_instruction(line)
                    if self.cycle_interval == 0:
                        self.run_cycle()

        except KeyboardInterrupt:
            print("\n\n  Session interrupted.")
        finally:
            self._running = False

    def _auto_cycle_loop(self) -> None:
        """Background thread that triggers cycles on an interval."""
        while self._running and self.cycle_interval > 0:
            time.sleep(self.cycle_interval)
            if self._running and self.cycle_interval > 0:
                self.run_cycle()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drone Decision Engine — Live Operator Session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", help="Path to JSON input file")
    parser.add_argument("--cv-dir", help="Path to CV module output folder")
    parser.add_argument("--instruction", help="Initial operator instruction")
    parser.add_argument(
        "--priority",
        choices=["safety", "crowd", "theft", "general"],
        default="general",
    )
    parser.add_argument(
        "--drone-pos", nargs=2, type=int, metavar=("X", "Y"), default=[500, 500],
    )
    parser.add_argument("--drone-alt", type=float, default=150.0)
    parser.add_argument("--drone-heading", type=float, default=0.0)
    parser.add_argument("--drone-zoom", type=float, default=1.0)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument(
        "--interval", type=float, default=0.0,
        help="Auto re-evaluation interval in seconds (0 = manual/on-input, default: 0)",
    )
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        with open(input_path) as f:
            raw = json.load(f)
        payload = DecisionInput.model_validate(raw)
    elif args.cv_dir:
        if not args.instruction:
            print("Error: --instruction required with --cv-dir", file=sys.stderr)
            sys.exit(1)
        from decision_engine.cv_intake import load_cv_output
        payload = load_cv_output(
            cv_dir=args.cv_dir,
            instruction_text=args.instruction,
            priority_mode=args.priority,
            drone_position_px=tuple(args.drone_pos),
            drone_altitude_ft=args.drone_alt,
            drone_heading_deg=args.drone_heading,
            drone_zoom=args.drone_zoom,
            venue_scale_ft_per_px=args.scale,
        )
    else:
        print("Error: provide --input or --cv-dir", file=sys.stderr)
        sys.exit(1)

    session = LiveSession(base_payload=payload, cycle_interval=args.interval)
    session.run_interactive()


if __name__ == "__main__":
    main()
