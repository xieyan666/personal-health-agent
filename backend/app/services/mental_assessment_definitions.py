"""Versioned, server-owned mental self-assessment definitions.

Questionnaire content is deliberately kept out of React. Each completed record
stores the definition version, so future wording changes do not alter history.
"""

from __future__ import annotations

from copy import deepcopy


QUESTIONNAIRE_CONFIGURED = "configured"
QUESTIONNAIRE_NOT_CONFIGURED = "questionnaire_not_configured"
DISCLAIMER = "测评结果仅用于心理健康筛查与自我了解，不构成医学诊断。"
FREQUENCY_OPTIONS = [
    {"label": "完全不会", "value": 0}, {"label": "有几天", "value": 1},
    {"label": "一半以上的天数", "value": 2}, {"label": "几乎每天", "value": 3},
]
WHO5_OPTIONS = [
    {"label": "所有时间", "value": 5}, {"label": "大部分时间", "value": 4},
    {"label": "超过一半的时间", "value": 3}, {"label": "少于一半的时间", "value": 2},
    {"label": "有时候", "value": 1}, {"label": "从未有过", "value": 0},
]
PSS10_OPTIONS = [
    {"label": "从不", "value": 0}, {"label": "几乎不", "value": 1},
    {"label": "有时", "value": 2}, {"label": "相当多", "value": 3},
    {"label": "总是", "value": 4},
]


def _questions(prefix: str, texts: list[str], options: list[dict], safety_question: int | None = None) -> list[dict]:
    return [
        {
            "id": f"{prefix}_q{index}", "order": index, "text": text, "required": True,
            "options": deepcopy(options), "safety_sensitive": index == safety_question,
        }
        for index, text in enumerate(texts, start=1)
    ]


def _configured(assessment_type: str, version: str, title: str, description: str, questions: list[dict], scoring: dict, source: dict, period: str = "过去两周", estimated_duration: str | None = None, result_note: str | None = None) -> dict:
    return {
        "assessment_type": assessment_type, "version": version, "name": assessment_type, "title": title,
        "period": period, "description": description, "question_count": len(questions),
        "estimated_minutes": 1 if assessment_type == "WHO-5" else 2,
        "estimated_duration": estimated_duration or f"约 {1 if assessment_type == 'WHO-5' else 2} 分钟",
        "result_usage": "用于心理健康筛查与自我了解，帮助你关注近期状态变化。",
        "disclaimer": DISCLAIMER, "questionnaire_status": QUESTIONNAIRE_CONFIGURED,
        "questions": questions, "scoring": scoring, "source": source, "enabled": True,
        "result_note": result_note or DISCLAIMER,
    }


