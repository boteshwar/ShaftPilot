"""Shaft mechanics: the deterministic maths the agent is NOT allowed to do itself.

Load model: a solid round shaft on two bearings (simply supported, span L)
with one radial force F (e.g. a gear or belt pulley) at distance a from the
left bearing, transmitting a constant torque T.

Methods
-------
* Torque from power and speed: T = P / omega
* Bending: M_max = F * a * b / L,   sigma_b = 32 M / (pi d^3)
* Torsion:                           tau_t   = 16 T / (pi d^3)
* Fatigue: DE-Goodman criterion (Shigley, Mechanical Engineering Design):
      1/n_f = Kf * sigma_a / Se  +  sqrt(3) * Kfs * tau_m / Rm
  Rotating shaft -> bending is fully reversed (sigma_a = sigma_b),
  constant torque -> torsion is steady (tau_m = tau_t).
  Se = ka * kb * sigma_bW with Marin surface (ka) and size (kb) factors.
* Static yield: n_y = Re / sqrt((Kf sigma_b)^2 + 3 (Kfs tau_t)^2)
* Deflection at the load point: f = F a^2 b^2 / (3 E I L)
  Limit f <= 0.0003 L (common guideline, e.g. Roloff/Matek)
* Bearing slope: theta_A = F b (L^2 - b^2) / (6 E I L),
                 theta_B = F a (L^2 - a^2) / (6 E I L)
  Limit 0.001 rad (deep groove ball bearings, conservative)

This is a concept-design check, not a full DIN 743 verification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from .materials import Material

# Common preferred shaft diameters in mm (based on DIN 748 / R20 series)
STANDARD_DIAMETERS_MM: list[float] = [
    10, 11, 12, 14, 16, 18, 19, 20, 22, 24, 25, 28, 30, 32, 35, 38, 40, 42,
    45, 48, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120, 125, 130,
    140, 150, 160,
]

# Marin surface factor ka = a * Rm^b  (Rm in MPa), Shigley Table 6-2
SURFACE_FACTORS: dict[str, tuple[float, float]] = {
    "ground": (1.58, -0.085),
    "machined": (4.51, -0.265),
    "hot-rolled": (57.7, -0.718),
    "forged": (272.0, -0.995),
}

DEFLECTION_LIMIT_RATIO = 0.0003   # f_allowed = 0.0003 * L
SLOPE_LIMIT_RAD = 0.001


def torque_from_power(power_kw: float, speed_rpm: float) -> float:
    """Torque in N*m from power in kW and speed in rpm."""
    if speed_rpm <= 0:
        raise ValueError("speed_rpm must be positive")
    omega = 2 * math.pi * speed_rpm / 60.0
    return power_kw * 1000.0 / omega


def max_bending_moment(force_n: float, span_mm: float, load_position_mm: float) -> float:
    """Maximum bending moment in N*m for a point load on a simply supported shaft."""
    _check_geometry(span_mm, load_position_mm)
    a = load_position_mm / 1000.0
    b = (span_mm - load_position_mm) / 1000.0
    L = span_mm / 1000.0
    return force_n * a * b / L


def surface_factor(surface: str, Rm: float) -> float:
    if surface not in SURFACE_FACTORS:
        raise ValueError(f"surface must be one of {list(SURFACE_FACTORS)}")
    a, b = SURFACE_FACTORS[surface]
    return min(1.0, a * Rm ** b)


def size_factor(d_mm: float) -> float:
    """Marin size factor kb for rotating bending (Shigley eq. 6-20)."""
    if d_mm <= 2.79:
        return 1.0
    if d_mm <= 51:
        return 1.24 * d_mm ** -0.107
    return 1.51 * d_mm ** -0.157


def standard_diameter(d_mm: float, direction: str = "up") -> float:
    """Snap a diameter to the nearest standard value (up or down)."""
    if direction == "up":
        for d in STANDARD_DIAMETERS_MM:
            if d >= d_mm - 1e-9:
                return float(d)
        raise ValueError(f"{d_mm} mm is larger than the largest standard diameter")
    if direction == "down":
        for d in reversed(STANDARD_DIAMETERS_MM):
            if d <= d_mm + 1e-9:
                return float(d)
        raise ValueError(f"{d_mm} mm is smaller than the smallest standard diameter")
    raise ValueError("direction must be 'up' or 'down'")


@dataclass
class ShaftCheck:
    diameter_mm: float
    material: str
    torque_nm: float
    bending_moment_nm: float
    sigma_b_mpa: float
    tau_t_mpa: float
    ka_surface: float
    kb_size: float
    Se_mpa: float
    safety_fatigue: float
    safety_yield: float
    deflection_mm: float
    deflection_limit_mm: float
    slope_rad: float
    slope_limit_rad: float
    mass_kg: float
    relative_cost: float
    required_safety: float
    is_standard_diameter: bool
    passes_fatigue: bool
    passes_yield: bool
    passes_deflection: bool
    passes_slope: bool
    passes_all: bool
    failed_checks: list[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def check_shaft(
    *,
    diameter_mm: float,
    material: Material,
    torque_nm: float,
    radial_force_n: float,
    span_mm: float,
    load_position_mm: float,
    required_safety: float,
    kf: float = 1.7,
    kfs: float = 1.5,
    surface: str = "machined",
) -> ShaftCheck:
    """Run every check on one candidate shaft and report pass/fail."""
    _check_geometry(span_mm, load_position_mm)
    if diameter_mm <= 0:
        raise ValueError("diameter_mm must be positive")

    d = diameter_mm  # mm, so stresses come out in N/mm^2 = MPa
    M = max_bending_moment(radial_force_n, span_mm, load_position_mm)  # N*m
    M_nmm = M * 1000.0
    T_nmm = torque_nm * 1000.0

    sigma_b = 32.0 * M_nmm / (math.pi * d ** 3)
    tau_t = 16.0 * T_nmm / (math.pi * d ** 3)

    ka = surface_factor(surface, material.Rm)
    kb = size_factor(d)
    Se = ka * kb * material.sigma_bW

    inv_nf = kf * sigma_b / Se + math.sqrt(3.0) * kfs * tau_t / material.Rm
    n_f = math.inf if inv_nf == 0 else 1.0 / inv_nf

    sigma_vm_max = math.sqrt((kf * sigma_b) ** 2 + 3.0 * (kfs * tau_t) ** 2)
    n_y = math.inf if sigma_vm_max == 0 else material.Re / sigma_vm_max

    # Deflection and bearing slope (all in mm and N)
    I = math.pi * d ** 4 / 64.0
    E = material.E
    L = span_mm
    a = load_position_mm
    b = L - a
    F = radial_force_n
    f = F * a ** 2 * b ** 2 / (3.0 * E * I * L)
    theta_A = F * b * (L ** 2 - b ** 2) / (6.0 * E * I * L)
    theta_B = F * a * (L ** 2 - a ** 2) / (6.0 * E * I * L)
    slope = max(abs(theta_A), abs(theta_B))
    f_lim = DEFLECTION_LIMIT_RATIO * L

    mass = material.density * math.pi * (d / 1000.0) ** 2 / 4.0 * (L / 1000.0)

    checks = {
        "fatigue": n_f >= required_safety,
        "yield": n_y >= required_safety,
        "deflection": f <= f_lim,
        "bearing_slope": slope <= SLOPE_LIMIT_RAD,
    }
    failed = [k for k, ok in checks.items() if not ok]

    return ShaftCheck(
        diameter_mm=d,
        material=material.name,
        torque_nm=torque_nm,
        bending_moment_nm=M,
        sigma_b_mpa=sigma_b,
        tau_t_mpa=tau_t,
        ka_surface=ka,
        kb_size=kb,
        Se_mpa=Se,
        safety_fatigue=n_f,
        safety_yield=n_y,
        deflection_mm=f,
        deflection_limit_mm=f_lim,
        slope_rad=slope,
        slope_limit_rad=SLOPE_LIMIT_RAD,
        mass_kg=mass,
        relative_cost=mass * material.relative_cost,
        required_safety=required_safety,
        is_standard_diameter=any(abs(d - s) < 1e-9 for s in STANDARD_DIAMETERS_MM),
        passes_fatigue=checks["fatigue"],
        passes_yield=checks["yield"],
        passes_deflection=checks["deflection"],
        passes_slope=checks["bearing_slope"],
        passes_all=not failed,
        failed_checks=failed,
    )


def _check_geometry(span_mm: float, load_position_mm: float) -> None:
    if span_mm <= 0:
        raise ValueError("span_mm must be positive")
    if not 0 < load_position_mm < span_mm:
        raise ValueError("load_position_mm must be between 0 and span_mm")
