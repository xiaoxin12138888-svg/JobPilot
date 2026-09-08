import { useEffect, useState } from 'react';

import type {
  ApiClient,
  AutofillEducationEntry,
  AutofillExperienceEntry,
  AutofillProfile,
  AutofillProfileInput,
} from '@jobpilot/api-client';

import { ProfileProjectEntries } from './ProfileProjectEntries';

const EMPTY_EDUCATION: AutofillEducationEntry = {
  school: null,
  major: null,
  degree: null,
  start: null,
  end: null,
};
const EMPTY_EXPERIENCE: AutofillExperienceEntry = {
  company: null,
  position: null,
  start: null,
  end: null,
  description: null,
};
type SettledLoad = { apiClient: ApiClient; requestNumber: number };

export function AutofillProfilePage({ apiClient }: { apiClient: ApiClient }) {
  const [draft, setDraft] = useState<AutofillProfileInput>();
  const [reloadNumber, setReloadNumber] = useState(0);
  const [settledLoad, setSettledLoad] = useState<SettledLoad>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const loading = !(
    settledLoad?.apiClient === apiClient && settledLoad.requestNumber === reloadNumber
  );

  useEffect(() => {
    let active = true;
    void apiClient.getAutofillProfile().then(
      ({ profile }) => {
        if (active) {
          setDraft(profile ? inputFromProfile(profile) : emptyProfile());
          setSettledLoad({ apiClient, requestNumber: reloadNumber });
        }
      },
      () => {
        if (active) {
          setDraft(undefined);
          setError('求职资料暂时无法读取，请确认本机服务后重试。');
          setSettledLoad({ apiClient, requestNumber: reloadNumber });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [apiClient, reloadNumber]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const normalized = normalizeInput(draft);
    if (!hasFact(normalized)) {
      setError('请至少填写一项求职资料。');
      setSaved(false);
      return;
    }
    setSaving(true);
    setError(undefined);
    setSaved(false);
    try {
      const response = await apiClient.replaceAutofillProfile(normalized);
      if (!response.profile) throw new Error('Profile was not returned');
      setDraft(inputFromProfile(response.profile));
      setSaved(true);
    } catch {
      setError('求职资料保存失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page-section profile-page" aria-labelledby="profile-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">LOCAL PROFILE VAULT</p>
          <h1 id="profile-title">求职资料</h1>
          <p>集中维护招聘表单中反复填写的结构化事实，与简历版本和投递记录相互独立。</p>
        </div>
      </div>

      <aside className="profile-privacy-note" aria-label="资料隐私说明">
        <strong>资料只保存在本机 SQLite</strong>
        <p>
          只有在简历导入预览中明确确认后才会更新所选资料；不会上传云端，Extension
          仅在你点击扫描后临时读取。
        </p>
      </aside>

      {loading ? (
        <p className="loading-state" role="status">
          正在读取求职资料…
        </p>
      ) : !draft ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setError(undefined);
              setReloadNumber((value) => value + 1);
            }}
          >
            重试
          </button>
        </div>
      ) : (
        <form className="profile-form" onSubmit={(event) => void save(event)}>
          <ProfileSection title="基本信息" description="只填写常用联系信息，不收集证件或家庭资料。">
            <div className="profile-fields">
              <TextField
                label="姓名"
                value={draft.personal.name}
                onChange={(name) => setDraft({ ...draft, personal: { ...draft.personal, name } })}
              />
              <TextField
                label="手机号"
                type="tel"
                value={draft.personal.phone}
                onChange={(phone) => setDraft({ ...draft, personal: { ...draft.personal, phone } })}
              />
              <TextField
                label="邮箱"
                type="email"
                value={draft.personal.email}
                onChange={(email) => setDraft({ ...draft, personal: { ...draft.personal, email } })}
              />
              <TextField
                label="当前城市"
                value={draft.personal.currentCity}
                onChange={(currentCity) =>
                  setDraft({ ...draft, personal: { ...draft.personal, currentCity } })
                }
              />
            </div>
          </ProfileSection>

          <ProfileSection
            title="教育经历"
            description="可保存多条；自动填写只处理招聘页面已有的表单行。"
          >
            <div className="profile-entry-list">
              {draft.education.map((entry, index) => (
                <article className="profile-entry" key={`education-${index}`}>
                  <div className="profile-entry-heading">
                    <h3>教育经历 {index + 1}</h3>
                    <button
                      type="button"
                      className="text-button danger-text"
                      aria-label={`删除教育经历 ${index + 1}`}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          education: draft.education.filter((_, itemIndex) => itemIndex !== index),
                        })
                      }
                    >
                      删除
                    </button>
                  </div>
                  <div className="profile-fields">
                    <TextField
                      label={`学校 ${index + 1}`}
                      value={entry.school}
                      onChange={(school) =>
                        setDraft({
                          ...draft,
                          education: replaceAt(draft.education, index, { ...entry, school }),
                        })
                      }
                    />
                    <TextField
                      label={`专业 ${index + 1}`}
                      value={entry.major}
                      onChange={(major) =>
                        setDraft({
                          ...draft,
                          education: replaceAt(draft.education, index, { ...entry, major }),
                        })
                      }
                    />
                    <TextField
                      label={`学历 ${index + 1}`}
                      value={entry.degree}
                      onChange={(degree) =>
                        setDraft({
                          ...draft,
                          education: replaceAt(draft.education, index, { ...entry, degree }),
                        })
                      }
                    />
                    <TextField
                      label={`入学月份 ${index + 1}`}
                      type="month"
                      value={entry.start}
                      onChange={(start) =>
                        setDraft({
                          ...draft,
                          education: replaceAt(draft.education, index, { ...entry, start }),
                        })
                      }
                    />
                    <TextField
                      label={`毕业月份 ${index + 1}`}
                      type="month"
                      value={entry.end}
                      onChange={(end) =>
                        setDraft({
                          ...draft,
                          education: replaceAt(draft.education, index, { ...entry, end }),
                        })
                      }
                    />
                  </div>
                </article>
              ))}
            </div>
            <button
              type="button"
              className="button secondary"
              disabled={draft.education.length >= 20}
              onClick={() =>
                setDraft({ ...draft, education: [...draft.education, { ...EMPTY_EDUCATION }] })
              }
            >
              添加教育经历
            </button>
          </ProfileSection>

          <ProfileSection
            title="工作 / 实习经历"
            description="记录可复用事实，不替代完整简历内容。"
          >
            <div className="profile-entry-list">
              {draft.experience.map((entry, index) => (
                <article className="profile-entry" key={`experience-${index}`}>
                  <div className="profile-entry-heading">
                    <h3>工作 / 实习经历 {index + 1}</h3>
                    <button
                      type="button"
                      className="text-button danger-text"
                      aria-label={`删除工作或实习经历 ${index + 1}`}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          experience: draft.experience.filter(
                            (_, itemIndex) => itemIndex !== index,
                          ),
                        })
                      }
                    >
                      删除
                    </button>
                  </div>
                  <div className="profile-fields">
                    <TextField
                      label={`公司 ${index + 1}`}
                      value={entry.company}
                      onChange={(company) =>
                        setDraft({
                          ...draft,
                          experience: replaceAt(draft.experience, index, { ...entry, company }),
                        })
                      }
                    />
                    <TextField
                      label={`职位 ${index + 1}`}
                      value={entry.position}
                      onChange={(position) =>
                        setDraft({
                          ...draft,
                          experience: replaceAt(draft.experience, index, { ...entry, position }),
                        })
                      }
                    />
                    <TextField
                      label={`开始月份 ${index + 1}`}
                      type="month"
                      value={entry.start}
                      onChange={(start) =>
                        setDraft({
                          ...draft,
                          experience: replaceAt(draft.experience, index, { ...entry, start }),
                        })
                      }
                    />
                    <TextField
                      label={`结束月份 ${index + 1}`}
                      type="month"
                      value={entry.end}
                      onChange={(end) =>
                        setDraft({
                          ...draft,
                          experience: replaceAt(draft.experience, index, { ...entry, end }),
                        })
                      }
                    />
                    <label className="field profile-wide-field">
                      <span>经历描述 {index + 1}</span>
                      <textarea
                        maxLength={20_000}
                        rows={5}
                        value={entry.description ?? ''}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            experience: replaceAt(draft.experience, index, {
                              ...entry,
                              description: event.target.value,
                            }),
                          })
                        }
                      />
                    </label>
                  </div>
                </article>
              ))}
            </div>
            <button
              type="button"
              className="button secondary"
              disabled={draft.experience.length >= 20}
              onClick={() =>
                setDraft({ ...draft, experience: [...draft.experience, { ...EMPTY_EXPERIENCE }] })
              }
            >
              添加工作或实习经历
            </button>
          </ProfileSection>

          <ProfileSection
            title="项目经历"
            description="独立记录项目事实；Extension 不会扫描或自动填写这些内容。"
          >
            <ProfileProjectEntries
              projects={draft.projects}
              onChange={(projects) => setDraft({ ...draft, projects })}
            />
          </ProfileSection>

          <ProfileSection title="链接" description="仅保存 HTTP / HTTPS 链接。">
            <div className="profile-fields">
              <TextField
                label="GitHub"
                type="url"
                value={draft.links.github}
                onChange={(github) => setDraft({ ...draft, links: { ...draft.links, github } })}
              />
              <TextField
                label="作品集"
                type="url"
                value={draft.links.portfolio}
                onChange={(portfolio) =>
                  setDraft({ ...draft, links: { ...draft.links, portfolio } })
                }
              />
              <TextField
                label="个人主页"
                type="url"
                value={draft.links.homepage}
                onChange={(homepage) => setDraft({ ...draft, links: { ...draft.links, homepage } })}
              />
            </div>
          </ProfileSection>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {saved && (
            <p className="success-note" role="status">
              求职资料已保存到本机。
            </p>
          )}
          <div className="form-actions profile-save-actions">
            <p>保存资料不会创建投递记录，也不会触发招聘网站提交。</p>
            <button type="submit" className="button primary" disabled={saving}>
              {saving ? '正在保存…' : '保存求职资料'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function ProfileSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="profile-section">
      <header>
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      {children}
    </section>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string | null;
  onChange(value: string): void;
  type?: 'text' | 'tel' | 'email' | 'url' | 'month';
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        maxLength={type === 'url' ? 2048 : 320}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function replaceAt<T>(items: T[], index: number, replacement: T): T[] {
  return items.map((item, itemIndex) => (itemIndex === index ? replacement : item));
}

function emptyProfile(): AutofillProfileInput {
  return {
    personal: { name: null, phone: null, email: null, currentCity: null },
    education: [],
    experience: [],
    projects: [],
    links: { github: null, portfolio: null, homepage: null },
  };
}

function inputFromProfile(profile: AutofillProfile): AutofillProfileInput {
  return {
    personal: { ...profile.personal },
    education: profile.education.map((item) => ({ ...item })),
    experience: profile.experience.map((item) => ({ ...item })),
    projects: profile.projects.map((item) => ({ ...item })),
    links: { ...profile.links },
  };
}

function normalizeInput(input: AutofillProfileInput): AutofillProfileInput {
  const text = (value: string | null) => value?.trim() || null;
  return {
    personal: {
      name: text(input.personal.name),
      phone: text(input.personal.phone),
      email: text(input.personal.email),
      currentCity: text(input.personal.currentCity),
    },
    education: input.education.map((item) => ({
      school: text(item.school),
      major: text(item.major),
      degree: text(item.degree),
      start: text(item.start),
      end: text(item.end),
    })),
    experience: input.experience.map((item) => ({
      company: text(item.company),
      position: text(item.position),
      start: text(item.start),
      end: text(item.end),
      description: text(item.description),
    })),
    projects: input.projects.map((item) => ({
      name: text(item.name),
      role: text(item.role),
      start: text(item.start),
      end: text(item.end),
      description: text(item.description),
    })),
    links: {
      github: text(input.links.github),
      portfolio: text(input.links.portfolio),
      homepage: text(input.links.homepage),
    },
  };
}

function hasFact(input: AutofillProfileInput): boolean {
  return [
    ...Object.values(input.personal),
    ...input.education.flatMap(Object.values),
    ...input.experience.flatMap(Object.values),
    ...input.projects.flatMap(Object.values),
    ...Object.values(input.links),
  ].some(Boolean);
}
