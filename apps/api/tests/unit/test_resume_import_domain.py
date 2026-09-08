from __future__ import annotations

import pytest

from jobpilot_api.domain.autofill_profiles import (
    AutofillProfileDraft,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
)
from jobpilot_api.domain.resume_imports import (
    DocumentBlock,
    DocumentBlockKind,
    ParsedResumeDocument,
    ResumeFileType,
    ResumeImportError,
    ResumeProfileImportPatch,
    ResumeSectionKind,
    build_resume_import_preview,
    merge_autofill_profile,
)


def test_structure_parser_detects_only_explicit_headings_and_keeps_order() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=(
            "基本信息\n张三\n电话：13800138000\n邮箱：candidate@example.invalid\n"
            "教育经历\n学校：示例大学\n专业：信息管理\n学历：本科\n"
            "时间：2022.09 - 2026.06\n"
            "项目经历\n在项目中负责用户访谈\n"
            "工作经历\n公司：示例公司\n职位：产品实习生\n"
            "时间：2025/01 至 2025/06\n专业技能\nPython、SQL、Figma"
        ),
        blocks=(
            DocumentBlock(DocumentBlockKind.TEXT, "基本信息"),
            DocumentBlock(DocumentBlockKind.TEXT, "张三"),
            DocumentBlock(DocumentBlockKind.TEXT, "电话：13800138000"),
            DocumentBlock(DocumentBlockKind.TEXT, "邮箱：candidate@example.invalid"),
            DocumentBlock(DocumentBlockKind.TEXT, "教育经历"),
            DocumentBlock(DocumentBlockKind.TEXT, "学校：示例大学"),
            DocumentBlock(DocumentBlockKind.TEXT, "专业：信息管理"),
            DocumentBlock(DocumentBlockKind.TEXT, "学历：本科"),
            DocumentBlock(DocumentBlockKind.TEXT, "时间：2022.09 - 2026.06"),
            DocumentBlock(DocumentBlockKind.TEXT, "项目经历"),
            DocumentBlock(DocumentBlockKind.TEXT, "在项目中负责用户访谈"),
            DocumentBlock(DocumentBlockKind.TEXT, "工作经历"),
            DocumentBlock(DocumentBlockKind.TEXT, "公司：示例公司"),
            DocumentBlock(DocumentBlockKind.TEXT, "职位：产品实习生"),
            DocumentBlock(DocumentBlockKind.TEXT, "时间：2025/01 至 2025/06"),
            DocumentBlock(DocumentBlockKind.TEXT, "专业技能"),
            DocumentBlock(DocumentBlockKind.TEXT, "Python、SQL、Figma"),
        ),
    )

    preview = build_resume_import_preview(document)

    assert [section.kind for section in preview.sections] == [
        ResumeSectionKind.BASIC,
        ResumeSectionKind.EDUCATION,
        ResumeSectionKind.PROJECT,
        ResumeSectionKind.EXPERIENCE,
        ResumeSectionKind.SKILLS,
    ]
    assert preview.sections[2].text == "在项目中负责用户访谈"
    assert preview.profile_candidates.personal.name == "张三"
    assert preview.profile_candidates.personal.phone == "13800138000"
    assert preview.profile_candidates.personal.email == "candidate@example.invalid"
    assert preview.profile_candidates.education[0].school == "示例大学"
    assert preview.profile_candidates.education[0].major == "信息管理"
    assert preview.profile_candidates.education[0].degree == "本科"
    assert preview.profile_candidates.education[0].start == "2022-09"
    assert preview.profile_candidates.education[0].end == "2026-06"
    assert preview.profile_candidates.experience[0].company == "示例公司"
    assert preview.profile_candidates.experience[0].position == "产品实习生"
    assert preview.profile_candidates.experience[0].start == "2025-01"
    assert preview.profile_candidates.experience[0].end == "2025-06"


