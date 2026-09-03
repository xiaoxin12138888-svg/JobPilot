import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

import {
  APPLICATION_STATUS_LABELS as STATUS_LABELS,
  JOB_SOURCE_LABELS,
} from '@jobpilot/api-client';
import type { ApiClient, ApplicationStatus, Job, JobListItem } from '@jobpilot/api-client';

interface JobLibraryProps {
  apiClient: ApiClient;
  onAdd(): void;
  onOpen(job: Job): void;
}

export function JobLibrary({ apiClient, onAdd, onOpen }: JobLibraryProps) {
  const [jobs, setJobs] = useState<JobListItem[]>();
  const [error, setError] = useState<string>();
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<ApplicationStatus | ''>('');
  const [query, setQuery] = useState({ keyword: '', status: '' as ApplicationStatus | '' });

  const load = useCallback(() => {
    const filters = {
      ...(query.keyword ? { keyword: query.keyword } : {}),
      ...(query.status ? { applicationStatus: query.status } : {}),
    };
    void apiClient
      .listJobs(filters)
      .then((response) => setJobs(response.items))
      .catch(() => setError('岗位库暂时无法加载，请确认本地 API 正常后重试。'));
  }, [apiClient, query]);

  useEffect(load, [load]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setJobs(undefined);
    setError(undefined);
    setQuery({ keyword: keyword.trim(), status });
  }

  return (
    <section className="page-section" aria-labelledby="job-library-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">JOB LIBRARY</p>
          <h1 id="job-library-title">岗位库</h1>
          <p>集中管理你确认保存的岗位快照和真实投递进度。</p>
        </div>
        {jobs && jobs.length > 0 && (
          <button type="button" className="button primary" onClick={onAdd}>
            添加岗位
          </button>
        )}
      </div>

      <form className="filter-bar" onSubmit={applyFilters}>
        <label>
          <span>搜索岗位</span>
          <input
            type="search"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="职位、公司或地点"
          />
        </label>
        <label>
          <span>投递状态</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as ApplicationStatus | '')}
          >
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="button secondary">
          筛选
        </button>
      </form>

      {error && (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setError(undefined);
              setJobs(undefined);
              load();
            }}
          >
            重新加载
          </button>
        </div>
      )}
      {!error && jobs === undefined && (
        <p className="loading-state" role="status" aria-live="polite">
          正在加载岗位…
        </p>
      )}
      {!error && jobs?.length === 0 && (
        <div className="empty-state">
          <span aria-hidden="true">＋</span>
          <h2>还没有保存岗位</h2>
          <p>先手动添加一个感兴趣的岗位，开始建立你的本地求职记录。</p>
          <button type="button" className="button primary" onClick={onAdd}>
            添加岗位
          </button>
        </div>
      )}
      {jobs && jobs.length > 0 && (
        <div className="job-grid" aria-live="polite">
          {jobs.map((job) => (
            <article className="job-card" key={job.id}>
              <div className="job-card-topline">
                <span className="source-badge">{JOB_SOURCE_LABELS[job.source]}</span>
                <span className={`status-badge status-${job.applicationStatus ?? 'none'}`}>
                  {job.applicationStatus ? STATUS_LABELS[job.applicationStatus] : '未建立投递'}
                </span>
              </div>
              <div>
                <h2>{job.title}</h2>
                <p className="company">{job.company}</p>
              </div>
              <dl className="compact-facts">
                <div>
                  <dt>地点</dt>
                  <dd>{job.location ?? '未填写'}</dd>
                </div>
                <div>
                  <dt>薪资</dt>
                  <dd>{job.salaryText ?? '未填写'}</dd>
                </div>
                <div>
                  <dt>保存</dt>
                  <dd>{formatDate(job.createdAt)}</dd>
                </div>
              </dl>
              <button type="button" className="button card-action" onClick={() => onOpen(job)}>
                查看详情
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(new Date(value));
}
