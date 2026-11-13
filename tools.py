"""The agent's toolbox and the design session that keeps it honest.

Design rule of ShaftPilot: the language model decides WHAT to try,
the tools decide WHETHER it works. Every number in the final report
comes from these functions, never from the model's own arithmetic.

Guardrails enforced here:
* Requirements are locked with `set_requirements`; checks always run
  against the locked case, so the agent cannot quietly weaken the loads.
* `submit_design` re-runs every check itself and rejects designs that
  fail, use a non-standard diameter, or break the user's constraints.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

from . import mechanics
from .materials import MATERIALS, get_material

OBJECTIVES = ("min_cost", "min_mass", "min_diameter")


@dataclass
class Requirements:
    power_kw: float
    speed_rpm: float
    radial_force_n: float
    span_mm: float
    load_position_mm: float
    required_safety: float = 2.0
    objective: str = "min_cost"
    allowed_materials: list[str] | None = None
    max_diameter_mm: float | None = None
    assumptions: list[str] = field(default_factory=list)

    @property
    def torque_nm(self) -> float:
        return mechanics.torque_from_power(self.power_kw, self.speed_rpm)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["torque_nm"] = round(self.torque_nm, 3)
        d["bending_moment_nm"] = round(
            mechanics.max_bending_moment(self.radial_force_n, self.span_mm, self.load_position_mm), 3
        )
        return d


@dataclass
class TraceEntry:
    step: int
    tool: str
    input: dict
    output: Any
    ok: bool


class DesignSession:
    """State shared by all tools during one design run."""

    def __init__(self) -> None:
        self.requirements: Requirements | None = None
        self.checks: list[mechanics.ShaftCheck] = []
        self.final: dict | None = None
        self.final_check: mechanics.ShaftCheck | None = None
        self.trace: list[TraceEntry] = []
        self.rejected_submissions = 0

    # ------------------------------------------------------------------ tools

    def set_requirements(
        self,
        power_kw: float,
        speed_rpm: float,
        radial_force_n: float,
        span_mm: float,
        load_position_mm: float | None = None,
        required_safety: float = 2.0,
        objective: str = "min_cost",
        allowed_materials: list[str] | None = None,
        max_diameter_mm: float | None = None,
        assumptions: list[str] | None = None,
    ) -> dict:
        if objective not in OBJECTIVES:
            raise ValueError(f"objective must be one of {OBJECTIVES}")
        if required_safety < 1.0:
            raise ValueError("required_safety below 1.0 is not allowed")
        if allowed_materials:
            allowed_materials = [get_material(m).name for m in allowed_materials]
        if load_position_mm is None:
            load_position_mm = span_mm / 2.0
        req = Requirements(
            power_kw=float(power_kw),
            speed_rpm=float(speed_rpm),
            radial_force_n=float(radial_force_n),
            span_mm=float(span_mm),
            load_position_mm=float(load_position_mm),
            required_safety=float(required_safety),
            objective=objective,
            allowed_materials=allowed_materials or None,
            max_diameter_mm=max_diameter_mm,
            assumptions=list(assumptions or []),
        )
        mechanics.max_bending_moment(req.radial_force_n, req.span_mm, req.load_position_mm)  # validates
        revised = self.requirements is not None
        self.requirements = req
        self.checks.clear()
        return {"locked": True, "revised": revised, "requirements": req.to_dict()}

    def list_materials(self) -> dict:
        allowed = self.requirements.allowed_materials if self.requirements else None
        return {
            "materials": [
                m.to_dict() for m in MATERIALS.values() if not allowed or m.name in allowed
            ],
            "note": "relative_cost is a price index per kg (S235JR = 1.0)",
        }

    def estimate_min_diameter(self, material: str, kf: float = 1.7, kfs: float = 1.5,
                              surface: str = "machined") -> dict:
        """Closed-form DE-Goodman starting estimate (assumes size factor kb = 0.85)."""
        req = self._req()
        mat = get_material(material)
        M = mechanics.max_bending_moment(req.radial_force_n, req.span_mm, req.load_position_mm) * 1000
        T = req.torque_nm * 1000
        Se = mechanics.surface_factor(surface, mat.Rm) * 0.85 * mat.sigma_bW
        n = req.required_safety
        d = (16 * n / math.pi * (2 * kf * M / Se + math.sqrt(3) * kfs * T / mat.Rm)) ** (1 / 3)
        return {
            "material": mat.name,
            "estimated_min_diameter_mm": round(d, 2),
            "next_standard_diameter_mm": mechanics.standard_diameter(d, "up"),
            "note": "Fatigue-only estimate. Verify with check_shaft - deflection or slope may need more.",
        }

    def check_shaft(self, diameter_mm: float, material: str, kf: float = 1.7, kfs: float = 1.5,
                    surface: str = "machined") -> dict:
        req = self._req()
        mat = get_material(material)
        result = mechanics.check_shaft(
            diameter_mm=float(diameter_mm),
            material=mat,
            torque_nm=req.torque_nm,
            radial_force_n=req.radial_force_n,
            span_mm=req.span_mm,
            load_position_mm=req.load_position_mm,
            required_safety=req.required_safety,
            kf=kf,
            kfs=kfs,
            surface=surface,
        )
        self.checks.append(result)
        out = result.to_dict()
        out["inputs"] = {"kf": kf, "kfs": kfs, "surface": surface}
        return out

    def standard_diameter(self, diameter_mm: float, direction: str = "up") -> dict:
        return {"standard_diameter_mm": mechanics.standard_diameter(float(diameter_mm), direction)}

    def submit_design(self, diameter_mm: float, material: str, rationale: str, kf: float = 1.7,
                      kfs: float = 1.5, surface: str = "machined") -> dict:
        req = self._req()
        mat = get_material(material)
        check = mechanics.check_shaft(
            diameter_mm=float(diameter_mm), material=mat, torque_nm=req.torque_nm,
            radial_force_n=req.radial_force_n, span_mm=req.span_mm,
            load_position_mm=req.load_position_mm, required_safety=req.required_safety,
            kf=kf, kfs=kfs, surface=surface,
        )
        problems: list[str] = []
        if not check.passes_all:
            problems.append(f"design fails: {', '.join(check.failed_checks)}")
        if not check.is_standard_diameter:
            problems.append("diameter is not a standard size - use standard_diameter")
        if req.allowed_materials and mat.name not in req.allowed_materials:
            problems.append(f"material {mat.name} is not allowed ({req.allowed_materials})")
        if req.max_diameter_mm and diameter_mm > req.max_diameter_mm:
            problems.append(f"diameter exceeds the limit of {req.max_diameter_mm} mm")
        if kf < 1.0 or kfs < 1.0:
            problems.append("stress concentration factors below 1.0 are not allowed")
        if problems:
            self.rejected_submissions += 1
            return {"accepted": False, "problems": problems,
                    "hint": "Fix the problems and submit again."}

        self.final = {"diameter_mm": float(diameter_mm), "material": mat.name, "surface": surface,
                      "kf": kf, "kfs": kfs, "rationale": rationale}
        self.final_check = check
        return {"accepted": True, "verified_check": check.to_dict()}

    # ---------------------------------------------------------------- helpers

    def _req(self) -> Requirements:
        if self.requirements is None:
            raise RuntimeError("Call set_requirements first.")
        return self.requirements

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Run a tool by name, log it, and return (json_result, ok)."""
        fn: Callable[..., dict] | None = getattr(self, name, None) if name in TOOL_NAMES else None
        try:
            if fn is None:
                raise ValueError(f"Unknown tool '{name}'")
            result = fn(**args)
            ok = True
        except Exception as exc:  # errors go back to the agent so it can recover
            result = {"error": f"{type(exc).__name__}: {exc}"}
            ok = False
        self.trace.append(TraceEntry(len(self.trace) + 1, name, args, result, ok))
        return json.dumps(result, default=_json_default), ok


