import { useCallback, useEffect, useState } from 'react';

import { APPLICATION_STATUS_LABELS as STATUS_LABELS } from '@jobpilot/api-client';
import type { ApiClient, Application, ApplicationStatus, Job } from '@jobpilot/api-client';

import { JobForm } from './JobForm';

interface JobDetailProps {
  apiClient: ApiClient;
  jobId: string;
  onBack(): void;
  onDeleted(): void;
}

export function JobDetail({ apiClient, jobId, onBack, onDeleted }: JobDetailProps) {
  const [job, setJob] = useState<Job>();
  const [application, setApplication] = useState<Application>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => {
    void Promise.all([apiClient.getJob(jobId), apiClient.listApplications({ limit: 100 })])
      .then(([loadedJob, applications]) => {
        setJob(loadedJob);
        setApplication(applications.items.find((item) => item.jobId === jobId));
      })
      .catch(() => setError('岗位详情暂时无法加载，请返回岗位库后重试。'))
      .finally(() => setLoading(false));
  }, [apiClient, jobId]);

  useEffect(load, [load]);

  if (loading) {
    return (
      <p className="loading-state" role="status">
        正在加载岗位详情…
      </p>
    );
  }
  if (error || !job) {
    return (
      <section className="page-section">
        <button type="button" className="back-button" onClick={onBack}>
          ← 返回岗位库
        </button>
        <div className="inline-error" role="alert">
          <p>{error ?? '岗位不存在。'}</p>
        </div>
      </section>
    );
  }
  if (editing) {
    return (
      <JobForm
        initial={job}
        onCancel={() => setEditing(false)}
        onSubmit={async (input) => {
          const updated = await apiClient.updateJob(job.id, input);
          setJob(updated);
          setEditing(false);
        }}
      />
    );
  }

  return (
    <section className="page-section detail-page" aria-labelledby="job-detail-title">
      <button type="button" className="back-button" onClick={onBack}>
        ← 返回岗位库
      </button>
      <div className="detail-hero">
        <div>
          <div className="job-card-topline">
            <span className="source-badge">手动录入</span>
            <span className={`status-badge status-${application?.status ?? 'none'}`}>
              {application ? STATUS_LABELS[application.status] : '未建立投递'}
            </span>
          </div>
          <h1 id="job-detail-title">{job.title}</h1>
          <p className="detail-company">{job.company}</p>
        </div>
        <div className="detail-actions">
          <button type="button" className="button secondary" onClick={() => setEditing(true)}>
            编辑岗位
          </button>
          {job.sourceUrl && (
            <a className="button primary" href={job.sourceUrl} target="_blank" rel="noreferrer">
              去原平台查看/投递
            </a>
          )}
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <section className="content-card">
            <h2>岗位信息</h2>
            <dl className="fact-grid">
              <div>
                <dt>地点</dt>
                <dd>{job.location ?? '未填写'}</dd>
              </div>
              <div>
                <dt>薪资</dt>
                <dd>{job.salaryText ?? '未填写'}</dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>手动录入</dd>
              </div>
              <div>
                <dt>保存时间</dt>
                <dd>{formatDate(job.createdAt)}</dd>
              </div>
            </dl>
          </section>
          <TextSection title="JD 快照" value={job.description} fallback="尚未填写 JD。" />
          <TextSection title="备注" value={job.notes} fallback="尚未添加备注。" />
        </div>
        <aside className="application-card">
          <p className="eyebrow">APPLICATION</p>
          <h2>投递进度</h2>
          {application ? (
            <ApplicationControl
              application={application}
              onChange={async (status, confirmApplied) => {
                setError(undefined);
                try {
                  const updated = await apiClient.updateApplication(application.id, {
                    status,
                    confirmApplied,
                  });
                  setApplication(updated);
                } catch (updateError) {
                  setError(messageFor(updateError, '状态更新失败，请稍后重试。'));
                }
              }}
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
                    .createApplication(job.id)
                    .then(setApplication)
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
      </div>

      <div className="danger-zone">
        <div>
          <h2>删除岗位</h2>
          <p>删除后会同时移除该岗位的投递记录，且无法恢复。</p>
        </div>
        <button
          type="button"
          className="button danger"
          onClick={() => {
            if (!window.confirm(`确认删除“${job.title}”及其投递记录吗？`)) return;
            void apiClient
              .deleteJob(job.id)
              .then(onDeleted)
              .catch((deleteError) => {
                setError(messageFor(deleteError, '删除失败，请稍后重试。'));
              });
          }}
        >
          删除岗位
        </button>
      </div>
    </section>
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

function TextSection({
  title,
  value,
  fallback,
}: {
  title: string;
  value: string | null;
  fallback: string;
}) {
  return (
    <section className="content-card">
      <h2>{title}</h2>
      <p className={value ? 'long-text' : 'muted'}>{value ?? fallback}</p>
    </section>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long', timeStyle: 'short' }).format(
    new Date(value),
  );
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
