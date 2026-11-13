"""Turns a finished design session into a Markdown design report.

Every number in the report is taken from the verified tool results.
"""

from __future__ import annotations

from datetime import date

from .tools import DesignSession

_CHECK_LABELS = {
    "fatigue": "Fatigue (DE-Goodman)",
    "yield": "Static yield",
    "deflection": "Deflection",
    "bearing_slope": "Bearing slope",
}


def _fmt(x: float, nd: int = 2) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.{nd}f}"


def _ok(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def build_report(session: DesignSession, request: str, agent_summary: str = "", mode: str = "agent") -> str:
    req = session.requirements
    lines: list[str] = ["# ShaftPilot design report", ""]
    lines.append(f"*Generated {date.today().isoformat()} - mode: {mode}*")
    lines.append("")
    lines += ["## Request", "", f"> {request}", ""]

    if req is None:
        lines.append("The agent did not set any requirements. No design was produced.")
        return "\n".join(lines)

    rd = req.to_dict()
    lines += [
        "## Locked requirements", "",
        "| Quantity | Value |", "|---|---|",
        f"| Power | {req.power_kw:g} kW |",
        f"| Speed | {req.speed_rpm:g} rpm |",
        f"| Torque (computed) | {rd['torque_nm']:.2f} N·m |",
        f"| Radial force | {req.radial_force_n:g} N |",
        f"| Bearing span | {req.span_mm:g} mm |",
        f"| Load position from left bearing | {req.load_position_mm:g} mm |",
        f"| Max bending moment (computed) | {rd['bending_moment_nm']:.2f} N·m |",
        f"| Required safety factor | {req.required_safety:g} |",
        f"| Objective | {req.objective} |",
    ]
    if req.allowed_materials:
        lines.append(f"| Allowed materials | {', '.join(req.allowed_materials)} |")
    if req.max_diameter_mm:
        lines.append(f"| Max diameter | {req.max_diameter_mm:g} mm |")
    lines.append("")

    if req.assumptions:
        lines += ["### Assumptions to double-check", ""]
        lines += [f"- {a}" for a in req.assumptions]
        lines.append("")

    fc = session.final_check
    if fc is None:
        lines += ["## Result", "", "**No design was accepted.**", ""]
    else:
        fin = session.final
        margins = {
            "fatigue": fc.safety_fatigue / fc.required_safety,
            "yield": fc.safety_yield / fc.required_safety,
            "deflection": fc.deflection_limit_mm / fc.deflection_mm if fc.deflection_mm else float("inf"),
            "bearing_slope": fc.slope_limit_rad / fc.slope_rad if fc.slope_rad else float("inf"),
        }
        limiting = min(margins, key=margins.get)
        lines += [
            "## Result", "",
            f"**Shaft: Ø {fc.diameter_mm:g} mm, {fc.material}, {fin['surface']} surface**", "",
            f"Limiting check: **{_CHECK_LABELS[limiting]}** "
            f"({(margins[limiting] - 1) * 100:.0f} % margin left).", "",
            "| Check | Value | Limit | Status |", "|---|---|---|---|",
            f"| Fatigue safety | {_fmt(fc.safety_fatigue)} | ≥ {fc.required_safety:g} | {_ok(fc.passes_fatigue)} |",
            f"| Yield safety | {_fmt(fc.safety_yield)} | ≥ {fc.required_safety:g} | {_ok(fc.passes_yield)} |",
            f"| Deflection at load | {fc.deflection_mm:.4f} mm | ≤ {fc.deflection_limit_mm:.4f} mm | {_ok(fc.passes_deflection)} |",
            f"| Bearing slope | {fc.slope_rad:.5f} rad | ≤ {fc.slope_limit_rad:g} rad | {_ok(fc.passes_slope)} |",
            "", "| Detail | Value |", "|---|---|",
            f"| Bending stress σ_b | {fc.sigma_b_mpa:.1f} MPa |",
            f"| Torsional stress τ_t | {fc.tau_t_mpa:.1f} MPa |",
            f"| Corrected endurance limit Se | {fc.Se_mpa:.1f} MPa (ka={fc.ka_surface:.3f}, kb={fc.kb_size:.3f}) |",
            f"| Stress concentration Kf / Kfs | {fin['kf']:g} / {fin['kfs']:g} |",
            f"| Mass (between bearings) | {fc.mass_kg:.2f} kg |",
            f"| Relative cost index | {fc.relative_cost:.2f} |",
            "",
        ]
        if fin.get("rationale"):
            lines += ["### Why this design", "", fin["rationale"], ""]

    if session.checks:
        lines += [
            "## Every candidate the agent checked", "",
            "| # | Ø mm | Material | n_fatigue | n_yield | f / f_lim | slope / lim | Mass kg | Cost | Result |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, c in enumerate(session.checks, 1):
            lines.append(
                f"| {i} | {c.diameter_mm:g} | {c.material} | {_fmt(c.safety_fatigue)} | {_fmt(c.safety_yield)} | "
                f"{c.deflection_mm / c.deflection_limit_mm:.2f} | {c.slope_rad / c.slope_limit_rad:.2f} | "
                f"{c.mass_kg:.2f} | {c.relative_cost:.2f} | "
                f"{'PASS' if c.passes_all else 'FAIL: ' + ', '.join(c.failed_checks)} |"
            )
        lines.append("")

    n_calls = len(session.trace)
    n_err = sum(not t.ok for t in session.trace)
    lines += [
        "## Agent trace", "",
        f"{n_calls} tool calls, {n_err} errors recovered, {session.rejected_submissions} submissions rejected by the verifier.",
        "",
    ]
    if agent_summary:
        lines += ["## Agent summary", "", agent_summary, ""]

    lines += [
        "---",
        "*Concept-design check using textbook methods (Shigley DE-Goodman, simply supported beam). "
        "Not a substitute for a full DIN 743 verification or supplier material data.*",
    ]
    return "\n".join(lines)