def test_structure_parser_does_not_split_on_heading_word_inside_body() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.PDF,
        raw_text="个人总结\n在项目中负责需求分析，也参与教育产品调研。",
        blocks=(
            DocumentBlock(DocumentBlockKind.TEXT, "个人总结"),
            DocumentBlock(DocumentBlockKind.TEXT, "在项目中负责需求分析，也参与教育产品调研。"),
        ),
        page_count=1,
    )

    preview = build_resume_import_preview(document)

    assert [section.kind for section in preview.sections] == [ResumeSectionKind.OTHER]
    assert preview.extracted_text == document.raw_text
    assert preview.profile_candidates.education == ()
    assert preview.profile_candidates.experience == ()
    assert "未识别到明确的教育经历" in [warning.message for warning in preview.warnings]


def test_multiple_labeled_education_and_experience_entries_remain_partial_facts() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=(
            "教育背景\n学校：甲大学\n专业：软件工程\n时间：2018-09 - 2022-06\n"
            "学校：乙大学\n时间：2022-09 - 至今\n"
            "实习经历\n公司：甲公司\n职位：产品实习生\n"
            "公司：乙公司\n职位：助理"
        ),
        blocks=tuple(
            DocumentBlock(DocumentBlockKind.TEXT, line)
            for line in (
                "教育背景",
                "学校：甲大学",
                "专业：软件工程",
                "时间：2018-09 - 2022-06",
                "学校：乙大学",
                "时间：2022-09 - 至今",
                "实习经历",
                "公司：甲公司",
                "职位：产品实习生",
                "公司：乙公司",
                "职位：助理",
            )
        ),
    )

    candidates = build_resume_import_preview(document).profile_candidates

    assert len(candidates.education) == 2
    assert candidates.education[1].school == "乙大学"
    assert candidates.education[1].degree is None
    assert candidates.education[1].start == "2022-09"
    assert candidates.education[1].end is None
    assert len(candidates.experience) == 2
    assert candidates.experience[1].company == "乙公司"
    assert candidates.experience[1].position == "助理"


def test_common_unlabeled_table_rows_are_parsed_only_when_core_facts_are_clear() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=(
            "教育经历\n示例大学 | 信息管理 | 本科 | 2022.09 - 2026.06\n"
            "工作经历\n示例科技有限公司 | 产品实习生 | 2025.01 - 2025.06\n"
            "参与项目调研 | 需求分析"
        ),
        blocks=(
            DocumentBlock(DocumentBlockKind.TEXT, "教育经历"),
            DocumentBlock(
                DocumentBlockKind.TABLE_ROW,
                "示例大学 | 信息管理 | 本科 | 2022.09 - 2026.06",
            ),
            DocumentBlock(DocumentBlockKind.TEXT, "工作经历"),
            DocumentBlock(
                DocumentBlockKind.TABLE_ROW,
                "示例科技有限公司 | 产品实习生 | 2025.01 - 2025.06",
            ),
            DocumentBlock(DocumentBlockKind.TABLE_ROW, "参与项目调研 | 需求分析"),
        ),
    )

    candidates = build_resume_import_preview(document).profile_candidates

    assert candidates.education == (
        EducationEntry("示例大学", "信息管理", "本科", "2022-09", "2026-06"),
    )
    assert candidates.experience == (
        ExperienceEntry("示例科技有限公司", "产品实习生", "2025-01", "2025-06", None),
    )