def _json_default(o: Any) -> Any:
    if isinstance(o, float) and math.isinf(o):
        return "inf"
    return str(o)


_DESIGN_VARS = {
    "kf": {"type": "number", "description": "Bending stress concentration factor at the critical shoulder/keyway (default 1.7)."},
    "kfs": {"type": "number", "description": "Torsion stress concentration factor (default 1.5)."},
    "surface": {"type": "string", "enum": list(mechanics.SURFACE_FACTORS),
                "description": "Surface finish (default machined)."},
}

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "set_requirements",
        "description": (
            "Lock the design requirements extracted from the user's request. Must be called first. "
            "If the user did not give a value, choose a sensible engineering default and record it "
            "in 'assumptions'. Calling it again replaces the requirements and clears previous checks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "power_kw": {"type": "number", "description": "Transmitted power in kW."},
                "speed_rpm": {"type": "number", "description": "Shaft speed in rpm."},
                "radial_force_n": {"type": "number", "description": "Radial force from gear/pulley in N."},
                "span_mm": {"type": "number", "description": "Distance between the two bearings in mm."},
                "load_position_mm": {"type": "number", "description": "Distance of the force from the left bearing in mm (default: mid-span)."},
                "required_safety": {"type": "number", "description": "Minimum safety factor for fatigue and yield (default 2.0)."},
                "objective": {"type": "string", "enum": list(OBJECTIVES), "description": "What to optimise."},
                "allowed_materials": {"type": "array", "items": {"type": "string"}, "description": "Optional list of allowed materials."},
                "max_diameter_mm": {"type": "number", "description": "Optional maximum diameter (installation space)."},
                "assumptions": {"type": "array", "items": {"type": "string"}, "description": "Every assumption you made."},
            },
            "required": ["power_kw", "speed_rpm", "radial_force_n", "span_mm", "assumptions"],
        },
    },
    {
        "name": "list_materials",
        "description": "List available shaft materials with strength, fatigue limit and relative cost.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "estimate_min_diameter",
        "description": "Quick closed-form estimate of the minimum diameter for fatigue for one material. A starting point only - always verify with check_shaft.",
        "input_schema": {
            "type": "object",
            "properties": {"material": {"type": "string"}, **_DESIGN_VARS},
            "required": ["material"],
        },
    },
    {
        "name": "check_shaft",
        "description": "Full verification of one candidate (diameter + material) against the locked requirements: fatigue, yield, deflection, bearing slope, mass and cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "diameter_mm": {"type": "number"},
                "material": {"type": "string"},
                **_DESIGN_VARS,
            },
            "required": ["diameter_mm", "material"],
        },
    },
    {
        "name": "standard_diameter",
        "description": "Round a diameter to the next standard shaft diameter (DIN 748 based).",
        "input_schema": {
            "type": "object",
            "properties": {
                "diameter_mm": {"type": "number"},
                "direction": {"type": "string", "enum": ["up", "down"]},
            },
            "required": ["diameter_mm"],
        },
    },
    {
        "name": "submit_design",
        "description": (
            "Submit the final design. The system re-verifies it independently and rejects it if any "
            "check fails, the diameter is non-standard, or a constraint is broken. Only call this after "
            "comparing alternatives."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "diameter_mm": {"type": "number"},
                "material": {"type": "string"},
                "rationale": {"type": "string", "description": "Why this design beats the alternatives you checked."},
                **_DESIGN_VARS,
            },
            "required": ["diameter_mm", "material", "rationale"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_SCHEMAS}
