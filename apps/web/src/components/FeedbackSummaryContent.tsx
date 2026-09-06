import {
  JOB_SOURCE_LABELS,
  QUESTION_CATEGORY_LABELS,
  QUESTION_PERFORMANCE_LABELS,
  REJECTION_REASON_LABELS,
} from '@jobpilot/api-client';
import type { FeedbackSummary, FunnelStageName } from '@jobpilot/api-client';

const FUNNEL_LABELS: Readonly<Record<FunnelStageName, string>> = {
  SAVED_JOBS: '保存岗位',
  APPLICATIONS: '投递记录',
  INTERVIEW_APPLICATIONS: '面试岗位',
  OFFERS: 'Offer',
};

export function FeedbackSummaryContent({ summary }: { summary: FeedbackSummary }) {
  const totals = [
    ['已保存岗位', summary.totals.savedJobs],
    ['已投递岗位', summary.totals.applications],
    ['面试岗位', summary.totals.interviewApplications],
    ['面试轮次', summary.totals.interviews],
    ['记录题目', summary.totals.questions],
    ['Offer', summary.totals.offers],
    ['淘汰', summary.totals.rejected],
  ] as const;
  const categories = summary.questionCategories.filter((item) => item.count > 0);
  const performances = summary.performances.filter((item) => item.count > 0);
  const rejectionReasons = summary.rejectionReasons.filter((item) => item.count > 0);

  return (
    <div className="feedback-content">
      <div className="feedback-totals">
        {totals.map(([label, count]) => (
          <article className="feedback-total" aria-label={label} key={label}>
            <span>{label}</span>
            <strong>{count}</strong>
          </article>
        ))}
      </div>

      <section className="feedback-section" aria-labelledby="feedback-funnel-title">
        <h2 id="feedback-funnel-title">求职漏斗</h2>
        <ol className="feedback-funnel">
          {summary.funnel.map((stage) => (
            <li key={stage.stage}>
              <span>{FUNNEL_LABELS[stage.stage]}</span>
              <strong>{stage.count}</strong>
              {stage.conversionRate !== null && <small>{formatRate(stage.conversionRate)}</small>}
            </li>
          ))}
        </ol>
        <p className="feedback-note">转化率以前一个阶段的记录数为分母。</p>
      </section>

      <div className="feedback-grid">
        <CountSection
          title="面试问题分类"
          items={categories.map(
            (item) => `${QUESTION_CATEGORY_LABELS[item.category]}：${item.count}`,
          )}
          empty="暂无面试题分类记录。"
        />
        <CountSection
          title="回答自评"
          items={performances.map(
            (item) => `${QUESTION_PERFORMANCE_LABELS[item.performance]}：${item.count}`,
          )}
          empty="暂无回答自评记录。"
        />
        <CountSection
          title="高频薄弱类别"
          items={summary.weakCategories.map(
            (item) =>
              `${QUESTION_CATEGORY_LABELS[item.category]}：${item.questionCount} 道记录，其中 ${item.weakCount} 道为“一般/答得不好”`,
          )}
          empty="暂无“一般”或“答得不好”的题目记录。"
        />
        <CountSection
          title="淘汰原因记录"
          items={[
            ...rejectionReasons.map(
              (item) => `${REJECTION_REASON_LABELS[item.reason]}：${item.count}`,
            ),
            ...(summary.unrecordedRejectionReasons > 0
              ? [`未记录原因：${summary.unrecordedRejectionReasons}`]
              : []),
          ]}
          empty="暂无淘汰原因记录。"
        />
      </div>

      <FeedbackTable
        title="按简历版本"
        firstColumn="简历版本"
        rows={summary.resumeVersions.map((item) => [
          item.resumeVersionName,
          item.applications,
          item.interviewApplications,
          item.offers,
        ])}
        empty="暂无关联简历版本的投递记录。"
      />
      <FeedbackTable
        title="按岗位来源"
        firstColumn="来源"
        rows={summary.sources.map((item) => [
          JOB_SOURCE_LABELS[item.source],
          item.applications,
          item.interviewApplications,
          item.offers,
        ])}
        empty="暂无岗位来源统计。"
      />
      <p className="feedback-boundary">
        以上只描述已经记录的本地事实，不代表不同简历版本或招聘平台之间存在因果差异。
      </p>
    </div>
  );
}

function CountSection({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <section className="feedback-section">
      <h2>{title}</h2>
      {items.length > 0 ? (
        <ul className="feedback-count-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

function FeedbackTable({
  title,
  firstColumn,
  rows,
  empty,
}: {
  title: string;
  firstColumn: string;
  rows: readonly (readonly [string, number, number, number])[];
  empty: string;
}) {
  return (
    <section className="feedback-section">
      <h2>{title}</h2>
      {rows.length > 0 ? (
        <div className="feedback-table-wrap">
          <table className="feedback-table">
            <thead>
              <tr>
                <th scope="col">{firstColumn}</th>
                <th scope="col">投递</th>
                <th scope="col">面试</th>
                <th scope="col">Offer</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, applications, interviews, offers]) => (
                <tr key={label}>
                  <th scope="row">{label}</th>
                  <td>{applications}</td>
                  <td>{interviews}</td>
                  <td>{offers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

function formatRate(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}
