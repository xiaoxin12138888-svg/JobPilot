import {
  ApiRequestError,
  type ApiHealthResponse,
  type CreateJobInput,
  type Job,
} from '@jobpilot/api-client';

import { renderPreview } from './popup-form';
import {
  renderDuplicate,
  renderParseError,
  renderReady,
  renderSaveError,
  renderSaved,
  renderStatus,
  renderUnavailable,
  renderUnsupported,
} from './popup-view';

export interface JobCaptureDraft {
  company: string;
  description: string;
  location: string;
  salaryText: string;
  source: 'boss';
  sourceUrl: string;
  title: string;
}

export type CaptureResult =
  | {
      draft: JobCaptureDraft;
      warnings: readonly string[];
    }
  | { status: 'unsupported' };

export interface CaptureDependencies {
  captureCurrentJob(): Promise<CaptureResult>;
  closePopup(): void;
  createJob(input: CreateJobInput): Promise<Job>;
  openJobPilot(jobId?: string): void;
  openManualFallback(): void;
}

interface PopupDependencies {
  getHealth(): Promise<ApiHealthResponse>;
  capture?: CaptureDependencies;
}

function getPopupRoot(): HTMLElement {
  const root = document.getElementById('popup-content');
  if (root === null) {
    throw new Error('Extension popup root was not found');
  }
  return root;
}

export async function initializePopup(dependencies: PopupDependencies): Promise<void> {
  const root = getPopupRoot();
  let requestInFlight = false;
  let currentDraft: JobCaptureDraft | undefined;
  let currentWarnings: readonly string[] = [];
  let lastSaveInput: CreateJobInput | undefined;

  function showPreview(validationMessage?: string): void {
    if (currentDraft === undefined || dependencies.capture === undefined) return;
    renderPreview(root, currentDraft, currentWarnings, validationMessage, (draft) => {
      currentDraft = draft;
      const input = toCreateJobInput(draft);
      if (input.title === '' || input.company === '') {
        showPreview('请确认职位名称和公司');
        return;
      }
      void save(input);
    });
  }

  async function capture(): Promise<void> {
    if (requestInFlight || dependencies.capture === undefined) return;
    requestInFlight = true;
    renderStatus(root, 'parsing', '正在读取当前岗位…', '只读取当前页面已呈现的岗位信息。');
    try {
      const result = await dependencies.capture.captureCurrentJob();
      if ('status' in result) {
        renderUnsupported(root, capture, dependencies.capture.openManualFallback);
        return;
      }
      currentDraft = result.draft;
      currentWarnings = result.warnings;
      showPreview();
    } catch {
      renderParseError(root, capture, dependencies.capture.openManualFallback);
    } finally {
      requestInFlight = false;
    }
  }

  async function save(input: CreateJobInput): Promise<void> {
    if (requestInFlight || dependencies.capture === undefined) return;
    requestInFlight = true;
    lastSaveInput = input;
    renderStatus(root, 'saving', '正在保存到 JobPilot…', '岗位将保存到本机工作台。');
    try {
      const job = await dependencies.capture.createJob(input);
      renderSaved(
        root,
        () => dependencies.capture?.openJobPilot(job.id),
        dependencies.capture.closePopup,
      );
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === 'DUPLICATE_JOB_URL') {
        renderDuplicate(root, () => dependencies.capture?.openJobPilot(error.resourceId));
      } else {
        renderSaveError(
          root,
          () => {
            if (lastSaveInput !== undefined) void save(lastSaveInput);
          },
          dependencies.capture.openManualFallback,
        );
      }
    } finally {
      requestInFlight = false;
    }
  }

  async function checkHealth(): Promise<void> {
    if (requestInFlight) return;
    requestInFlight = true;
    renderStatus(root, 'checking', '正在检查本机 JobPilot…', '正在连接本机服务。');
    try {
      await dependencies.getHealth();
      if (dependencies.capture === undefined) {
        renderStatus(root, 'available', '本机 JobPilot 可用', '服务正在运行，可以使用本地工作台。');
      } else {
        renderReady(root, capture);
      }
    } catch {
      renderUnavailable(root, checkHealth);
    } finally {
      requestInFlight = false;
    }
  }

  await checkHealth();
}

function toCreateJobInput(draft: JobCaptureDraft): CreateJobInput {
  return {
    company: draft.company.trim(),
    description: optionalText(draft.description),
    location: optionalText(draft.location),
    salaryText: optionalText(draft.salaryText),
    source: draft.source,
    sourceUrl: draft.sourceUrl,
    title: draft.title.trim(),
  };
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}
