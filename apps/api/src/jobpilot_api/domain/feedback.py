from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jobpilot_api.domain.applications import RejectionReason
from jobpilot_api.domain.interviews import QuestionCategory, QuestionPerformance


class FunnelStageName(StrEnum):
    SAVED_JOBS = "SAVED_JOBS"
    APPLICATIONS = "APPLICATIONS"
    INTERVIEW_APPLICATIONS = "INTERVIEW_APPLICATIONS"
    OFFERS = "OFFERS"


@dataclass(frozen=True, slots=True)
class FeedbackTotals:
    saved_jobs: int
    applications: int
    interview_applications: int
    interviews: int
    questions: int
    offers: int
    rejected: int


@dataclass(frozen=True, slots=True)
class FunnelStage:
    stage: FunnelStageName
    count: int
    conversion_rate: float | None


@dataclass(frozen=True, slots=True)
class QuestionCategoryCount:
    category: QuestionCategory
    count: int


@dataclass(frozen=True, slots=True)
class PerformanceCount:
    performance: QuestionPerformance
    count: int


@dataclass(frozen=True, slots=True)
class WeakCategoryCount:
    category: QuestionCategory
    question_count: int
    weak_count: int


@dataclass(frozen=True, slots=True)
class RejectionReasonCount:
    reason: RejectionReason
    count: int


@dataclass(frozen=True, slots=True)
class FeedbackGroupStats:
    applications: int
    interview_applications: int
    offers: int


@dataclass(frozen=True, slots=True)
class SourceFeedbackStats(FeedbackGroupStats):
    source: str


@dataclass(frozen=True, slots=True)
class ResumeVersionFeedbackStats(FeedbackGroupStats):
    resume_version_id: str
    resume_version_name: str


@dataclass(frozen=True, slots=True)
class FeedbackSummary:
    has_data: bool
    totals: FeedbackTotals
    funnel: tuple[FunnelStage, ...]
    question_categories: tuple[QuestionCategoryCount, ...]
    performances: tuple[PerformanceCount, ...]
    weak_categories: tuple[WeakCategoryCount, ...]
    rejection_reasons: tuple[RejectionReasonCount, ...]
    unrecorded_rejection_reasons: int
    resume_versions: tuple[ResumeVersionFeedbackStats, ...]
    sources: tuple[SourceFeedbackStats, ...]


def build_feedback_summary(
    *,
    totals: FeedbackTotals,
    category_counts: dict[QuestionCategory, int],
    performance_counts: dict[QuestionPerformance, int],
    weak_counts: dict[QuestionCategory, tuple[int, int]],
    rejection_reason_counts: dict[RejectionReason, int],
    unrecorded_rejection_reasons: int,
    resume_versions: tuple[ResumeVersionFeedbackStats, ...],
    source_counts: dict[str, FeedbackGroupStats],
) -> FeedbackSummary:
    category_order = {category: index for index, category in enumerate(QuestionCategory)}
    weak_categories = [
        WeakCategoryCount(
            category=category,
            question_count=question_count,
            weak_count=weak_count,
        )
        for category, (question_count, weak_count) in weak_counts.items()
        if weak_count > 0
    ]
    weak_categories.sort(
        key=lambda item: (
            -item.weak_count,
            -item.question_count,
            category_order[item.category],
        )
    )
    return FeedbackSummary(
        has_data=totals.applications > 0,
        totals=totals,
        funnel=(
            FunnelStage(FunnelStageName.SAVED_JOBS, totals.saved_jobs, None),
            FunnelStage(
                FunnelStageName.APPLICATIONS,
                totals.applications,
                _rate(totals.applications, totals.saved_jobs),
            ),
            FunnelStage(
                FunnelStageName.INTERVIEW_APPLICATIONS,
                totals.interview_applications,
                _rate(totals.interview_applications, totals.applications),
            ),
            FunnelStage(
                FunnelStageName.OFFERS,
                totals.offers,
                _rate(totals.offers, totals.interview_applications),
            ),
        ),
        question_categories=tuple(
            QuestionCategoryCount(category, category_counts.get(category, 0))
            for category in QuestionCategory
        ),
        performances=tuple(
            PerformanceCount(performance, performance_counts.get(performance, 0))
            for performance in QuestionPerformance
        ),
        weak_categories=tuple(weak_categories),
        rejection_reasons=tuple(
            RejectionReasonCount(reason, rejection_reason_counts.get(reason, 0))
            for reason in RejectionReason
        ),
        unrecorded_rejection_reasons=unrecorded_rejection_reasons,
        resume_versions=resume_versions,
        sources=tuple(
            SourceFeedbackStats(
                source=source,
                applications=source_counts.get(source, FeedbackGroupStats(0, 0, 0)).applications,
                interview_applications=source_counts.get(
                    source, FeedbackGroupStats(0, 0, 0)
                ).interview_applications,
                offers=source_counts.get(source, FeedbackGroupStats(0, 0, 0)).offers,
            )
            for source in ("manual", "boss", "nowcoder")
        ),
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
