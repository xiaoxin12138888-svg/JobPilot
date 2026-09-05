import { useEffect, useState } from 'react';

import type { ApiClient, ResumeVersion } from '@jobpilot/api-client';

interface ResumeVersionsPageProps {
  apiClient: ApiClient;
}

type EditorState =
  | { mode: 'create'; name: string; content: string }
  | { mode: 'edit'; resumeId: string; name: string; content: string };

export function ResumeVersionsPage({ apiClient }: ResumeVersionsPageProps) {
  const [resumes, setResumes] = useState<ResumeVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [editor, setEditor] = useState<EditorState>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void apiClient
      .listResumeVersions()
      .then((response) => {
        if (active) setResumes(response.items);
      })
      .catch(() => {
        if (active) setError('简历版本暂时无法读取，请稍后重试。');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiClient]);

  async function saveEditor() {
    if (!editor) return;
    const name = editor.name.trim();
    const content = editor.content.trim();
    if (!name || !content) {
      setError('请填写版本名称和简历正文。');
      return;
    }
    setSaving(true);
    setError(undefined);
    try {
      if (editor.mode === 'create') {
        const created = await apiClient.createResumeVersion({ name, content });
        setResumes((items) => [created, ...items]);
      } else {
        const updated = await apiClient.updateResumeVersion(editor.resumeId, { name, content });
        setResumes((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      }
      setEditor(undefined);
    } catch (saveError) {
      setError(messageFor(saveError, '简历版本保存失败，请稍后重试。'));
    } finally {
      setSaving(false);
    }
  }

  async function duplicate(resume: ResumeVersion) {
    setError(undefined);
    try {
      const created = await apiClient.duplicateResumeVersion(resume.id, {
        name: `${resume.name} 副本`,
      });
      setResumes((items) => [created, ...items]);
    } catch (duplicateError) {
      setError(messageFor(duplicateError, '复制简历版本失败，请稍后重试。'));
    }
  }

  async function remove(resume: ResumeVersion) {
    if (!window.confirm(`确认删除简历版本“${resume.name}”吗？`)) return;
    setError(undefined);
    try {
      await apiClient.deleteResumeVersion(resume.id);
      setResumes((items) => items.filter((item) => item.id !== resume.id));
    } catch (deleteError) {
      setError(messageFor(deleteError, '删除简历版本失败，请稍后重试。'));
    }
  }

  if (editor) {
    return (
      <section className="page-section narrow" aria-labelledby="resume-editor-title">
        <button type="button" className="back-button" onClick={() => setEditor(undefined)}>
          ← 返回简历版本
        </button>
        <div className="page-heading">
          <div>
            <p className="eyebrow">PLAIN TEXT RESUME</p>
            <h1 id="resume-editor-title">
              {editor.mode === 'create' ? '新建简历版本' : '查看 / 编辑简历版本'}
            </h1>
            <p>正文只保存在本机 SQLite；V1 仅支持手动录入或粘贴纯文本。</p>
          </div>
        </div>
        <div className="resume-editor content-card">
          <label className="field">
            <span>版本名称 *</span>
            <input
              maxLength={200}
              value={editor.name}
              onChange={(event) => setEditor({ ...editor, name: event.target.value })}
            />
          </label>
          <label className="field">
            <span>简历正文 *</span>
            <textarea
              maxLength={100_000}
              rows={20}
              value={editor.content}
              onChange={(event) => setEditor({ ...editor, content: event.target.value })}
              placeholder="建议粘贴简历经历、项目、技能等正文。"
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={() => setEditor(undefined)}>
              取消
            </button>
            <button
              type="button"
              className="button primary"
              disabled={saving}
              onClick={() => void saveEditor()}
            >
              {saving ? '正在保存…' : editor.mode === 'create' ? '保存简历版本' : '保存修改'}
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page-section" aria-labelledby="resume-list-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">RESUME VERSIONS</p>
          <h1 id="resume-list-title">简历版本</h1>
          <p>保存不同岗位方向的纯文本简历版本，并记录真实投递时使用的版本。</p>
        </div>
        <button
          type="button"
          className="button primary"
          onClick={() => setEditor({ mode: 'create', name: '', content: '' })}
        >
          新建简历版本
        </button>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          <p>{error}</p>
        </div>
      )}
      {loading ? (
        <p className="loading-state" role="status">
          正在读取简历版本…
        </p>
      ) : resumes.length === 0 ? (
        <div className="empty-state">
          <span aria-hidden="true">＋</span>
          <h2>还没有简历版本</h2>
          <p>新建一个版本并粘贴脱敏后的简历正文，后续可按岗位生成证据映射。</p>
          <button
            type="button"
            className="button primary"
            onClick={() => setEditor({ mode: 'create', name: '', content: '' })}
          >
            新建简历版本
          </button>
        </div>
      ) : (
        <div className="resume-grid">
          {resumes.map((resume) => (
            <article className="resume-card" key={resume.id}>
              <div>
                <p className="eyebrow">LOCAL VERSION</p>
                <h2>{resume.name}</h2>
                <p className="muted">更新于 {formatDate(resume.updatedAt)}</p>
              </div>
              <p className="resume-preview">{resume.content}</p>
              <p className="resume-usage">
                {resume.applicationCount > 0
                  ? `已关联 ${resume.applicationCount} 条投递记录`
                  : '尚未关联投递记录'}
              </p>
              <div className="resume-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    setEditor({
                      mode: 'edit',
                      resumeId: resume.id,
                      name: resume.name,
                      content: resume.content,
                    })
                  }
                >
                  查看/编辑
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void duplicate(resume)}
                >
                  复制
                </button>
                <button
                  type="button"
                  className="text-button danger-text"
                  onClick={() => void remove(resume)}
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
