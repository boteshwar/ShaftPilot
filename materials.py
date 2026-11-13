"""Material database for shaft steels.

Values are typical textbook values for small cross-sections (d <= 16 mm)
and are meant for concept design and teaching. Always check the supplier
datasheet before using a design for real.

Units: strengths in MPa, density in kg/m^3, E in MPa.
relative_cost is a rough price index per kg (S235 = 1.0).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Material:
    name: str
    description: str
    Rm: float          # ultimate tensile strength [MPa]
    Re: float          # yield strength [MPa]
    sigma_bW: float    # fully reversed bending fatigue limit [MPa]
    E: float           # Young's modulus [MPa]
    density: float     # [kg/m^3]
    relative_cost: float

    def to_dict(self) -> dict:
        return asdict(self)


_STEEL_E = 210_000.0
_STEEL_RHO = 7850.0

MATERIALS: dict[str, Material] = {
    m.name: m
    for m in [
        Material("S235JR", "General structural steel, cheap, low strength",
                 Rm=360, Re=235, sigma_bW=180, E=_STEEL_E, density=_STEEL_RHO, relative_cost=1.0),
        Material("E295", "Classic machine-building steel for lightly loaded shafts",
                 Rm=470, Re=295, sigma_bW=235, E=_STEEL_E, density=_STEEL_RHO, relative_cost=1.2),
        Material("C45+N", "Carbon steel C45, normalized - the standard shaft steel",
                 Rm=620, Re=340, sigma_bW=280, E=_STEEL_E, density=_STEEL_RHO, relative_cost=1.4),
        Material("C45+QT", "Carbon steel C45, quenched and tempered",
                 Rm=700, Re=490, sigma_bW=315, E=_STEEL_E, density=_STEEL_RHO, relative_cost=1.7),
        Material("42CrMo4+QT", "Alloy steel, quenched and tempered, high strength",
                 Rm=1100, Re=900, sigma_bW=495, E=_STEEL_E, density=_STEEL_RHO, relative_cost=2.6),
        Material("34CrNiMo6+QT", "High-alloy steel for heavily loaded shafts",
                 Rm=1200, Re=1000, sigma_bW=540, E=_STEEL_E, density=_STEEL_RHO, relative_cost=3.4),
    ]
}


def get_material(name: str) -> Material:
    """Look up a material by name (case- and space-insensitive)."""
    key = name.replace(" ", "").lower()
    for mname, mat in MATERIALS.items():
        if mname.replace(" ", "").lower() == key:
            return mat
    known = ", ".join(MATERIALS)
    raise KeyError(f"Unknown material '{name}'. Known materials: {known}")
