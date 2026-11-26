from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    mode: str = "all_or_nothing"
    base_points: float = 1000.0
    min_points: float = 0.0
    max_points: float = 1000.0
    coeff_a: float | None = None
    coeff_b: float = 0.0
    coeff_c: float = 0.0
    coeff_d: float = 0.0
    custom_map: dict[int, float] | None = None
    speed_bonus_enabled: bool = False
    k_max: float = 1.0
    k_min: float = 0.5
    t0_seconds: float = 0.0


def compute_speed_multiplier(
    answer_time_ms: int,
    duration_seconds: float,
    k_max: float = 1.0,
    k_min: float = 0.5,
    t0_seconds: float = 0.0,
) -> float:
    if duration_seconds <= 0:
        return k_max
    t = max(0.0, min(answer_time_ms / 1000.0, duration_seconds))
    if t <= t0_seconds or duration_seconds <= t0_seconds:
        return k_max
    return k_max - (k_max - k_min) * (t - t0_seconds) / (duration_seconds - t0_seconds)


def score_question(
    option_ids: list[str],
    correct_ids: set[str],
    selected_ids: set[str],
    config: ScoringConfig,
    answer_time_ms: int,
    duration_seconds: float,
) -> float:
    total_correct = len(correct_ids)
    tp = len(selected_ids & correct_ids)
    fp = len(selected_ids - correct_ids)
    fn = len(correct_ids - selected_ids)
    tn = len(set(option_ids) - correct_ids - selected_ids)

    if config.mode == "all_or_nothing":
        raw = config.base_points if selected_ids == correct_ids else 0.0
    elif config.mode == "per_item":
        default_a = (config.base_points / total_correct) if total_correct > 0 else 0.0
        a = default_a if config.coeff_a is None else config.coeff_a
        raw = tp * a + fp * config.coeff_b + tn * config.coeff_c + fn * config.coeff_d
    elif config.mode == "by_correct_count":
        if total_correct == 0 or fp > 0:
            raw = 0.0
        else:
            raw = config.base_points * (tp / total_correct)
    elif config.mode == "custom":
        mapping = config.custom_map or {}
        raw = float(mapping.get(tp, 0.0)) if fp == 0 else 0.0
    else:
        raw = 0.0

    clamped = max(config.min_points, min(config.max_points, raw))
    if config.speed_bonus_enabled and clamped > 0:
        multiplier = compute_speed_multiplier(
            answer_time_ms=answer_time_ms,
            duration_seconds=duration_seconds,
            k_max=config.k_max,
            k_min=config.k_min,
            t0_seconds=config.t0_seconds,
        )
        return round(clamped * multiplier, 2)
    return round(clamped, 2)


def rank_participants(entries: list[dict]) -> list[dict]:
    ordered = sorted(
        entries,
        key=lambda item: (-float(item["total_score"]), int(item["total_time_ms"])),
    )
    ranked: list[dict] = []
    prev_key = None
    prev_rank = 0
    for idx, item in enumerate(ordered, start=1):
        key = (float(item["total_score"]), int(item["total_time_ms"]))
        rank = prev_rank if key == prev_key else idx
        prev_key = key
        prev_rank = rank
        ranked.append({**item, "rank": rank})
    return ranked
