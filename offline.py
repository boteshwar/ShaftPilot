"""Offline mode: a scripted, rule-based planner that uses the SAME tools as the agent.

It needs no API key, so anyone can run the demo. It is also a useful baseline:
it brute-forces every material, while the LLM agent has to reason its way there
and can handle requirements written in plain language.
"""

from __future__ import annotations

import json
from typing import Callable

from .mechanics import STANDARD_DIAMETERS_MM
from .tools import DesignSession

EventHandler = Callable[[str, dict], None]

_OBJECTIVE_KEY = {"min_cost": "relative_cost", "min_mass": "mass_kg", "min_diameter": "diameter_mm"}


def run_offline(spec: dict, on_event: EventHandler | None = None) -> tuple[DesignSession, str]:
    emit = on_event or (lambda kind, data: None)
    s = DesignSession()

    def call(name: str, **args) -> dict:
        emit("tool_call", {"name": name, "input": args})
        out, ok = s.call(name, args)
        emit("tool_result", {"name": name, "ok": ok, "result": out})
        return json.loads(out)

    call("set_requirements", **spec)
    materials = [m["name"] for m in call("list_materials")["materials"]]

    best_per_material = []
    for mat in materials:
        d = call("estimate_min_diameter", material=mat)["next_standard_diameter_mm"]
        idx = STANDARD_DIAMETERS_MM.index(d)
        while idx < len(STANDARD_DIAMETERS_MM):
            d = STANDARD_DIAMETERS_MM[idx]
            if s.requirements.max_diameter_mm and d > s.requirements.max_diameter_mm:
                break
            res = call("check_shaft", diameter_mm=d, material=mat)
            if res["passes_all"]:
                best_per_material.append(res)
                break
            idx += 1

    if not best_per_material:
        return s, "No material/diameter combination satisfies the requirements."

    key = _OBJECTIVE_KEY[s.requirements.objective]
    best = min(best_per_material, key=lambda r: r[key])
    rationale = (
        f"Scripted search over {len(materials)} materials; "
        f"{best['material']} at {best['diameter_mm']:g} mm has the lowest {key}."
    )
    call("submit_design", diameter_mm=best["diameter_mm"], material=best["material"], rationale=rationale)
    return s, rationale