_DEFINITIONS = {
    "WHO-5": _configured(
        "WHO-5", "WHO-2024-ZH-CN", "幸福感自评", "用于了解过去两周的主观幸福感状态。",
        _questions("who5", [
            "我感觉快乐、心情舒畅", "我感觉宁静和放松", "我感觉充满活力、精力充沛",
            "我睡醒时感到清新、得到了足够休息", "我每天生活充满了有趣的事情",
        ], WHO5_OPTIONS),
        {"method": "sum", "min": 0, "max": 25, "percentage_multiplier": 4, "cutoff": 13, "higher_is_better": True},
        {"source_name": "World Health Organization", "source_version": "WHO-5 Chinese PR / 2024 publication", "source_url": "https://www.who.int/publications/m/item/WHO-UCN-MSD-MHE-2024.01", "license": "CC BY-NC-SA 3.0 IGO"},
    ),
    "GAD-7": _configured(
        "GAD-7", "validated-zh-v1", "焦虑症状筛查", "用于了解过去两周的焦虑相关自评状态。",
        _questions("gad7", [
            "感觉紧张、焦虑或急切", "不能够停止或控制担忧", "对各种各样的事情担忧过多", "很难放松下来",
            "由于不安而无法静坐", "变得容易烦恼或急躁", "感到好像有什么可怕的事会发生",
        ], FREQUENCY_OPTIONS),
        {"method": "sum", "min": 0, "max": 21, "ranges": [
            {"min": 0, "max": 4, "level": "minimal"}, {"min": 5, "max": 9, "level": "mild"},
            {"min": 10, "max": 14, "level": "moderate"}, {"min": 15, "max": 21, "level": "severe"},
        ], "follow_up_threshold": 10},
        {"source_name": "Spitzer et al.", "source_version": "validated Chinese version v1", "source_url": "https://www.phqscreeners.com/", "license": "confirmed project use"},
    ),
    "PHQ-9": _configured(
        "PHQ-9", "validated-zh-v1", "抑郁症状筛查", "用于了解过去两周的情绪低落相关自评状态。",
        _questions("phq9", [
            "做事时提不起劲或没有兴趣", "感到心情低落、沮丧或绝望", "入睡困难、睡不安稳或睡眠过多",
            "感觉疲倦或没有活力", "食欲不振或吃太多", "觉得自己很糟，或觉得自己很失败，或让自己或家人失望",
            "对事物专注有困难，例如阅读报纸或看电视时", "动作或说话速度缓慢到别人已经察觉，或正好相反——烦躁或坐立不安、动来动去的情况更胜于平常",
            "有不如死掉或用某种方式伤害自己的念头",
        ], FREQUENCY_OPTIONS, safety_question=9),
        {"method": "sum", "min": 0, "max": 27, "ranges": [
            {"min": 0, "max": 4, "level": "minimal"}, {"min": 5, "max": 9, "level": "mild"},
            {"min": 10, "max": 14, "level": "moderate"}, {"min": 15, "max": 19, "level": "moderately_severe"},
            {"min": 20, "max": 27, "level": "severe"},
        ], "safety_rules": [{"question_id": "phq9_q9", "operator": ">", "value": 0, "action": "mental_health_safety_flow"}]},
        {"source_name": "Kroenke et al.", "source_version": "validated Chinese version v1", "source_url": "https://www.phqscreeners.com/", "license": "confirmed project use"},
    ),
    "PSS-10": _configured(
        "PSS-10", "CPSS10-zh-CN-v1", "压力感受自评", "用于了解过去一个月的主观压力感受状态。",
        _questions("pss10", [
            "在过去一个月里，有多少次您因为发生了一些意外的事情而感到心烦意乱？",
            "在过去一个月里，有多少次您感觉到不能控制生活中的重要事情？",
            "在过去一个月里，有多少次您感到紧张不安和压力？",
            "在过去一个月里，有多少次您很有信心地能够处理好个人生活中恼人的问题？",
            "在过去一个月里，有多少次您感到事情正按您的意愿进行？",
            "在过去一个月里，有多少次您发现自己无法应付必须去做的所有事情？",
            "在过去一个月里，有多少次您能够控制生活中令人恼火的事情？",
            "在过去一个月里，有多少次您感觉到自己掌控着事情？",
            "在过去一个月里，有多少次您因为发生了自己无法控制的事情而感到气愤？",
            "在过去一个月里，有多少次您觉得困难堆积如山，以至于无法克服？",
        ], PSS10_OPTIONS),
        {
            "method": "sum_with_reverse_items", "min": 0, "max": 40,
            "reverse_question_ids": ["pss10_q4", "pss10_q5", "pss10_q7", "pss10_q8"],
            "ranges": [
                {"min": 0, "max": 10, "level": "pss_low", "display_level": "近期主观压力感受相对较低"},
                {"min": 11, "max": 20, "level": "pss_some", "display_level": "近期存在一定主观压力感受"},
                {"min": 21, "max": 30, "level": "pss_noticeable", "display_level": "近期主观压力感受较明显"},
                {"min": 31, "max": 40, "level": "pss_high", "display_level": "近期主观压力感受较高，建议持续关注近期状态"},
            ],
        },
        {"source_name": "Perceived Stress Scale (PSS-10)", "source_version": "Simplified Chinese version / project-confirmed use", "source_url": "https://eprovide.mapi-trust.org/instruments/perceived-stress-scale-10-items", "license": "confirmed project use"},
        period="过去一个月",
        estimated_duration="约 2~3 分钟",
        result_note="分数越高表示近期感受到的压力越高。该结果用于状态了解和趋势跟踪，不构成医学诊断。",
    ),
}


def list_assessment_definitions() -> list[dict]:
    return [deepcopy(item) for item in _DEFINITIONS.values()]


def get_assessment_definition(assessment_type: str, version: str | None = None) -> dict:
    definition = _DEFINITIONS.get(assessment_type)
    if definition is None:
        raise KeyError(assessment_type)
    if version is not None and version != definition["version"]:
        raise LookupError(version)
    return deepcopy(definition)
