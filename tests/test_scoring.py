from shared.scoring import ScoringConfig, compute_speed_multiplier, rank_participants, score_question


def test_speed_bonus_linear_example():
    config = ScoringConfig(
        mode="all_or_nothing",
        base_points=1000.0,
        min_points=0.0,
        max_points=1000.0,
        speed_bonus_enabled=True,
        k_max=1.0,
        k_min=0.5,
        t0_seconds=0.0,
    )
    score_12s = score_question(
        option_ids=["a", "b"],
        correct_ids={"a"},
        selected_ids={"a"},
        config=config,
        answer_time_ms=12000,
        duration_seconds=30.0,
    )
    score_30s = score_question(
        option_ids=["a", "b"],
        correct_ids={"a"},
        selected_ids={"a"},
        config=config,
        answer_time_ms=30000,
        duration_seconds=30.0,
    )
    assert score_12s == 800.0
    assert score_30s == 500.0


def test_speed_multiplier_with_delay():
    assert compute_speed_multiplier(3000, 30.0, k_max=1.0, k_min=0.5, t0_seconds=5.0) == 1.0


def test_per_item_scoring_example():
    config = ScoringConfig(
        mode="per_item",
        base_points=1000.0,
        min_points=0.0,
        max_points=1000.0,
        coeff_a=None,
        coeff_b=0.0,
        coeff_c=0.0,
        coeff_d=0.0,
    )
    opts = ["a", "b", "c", "d"]
    correct = {"a", "b"}
    assert score_question(opts, correct, {"a", "c"}, config, 5000, 30.0) == 500.0
    assert score_question(opts, correct, {"a", "b"}, config, 5000, 30.0) == 1000.0
    assert score_question(opts, correct, {"c", "d"}, config, 5000, 30.0) == 0.0


def test_ranking_tie_breakers():
    entries = [
        {"participant_id": "1", "nickname": "A", "total_score": 1000.0, "total_time_ms": 8000},
        {"participant_id": "2", "nickname": "B", "total_score": 1000.0, "total_time_ms": 5000},
        {"participant_id": "3", "nickname": "C", "total_score": 1000.0, "total_time_ms": 5000},
        {"participant_id": "4", "nickname": "D", "total_score": 500.0, "total_time_ms": 2000},
    ]
    ranked = rank_participants(entries)
    assert [r["participant_id"] for r in ranked] == ["2", "3", "1", "4"]
    assert [r["rank"] for r in ranked] == [1, 1, 3, 4]
