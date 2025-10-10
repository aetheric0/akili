def calculate_xp_gain(duration_minutes: float) -> int:
    """
    Basic XP calculation:
    - 5 XP per minute
    - +20 bonus for >= 60 minutes
    """
    if duration_minutes < 1:
        return 0
    base_xp = duration_minutes * 5
    bonus = 20 if duration_minutes >= 60 else 0
    return int(base_xp + bonus)
