from dataclasses import replace

from horse_racing_game.domain.horse import Horse, HorseStats


MAX_TRAINING_LEVEL = 5


def clamp_training_level(level: int) -> int:
    return min(max(level, 0), MAX_TRAINING_LEVEL)


def next_training_level(level: int, finished: bool) -> int:
    if not finished:
        return clamp_training_level(level)
    return clamp_training_level(level + 1)


def training_intro(horse_name: str, level: int) -> str:
    bounded = clamp_training_level(level)
    return f"Training {horse_name}. Current level {bounded} of {MAX_TRAINING_LEVEL}. Finish to improve control and stamina."


def apply_training_boost(horse: Horse, level: int) -> Horse:
    bounded = clamp_training_level(level)
    if bounded <= 0:
        return horse
    stats = horse.stats
    boosted_stats = HorseStats(
        max_speed_mps=stats.max_speed_mps * (1.0 + bounded * 0.006),
        acceleration=stats.acceleration * (1.0 + bounded * 0.025),
        stamina_capacity=stats.stamina_capacity * (1.0 + bounded * 0.018),
        stamina_recovery=stats.stamina_recovery * (1.0 + bounded * 0.025),
        handling=stats.handling * (1.0 + bounded * 0.02),
        nervousness=max(0.0, stats.nervousness - bounded * 0.18),
    )
    return replace(horse, stats=boosted_stats)
