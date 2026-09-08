import type { AutofillProjectEntry } from '@jobpilot/api-client';

const EMPTY_PROJECT: AutofillProjectEntry = {
  name: null,
  role: null,
  start: null,
  end: null,
  description: null,
};

export function ProfileProjectEntries({
  projects,
  onChange,
}: {
  projects: AutofillProjectEntry[];
  onChange(projects: AutofillProjectEntry[]): void;
}) {
  return (
    <>
      <div className="profile-entry-list">
        {projects.map((entry, index) => (
          <article className="profile-entry" key={`project-${index}`}>
            <div className="profile-entry-heading">
              <h3>项目经历 {index + 1}</h3>
              <button
                type="button"
                className="text-button danger-text"
                aria-label={`删除项目经历 ${index + 1}`}
                onClick={() => onChange(projects.filter((_, itemIndex) => itemIndex !== index))}
              >
                删除
              </button>
            </div>
            <div className="profile-fields">
              <ProjectTextField
                label={`项目名称 ${index + 1}`}
                value={entry.name}
                onChange={(name) => onChange(replaceAt(projects, index, { ...entry, name }))}
              />
              <ProjectTextField
                label={`项目角色 ${index + 1}`}
                value={entry.role}
                onChange={(role) => onChange(replaceAt(projects, index, { ...entry, role }))}
              />
              <ProjectTextField
                label={`开始月份 ${index + 1}`}
                value={entry.start}
                type="month"
                onChange={(start) => onChange(replaceAt(projects, index, { ...entry, start }))}
              />
              <ProjectTextField
                label={`结束月份 ${index + 1}`}
                value={entry.end}
                type="month"
                onChange={(end) => onChange(replaceAt(projects, index, { ...entry, end }))}
              />
              <label className="field profile-wide-field">
                <span>项目描述 {index + 1}</span>
                <textarea
                  maxLength={20_000}
                  rows={5}
                  value={entry.description ?? ''}
                  onChange={(event) =>
                    onChange(
                      replaceAt(projects, index, {
                        ...entry,
                        description: event.target.value,
                      }),
                    )
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
        disabled={projects.length >= 20}
        onClick={() => onChange([...projects, { ...EMPTY_PROJECT }])}
      >
        添加项目经历
      </button>
    </>
  );
}

function ProjectTextField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string | null;
  onChange(value: string): void;
  type?: 'text' | 'month';
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        maxLength={320}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function replaceAt<T>(items: T[], index: number, replacement: T): T[] {
  return items.map((item, itemIndex) => (itemIndex === index ? replacement : item));
}
