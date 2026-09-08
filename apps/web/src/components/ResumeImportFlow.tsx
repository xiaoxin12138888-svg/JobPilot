import { useState } from 'react';

import type {
  ApiClient,
  AutofillEducationEntry,
  AutofillExperienceEntry,
  AutofillProjectEntry,
  AutofillPersonalDetails,
  AutofillProfile,
  AutofillProfileLinks,
  ConfirmResumeImportInput,
  ResumeImportConfirmResponse,
  ResumeImportParseResponse,
} from '@jobpilot/api-client';

import {
  ImportEducationList,
  ImportExperienceList,
  ImportProjectList,
  type EducationSelection,
  type ExperienceSelection,
  type ProjectSelection,
} from './ResumeImportCandidateLists';

interface ResumeImportFlowProps {
  apiClient: ApiClient;
  onCancel(): void;
  onConfirmed(result: ResumeImportConfirmResponse): void;
}

type Phase = 'choose' | 'parsing' | 'preview' | 'confirming' | 'done';
type PersonalKey = keyof AutofillPersonalDetails;
type LinkKey = keyof AutofillProfileLinks;
type SelectedPersonal = Record<PersonalKey, boolean>;
type SelectedLinks = Record<LinkKey, boolean>;

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const PERSONAL_FIELDS: readonly [PersonalKey, string, boolean][] = [
  ['name', '姓名', false],
  ['phone', '手机号', true],
  ['email', '邮箱', true],
  ['currentCity', '当前城市', false],
];
const LINK_FIELDS: readonly [LinkKey, string][] = [
  ['github', 'GitHub'],
  ['portfolio', '作品集'],
  ['homepage', '个人主页'],
];

