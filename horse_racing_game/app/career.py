CAREER_LENGTH = 6
MAX_CAREER_ENERGY = 3
DEFAULT_CAREER_ENERGY = 2


def points_for_rank(rank: int) -> int:
    if rank <= 1:
        return 10
    if rank == 2:
        return 7
    if rank == 3:
        return 5
    if rank == 4:
        return 3
    if rank == 5:
        return 1
    return 0


def career_title(points: int, races_completed: int, career_length: int = CAREER_LENGTH) -> str:
    if races_completed < career_length:
        return f"Career race {races_completed + 1} of {career_length}. {points} points."
    if points >= 24:
        return f"Champion season complete. {points} points."
    if points >= 15:
        return f"Strong season complete. {points} points."
    return f"Rookie season complete. {points} points."


def clamp_career_energy(energy: int) -> int:
    return min(max(energy, 0), MAX_CAREER_ENERGY)


def career_energy_modifier(energy: int) -> float:
    bounded = clamp_career_energy(energy)
    if bounded <= 0:
        return 1.05
    if bounded >= MAX_CAREER_ENERGY:
        return 0.98
    return 1.0


def career_reward_for_rank(rank: int) -> int:
    return max(points_for_rank(rank), 1)
