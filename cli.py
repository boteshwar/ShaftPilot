"""Command-line interface.

    python -m shaftpilot "5 kW motor at 1450 rpm, spur gear with 2 kN radial force
                          in the middle of a 300 mm bearing span, safety 2, cheapest"

    python -m shaftpilot --offline examples/gearbox_input_shaft.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .report import build_report

_C = {"dim": "\033[2m", "cyan": "\033[36m", "green": "\033[32m", "red": "\033[31m",
      "yellow": "\033[33m", "bold": "\033[1m", "end": "\033[0m"}
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    _C = {k: "" for k in _C}


def _short(result_json: str) -> str:
    try:
        r = json.loads(result_json)
    except json.JSONDecodeError:
        return result_json[:120]
    if "error" in r:
        return r["error"]
    if "passes_all" in r:
        verdict = "PASS" if r["passes_all"] else "FAIL " + ",".join(r["failed_checks"])
        return (f"Ø{r['diameter_mm']:g} {r['material']}: n_f={r['safety_fatigue']}, "
                f"n_y={r['safety_yield']}, f={r['deflection_mm']:.4f}/{r['deflection_limit_mm']:.4f} mm "
                f"-> {verdict}")
    if "accepted" in r:
        return "ACCEPTED by verifier" if r["accepted"] else "REJECTED: " + "; ".join(r["problems"])
    if "estimated_min_diameter_mm" in r:
        return f"{r['material']}: d_min≈{r['estimated_min_diameter_mm']} mm -> try {r['next_standard_diameter_mm']:g}"
    if "locked" in r:
        q = r["requirements"]
        return f"locked: T={q['torque_nm']} N·m, M={q['bending_moment_nm']} N·m, objective={q['objective']}"
    if "materials" in r:
        return f"{len(r['materials'])} materials available"
    return result_json[:120]


def _printer(kind: str, data: dict) -> None:
    c = _C
    if kind == "thought":
        print(f"{c['cyan']}🤔 {data['text'].strip()}{c['end']}\n")
    elif kind == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in data["input"].items() if k not in ("assumptions", "rationale"))
        print(f"{c['bold']}🔧 {data['name']}{c['end']}{c['dim']}({args}){c['end']}")
    elif kind == "tool_result":
        colour = c["green"] if data["ok"] else c["red"]
        print(f"   {colour}↳ {_short(data['result'])}{c['end']}")
    elif kind == "warning":
        print(f"{c['yellow']}⚠ {data['text']}{c['end']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shaftpilot", description="AI agent that designs and verifies machine shafts.")
    p.add_argument("request", nargs="?", help="Design request in plain language (agent mode).")
    p.add_argument("--offline", metavar="SPEC.json", help="Run the scripted planner on a JSON spec (no API key needed).")
    p.add_argument("--report", metavar="FILE.md", default="shaftpilot_report.md", help="Where to write the report.")
    p.add_argument("--model", default=None, help="Claude model to use (default: claude-sonnet-5-5).")
    p.add_argument("--quiet", action="store_true", help="Do not print the live trace.")
    args = p.parse_args(argv)

    on_event = None if args.quiet else _printer

    if args.offline:
        from .offline import run_offline

        spec = json.loads(Path(args.offline).read_text(encoding="utf-8"))
        request = spec.pop("request", f"Offline spec from {args.offline}")
        print(f"{_C['bold']}ShaftPilot (offline scripted planner){_C['end']}\n")
        session, summary = run_offline(spec, on_event=on_event)
        mode = "offline scripted planner"
    elif args.request:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Set ANTHROPIC_API_KEY first, or try the demo with --offline examples/gearbox_input_shaft.json",
                  file=sys.stderr)
            return 2
        from .agent import run_agent, DEFAULT_MODEL

        request = args.request
        print(f"{_C['bold']}ShaftPilot agent{_C['end']}\n")
        session, summary = run_agent(request, model=args.model or DEFAULT_MODEL, on_event=on_event)
        mode = f"LLM agent ({args.model or DEFAULT_MODEL})"
    else:
        p.print_help()
        return 1

    report = build_report(session, request, agent_summary=summary, mode=mode)
    Path(args.report).write_text(report, encoding="utf-8")

    if session.final_check:
        fc = session.final_check
        print(f"\n{_C['green']}{_C['bold']}✅ Verified design: Ø {fc.diameter_mm:g} mm, {fc.material}{_C['end']}")
    else:
        print(f"\n{_C['red']}No verified design.{_C['end']}")
    print(f"Report written to {args.report}")
    return 0 if session.final_check else 3
