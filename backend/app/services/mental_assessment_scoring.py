"""Definition-driven mental self-assessment scoring.

No LLM is involved.  Scorers only operate on an approved definition containing
questions and scoring ranges.  Until such a definition is configured, requests
are rejected with a stable business code instead of guessing a clinical score.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.mental_assessment_definitions import (
    QUESTIONNAIRE_NOT_CONFIGURED,
    get_assessment_definition,
)


class QuestionnaireNotConfiguredError(ValueError):
    code = "QUESTIONNAIRE_NOT_CONFIGURED"


class InvalidAssessmentAnswersError(ValueError):
    code = "ASSESSMENT_ANSWERS_INVALID"


@dataclass(frozen=True)
class AssessmentScore:
    score: int
    level: str
    summary: dict
    raw_score: int | None = None
    percentage_score: int | None = None
    needs_follow_up: bool = False
    safety_flag: bool = False
    safety_reason: str | None = None


class DefinitionScorer:
    """Generic scorer used by each named scale once official config exists."""

    def score(self, definition: dict, answers: list[dict]) -> AssessmentScore:
        questions = definition.get("questions") or []
        scoring = definition.get("scoring") or {}
        if definition.get("questionnaire_status") != "configured" or not questions or not scoring:
            raise QuestionnaireNotConfiguredError(QUESTIONNAIRE_NOT_CONFIGURED)
        expected = {item["id"] for item in questions}
        submitted = {item.get("question_id") for item in answers}
        if expected != submitted:
            raise InvalidAssessmentAnswersError("answers must cover every configured question exactly once")
        values = [item.get("value") for item in answers]
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            raise InvalidAssessmentAnswersError("answer values must be integers")
        allowed_values = {
            question["id"]: {option["value"] for option in question.get("options", [])}
            for question in questions
        }
        if any(item["value"] not in allowed_values.get(item["question_id"], set()) for item in answers):
            raise InvalidAssessmentAnswersError("answer values are outside configured options")
        submitted_values = {item["question_id"]: item["value"] for item in answers}
        reverse_question_ids = set(scoring.get("reverse_question_ids") or [])
        score = sum(
            4 - value if question_id in reverse_question_ids else value
            for question_id, value in submitted_values.items()
        )
        if not scoring.get("ranges"):
            return self._score_without_ranges(definition, score)
        ranges = scoring.get("ranges") or []
        matched = next((item for item in ranges if item["min"] <= score <= item["max"]), None)
        if matched is None:
            raise InvalidAssessmentAnswersError("score is outside configured ranges")
        level = matched["level"]
        display_level = matched.get("display_level") or {
            "minimal": "最低症状范围", "mild": "轻度症状范围", "moderate": "中度症状范围",
            "moderately_severe": "中重度症状范围", "severe": "较高症状范围",
        }.get(level, level)
        needs_follow_up = score >= int(scoring.get("follow_up_threshold", 10_000))
        safety_rule = next((rule for rule in scoring.get("safety_rules", []) if submitted_values.get(rule["question_id"], 0) > rule.get("value", 0)), None)
        safety_flag = safety_rule is not None
        return AssessmentScore(
            score=score, level=level,
            summary={"disclaimer": definition["disclaimer"], "result_note": definition.get("result_note", definition["disclaimer"]), "display_level": display_level, "max_score": scoring.get("max"), "needs_follow_up": needs_follow_up, "safety_flag": safety_flag},
            raw_score=score, needs_follow_up=needs_follow_up, safety_flag=safety_flag,
            safety_reason="PHQ9_ITEM9_POSITIVE" if safety_flag else None,
        )

    def _score_without_ranges(self, definition: dict, score: int) -> AssessmentScore:
        scoring = definition["scoring"]
        percentage = score * int(scoring.get("percentage_multiplier", 1))
        level = "adequate_wellbeing" if score >= int(scoring.get("cutoff", 0)) else "low_wellbeing"
        return AssessmentScore(
            score=score, raw_score=score, percentage_score=percentage, level=level,
            summary={
                "disclaimer": definition["disclaimer"], "display_level": "幸福感状态良好" if level == "adequate_wellbeing" else "幸福感偏低，建议持续关注",
                "max_score": scoring.get("max"), "percentage_score": percentage, "needs_follow_up": False, "safety_flag": False,
            },
        )


class WHO5Scorer(DefinitionScorer):
    pass


class PSS10Scorer(DefinitionScorer):
    pass


class GAD7Scorer(DefinitionScorer):
    pass


class PHQ9Scorer(DefinitionScorer):
    pass


class MentalAssessmentScoringService:
    _scorers = {"WHO-5": WHO5Scorer(), "PSS-10": PSS10Scorer(), "GAD-7": GAD7Scorer(), "PHQ-9": PHQ9Scorer()}

    def score(self, assessment_type: str, version: str, answers: list[dict]) -> AssessmentScore:
        definition = get_assessment_definition(assessment_type, version)
        return self._scorers[assessment_type].score(definition, answers)
