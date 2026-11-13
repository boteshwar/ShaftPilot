import math

import pytest

from shaftpilot import mechanics
from shaftpilot.materials import get_material


def test_torque_from_power():
    # 5 kW at 1450 rpm -> 32.93 N*m
    assert mechanics.torque_from_power(5, 1450) == pytest.approx(32.929, rel=1e-4)


def test_bending_moment_mid_span_is_FL_over_4():
    assert mechanics.max_bending_moment(1000, 400, 200) == pytest.approx(1000 * 0.4 / 4)


def test_bending_moment_off_centre():
    # F*a*b/L = 2500 * 0.12 * 0.18 / 0.3
    assert mechanics.max_bending_moment(2500, 300, 120) == pytest.approx(180.0)


def test_hand_calculation_matches():
    """Hand-checked example: d = 38 mm, S235JR, M = 180 N*m, T = 32.93 N*m."""
    c = mechanics.check_shaft(
        diameter_mm=38, material=get_material("S235JR"), torque_nm=32.929,
        radial_force_n=2500, span_mm=300, load_position_mm=120, required_safety=2.0,
    )
    assert c.sigma_b_mpa == pytest.approx(33.41, abs=0.02)
    assert c.tau_t_mpa == pytest.approx(3.056, abs=0.005)
    assert c.safety_fatigue == pytest.approx(2.391, abs=0.005)
    assert c.deflection_mm == pytest.approx(0.0603, abs=0.0002)
    assert c.passes_all


def test_mid_span_deflection_matches_textbook_formula():
    F, L, d = 1000.0, 500.0, 40.0
    c = mechanics.check_shaft(diameter_mm=d, material=get_material("C45+N"), torque_nm=0,
                              radial_force_n=F, span_mm=L, load_position_mm=L / 2, required_safety=1)
    I = math.pi * d ** 4 / 64
    assert c.deflection_mm == pytest.approx(F * L ** 3 / (48 * 210_000 * I))
    assert c.slope_rad == pytest.approx(F * L ** 2 / (16 * 210_000 * I))


def test_stronger_steel_does_not_fix_stiffness():
    common = dict(diameter_mm=28, torque_nm=33, radial_force_n=2500, span_mm=300,
                  load_position_mm=120, required_safety=2.0)
    weak = mechanics.check_shaft(material=get_material("C45+N"), **common)
    strong = mechanics.check_shaft(material=get_material("34CrNiMo6+QT"), **common)
    assert weak.deflection_mm == pytest.approx(strong.deflection_mm)
    assert not strong.passes_deflection


def test_standard_diameter_rounding():
    assert mechanics.standard_diameter(31.3) == 32
    assert mechanics.standard_diameter(32) == 32
    assert mechanics.standard_diameter(31.3, "down") == 30


def test_bad_geometry_rejected():
    with pytest.raises(ValueError):
        mechanics.max_bending_moment(100, 300, 400)


def test_unknown_material():
    with pytest.raises(KeyError):
        get_material("unobtainium")
    assert get_material("c45 +n").name == "C45+N"
