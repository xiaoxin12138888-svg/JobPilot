import type {
  AutofillEducationEntry,
  AutofillExperienceEntry,
  ResumeImportEducationCandidate,
  ResumeImportExperienceCandidate,
} from '@jobpilot/api-client';

export type EducationSelection = ResumeImportEducationCandidate & {
  selected: boolean;
  possibleDuplicate: boolean;
};

export type ExperienceSelection = ResumeImportExperienceCandidate & {
  selected: boolean;
  possibleDuplicate: boolean;
};

interface CandidateListProps<T> {
  items: T[];
  disabled: boolean;
  onChange(items: T[]): void;
}

export function ImportEducationList({
  items,
  existing,
  disabled,
  onChange,
}: CandidateListProps<EducationSelection> & { existing: AutofillEducationEntry[] }) {
  return (
    <section className="import-candidate-section" aria-labelledby="import-education-title">
      <h3 id="import-education-title">教育经历</h3>
      <ExistingRows
        label="现有教育经历"
        emptyMessage="当前没有已保存的教育经历。"
        rows={existing.map(formatEducation)}
      />
      <h4>导入候选</h4>
      {items.length === 0 ? (
        <p>未识别到可映射的教育经历。</p>
      ) : (
        items.map((item, index) => (
          <fieldset
            className="import-candidate"
            aria-label={`导入教育经历 ${index + 1}`}
            key={index}
          >
            <legend>教育经历 {index + 1}</legend>
            {item.possibleDuplicate && <p className="duplicate-note">可能与现有经历重复</p>}
            <CandidateFields
              values={item}
              fields={EDUCATION_FIELDS}
              disabled={disabled}
              onChange={(key, value) =>
                onChange(
                  items.map((entry, itemIndex) =>
                    itemIndex === index ? { ...entry, [key]: value } : entry,
                  ),
                )
              }
            />
            <CandidateToggle
              checked={item.selected}
              disabled={disabled}
              label="添加这条教育经历"
              onChange={(selected) =>
                onChange(
                  items.map((entry, itemIndex) =>
                    itemIndex === index ? { ...entry, selected } : entry,
                  ),
                )
              }
            />
          </fieldset>
        ))
      )}
    </section>
  );
}

export function ImportExperienceList({
  items,
  existing,
  disabled,
  onChange,
}: CandidateListProps<ExperienceSelection> & { existing: AutofillExperienceEntry[] }) {
  return (
    <section className="import-candidate-section" aria-labelledby="import-experience-title">
      <h3 id="import-experience-title">工作 / 实习经历</h3>
      <ExistingRows
        label="现有工作或实习经历"
        emptyMessage="当前没有已保存的工作或实习经历。"
        rows={existing.map(formatExperience)}
      />
      <h4>导入候选</h4>
      {items.length === 0 ? (
        <p>未识别到可映射的工作或实习经历。</p>
      ) : (
        items.map((item, index) => (
          <fieldset
            className="import-candidate"
            aria-label={`导入工作经历 ${index + 1}`}
            key={index}
          >
            <legend>工作 / 实习经历 {index + 1}</legend>
            {item.possibleDuplicate && <p className="duplicate-note">可能与现有经历重复</p>}
            <CandidateFields
              values={item}
              fields={EXPERIENCE_FIELDS}
              disabled={disabled}
              onChange={(key, value) =>
                onChange(
                  items.map((entry, itemIndex) =>
                    itemIndex === index ? { ...entry, [key]: value } : entry,
                  ),
                )
              }
            />
            <CandidateToggle
              checked={item.selected}
              disabled={disabled}
              label="添加这条工作经历"
              onChange={(selected) =>
                onChange(
                  items.map((entry, itemIndex) =>
                    itemIndex === index ? { ...entry, selected } : entry,
                  ),
                )
              }
            />
          </fieldset>
        ))
      )}
    </section>
  );
}

function ExistingRows({
  label,
  emptyMessage,
  rows,
}: {
  label: string;
  emptyMessage: string;
  rows: string[];
}) {
  return rows.length > 0 ? (
    <div className="import-existing">
      <p>当前已保存</p>
      <ul aria-label={label}>
        {rows.map((row, index) => (
          <li key={`${row}-${index}`}>{row}</li>
        ))}
      </ul>
    </div>
  ) : (
    <p>{emptyMessage}</p>
  );
}

function CandidateToggle({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean;
  disabled: boolean;
  label: string;
  onChange(selected: boolean): void;
}) {
  return (
    <label>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

const EDUCATION_FIELDS: readonly [keyof AutofillEducationEntry, string][] = [
  ['school', '学校'],
  ['major', '专业'],
  ['degree', '学历 / 学位'],
  ['start', '开始月份'],
  ['end', '结束月份'],
];
const EXPERIENCE_FIELDS: readonly [keyof AutofillExperienceEntry, string][] = [
  ['company', '公司'],
  ['position', '职位'],
  ['start', '开始月份'],
  ['end', '结束月份'],
  ['description', '经历描述'],
];

function CandidateFields<T extends object>({
  values,
  fields,
  disabled,
  onChange,
}: {
  values: T;
  fields: readonly [keyof T, string][];
  disabled: boolean;
  onChange(key: keyof T, value: string | null): void;
}) {
  return (
    <div className="profile-fields">
      {fields.map(([key, label]) => (
        <label className="field" key={String(key)}>
          <span>{label}</span>
          <input
            value={typeof values[key] === 'string' ? (values[key] as string) : ''}
            disabled={disabled}
            onChange={(event) => onChange(key, event.target.value || null)}
          />
        </label>
      ))}
    </div>
  );
}

function formatEducation(item: AutofillEducationEntry): string {
  return compactFacts([item.school, item.major, item.degree, formatPeriod(item.start, item.end)]);
}

function formatExperience(item: AutofillExperienceEntry): string {
  return compactFacts([item.company, item.position, formatPeriod(item.start, item.end)]);
}

function formatPeriod(start: string | null, end: string | null): string | null {
  if (!start && !end) return null;
  return `${start ?? '时间未填'} — ${end ?? '至今'}`;
}

function compactFacts(values: (string | null)[]): string {
  return values.filter((value): value is string => Boolean(value)).join(' · ');
}
