from __future__ import annotations

from jobpilot_api.application.evidence_maps import EVIDENCE_MAP_SYSTEM_PROMPT_V2


def test_prompt_requires_semantic_grounded_search_without_external_fact_completion() -> None:
    required_rules = (
        "先理解每项 requirement 的实际含义",
        "完整 resumeContent",
        "措辞不需要一致",
        "The wording does not need to match. Judge semantic evidence, not keyword overlap.",
        "不同 section",
        "1 至 3 条",
        "扫描完整简历后",
        "不得虚构毕业年份",
        "未明确提供毕业年份、预计毕业时间或培养年限",
        "事实与判断的关系",
    )
    for rule in required_rules:
        assert rule in EVIDENCE_MAP_SYSTEM_PROMPT_V2

    forbidden_rules = (
        "通常学制",
        "按通常",
        "自动断言",
    )
    for rule in forbidden_rules:
        assert rule not in EVIDENCE_MAP_SYSTEM_PROMPT_V2

    case_specific_text = (
        "负责用户反馈梳理、需求定义并输出 PRD",
        "协同相关人员完成问题确认、修复跟踪及回归验证",
        "3年以上B2B销售经验",
        "2025.09—至今 硕士在读",
    )
    for text in case_specific_text:
        assert text not in EVIDENCE_MAP_SYSTEM_PROMPT_V2
