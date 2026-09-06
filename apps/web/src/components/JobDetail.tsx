import { useCallback, useEffect, useState } from 'react';

import {
  APPLICATION_STATUS_LABELS as STATUS_LABELS,
  JOB_SOURCE_LABELS,
} from '@jobpilot/api-client';
import type {
  ApiClient,
  Application,
  Job,
  JobAnalysisResponse,
  ResumeVersion,
} from '@jobpilot/api-client';

import { ApplicationPanel } from './ApplicationPanel';
import { JobForm } from './JobForm';
import { JDAnalysisPanel } from './JDAnalysisPanel';
import { EvidenceMapPanel } from './EvidenceMapPanel';
import { InterviewPanel } from './InterviewPanel';

interface JobDetailProps {
  apiClient: ApiClient;
  jobId: string;
  onBack(): void;
  onDeleted(): void;
}

export function JobDetail({ apiClient, jobId, onBack, onDeleted }: JobDetailProps) {
  const [job, setJob] = useState<Job>();
  const [application, setApplication] = useState<Application>();
  const [resumeVersions, setResumeVersions] = useState<ResumeVersion[]>([]);
  const [resumeLoadError, setResumeLoadError] = useState<string>();
  const [analysisState, setAnalysisState] = useState<JobAnalysisResponse | null>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => {
    void Promise.all([apiClient.getJob(jobId), apiClient.listApplications({ jobId, limit: 1 })])
      .then(([loadedJob, applications]) => {
        setJob(loadedJob);
        setApplication(applications.items.find((item) => item.jobId === jobId));
      })
      .catch(() => setError('岗位详情暂时无法加载，请返回岗位库后重试。'))
      .finally(() => setLoading(false));
  }, [apiClient, jobId]);

  useEffect(load, [load]);

  useEffect(() => {
    let active = true;
    void apiClient.listResumeVersions().then(
      (response) => {
        if (active) setResumeVersions(response.items);
      },
      () => {
        if (active) setResumeLoadError('简历版本暂时无法读取，请稍后重试。');
      },
    );
    return () => {
      active = false;
    };
  }, [apiClient]);

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
            <span className="source-badge">{JOB_SOURCE_LABELS[job.source]}</span>
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
                <dd>{JOB_SOURCE_LABELS[job.source]}</dd>
              </div>
              <div>
                <dt>保存时间</dt>
                <dd>{formatDate(job.createdAt)}</dd>
              </div>
            </dl>
          </section>
          <InterviewPanel
            key={application?.id ?? 'no-application'}
            apiClient={apiClient}
            application={application}
          />
          <JDAnalysisPanel apiClient={apiClient} job={job} onStateChange={setAnalysisState} />
          <EvidenceMapPanel
            apiClient={apiClient}
            job={job}
            analysisState={analysisState}
            resumeVersions={resumeVersions}
            resumeLoadError={resumeLoadError}
          />
          <TextSection title="JD 快照" value={job.description} fallback="尚未填写 JD。" />
          <TextSection title="备注" value={job.notes} fallback="尚未添加备注。" />
        </div>
        <ApplicationPanel
          apiClient={apiClient}
          jobId={job.id}
          application={application}
          resumeVersions={resumeVersions}
          resumeLoadError={resumeLoadError}
          onApplicationChange={setApplication}
        />
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
