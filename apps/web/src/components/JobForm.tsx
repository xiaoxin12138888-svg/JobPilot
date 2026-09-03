import { useState } from 'react';
import type { FormEvent } from 'react';

import type { CreateJobInput, Job } from '@jobpilot/api-client';

interface JobFormProps {
  initial?: Job;
  onSubmit(input: CreateJobInput): Promise<void>;
  onCancel(): void;
}

export function JobForm({ initial, onSubmit, onCancel }: JobFormProps) {
  const [values, setValues] = useState({
    title: initial?.title ?? '',
    company: initial?.company ?? '',
    sourceUrl: initial?.sourceUrl ?? '',
    location: initial?.location ?? '',
    salaryText: initial?.salaryText ?? '',
    description: initial?.description ?? '',
    notes: initial?.notes ?? '',
  });
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  function update(name: keyof typeof values, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!values.title.trim() || !values.company.trim()) {
      setError('请填写职位名称和公司。');
      return;
    }
    if (values.sourceUrl.trim() && !isHttpUrl(values.sourceUrl.trim())) {
      setError('岗位链接必须是有效的 HTTP 或 HTTPS 地址。');
      return;
    }
    setSaving(true);
    setError(undefined);
    try {
      await onSubmit({
        title: values.title,
        company: values.company,
        location: nullable(values.location),
        salaryText: nullable(values.salaryText),
        source: initial?.source ?? 'manual',
        sourceUrl: nullable(values.sourceUrl),
        description: nullable(values.description),
        notes: nullable(values.notes),
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '保存失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page-section narrow" aria-labelledby="job-form-title">
      <button type="button" className="back-button" onClick={onCancel}>
        ← 返回岗位库
      </button>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MANUAL ENTRY</p>
          <h1 id="job-form-title">{initial ? '编辑岗位' : '添加岗位'}</h1>
          <p>保存一份只属于你的本地岗位快照。</p>
        </div>
      </div>
      <form className="job-form" onSubmit={submit} noValidate>
        <div className="form-grid">
          <Field label="职位名称 *">
            <input
              value={values.title}
              onChange={(event) => update('title', event.target.value)}
              aria-required="true"
              maxLength={200}
            />
          </Field>
          <Field label="公司 *">
            <input
              value={values.company}
              onChange={(event) => update('company', event.target.value)}
              aria-required="true"
              maxLength={200}
            />
          </Field>
          <Field label="岗位链接" wide>
            <input
              type="url"
              value={values.sourceUrl}
              onChange={(event) => update('sourceUrl', event.target.value)}
              placeholder="https://..."
              maxLength={2048}
            />
          </Field>
          <Field label="地点">
            <input
              value={values.location}
              onChange={(event) => update('location', event.target.value)}
              maxLength={300}
            />
          </Field>
          <Field label="薪资">
            <input
              value={values.salaryText}
              onChange={(event) => update('salaryText', event.target.value)}
              maxLength={300}
            />
          </Field>
          <Field label="JD" wide>
            <textarea
              value={values.description}
              onChange={(event) => update('description', event.target.value)}
              rows={10}
              maxLength={100000}
            />
          </Field>
          <Field label="备注" wide>
            <textarea
              value={values.notes}
              onChange={(event) => update('notes', event.target.value)}
              rows={4}
              maxLength={20000}
            />
          </Field>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button type="button" className="button secondary" onClick={onCancel}>
            取消
          </button>
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? '正在保存…' : initial ? '保存修改' : '保存岗位'}
          </button>
        </div>
      </form>
    </section>
  );
}

function Field({
  label,
  wide = false,
  children,
}: {
  label: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={wide ? 'field wide' : 'field'}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function nullable(value: string): string | null {
  return value.trim() || null;
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}
