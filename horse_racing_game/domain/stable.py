from dataclasses import dataclass

from horse_racing_game.domain.horse import Horse, HorseStats


@dataclass(frozen=True)
class Stable:
    stable_id: str
    name: str
    focus: str
    description: str
    speed_modifier: float = 1.0
    stamina_modifier: float = 1.0
    handling_modifier: float = 1.0
    calm_modifier: float = 1.0


def apply_stable_boost(horse: Horse, stable: Stable) -> Horse:
    stats = horse.stats
    return Horse(
        horse_id=horse.horse_id,
        name=horse.name,
        role=horse.role,
        preferred_surface=horse.preferred_surface,
        signature_sound=horse.signature_sound,
        stats=HorseStats(
            max_speed_mps=stats.max_speed_mps * stable.speed_modifier,
            acceleration=stats.acceleration,
            stamina_capacity=stats.stamina_capacity * stable.stamina_modifier,
            stamina_recovery=stats.stamina_recovery,
            handling=stats.handling * stable.handling_modifier,
            nervousness=max(0.0, stats.nervousness * stable.calm_modifier),
        ),
        traits=horse.traits + (f"stable_{stable.stable_id}",),
    )
