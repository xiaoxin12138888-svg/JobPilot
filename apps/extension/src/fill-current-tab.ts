import type { FillPlanItem, FormFieldDescriptor } from './autofill-types';
import {
  type FillExecutionRequest,
  type FillExecutionResult,
  type FillFailureCode,
  fillApplicationForm,
} from './fill-executor';
import type { FormScanSession } from './scan-current-tab';

const emptyResult: FillExecutionResult = {
  status: 'COMPLETED',
  attempted: 0,
  filled: 0,
  failures: [],
};

export async function fillCurrentApplicationForm(
  session: FormScanSession,
  plan: readonly FillPlanItem[],
): Promise<FillExecutionResult> {
  const request = executionRequest(session, plan);
  if (request.fields.length === 0) return emptyResult;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id !== session.tabId || tab.url !== session.pageUrl) {
    return { ...emptyResult, status: 'PAGE_CHANGED' };
  }

  const results = await chrome.scripting.executeScript({
    args: [request],
    func: fillApplicationForm,
    target: { tabId: tab.id },
  });
  const result: unknown = results[0]?.result;
  if (!isFillExecutionResult(result, request.fields)) {
    throw new Error('未能确认页面填写结果');
  }
  return result;
}

function executionRequest(
  session: FormScanSession,
  plan: readonly FillPlanItem[],
): FillExecutionRequest {
  const descriptors = new Map<string, FormFieldDescriptor>();
  for (const field of session.fields) {
    if (!descriptors.has(field.ref)) descriptors.set(field.ref, field);
  }

  const usedRefs = new Set<string>();
  const fields: FillExecutionRequest['fields'] = [];
  for (const item of plan) {
    if (
      !item.selected ||
      item.proposedValue === null ||
      item.canonicalKey === null ||
      (item.status !== 'READY' && item.status !== 'REVIEW_REQUIRED') ||
      usedRefs.has(item.fieldRef)
    ) {
      continue;
    }
    const field = descriptors.get(item.fieldRef);
    if (
      field === undefined ||
      !['TEXT', 'TEXTAREA', 'SELECT', 'COMBOBOX', 'DATE'].includes(field.kind)
    ) {
      continue;
    }
    usedRefs.add(item.fieldRef);
    fields.push({ field, value: item.proposedValue });
  }
  return { pageUrl: session.pageUrl, scanToken: session.scanToken, fields };
}

function isFillExecutionResult(
  value: unknown,
  instructions: FillExecutionRequest['fields'],
): value is FillExecutionResult {
  if (!isRecord(value)) return false;
  if (!['COMPLETED', 'PARTIAL_FAILURE', 'PAGE_CHANGED'].includes(String(value.status))) {
    return false;
  }
  if (
    !isCount(value.attempted, instructions.length) ||
    !isCount(value.filled, value.attempted) ||
    !Array.isArray(value.failures) ||
    value.failures.length !== value.attempted - value.filled
  ) {
    return false;
  }
  const refs = new Set(instructions.map((instruction) => instruction.field.ref));
  return value.failures.every(
    (failure) =>
      isRecord(failure) &&
      typeof failure.fieldRef === 'string' &&
      refs.has(failure.fieldRef) &&
      isFailureCode(failure.code),
  );
}

function isCount(value: unknown, maximum: number): value is number {
  return Number.isInteger(value) && Number(value) >= 0 && Number(value) <= maximum;
}

function isFailureCode(value: unknown): value is FillFailureCode {
  return (
    typeof value === 'string' &&
    [
      'MISSING_REF',
      'STALE_FIELD',
      'FORBIDDEN_FIELD',
      'READONLY_FIELD',
      'NO_UNIQUE_OPTION',
      'UNSUPPORTED_CONTROL',
      'FILL_FAILED',
    ].includes(value)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
