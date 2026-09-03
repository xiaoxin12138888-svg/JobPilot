import { useState } from 'react';

import { APPLICATION_STATUS_LABELS as STATUS_LABELS } from '@jobpilot/api-client';
import type { ApiClient, Application, ApplicationStatus } from '@jobpilot/api-client';

interface ApplicationPanelProps {
  apiClient: ApiClient;
  jobId: string;
  application: Application | undefined;
  onApplicationChange(application: Application): void;
}

export function ApplicationPanel({
  apiClient,
  jobId,
  application,
  onApplicationChange,
}: ApplicationPanelProps) {
  const [error, setError] = useState<string>();

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

  return (
    <aside className="application-card">
      <p className="eyebrow">APPLICATION</p>
      <h2>投递进度</h2>
      {application ? (
        <ApplicationControl
          key={application.status}
          application={application}
          onChange={changeStatus}
        />
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