export function ResumeImportFlow({ apiClient, onCancel, onConfirmed }: ResumeImportFlowProps) {
  const [phase, setPhase] = useState<Phase>('choose');
  const [error, setError] = useState<string>();
  const [preview, setPreview] = useState<ResumeImportParseResponse>();
  const [currentProfile, setCurrentProfile] = useState<AutofillProfile | null>(null);
  const [profileReadable, setProfileReadable] = useState(true);
  const [versionName, setVersionName] = useState(defaultVersionName);
  const [resumeText, setResumeText] = useState('');
  const [createResume, setCreateResume] = useState(true);
  const [updateProfile, setUpdateProfile] = useState(false);
  const [showContacts, setShowContacts] = useState(false);
  const [personal, setPersonal] = useState<AutofillPersonalDetails>(emptyPersonal);
  const [selectedPersonal, setSelectedPersonal] = useState<SelectedPersonal>(emptySelectedPersonal);
  const [links, setLinks] = useState<AutofillProfileLinks>(emptyLinks);
  const [selectedLinks, setSelectedLinks] = useState<SelectedLinks>(emptySelectedLinks);
  const [education, setEducation] = useState<EducationSelection[]>([]);
  const [experience, setExperience] = useState<ExperienceSelection[]>([]);
  const [projects, setProjects] = useState<ProjectSelection[]>([]);
  const [result, setResult] = useState<ResumeImportConfirmResponse>();

  async function selectFile(file: File | undefined) {
    if (!file) return;
    setError(undefined);
    const extension = file.name.toLowerCase().split('.').pop();
    if (extension !== 'pdf' && extension !== 'docx') {
      setError('当前支持 PDF 和 DOCX 简历。');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setError('简历文件不能超过 10 MiB。');
      return;
    }
    setPhase('parsing');
    const profileRequest = apiClient
      .getAutofillProfile()
      .then((response) => ({ readable: true as const, profile: response.profile }))
      .catch(() => ({ readable: false as const, profile: null }));
    try {
      const parsed = await apiClient.parseResumeImport(file);
      const profileState = await profileRequest;
      setPreview(parsed);
      setCurrentProfile(profileState.profile);
      setProfileReadable(profileState.readable);
      setVersionName(defaultVersionName());
      setResumeText(parsed.extractedText);
      setPersonal(parsed.profileCandidates.personal);
      setLinks(parsed.profileCandidates.links);
      setSelectedPersonal(
        Object.fromEntries(
          PERSONAL_FIELDS.map(([key]) => [
            key,
            Boolean(parsed.profileCandidates.personal[key]) && !profileState.profile?.personal[key],
          ]),
        ) as SelectedPersonal,
      );
      setSelectedLinks(
        Object.fromEntries(
          LINK_FIELDS.map(([key]) => [
            key,
            Boolean(parsed.profileCandidates.links[key]) && !profileState.profile?.links[key],
          ]),
        ) as SelectedLinks,
      );
      setEducation(
        refreshEducationDuplicates(
          parsed.profileCandidates.education.map((item) => ({
            ...item,
            possibleDuplicate: false,
            selected: true,
          })),
          profileState.profile?.education ?? [],
        ),
      );
      setExperience(
        refreshExperienceDuplicates(
          parsed.profileCandidates.experience.map((item) => ({
            ...item,
            possibleDuplicate: false,
            selected: true,
          })),
          profileState.profile?.experience ?? [],
        ),
      );
      setProjects(
        refreshProjectDuplicates(
          parsed.profileCandidates.projects.map((item) => ({
            ...item,
            possibleDuplicate: false,
            selected: true,
          })),
          profileState.profile?.projects ?? [],
        ),
      );
      setPhase('preview');
    } catch (parseError) {
      setError(messageFor(parseError, '简历解析失败，请检查文件后重试。'));
      setPhase('choose');
    }
  }

  async function confirmImport() {
    if (!preview || phase === 'confirming') return;
    setError(undefined);
    const input: {
      resumeVersion?: ConfirmResumeImportInput extends { resumeVersion?: infer T } ? T : never;
      profileImport?: ConfirmResumeImportInput extends { profileImport?: infer T } ? T : never;
    } = {};
    if (createResume) {
      if (!versionName.trim() || !resumeText.trim()) {
        setError('请填写版本名称和简历正文。');
        return;
      }
      input.resumeVersion = { name: versionName.trim(), content: resumeText.trim() };
    }
    if (updateProfile) {
      const profileImport = {
        personal: selectedObject(personal, selectedPersonal),
        education: education.filter((item) => item.selected).map(withoutSelection),
        experience: experience.filter((item) => item.selected).map(withoutSelection),
        projects: projects.filter((item) => item.selected).map(withoutSelection),
        links: selectedObject(links, selectedLinks),
      };
      if (
        Object.keys(profileImport.personal).length === 0 &&
        profileImport.education.length === 0 &&
        profileImport.experience.length === 0 &&
        profileImport.projects.length === 0 &&
        Object.keys(profileImport.links).length === 0
      ) {
        setError('请选择至少一个要写入求职资料的字段或经历。');
        return;
      }
      input.profileImport = profileImport;
    }
    if (!input.resumeVersion && !input.profileImport) {
      setError('请至少选择“创建简历版本”或“更新求职资料”。');
      return;
    }
    setPhase('confirming');
    try {
      const confirmed = await apiClient.confirmResumeImport(input as ConfirmResumeImportInput);
      setResult(confirmed);
      onConfirmed(confirmed);
      setPhase('done');
    } catch (confirmError) {
      setError(messageFor(confirmError, '确认导入失败，请稍后重试。'));
      setPhase('preview');
    }
  }

  if (phase === 'done') {
    return (
      <section className="page-section narrow" aria-labelledby="resume-import-done-title">
        <div className="import-complete content-card">
          <p className="eyebrow">LOCAL IMPORT</p>
          <h1 id="resume-import-done-title">导入完成</h1>
          <p>已按你的选择写入本机 JobPilot，原始文件没有保存。</p>
          <ul>
            {result?.resumeVersion && <li>已创建简历版本：{result.resumeVersion.name}</li>}
            {result?.profile && <li>已更新所选求职资料</li>}
          </ul>
          <button type="button" className="button primary" onClick={onCancel}>
            返回简历版本
          </button>
        </div>
      </section>
    );
  }

  if (phase === 'choose' || phase === 'parsing') {
    return (
      <section className="page-section narrow" aria-labelledby="resume-import-title">
        <button
          type="button"
          className="back-button"
          onClick={onCancel}
          disabled={phase === 'parsing'}
        >
          ← 返回简历版本
        </button>
        <div className="page-heading">
          <div>
            <p className="eyebrow">LOCAL RESUME IMPORT</p>
            <h1 id="resume-import-title">导入简历</h1>
            <p>文件只发送到本机 JobPilot API；先解析预览，确认后才写入。</p>
          </div>
        </div>
        <div className="import-picker content-card">
          <label className="field">
            <span>选择 PDF 或 DOCX 简历</span>
            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              disabled={phase === 'parsing'}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = '';
                void selectFile(file);
              }}
            />
          </label>
          <p className="muted">最大 10 MiB。PDF 需为可复制文字版本；当前不支持 OCR。</p>
          {phase === 'parsing' && (
            <p className="loading-state" role="status" aria-live="polite">
              正在本地解析…
            </p>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </section>
    );
  }

  if (!preview) return null;
  const hasContacts = Boolean(
    personal.phone ||
    personal.email ||
    currentProfile?.personal.phone ||
    currentProfile?.personal.email,
  );
  const submitting = phase === 'confirming';
  return (
    <section className="page-section import-preview" aria-labelledby="resume-import-preview-title">
      <button type="button" className="back-button" onClick={onCancel} disabled={submitting}>
        ← 取消导入
      </button>
      <div className="page-heading">
        <div>
          <p className="eyebrow">REVIEW BEFORE WRITE</p>
          <h1 id="resume-import-preview-title">导入预览</h1>
          <p>检查并编辑解析结果。未勾选的资料不会写入，现有简历版本不会被覆盖。</p>
        </div>
        <span className="source-badge">{preview.fileType.toUpperCase()}</span>
      </div>

      <div className="import-metrics" aria-label="解析统计">
        <span>{formatBytes(preview.metrics.fileSizeBytes)}</span>
        {preview.metrics.pageCount !== null && <span>{preview.metrics.pageCount} 页</span>}
        <span>{preview.metrics.extractedCharacterCount.toLocaleString('zh-CN')} 字符</span>
        <span>{preview.metrics.parseLatencyMs} ms</span>
      </div>

      {preview.warnings.length > 0 && (
        <section className="import-warning" aria-labelledby="import-warning-title">
          <h2 id="import-warning-title">需要检查</h2>
          <ul>
            {preview.warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="import-targets">
        <section className="content-card import-target" aria-labelledby="resume-target-title">
          <label className="target-toggle">
            <input
              type="checkbox"
              checked={createResume}
              disabled={submitting}
              onChange={(event) => setCreateResume(event.target.checked)}
            />
            <span id="resume-target-title">创建简历版本</span>
          </label>
          <label className="field">
            <span>版本名称</span>
            <input
              maxLength={200}
              value={versionName}
              disabled={!createResume || submitting}
              onChange={(event) => setVersionName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>简历正文</span>
            <textarea
              rows={24}
              maxLength={100_000}
              value={resumeText}
              disabled={!createResume || submitting}
              onChange={(event) => setResumeText(event.target.value)}
            />
          </label>
          <div className="section-tags" aria-label="识别到的区块">
            {preview.sections.map((section, index) => (
              <span key={`${section.type}-${index}`}>{section.heading ?? section.type}</span>
            ))}
          </div>
        </section>

        <section className="content-card import-target" aria-labelledby="profile-target-title">
          <label className="target-toggle">
            <input
              type="checkbox"
              checked={updateProfile}
              disabled={!profileReadable || submitting}
              onChange={(event) => setUpdateProfile(event.target.checked)}
            />
            <span id="profile-target-title">更新求职资料</span>
          </label>
          {!profileReadable && (
            <p className="form-error">
              当前求职资料无法读取。为避免覆盖风险，本次只能创建简历版本。
            </p>
          )}
          {hasContacts && (
            <button
              type="button"
              className="text-button"
              disabled={submitting}
              onClick={() => setShowContacts((shown) => !shown)}
            >
              {showContacts ? '隐藏联系方式' : '显示联系方式'}
            </button>
          )}
          <div className="import-comparison-list">
            {PERSONAL_FIELDS.map(([key, label, sensitive]) => {
              const imported = personal[key];
              if (!imported) return null;
              const current = currentProfile?.personal[key] ?? null;
              const hidden = sensitive && !showContacts;
              return (
                <fieldset className="import-comparison" key={key}>
                  <legend>{label}</legend>
                  <div>
                    <span>当前</span>
                    <strong>{displayValue(current, hidden, key)}</strong>
                  </div>
                  <div>
                    <span>导入</span>
                    {hidden ? (
                      <strong>{displayValue(imported, true, key)}</strong>
                    ) : (
                      <input
                        aria-label={`导入${label}`}
                        value={imported}
                        disabled={submitting}
                        onChange={(event) =>
                          setPersonal((value) => ({ ...value, [key]: event.target.value }))
                        }
                      />
                    )}
                  </div>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedPersonal[key]}
                      disabled={!updateProfile || submitting}
                      onChange={(event) =>
                        setSelectedPersonal((value) => ({ ...value, [key]: event.target.checked }))
                      }
                    />
                    使用导入的{label}
                  </label>
                </fieldset>
              );
            })}
          </div>

          <ImportEducationList
            items={education}
            disabled={!updateProfile || submitting}
            existing={currentProfile?.education ?? []}
            onChange={(items) =>
              setEducation(refreshEducationDuplicates(items, currentProfile?.education ?? []))
            }
          />
          <ImportExperienceList
            items={experience}
            disabled={!updateProfile || submitting}
            existing={currentProfile?.experience ?? []}
            onChange={(items) =>
              setExperience(refreshExperienceDuplicates(items, currentProfile?.experience ?? []))
            }
          />
          <ImportProjectList
            items={projects}
            disabled={!updateProfile || submitting}
            existing={currentProfile?.projects ?? []}
            onChange={(items) =>
              setProjects(refreshProjectDuplicates(items, currentProfile?.projects ?? []))
            }
          />
          {LINK_FIELDS.map(([key, label]) => {
            const imported = links[key];
            if (!imported) return null;
            return (
              <fieldset className="import-comparison" key={key}>
                <legend>{label}</legend>
                <div>
                  <span>当前</span>
                  <strong>{currentProfile?.links[key] ?? '未填写'}</strong>
                </div>
                <div>
                  <span>导入</span>
                  <input
                    aria-label={`导入${label}`}
                    value={imported}
                    disabled={submitting}
                    onChange={(event) =>
                      setLinks((value) => ({ ...value, [key]: event.target.value }))
                    }
                  />
                </div>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedLinks[key]}
                    disabled={!updateProfile || submitting}
                    onChange={(event) =>
                      setSelectedLinks((value) => ({ ...value, [key]: event.target.checked }))
                    }
                  />
                  使用导入的{label}
                </label>
              </fieldset>
            );
          })}
        </section>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="button" className="button secondary" onClick={onCancel} disabled={submitting}>
          取消
        </button>
        <button
          type="button"
          className="button primary"
          onClick={() => void confirmImport()}
          disabled={submitting}
        >
          {submitting ? '正在导入…' : '确认导入'}
        </button>
      </div>
    </section>
  );
}

function selectedObject<T extends object>(
  values: T,
  selected: Record<keyof T, boolean>,
): Partial<T> {
  return Object.fromEntries(
    (Object.keys(values) as (keyof T)[])
      .filter((key) => selected[key])
      .map((key) => [key, values[key]]),
  ) as Partial<T>;
}

function withoutSelection<T extends { selected: boolean; possibleDuplicate: boolean }>(
  item: T,
): Omit<T, 'selected' | 'possibleDuplicate'> {
  return Object.fromEntries(
    Object.entries(item).filter(([key]) => key !== 'selected' && key !== 'possibleDuplicate'),
  ) as Omit<T, 'selected' | 'possibleDuplicate'>;
}

function emptyPersonal(): AutofillPersonalDetails {
  return { name: null, phone: null, email: null, currentCity: null };
}
function emptySelectedPersonal(): SelectedPersonal {
  return { name: false, phone: false, email: false, currentCity: false };
}
function emptyLinks(): AutofillProfileLinks {
  return { github: null, portfolio: null, homepage: null };
}
function emptySelectedLinks(): SelectedLinks {
  return { github: false, portfolio: false, homepage: false };
}
function defaultVersionName(): string {
  return `导入简历 ${new Date().toLocaleDateString('sv-SE')}`;
}
function formatBytes(value: number): string {
  return value < 1024 * 1024
    ? `${Math.max(1, Math.round(value / 1024))} KiB`
    : `${(value / 1024 / 1024).toFixed(1)} MiB`;
}
function messageFor(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
function displayValue(value: string | null, hidden: boolean, key: PersonalKey): string {
  if (!value) return '未填写';
  if (!hidden) return value;
  return key === 'phone' ? maskPhone(value) : maskEmail(value);
}
function maskPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  return digits.length >= 7 ? `${digits.slice(0, 3)}****${digits.slice(-4)}` : '***';
}
function maskEmail(value: string): string {
  const [name, domain] = value.split('@');
  return domain ? `${name?.slice(0, 2) ?? ''}***@${domain}` : '***';
}

function isDuplicateEducation(
  candidate: AutofillEducationEntry,
  existing: AutofillEducationEntry[],
): boolean {
  if (!candidate.school) return false;
  const key = educationKey(candidate);
  return existing.some((item) => educationKey(item) === key);
}

function isDuplicateExperience(
  candidate: AutofillExperienceEntry,
  existing: AutofillExperienceEntry[],
): boolean {
  if (!candidate.company) return false;
  const key = experienceKey(candidate);
  return existing.some((item) => experienceKey(item) === key);
}

function isDuplicateProject(
  candidate: AutofillProjectEntry,
  existing: AutofillProjectEntry[],
): boolean {
  if (!candidate.name) return false;
  const key = projectKey(candidate);
  return existing.some((item) => projectKey(item) === key);
}

function refreshEducationDuplicates(
  items: EducationSelection[],
  existing: AutofillEducationEntry[],
): EducationSelection[] {
  return items.map((item) => withDuplicateState(item, isDuplicateEducation(item, existing)));
}

function refreshExperienceDuplicates(
  items: ExperienceSelection[],
  existing: AutofillExperienceEntry[],
): ExperienceSelection[] {
  return items.map((item) => withDuplicateState(item, isDuplicateExperience(item, existing)));
}

function refreshProjectDuplicates(
  items: ProjectSelection[],
  existing: AutofillProjectEntry[],
): ProjectSelection[] {
  return items.map((item) => withDuplicateState(item, isDuplicateProject(item, existing)));
}

function withDuplicateState<T extends { selected: boolean; possibleDuplicate: boolean }>(
  item: T,
  possibleDuplicate: boolean,
): T {
  return {
    ...item,
    possibleDuplicate,
    selected: possibleDuplicate && !item.possibleDuplicate ? false : item.selected,
  };
}

function educationKey(item: AutofillEducationEntry): string {
  return [item.school, item.major, item.start, item.end].map(normalizedFact).join('|');
}

function experienceKey(item: AutofillExperienceEntry): string {
  return [item.company, item.position, item.start, item.end].map(normalizedFact).join('|');
}

function projectKey(item: AutofillProjectEntry): string {
  return [item.name, item.role, item.start, item.end].map(normalizedFact).join('|');
}

function normalizedFact(value: string | null): string {
  return (value ?? '').replace(/\s/g, '').toLocaleLowerCase();
}
