import type { AutofillProfileResponse } from '@jobpilot/api-client';

import type { FillPlanItem } from './autofill-types';
import { resolveFormFields } from './field-resolver';
import type { FillExecutionResult } from './fill-executor';
import {
  renderAutofillApiUnavailable,
  renderAutofillFillError,
  renderAutofillNoProfile,
  renderAutofillPreview,
  renderAutofillResult,
  renderAutofillScanError,
  renderAutofillUnsupported,
} from './popup-autofill-view';
import { renderStatus } from './popup-view';
import type { FormScanSession } from './scan-current-tab';

export interface AutofillDependencies {
  closePopup(): void;
  fillCurrentForm(
    session: FormScanSession,
    plan: readonly FillPlanItem[],
  ): Promise<FillExecutionResult>;
  getAutofillProfile(): Promise<AutofillProfileResponse>;
  openProfile(): void;
  scanCurrentForm(): Promise<FormScanSession>;
}

export interface AutofillWorkflow {
  scan(): Promise<void>;
}

export function createAutofillWorkflow(
  root: HTMLElement,
  dependencies: AutofillDependencies,
): AutofillWorkflow {
  let requestInFlight = false;
  let currentSession: FormScanSession | undefined;
  let currentPlan: FillPlanItem[] = [];

  const scan = async (): Promise<void> => {
    if (requestInFlight) return;
    requestInFlight = true;
    renderStatus(root, 'scanning', '正在扫描当前表单…', '扫描不会修改页面内容。');
    const [profileResult, scanResult] = await Promise.allSettled([
      dependencies.getAutofillProfile(),
      dependencies.scanCurrentForm(),
    ]);
    try {
      if (scanResult.status === 'rejected') {
        renderAutofillScanError(root, scan);
        return;
      }
      if (profileResult.status === 'rejected') {
        renderAutofillApiUnavailable(root, scan);
        return;
      }
      currentSession = scanResult.value;
      if (currentSession.fields.length === 0) {
        renderAutofillUnsupported(root, scan);
        return;
      }
      if (profileResult.value.profile === null) {
        currentPlan = [];
        renderAutofillNoProfile(root, currentSession.fields.length, dependencies.openProfile, scan);
        return;
      }
      currentPlan = resolveFormFields(currentSession.fields, profileResult.value.profile);
      showPreview();
    } finally {
      requestInFlight = false;
    }
  };

  const showPreview = (): void => {
    renderAutofillPreview(
      root,
      currentPlan,
      (fieldRef, selected) => {
        currentPlan = currentPlan.map((item) =>
          item.fieldRef === fieldRef ? { ...item, selected } : item,
        );
      },
      fill,
      scan,
    );
  };

  const fill = async (): Promise<void> => {
    if (requestInFlight || currentSession === undefined) return;
    requestInFlight = true;
    renderStatus(root, 'filling', '正在填写已确认字段…', '不会点击提交或继续按钮。');
    try {
      const result = await dependencies.fillCurrentForm(currentSession, currentPlan);
      renderAutofillResult(root, result, scan, dependencies.closePopup);
    } catch {
      renderAutofillFillError(root, scan);
    } finally {
      requestInFlight = false;
    }
  };

  return { scan };
}
