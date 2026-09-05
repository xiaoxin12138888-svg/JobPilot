from __future__ import annotations

from jobpilot_api.application.jd_analysis import (
    CURRENT_JD_ANALYSIS_PROMPT_VERSION,
    JD_ANALYSIS_SYSTEM_PROMPT_V1,
    JD_ANALYSIS_SYSTEM_PROMPT_V2,
    JD_ANALYSIS_SYSTEM_PROMPTS,
)


def test_prompt_v2_is_versioned_generalized_and_covers_observed_bad_case_rules() -> None:
    assert JD_ANALYSIS_SYSTEM_PROMPTS == {
        "v1": JD_ANALYSIS_SYSTEM_PROMPT_V1,
        "v2": JD_ANALYSIS_SYSTEM_PROMPT_V2,
    }
    assert CURRENT_JD_ANALYSIS_PROMPT_VERSION == "v2"
    assert JD_ANALYSIS_SYSTEM_PROMPT_V2 != JD_ANALYSIS_SYSTEM_PROMPT_V1

    required_rules = (
        "最小且完整的连续原文子句",
        "不要同义改写",
        "不要擅自拆分",
        "所有明确硬性要求的总视图",
        "不限制、未限定、未说明、无要求、不要求",
        "只记录明确的硬性经历",
        "可选经历只能进入 preferredRequirements",
        "不得从职责、领域关键词、证书或加分项自动派生",
        "公司介绍和福利不是岗位要求",
        "不可信",
    )
    for rule in required_rules:
        assert rule in JD_ANALYSIS_SYSTEM_PROMPT_V2

    dataset_specific_text = (
        "jd-001",
        "jd-020",
        "零售行业分析经验",
        "临床医学或药学硕士",
        "PMP",
        "CISSP",
    )
    for text in dataset_specific_text:
        assert text not in JD_ANALYSIS_SYSTEM_PROMPT_V2
    assert len(JD_ANALYSIS_SYSTEM_PROMPT_V2) < 2_500
