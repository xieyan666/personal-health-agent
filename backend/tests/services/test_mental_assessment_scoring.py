import pytest

from backend.app.services.mental_assessment_definitions import (
    QUESTIONNAIRE_CONFIGURED,
    get_assessment_definition,
    list_assessment_definitions,
)
from backend.app.services.mental_assessment_scoring import (
    InvalidAssessmentAnswersError,
    MentalAssessmentScoringService,
)


def _answers(definition: dict, values: list[int]) -> list[dict]:
    return [
        {"question_id": question["id"], "value": value}
        for question, value in zip(definition["questions"], values, strict=True)
    ]


def test_four_confirmed_questionnaires_expose_server_owned_questions():
    definitions = {item["assessment_type"]: item for item in list_assessment_definitions()}

    assert definitions["WHO-5"]["questionnaire_status"] == QUESTIONNAIRE_CONFIGURED
    assert definitions["GAD-7"]["questionnaire_status"] == QUESTIONNAIRE_CONFIGURED
    assert definitions["PHQ-9"]["questionnaire_status"] == QUESTIONNAIRE_CONFIGURED
    assert definitions["PSS-10"]["questionnaire_status"] == QUESTIONNAIRE_CONFIGURED
    assert len(definitions["WHO-5"]["questions"]) == 5
    assert len(definitions["GAD-7"]["questions"]) == 7
    assert len(definitions["PHQ-9"]["questions"]) == 9
    assert len(definitions["PSS-10"]["questions"]) == 10


def test_who5_returns_raw_and_percentage_score():
    definition = get_assessment_definition("WHO-5")
    result = MentalAssessmentScoringService().score("WHO-5", definition["version"], _answers(definition, [5, 4, 3, 2, 3]))

    assert result.raw_score == 17
    assert result.percentage_score == 68
    assert result.level == "adequate_wellbeing"
    assert result.summary["display_level"] == "幸福感状态良好"


def test_gad7_uses_rules_for_follow_up_not_llm():
    definition = get_assessment_definition("GAD-7")
    result = MentalAssessmentScoringService().score("GAD-7", definition["version"], _answers(definition, [2, 2, 2, 1, 1, 1, 1]))

    assert result.score == 10
    assert result.level == "moderate"
    assert result.needs_follow_up is True
    assert result.safety_flag is False


def test_phq9_positive_safety_item_sets_structured_safety_flag():
    definition = get_assessment_definition("PHQ-9")
    result = MentalAssessmentScoringService().score("PHQ-9", definition["version"], _answers(definition, [0, 0, 0, 0, 0, 0, 0, 0, 1]))

    assert result.safety_flag is True
    assert result.safety_reason == "PHQ9_ITEM9_POSITIVE"
    assert result.summary["safety_flag"] is True


def test_scoring_rejects_answers_outside_definition_options():
    definition = get_assessment_definition("GAD-7")
    with pytest.raises(InvalidAssessmentAnswersError):
        MentalAssessmentScoringService().score("GAD-7", definition["version"], _answers(definition, [4] * 7))


def test_pss10_reverse_scores_items_4_5_7_8_and_uses_non_diagnostic_display_level():
    definition = get_assessment_definition("PSS-10")
    # q4/q5/q7/q8 are reverse-scored: all 4s become 0; the six remaining
    # 4s remain 4, producing 24 rather than a raw input sum of 40.
    result = MentalAssessmentScoringService().score("PSS-10", definition["version"], _answers(definition, [4] * 10))

    assert result.score == 24
    assert result.raw_score == 24
    assert result.level == "pss_noticeable"
    assert result.summary["display_level"] == "近期主观压力感受较明显"
