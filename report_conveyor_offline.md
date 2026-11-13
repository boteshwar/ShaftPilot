# ShaftPilot design report

*Generated 2026-11-13 - mode: offline scripted planner*

## Request

> Drive shaft for a belt conveyor: 15 kW at 90 rpm, belt pulley load 12 kN in the middle of a 600 mm bearing span, safety factor 2.5, must fit in 80 mm, lightest possible.

## Locked requirements

| Quantity | Value |
|---|---|
| Power | 15 kW |
| Speed | 90 rpm |
| Torque (computed) | 1591.55 N·m |
| Radial force | 12000 N |
| Bearing span | 600 mm |
| Load position from left bearing | 300 mm |
| Max bending moment (computed) | 1800.00 N·m |
| Required safety factor | 2.5 |
| Objective | min_mass |
| Max diameter | 80 mm |

### Assumptions to double-check

- Pulley sits at mid-span
- Machined surface, keyway at the pulley seat (Kf = 1.7, Kfs = 1.5)

## Result

**Shaft: Ø 75 mm, 42CrMo4+QT, machined surface**

Limiting check: **Deflection** (9 % margin left).

| Check | Value | Limit | Status |
|---|---|---|---|
| Fatigue safety | 3.11 | ≥ 2.5 | PASS |
| Yield safety | 10.09 | ≥ 2.5 | PASS |
| Deflection at load | 0.1656 mm | ≤ 0.1800 mm | PASS |
| Bearing slope | 0.00083 rad | ≤ 0.001 rad | PASS |

| Detail | Value |
|---|---|
| Bending stress σ_b | 43.5 MPa |
| Torsional stress τ_t | 19.2 MPa |
| Corrected endurance limit Se | 267.6 MPa (ka=0.705, kb=0.767) |
| Stress concentration Kf / Kfs | 1.7 / 1.5 |
| Mass (between bearings) | 20.81 kg |
| Relative cost index | 54.10 |

### Why this design

Scripted search over 6 materials; 42CrMo4+QT at 75 mm has the lowest mass_kg.

## Every candidate the agent checked

| # | Ø mm | Material | n_fatigue | n_yield | f / f_lim | slope / lim | Mass kg | Cost | Result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 80 | C45+N | 2.41 | 4.63 | 0.71 | 0.64 | 23.68 | 33.15 | FAIL: fatigue |
| 2 | 80 | C45+QT | 2.64 | 6.67 | 0.71 | 0.64 | 23.68 | 40.25 | PASS |
| 3 | 70 | 42CrMo4+QT | 2.55 | 8.21 | 1.21 | 1.09 | 18.13 | 47.13 | FAIL: deflection, bearing_slope |
| 4 | 75 | 42CrMo4+QT | 3.11 | 10.09 | 0.92 | 0.83 | 20.81 | 54.10 | PASS |
| 5 | 70 | 34CrNiMo6+QT | 2.73 | 9.12 | 1.21 | 1.09 | 18.13 | 61.63 | FAIL: deflection, bearing_slope |
| 6 | 75 | 34CrNiMo6+QT | 3.33 | 11.22 | 0.92 | 0.83 | 20.81 | 70.75 | PASS |

## Agent trace

15 tool calls, 0 errors recovered, 0 submissions rejected by the verifier.

## Agent summary

Scripted search over 6 materials; 42CrMo4+QT at 75 mm has the lowest mass_kg.

---
*Concept-design check using textbook methods (Shigley DE-Goodman, simply supported beam). Not a substitute for a full DIN 743 verification or supplier material data.*