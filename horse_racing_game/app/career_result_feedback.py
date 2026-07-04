def career_result_summary_lines(summary: dict | None) -> tuple[str, ...]:
    if summary is None:
        return ("No completed career result yet.",)
    if not bool(summary.get("finished", True)):
        return (
            "Career attempt incomplete.",
            "No career rewards were paid.",
            f"Rewards balance: {_summary_value(summary, 'rewards_balance')}.",
        )

    base_reward = _summary_value(summary, "base_reward")
    contract_reward = _summary_value(summary, "contract_reward")
    staff_upkeep = _summary_value(summary, "staff_upkeep")
    fatigue_before = _summary_value(summary, "fatigue_before")
    fatigue_after = _summary_value(summary, "fatigue_after")
    injury_days = _summary_value(summary, "injury_days")
    net_reward = _summary_value(summary, "net_reward")
    rewards_balance = _summary_value(summary, "rewards_balance")
    rank = _summary_value(summary, "rank")
    lines = [
        f"Career result: rank {rank}.",
        f"Rewards: base {base_reward} | contract {contract_reward} | staff upkeep {staff_upkeep} | net {net_reward}.",
        f"Condition: fatigue {fatigue_before} to {fatigue_after} | injury days {injury_days}.",
        f"Rewards balance: {rewards_balance}.",
    ]
    difficulty_tier = summary.get("difficulty_tier")
    reward_multiplier = summary.get("reward_multiplier")
    if difficulty_tier and reward_multiplier not in (None, 1.0):
        lines.append(
            f"Difficulty bonus: {difficulty_tier} tier scaled base reward by {reward_multiplier:.2f}x."
        )
    if staff_upkeep != 0:
        lines.append(f"Stable consequence: staff upkeep reduced race earnings by {staff_upkeep}.")
    elif contract_reward != 0:
        lines.append(f"Contract consequence: active sponsor added {contract_reward} rewards.")
    else:
        lines.append("Stable consequence: no staff upkeep was due this race.")
    return tuple(lines)


def career_result_summary_text(summary: dict | None) -> str:
    return " ".join(career_result_summary_lines(summary))


def _summary_value(summary: dict, key: str) -> object:
    return summary.get(key, "?")
