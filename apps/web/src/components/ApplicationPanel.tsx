import { useState } from 'react';

import { APPLICATION_STATUS_LABELS as STATUS_LABELS } from '@jobpilot/api-client';
import type {
  ApiClient,
  Application,
  ApplicationStatus,
  ResumeVersion,
  UpdateApplicationInput,
} from '@jobpilot/api-client';

import { ApplicationOutcomeForm } from './ApplicationOutcomeForm';

interface ApplicationPanelProps {
  apiClient: ApiClient;
  jobId: string;
  application: Application | undefined;
  resumeVersions: ResumeVersion[];
  resumeLoadError: string | undefined;
  onApplicationChange(application: Application): void;
}

export function ApplicationPanel({
  apiClient,
  jobId,
  application,
  resumeVersions,
  resumeLoadError,
  onApplicationChange,
}: ApplicationPanelProps) {
  const [error, setError] = useState<string>();
  const [associationSaved, setAssociationSaved] = useState(false);

  async function changeStatus(status: ApplicationStatus, confirmApplied: boolean) {
    if (!application) return;
    setError(undefined);
    try {
      onApplicationChange(
        await apiClient.updateApplication(application.id, { status, confirmApplied }),
      );
    } catch (updateError) {
      setError(messageFor(updateError, '状态更新失败，请稍后重试。'));
    }
  }

  async function saveResumeVersion(resumeVersionId: string | null) {
    if (!application) return;
    setError(undefined);
    setAssociationSaved(false);
    try {
      onApplicationChange(await apiClient.updateApplication(application.id, { resumeVersionId }));
      setAssociationSaved(true);
    } catch (updateError) {
      setError(messageFor(updateError, '简历版本关联失败，请稍后重试。'));
    }
  }

  async function saveOutcome(input: UpdateApplicationInput) {
    if (!application) return;
    setError(undefined);
    try {
      onApplicationChange(await apiClient.updateApplication(application.id, input));
    } catch (updateError) {
      setError(messageFor(updateError, '结果记录保存失败，请稍后重试。'));
      throw updateError;
    }
  }

  return (
    <aside className="application-card">
      <p className="eyebrow">APPLICATION</p>
      <h2>投递进度</h2>
      {application ? (
        <>
          <ResumeAssociation
            application={application}
            resumeVersions={resumeVersions}
            resumeLoadError={resumeLoadError}
            onSave={saveResumeVersion}
          />
          {associationSaved && (
            <p className="success-note" role="status">
              已记录本次投递使用的简历版本。
            </p>
          )}
          <ApplicationControl
            key={application.status}
            application={application}
            onChange={changeStatus}
          />
          {isOutcomeStatus(application.status) && (
            <ApplicationOutcomeForm application={application} onSave={saveOutcome} />
          )}
        </>
      ) : (
        <>
          <p>还没有投递记录。建立后初始状态为“计划投递”。</p>
          <button
            type="button"
            className="button primary full-width"
            onClick={() => {
              setError(undefined);
              void apiClient
                .createApplication(jobId)
                .then(onApplicationChange)
                .catch((createError) =>
                  setError(messageFor(createError, '建立投递失败，请稍后重试。')),
                );
            }}
          >
            建立投递
          </button>
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <p className="confirmation-note">
        打开原平台不会改变状态；只有你确认完成投递后才会标记“已投递”。
      </p>
    </aside>
  );
}

function ResumeAssociation({
  application,
  resumeVersions,
  resumeLoadError,
  onSave,
}: {
  application: Application;
  resumeVersions: ResumeVersion[];
  resumeLoadError: string | undefined;
  onSave(resumeVersionId: string | null): Promise<void>;
}) {
  const [selected, setSelected] = useState(application.resumeVersionId ?? '');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    await onSave(selected || null);
    setSaving(false);
  }

  return (
    <div className="resume-association">
      <label className="field">
        <span>本次投递使用简历</span>
        <select
          value={selected}
          disabled={Boolean(resumeLoadError)}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">未选择</option>
          {resumeVersions.map((resume) => (
            <option value={resume.id} key={resume.id}>
              {resume.name}
            </option>
          ))}
        </select>
      </label>
      {resumeLoadError ? (
        <p className="form-error">{resumeLoadError}</p>
      ) : resumeVersions.length === 0 ? (
        <p className="muted">暂无可选简历版本；不会自动选择。</p>
      ) : (
        <button
          type="button"
          className="button secondary full-width"
          disabled={saving || selected === (application.resumeVersionId ?? '')}
          onClick={() => void save()}
        >
          {saving ? '正在保存…' : '保存使用版本'}
        </button>
      )}
    </div>
  );
}

function ApplicationControl({
  application,
  onChange,
}: {
  application: Application;
  onChange(status: ApplicationStatus, confirmApplied: boolean): Promise<void>;
}) {
  const [target, setTarget] = useState<ApplicationStatus>(application.status);
  const [saving, setSaving] = useState(false);

  if (application.status === 'planned') {
    return (
      <div className="application-control">
        <p className="large-status">{STATUS_LABELS[application.status]}</p>
        <button
          type="button"
          className="button primary full-width"
          onClick={() => void onChange('applied', true)}
        >
          我已完成投递
        </button>
      </div>
    );
  }

  async function save() {
    if (target === application.status) return;
    const confirmApplied =
      target !== 'applied' || window.confirm('确认你已经在原招聘平台完成了这次投递吗？');
    if (!confirmApplied) return;
    setSaving(true);
    await onChange(target, target === 'applied');
    setSaving(false);
  }

  return (
    <div className="application-control">
      <p className="large-status">{STATUS_LABELS[application.status]}</p>
      <label className="field">
        <span>更正或推进状态</span>
        <select
          value={target}
          onChange={(event) => setTarget(event.target.value as ApplicationStatus)}
        >
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="button secondary full-width"
        disabled={saving}
        onClick={save}
      >
        {saving ? '正在保存…' : '保存状态'}
      </button>
    </div>
  );
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function isOutcomeStatus(status: ApplicationStatus): boolean {
  return (
    status === 'offer' || status === 'rejected' || status === 'withdrawn' || status === 'closed'
  );
}
