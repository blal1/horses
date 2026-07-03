"""Per-tick race effects derived from a horse's traits.

Traits are loaded from content (`Horse.traits`) and surfaced in the UI, but
the simulation also reads them here so they actually change how a horse races.
Everything in this module is pure and deterministic — no RNG, no I/O — so it
preserves the engine's "same seed, same race" guarantee.

Each effect is expressed as a multiplier (1.0 = no change) or, for the final
stretch, folded into the speed multiplier so there is a single speed knob.
Effects apply to every runner equally, player and opponent alike.
"""

from dataclasses import dataclass


SOFT_SURFACES = frozenset({"mud", "soft_turf"})


@dataclass(frozen=True)
class TraitEffect:
    speed_multiplier: float = 1.0
    stamina_cost_multiplier: float = 1.0
    acceleration_multiplier: float = 1.0


def trait_effect(
    traits: tuple[str, ...],
    *,
    surface: str,
    weather_id: str,
    curve_intensity: float,
    in_final_stretch: bool,
) -> TraitEffect:
    """Combine every recognised trait into a single multiplier bundle.

    Unknown traits (including the ``stable_*`` markers added by stable boosts)
    are ignored, so new content never breaks the engine.
    """
    speed = 1.0
    stamina = 1.0
    acceleration = 1.0

    for trait in traits:
        if trait == "sprinter":
            # raw top-end speed, paid for with faster stamina burn
            speed *= 1.02
            stamina *= 1.08
        elif trait == "front_runner":
            speed *= 1.01
        elif trait in {"fast_finisher", "late_surge"}:
            if in_final_stretch:
                speed *= 1.06
        elif trait == "quick_start":
            acceleration *= 1.10
        elif trait in {"endurance", "patient_runner"}:
            stamina *= 0.90
        elif trait == "mud_specialist":
            if surface in SOFT_SURFACES:
                speed *= 1.03
        elif trait == "rain_comfort":
            if weather_id == "rain":
                speed *= 1.02
                stamina *= 0.95
        elif trait == "inside_runner":
            # softens the curve slowdown rather than adding flat speed
            speed *= 1.0 + curve_intensity * 0.04

    return TraitEffect(
        speed_multiplier=speed,
        stamina_cost_multiplier=stamina,
        acceleration_multiplier=acceleration,
    )
