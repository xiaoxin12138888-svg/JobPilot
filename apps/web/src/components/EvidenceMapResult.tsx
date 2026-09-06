import type {
  EvidenceCoverage,
  EvidenceMapping,
  EvidenceRequirementType,
} from '@jobpilot/api-client';

const CONCLUSION_LABELS: Record<EvidenceCoverage, string> = {
  DIRECT: '支持',
  PARTIAL: '部分支持 / 待确认',
  GAP: '当前无法证明',
};

const GROUPS: ReadonlyArray<{ type: EvidenceRequirementType; title: string }> = [
  { type: 'MUST_HAVE', title: '硬性要求' },
  { type: 'PREFERRED', title: '加分项' },
  { type: 'RESPONSIBILITY', title: '岗位职责' },
  { type: 'SKILL', title: '技能' },
  { type: 'EXPERIENCE', title: '经验' },
  { type: 'EDUCATION', title: '学历' },
];

const GROUP_LABELS = Object.fromEntries(GROUPS.map((group) => [group.type, group.title])) as Record<
  EvidenceRequirementType,
  string
>;
const MAX_PRIORITY_ITEMS = 3;

export function EvidenceMapResult({ mappings }: { mappings: EvidenceMapping[] }) {
  const counts = countCoverage(mappings);
  const pending = mappings.filter((item) => item.coverage === 'PARTIAL');
  const gaps = mappings.filter((item) => item.coverage === 'GAP');

  return (
    <div className="evidence-result">
      <section className="evidence-overview" aria-labelledby="evidence-overview-title">
        <div className="evidence-overview-header">
          <div>
            <p className="eyebrow">WHOLE MAP</p>
            <h3 id="evidence-overview-title">综合判断</h3>
          </div>
          <dl className="evidence-overview-counts" aria-label="全部岗位条件判断统计">
            <div>
              <dt>支持</dt>
              <dd>{counts.DIRECT}</dd>
            </div>
            <div>
              <dt>部分支持 / 待确认</dt>
              <dd>{counts.PARTIAL}</dd>
            </div>
            <div>
              <dt>当前无法证明</dt>
              <dd>{counts.GAP}</dd>
            </div>
          </dl>
        </div>
        <p className="evidence-overview-summary">
          共分析 {mappings.length} 项：支持 {counts.DIRECT} 项，部分支持 / 待确认 {counts.PARTIAL}{' '}
          项，当前无法证明 {counts.GAP} 项。
        </p>
        <div className="evidence-priority-grid">
          <PriorityList
            title="待确认事项"
            mappings={pending}
            emptyText="当前没有需要进一步确认的部分支持项。"
          />
          <PriorityList
            title="主要证据缺口"
            mappings={gaps}
            emptyText="当前没有无法证明的岗位条件。"
          />
        </div>
        <p className="evidence-boundary-note">
          以上结论只依据当前选择的简历版本；“当前无法证明”不代表你不具备相应能力。
        </p>
      </section>

      {GROUPS.map((group) => (
        <EvidenceGroup
          key={group.type}
          title={group.title}
          mappings={mappings.filter((item) => item.requirementType === group.type)}
        />
      ))}
    </div>
  );
}

function PriorityList({
  title,
  mappings,
  emptyText,
}: {
  title: string;
  mappings: EvidenceMapping[];
  emptyText: string;
}) {
  const visible = mappings.slice(0, MAX_PRIORITY_ITEMS);
  const remaining = mappings.length - visible.length;
  return (
    <section className="evidence-priority-list">
      <h4>{title}</h4>
      {visible.length === 0 ? (
        <p className="muted">{emptyText}</p>
      ) : (
        <ul>
          {visible.map((mapping, index) => (
            <li key={`${mapping.requirementType}-${mapping.requirementText}-${index}`}>
              <span>{GROUP_LABELS[mapping.requirementType]}</span>
              {mapping.requirementText}
            </li>
          ))}
          {remaining > 0 && <li className="muted">另有 {remaining} 项，请查看下方分组。</li>}
        </ul>
      )}
    </section>
  );
}

function EvidenceGroup({ title, mappings }: { title: string; mappings: EvidenceMapping[] }) {
  const counts = countCoverage(mappings);
  return (
    <section className="evidence-group">
      <div className="evidence-group-header">
        <h3>{title}</h3>
        <div className="evidence-counts" aria-label={`${title}判断统计`}>
          <span>支持 {counts.DIRECT}</span>
          <span>部分支持 {counts.PARTIAL}</span>
          <span>无法证明 {counts.GAP}</span>
        </div>
      </div>
      {mappings.length === 0 ? (
        <p className="muted">当前 JD Analysis 没有这一类岗位条件。</p>
      ) : (
        <div className="evidence-mappings">
          {mappings.map((mapping, index) => (
            <article
              className="evidence-mapping"
              aria-label={`岗位条件：${mapping.requirementText}`}
              key={`${mapping.requirementText}-${index}`}
            >
              <h4>{mapping.requirementText}</h4>
              <p
                className={`coverage-badge coverage-${mapping.coverage.toLowerCase()} evidence-conclusion`}
              >
                结论：{CONCLUSION_LABELS[mapping.coverage]}
              </p>
              <div className="evidence-basis">
                <h5>判断依据</h5>
                <p>{mapping.reason}</p>
              </div>
              <div className="resume-quotes">
                <h5>简历原文证据</h5>
                {mapping.resumeEvidence.length > 0 ? (
                  mapping.resumeEvidence.map((evidence, evidenceIndex) => (
                    <blockquote key={`${evidence.quote}-${evidenceIndex}`}>
                      {evidence.quote}
                    </blockquote>
                  ))
                ) : (
                  <p className="muted">当前简历版本中未发现可追溯的支持内容。</p>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function countCoverage(mappings: EvidenceMapping[]): Record<EvidenceCoverage, number> {
  return {
    DIRECT: mappings.filter((item) => item.coverage === 'DIRECT').length,
    PARTIAL: mappings.filter((item) => item.coverage === 'PARTIAL').length,
    GAP: mappings.filter((item) => item.coverage === 'GAP').length,
  };
}
