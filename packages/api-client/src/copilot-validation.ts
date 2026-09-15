import type { CopilotResponse } from '@jobpilot/shared-types';

import { isDateString, isNullableString, isRecordWithKeys } from './validation.ts';

export function requireCopilotResponse(value: unknown): CopilotResponse {
  if (
    !isRecordWithKeys(value, ['isConfigured', 'record']) ||
    typeof value.isConfigured !== 'boolean' ||
    (value.record !== null && !isCopilotRecord(value.record))
  ) {
    throw new Error('JobPilot API returned an invalid Copilot response');
  }
  return value as unknown as CopilotResponse;
}

function isCopilotRecord(value: unknown): boolean {
  if (
    !isRecordWithKeys(value, [
      'id',
      'jobId',
      'resumeVersionId',
      'kind',
      'schemaVersion',
      'result',
      'inputFingerprint',
      'model',
      'promptVersion',
      'isStale',
      'createdAt',
    ]) ||
    typeof value.id !== 'string' ||
    typeof value.jobId !== 'string' ||
    !isNullableString(value.resumeVersionId) ||
    (value.schemaVersion !== 1 && value.schemaVersion !== 2) ||
    typeof value.inputFingerprint !== 'string' ||
    !/^[a-f0-9]{64}$/.test(value.inputFingerprint) ||
    typeof value.model !== 'string' ||
    typeof value.promptVersion !== 'string' ||
    typeof value.isStale !== 'boolean' ||
    !isDateString(value.createdAt)
  ) {
    return false;
  }
  if (value.kind === 'MATCH') return isJobMatchResult(value.result);
  if (value.kind === 'RESUME_ADVICE') return isResumeAdviceResult(value.result);
  if (value.kind === 'INTERVIEW_PREP')
    return isInterviewPrepResult(value.result, value.schemaVersion);
  return false;
}

function isJobMatchResult(value: unknown): boolean {
  return (
    isRecordWithKeys(value, ['summary', 'strengths', 'gaps', 'suggestions']) &&
    typeof value.summary === 'string' &&
    isGroundedItems(value.strengths, 'RESUME') &&
    isGroundedItems(value.gaps, 'JOB') &&
    isStringArray(value.suggestions)
  );
}

function isResumeAdviceResult(value: unknown): boolean {
  return (
    isRecordWithKeys(value, ['highlight', 'possibleImprovement', 'interviewFocus']) &&
    isGroundedItems(value.highlight, 'RESUME') &&
    isStringArray(value.possibleImprovement) &&
    isGroundedItems(value.interviewFocus, 'JOB')
  );
}

function isInterviewPrepResult(value: unknown, schemaVersion: 1 | 2): boolean {
  return (
    isRecordWithKeys(value, ['possibleQuestions', 'review']) &&
    Array.isArray(value.possibleQuestions) &&
    value.possibleQuestions.every((item) => isCopilotInterviewQuestion(item, schemaVersion)) &&
    isRecordWithKeys(value.review, ['strengths', 'weaknesses', 'nextActions']) &&
    isGroundedItems(value.review.strengths, 'INTERVIEW') &&
    isGroundedItems(value.review.weaknesses, 'INTERVIEW') &&
    isStringArray(value.review.nextActions)
  );
}

function isCopilotInterviewQuestion(value: unknown, schemaVersion: 1 | 2): boolean {
  return (
    isRecordWithKeys(value, ['category', 'question', 'reason', 'sourceEvidence']) &&
    (value.category === 'PRODUCT' ||
      value.category === 'AI' ||
      value.category === 'PROJECT' ||
      (schemaVersion === 2 &&
        (value.category === 'TECHNICAL' ||
          value.category === 'BEHAVIORAL' ||
          value.category === 'DOMAIN'))) &&
    typeof value.question === 'string' &&
    typeof value.reason === 'string' &&
    isCopilotSourceEvidence(value.sourceEvidence, 'JOB')
  );
}

function isGroundedItems(value: unknown, sourceType: string): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecordWithKeys(item, ['text', 'sourceEvidence']) &&
        typeof item.text === 'string' &&
        isCopilotSourceEvidence(item.sourceEvidence, sourceType),
    )
  );
}

function isCopilotSourceEvidence(value: unknown, sourceType: string): boolean {
  return (
    isRecordWithKeys(value, ['text', 'sourceType', 'sourceId']) &&
    typeof value.text === 'string' &&
    value.sourceType === sourceType &&
    typeof value.sourceId === 'string'
  );
}

function isStringArray(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}
