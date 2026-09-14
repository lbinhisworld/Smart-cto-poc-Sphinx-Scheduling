"""§11 T3 SPH 口径（BR-10 / BR-11 / BR-12 / BR-13）。"""

from datetime import date
from decimal import Decimal

from engine.capacity import day_capacity, detect_e8, group_rate, hours_wall
from engine.models import SphBasis

EPS = Decimal("0.0001")


def test_br10_sph_single_p1(p1_sph, p1_converts):
    assert group_rate(p1_sph, crew_plan=3, converts=p1_converts) == Decimal("37.5")


def test_br11_crew_no_multiply(s2_sph, s2_converts):
    assert group_rate(s2_sph, crew_plan=4, converts=s2_converts) == Decimal("40")


def test_br11_e8_when_crew_mismatch(s2_sph):
    conflict = detect_e8(s2_sph, crew_plan=5)
    assert conflict is not None
    assert conflict.code == "E8"


def test_br11_sph_basis_error_magnitude(p1_sph, p1_converts):
    """算例②：把 SINGLE 误当成 CREW，工时差 3 倍。"""
    sph_single = p1_sph.model_copy(update={"sph_basis": SphBasis.SINGLE})
    sph_crew = p1_sph.model_copy(update={"sph_basis": SphBasis.CREW})
    h_single = hours_wall(420, sph_single, 3, p1_converts)
    h_crew = hours_wall(420, sph_crew, 3, p1_converts)
    assert abs(h_single - Decimal("11.2")) < EPS
    assert abs(h_crew - Decimal("33.6")) < EPS


def test_br13_day_capacity_p1_reserved_zero(schedule_input, p1_sph, p1_converts):
    cap = day_capacity(
        schedule_input.calendar,
        p1_sph.group_code,
        date(2026, 9, 23),
        p1_sph,
        crew_plan=3,
        converts=p1_converts,
        reserved_ratio=schedule_input.config.reserved_ratio,
    )
    assert cap == 300
