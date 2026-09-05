import type { EvidenceCoverage, EvidenceMapping } from '@jobpilot/api-client';

const COVERAGE_LABELS: Record<EvidenceCoverage, string> = {
  DIRECT: '直接证据',
  PARTIAL: '部分证据',
  GAP: '暂未发现证据',
};

export function EvidenceMapResult({ mappings }: { mappings: EvidenceMapping[] }) {
  const mustHave = mappings.filter((item) => item.requirementType === 'MUST_HAVE');
  const preferred = mappings.filter((item) => item.requirementType === 'PREFERRED');
  return (
    <div className="evidence-result">
      <EvidenceGroup title="硬性要求" mappings={mustHave} />
      <EvidenceGroup title="加分项" mappings={preferred} />
    </div>
  );
}

function EvidenceGroup({ title, mappings }: { title: string; mappings: EvidenceMapping[] }) {
  const counts = {
    DIRECT: mappings.filter((item) => item.coverage === 'DIRECT').length,
    PARTIAL: mappings.filter((item) => item.coverage === 'PARTIAL').length,
    GAP: mappings.filter((item) => item.coverage === 'GAP').length,
  };
  return (
    <section className="evidence-group">
      <div className="evidence-group-header">
        <h3>{title}</h3>
        <div className="evidence-counts" aria-label={`${title}证据统计`}>
          <span>直接证据 {counts.DIRECT}</span>
          <span>部分证据 {counts.PARTIAL}</span>
          <span>暂未发现证据 {counts.GAP}</span>
        </div>
      </div>
      {mappings.length === 0 ? (
        <p className="muted">当前 JD Analysis 没有这一类要求。</p>
      ) : (
        <div className="evidence-mappings">
          {mappings.map((mapping, index) => (
            <article className="evidence-mapping" key={`${mapping.requirementText}-${index}`}>
              <span className={`coverage-badge coverage-${mapping.coverage.toLowerCase()}`}>
                {COVERAGE_LABELS[mapping.coverage]}
              </span>
              <h4>{mapping.requirementText}</h4>
              {mapping.resumeEvidence.length > 0 ? (
                <div className="resume-quotes">
                  <p>简历证据</p>
                  {mapping.resumeEvidence.map((evidence, evidenceIndex) => (
                    <blockquote key={`${evidence.quote}-${evidenceIndex}`}>
                      {evidence.quote}
                    </blockquote>
                  ))}
                </div>
              ) : (
                <p className="muted">当前简历版本中未发现可直接支持该要求的内容。</p>
              )}
              <p className="evidence-reason">{mapping.reason}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
