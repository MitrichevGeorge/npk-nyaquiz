from backend.services.run_service import _build_results_payload, _strip_question_for_live


SAMPLE_QUESTION = {
    "id": "q1",
    "prompt": "Решите $\\frac{a}{b}$",
    "explanation": "Секретное пояснение",
    "sandbox_html": "<div>interactive</div>",
    "options": [
        {"id": "a", "text": "1", "is_correct": True},
        {"id": "b", "text": "2", "is_correct": False},
    ],
}


def test_live_question_never_leaks_answers_or_explanation():
    rules = {"show_question_text": True, "show_options": True}
    payload = _strip_question_for_live(SAMPLE_QUESTION, rules)
    assert "explanation" not in payload
    assert "stats" not in payload
    for opt in payload["options"]:
        assert "is_correct" not in opt


def test_live_question_respects_hidden_rules():
    rules = {"show_question_text": False, "show_options": False}
    payload = _strip_question_for_live(SAMPLE_QUESTION, rules)
    assert "prompt" not in payload
    assert "options" not in payload
    assert "sandbox_html" not in payload


def test_results_payload_respects_visibility_switches():
    rules = {
        "show_question_text": True,
        "show_options": True,
        "show_correct_on_results": False,
        "show_explanation_on_results": False,
        "show_stats_on_results": False,
    }
    payload = _build_results_payload(SAMPLE_QUESTION, {"answered": 10, "options": {"a": 6}}, rules)
    assert "explanation" not in payload
    assert "stats" not in payload
    for opt in payload["options"]:
        assert "is_correct" not in opt
