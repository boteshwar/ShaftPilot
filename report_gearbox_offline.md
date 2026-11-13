# ShaftPilot design report

*Generated 2026-11-13 - mode: offline scripted planner*

## Request

> Input shaft of a small gearbox: 5 kW electric motor at 1450 rpm, spur gear with 2.5 kN radial force 120 mm from the left bearing, 300 mm bearing span, safety factor 2, as cheap as possible.

## Locked requirements

| Quantity | Value |
|---|---|
| Power | 5 kW |
| Speed | 1450 rpm |
| Torque (computed) | 32.93 N·m |
| Radial force | 2500 N |
| Bearing span | 300 mm |
| Load position from left bearing | 120 mm |
| Max bending moment (computed) | 180.00 N·m |
| Required safety factor | 2 |
| Objective | min_cost |

### Assumptions to double-check

- Shaft is machined, with a shoulder at the gear seat (Kf = 1.7, Kfs = 1.5)
- Deep groove ball bearings, slope limit 0.001 rad

## Result

**Shaft: Ø 38 mm, S235JR, machined surface**

Limiting check: **Fatigue (DE-Goodman)** (20 % margin left).

| Check | Value | Limit | Status |
|---|---|---|---|
| Fatigue safety | 2.39 | ≥ 2 | PASS |
| Yield safety | 4.10 | ≥ 2 | PASS |
| Deflection at load | 0.0603 mm | ≤ 0.0900 mm | PASS |
| Bearing slope | 0.00067 rad | ≤ 0.001 rad | PASS |

| Detail | Value |
|---|---|
| Bending stress σ_b | 33.4 MPa |
| Torsional stress τ_t | 3.1 MPa |
| Corrected endurance limit Se | 143.4 MPa (ka=0.948, kb=0.840) |
| Stress concentration Kf / Kfs | 1.7 / 1.5 |
| Mass (between bearings) | 2.67 kg |
| Relative cost index | 2.67 |

### Why this design

Scripted search over 6 materials; S235JR at 38 mm has the lowest relative_cost.

## Every candidate the agent checked

| # | Ø mm | Material | n_fatigue | n_yield | f / f_lim | slope / lim | Mass kg | Cost | Result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 38 | S235JR | 2.39 | 4.10 | 0.67 | 0.67 | 2.67 | 2.67 | PASS |
| 2 | 35 | E295 | 2.30 | 4.02 | 0.93 | 0.93 | 2.27 | 2.72 | PASS |
| 3 | 35 | C45+N | 2.57 | 4.63 | 0.93 | 0.93 | 2.27 | 3.17 | PASS |
| 4 | 32 | C45+QT | 2.16 | 5.10 | 1.33 | 1.33 | 1.89 | 3.22 | FAIL: deflection, bearing_slope |
| 5 | 35 | C45+QT | 2.80 | 6.68 | 0.93 | 0.93 | 2.27 | 3.85 | PASS |
| 6 | 28 | 42CrMo4+QT | 2.05 | 6.28 | 2.27 | 2.27 | 1.45 | 3.77 | FAIL: deflection, bearing_slope |
| 7 | 30 | 42CrMo4+QT | 2.51 | 7.72 | 1.72 | 1.72 | 1.66 | 4.33 | FAIL: deflection, bearing_slope |
| 8 | 32 | 42CrMo4+QT | 3.03 | 9.37 | 1.33 | 1.33 | 1.89 | 4.92 | FAIL: deflection, bearing_slope |
| 9 | 35 | 42CrMo4+QT | 3.92 | 12.26 | 0.93 | 0.93 | 2.27 | 5.89 | PASS |
| 10 | 28 | 34CrNiMo6+QT | 2.19 | 6.98 | 2.27 | 2.27 | 1.45 | 4.93 | FAIL: deflection, bearing_slope |
| 11 | 30 | 34CrNiMo6+QT | 2.68 | 8.58 | 1.72 | 1.72 | 1.66 | 5.66 | FAIL: deflection, bearing_slope |
| 12 | 32 | 34CrNiMo6+QT | 3.23 | 10.41 | 1.33 | 1.33 | 1.89 | 6.44 | FAIL: deflection, bearing_slope |
| 13 | 35 | 34CrNiMo6+QT | 4.18 | 13.62 | 0.93 | 0.93 | 2.27 | 7.70 | PASS |

## Agent trace

22 tool calls, 0 errors recovered, 0 submissions rejected by the verifier.

## Agent summary

Scripted search over 6 materials; S235JR at 38 mm has the lowest relative_cost.

---
*Concept-design check using textbook methods (Shigley DE-Goodman, simply supported beam). Not a substitute for a full DIN 743 verification or supplier material data.*