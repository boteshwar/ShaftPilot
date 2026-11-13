"""The agent loop: Claude plans, calls tools, reads results, and iterates."""

from __future__ import annotations

import os
from typing import Any, Callable

from .tools import DesignSession, TOOL_SCHEMAS

DEFAULT_MODEL = os.environ.get("SHAFTPILOT_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 30

SYSTEM_PROMPT = """You are ShaftPilot, a mechanical design agent that sizes power-transmission shafts.

How you work:
1. Read the user's request and extract the load case. Convert units yourself only for
   simple unit changes (e.g. m -> mm, W -> kW). If something is missing, pick a sensible,
   conservative engineering default and write it down as an assumption. Then call
   set_requirements.
2. Never compute stresses, safety factors or deflections in your head. Use the tools.
3. Explore the design space like an engineer: compare at least two materials, use
   estimate_min_diameter as a starting point, verify candidates with check_shaft, and
   step up to the next standard diameter when a check fails. Pay attention to WHICH check
   fails - a stiffness problem (deflection/slope) is not solved by a stronger steel,
   because all steels have nearly the same Young's modulus.
4. Choose the best design for the objective (min_cost uses relative_cost, min_mass uses
   mass_kg, min_diameter uses diameter_mm) and call submit_design with a short rationale.
   If it is rejected, read the problems and fix them.
5. After acceptance, reply with a short summary for the user: the chosen design, why it
   wins, which check was the limiting one, and the assumptions they should double-check.

Be concise. Use SI units. This is concept design, not a certified calculation."""


EventHandler = Callable[[str, dict], None]


def run_agent(
    request: str,
    *,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    max_steps: int = MAX_STEPS,
    on_event: EventHandler | None = None,
) -> tuple[DesignSession, str]:
    """Run the agent on a natural-language request.

    Returns the design session (with trace and verified result) and the
    agent's final message to the user.
    """
    if client is None:
        import anthropic  # imported lazily so offline mode needs no API key

        client = anthropic.Anthropic()

    emit = on_event or (lambda kind, data: None)
    session = DesignSession()
    messages: list[dict] = [{"role": "user", "content": request}]
    final_text = ""

    for _ in range(max_steps):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                emit("thought", {"text": block.text})
                final_text = block.text
            elif block.type == "tool_use":
                emit("tool_call", {"name": block.name, "input": block.input})
                result_json, ok = session.call(block.name, dict(block.input))
                emit("tool_result", {"name": block.name, "ok": ok, "result": result_json})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                    "is_error": not ok,
                })

        if response.stop_reason != "tool_use" or not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})
    else:
        emit("warning", {"text": f"Stopped after {max_steps} steps without finishing."})

    return session, final_text
