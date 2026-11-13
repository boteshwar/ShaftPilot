"""Tests for the guardrails and the agent loop (with a fake LLM, no API key needed)."""

import json
from types import SimpleNamespace as NS

from shaftpilot.agent import run_agent
from shaftpilot.offline import run_offline
from shaftpilot.report import build_report
from shaftpilot.tools import DesignSession

REQ = dict(power_kw=5, speed_rpm=1450, radial_force_n=2500, span_mm=300,
           load_position_mm=120, assumptions=["test"])


def test_tools_need_requirements_first():
    s = DesignSession()
    out, ok = s.call("check_shaft", {"diameter_mm": 30, "material": "C45+N"})
    assert not ok and "set_requirements" in json.loads(out)["error"]


def test_verifier_rejects_failing_design():
    s = DesignSession()
    s.call("set_requirements", REQ)
    out, ok = s.call("submit_design", {"diameter_mm": 28, "material": "42CrMo4+QT", "rationale": "x"})
    r = json.loads(out)
    assert ok and r["accepted"] is False
    assert any("deflection" in p for p in r["problems"])
    assert s.final is None and s.rejected_submissions == 1


def test_verifier_rejects_non_standard_diameter():
    s = DesignSession()
    s.call("set_requirements", REQ)
    r = json.loads(s.call("submit_design", {"diameter_mm": 37.3, "material": "C45+N", "rationale": "x"})[0])
    assert not r["accepted"]
    assert any("standard" in p for p in r["problems"])


def test_verifier_blocks_cheating_with_kf():
    s = DesignSession()
    s.call("set_requirements", REQ)
    r = json.loads(s.call("submit_design", {"diameter_mm": 35, "material": "C45+N",
                                            "rationale": "x", "kf": 0.5})[0])
    assert not r["accepted"]


def test_unknown_tool_is_reported_not_crashing():
    s = DesignSession()
    out, ok = s.call("delete_everything", {})
    assert not ok and "Unknown tool" in out


def test_offline_planner_finds_cheapest_valid_design():
    spec = dict(REQ, objective="min_cost")
    s, _ = run_offline(spec)
    assert s.final_check is not None and s.final_check.passes_all
    passing = [c for c in s.checks if c.passes_all]
    assert s.final_check.relative_cost == min(c.relative_cost for c in passing)


# ---------------------------------------------------------------- fake LLM

def _tool(i, name, args):
    return NS(type="tool_use", id=f"t{i}", name=name, input=args)


class FakeClient:
    """Replays a scripted conversation, like a real model that makes one mistake."""

    def __init__(self):
        self.turns = [
            [NS(type="text", text="Extracting the load case."), _tool(1, "set_requirements", REQ)],
            [_tool(2, "check_shaft", {"diameter_mm": 28, "material": "42CrMo4+QT"}),
             _tool(3, "check_shaft", {"diameter_mm": 35, "material": "C45+N"})],
            [_tool(4, "submit_design", {"diameter_mm": 28, "material": "42CrMo4+QT", "rationale": "smallest"})],
            [_tool(5, "submit_design", {"diameter_mm": 35, "material": "C45+N", "rationale": "stiffness-limited"})],
            [NS(type="text", text="Done: 35 mm C45+N.")],
        ]
        self.calls = []
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.turns.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return NS(content=content, stop_reason=stop)


def test_agent_loop_recovers_from_rejected_submission():
    client = FakeClient()
    events = []
    session, summary = run_agent("design a shaft", client=client, on_event=lambda k, d: events.append(k))

    assert session.final == {"diameter_mm": 35.0, "material": "C45+N", "surface": "machined",
                             "kf": 1.7, "kfs": 1.5, "rationale": "stiffness-limited"}
    assert session.rejected_submissions == 1
    assert summary == "Done: 35 mm C45+N."
    assert len(client.calls) == 5
    # tool results are fed back with the right ids
    last_user = [m for m in client.calls[-1]["messages"] if m["role"] == "user"][-1]
    assert last_user["content"][0]["tool_use_id"] == "t5"
    assert "tool_call" in events and "tool_result" in events

    report = build_report(session, "design a shaft", summary)
    assert "Ø 35 mm, C45+N" in report
    assert "1 submissions rejected" in report