def test_dated_unlabeled_lines_map_clear_education_and_internship_facts() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=(
            "实习经历\n"
            "2024.12 — 2025.02 示例研究所 运维实习生（系统验收）\n"
            "参与系统验收并跟进问题闭环。\n"
            "教育经历\n"
            "2025.09 — 至今 示例理工大学 硕士｜电子信息\n"
            "2021.09 — 2025.07 示例师范大学 本科｜计算机科学与技术\n"
            "项目经历\n"
            "2026.06 — 2026.08 JobPilot：本地求职工作台\n"
            "产品设计：完成需求分析与交互原型。\n"
            "项目推进：完成阶段验收。\n"
            "2025.10 — 2025.12 K-Chat：个人知识库问答助手\n"
            "方案落地：实现文档检索与问答链路。"
        ),
        blocks=tuple(
            DocumentBlock(DocumentBlockKind.TEXT, line)
            for line in (
                "实习经历",
                "2024.12 — 2025.02 示例研究所 运维实习生（系统验收）",
                "参与系统验收并跟进问题闭环。",
                "教育经历",
                "2025.09 — 至今 示例理工大学 硕士｜电子信息",
                "2021.09 — 2025.07 示例师范大学 本科｜计算机科学与技术",
                "项目经历",
                "2026.06 — 2026.08 JobPilot：本地求职工作台",
                "产品设计：完成需求分析与交互原型。",
                "项目推进：完成阶段验收。",
                "2025.10 — 2025.12 K-Chat：个人知识库问答助手",
                "方案落地：实现文档检索与问答链路。",
            )
        ),
    )

    candidates = build_resume_import_preview(document).profile_candidates

    assert candidates.experience == (
        ExperienceEntry("示例研究所", "运维实习生（系统验收）", "2024-12", "2025-02", None),
    )
    assert candidates.education == (
        EducationEntry("示例理工大学", "电子信息", "硕士", "2025-09", None),
        EducationEntry("示例师范大学", "计算机科学与技术", "本科", "2021-09", "2025-07"),
    )
    assert candidates.projects == (
        ProjectEntry(
            "JobPilot",
            None,
            "2026-06",
            "2026-08",
            "本地求职工作台\n产品设计：完成需求分析与交互原型。\n项目推进：完成阶段验收。",
        ),
        ProjectEntry(
            "K-Chat",
            None,
            "2025-10",
            "2025-12",
            "个人知识库问答助手\n方案落地：实现文档检索与问答链路。",
        ),
    )


def test_dated_narrative_lines_are_not_mapped_as_profile_rows() -> None:
    document = ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=(
            "实习经历\n"
            "2024.12 — 2025.02 参与研究所 项目交付与问题跟进\n"
            "教育经历\n"
            "2021.09 — 2025.07 示例大学 参与课程调研"
        ),
        blocks=(
            DocumentBlock(DocumentBlockKind.TEXT, "实习经历"),
            DocumentBlock(
                DocumentBlockKind.TEXT,
                "2024.12 — 2025.02 参与研究所 项目交付与问题跟进",
            ),
            DocumentBlock(DocumentBlockKind.TEXT, "教育经历"),
            DocumentBlock(
                DocumentBlockKind.TEXT,
                "2021.09 — 2025.07 示例大学 参与课程调研",
            ),
        ),
    )

    candidates = build_resume_import_preview(document).profile_candidates

    assert candidates.experience == ()
    assert candidates.education == ()


def test_profile_patch_changes_only_selected_scalars_and_appends_selected_rows() -> None:
    current_draft = AutofillProfileDraft.create(
        personal={
            "name": "当前姓名",
            "phone": "13000000000",
            "email": "current@example.invalid",
            "currentCity": "北京",
        },
        education=[{"school": "既有大学", "major": "数学"}],
        experience=[{"company": "既有公司", "position": "助理"}],
        projects=[{"name": "既有项目", "role": "成员"}],
        links={"github": "https://github.com/current"},
    )
    patch = ResumeProfileImportPatch.create(
        personal={"phone": "13800138000"},
        education=[{"school": "新增大学", "major": "信息管理"}],
        experience=[{"company": "新增公司", "position": "产品实习生"}],
        projects=[{"name": "新增项目", "role": "负责人"}],
        links={},
    )

    merged = merge_autofill_profile(current_draft, patch)

    assert merged.personal.name == "当前姓名"
    assert merged.personal.phone == "13800138000"
    assert merged.personal.email == "current@example.invalid"
    assert merged.personal.current_city == "北京"
    assert [item.school for item in merged.education] == ["既有大学", "新增大学"]
    assert [item.company for item in merged.experience] == ["既有公司", "新增公司"]
    assert [item.name for item in merged.projects] == ["既有项目", "新增项目"]
    assert merged.links.github == "https://github.com/current"


def test_profile_patch_rejects_null_or_blank_selected_scalars() -> None:
    for personal in ({"phone": None}, {"email": "  "}):
        with pytest.raises(ResumeImportError) as error:
            ResumeProfileImportPatch.create(
                personal=personal, education=[], experience=[], links={}
            )
        assert error.value.code == "VALIDATION_ERROR"
