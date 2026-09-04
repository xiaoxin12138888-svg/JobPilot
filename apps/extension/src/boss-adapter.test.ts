import { afterEach, describe, expect, it } from 'vitest';

import { captureBossJobFromPage } from './boss-adapter';
import type { JobCaptureResult } from './job-capture';
import validBossJobDetail from './fixtures/boss-job-detail.html?raw';

const canonicalUrl = 'https://www.zhipin.com/job_detail/fixture_123.html';

function renderFixture(html = validBossJobDetail): void {
  document.body.innerHTML = html;
}

function requireCapture(result: JobCaptureResult) {
  expect(result).not.toHaveProperty('status');
  if ('status' in result) throw new Error('Expected a captured BOSS job');
  return result;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe('captureBossJobFromPage', () => {
  it('extracts only the current BOSS job detail fields and removes URL tracking data', () => {
    renderFixture();

    const result = requireCapture(
      captureBossJobFromPage(`${canonicalUrl}?pk=search&ka=list_job&sessionId=do-not-store#apply`),
    );

    expect(result).toEqual({
      draft: {
        company: '示例科技（北京）',
        description: '工作职责： 负责 AI 产品设计\n推进需求落地',
        location: '北京',
        salaryText: '200-250元/天',
        source: 'boss',
        sourceUrl: canonicalUrl,
        title: 'AI产品经理实习生',
      },
      warnings: [],
    });
    expect(JSON.stringify(result)).not.toMatch(/推荐产品经理|350-450元\/天|竞争力分析|sessionId/iu);
  });

  it.each([
    ['BOSS home', 'https://www.zhipin.com/'],
    ['BOSS list', 'https://www.zhipin.com/web/geek/job'],
    ['non-BOSS page', 'https://example.com/job_detail/fixture_123.html'],
    ['unsafe scheme', 'javascript:alert(1)'],
  ])('rejects an unsupported %s URL', (_label, url) => {
    renderFixture();

    expect(captureBossJobFromPage(url)).toEqual({ status: 'unsupported' });
  });

  it('requires real Job detail structure in addition to a matching URL', () => {
    renderFixture('<main><h1>列表中的岗位标题</h1></main>');

    expect(captureBossJobFromPage(canonicalUrl)).toEqual({ status: 'unsupported' });
  });

  it('leaves missing required fields editable and returns explicit warnings', () => {
    renderFixture();
    document.querySelector('.name > h1')?.remove();
    document.querySelector('.company-info')?.replaceChildren();

    const result = requireCapture(captureBossJobFromPage(canonicalUrl));

    expect(result.draft.title).toBe('');
    expect(result.draft.company).toBe('');
    expect(result.warnings).toEqual(['未识别职位名称，请手动补充', '未识别公司名称，请手动补充']);
  });

  it('returns warnings when optional fields are absent', () => {
    renderFixture();
    document.querySelector('.text-city')?.remove();
    document.querySelector('.name > .salary')?.remove();
    document.querySelector('.job-sec-text')?.remove();

    const result = requireCapture(captureBossJobFromPage(canonicalUrl));

    expect(result.draft.location).toBe('');
    expect(result.draft.salaryText).toBe('');
    expect(result.draft.description).toBe('');
    expect(result.warnings).toEqual([
      '未识别工作地点，请确认',
      '未识别薪资，请确认',
      '未识别职位描述，请确认',
    ]);
  });

  it('normalizes whitespace and treats odd markup as plain visible text', () => {
    renderFixture();
    const title = document.querySelector('.name > h1');
    const description = document.querySelector('.job-sec-text');
    if (title === null || description === null) throw new Error('Fixture is incomplete');
    title.textContent = '  AI\u0000   产品经理  ';
    description.innerHTML =
      ' 第一行\r\n <strong>普通文本</strong><br>第二行' +
      '<script>secretScript()</script><span hidden>隐藏内容</span>';

    const result = requireCapture(captureBossJobFromPage(canonicalUrl));

    expect(result.draft.title).toBe('AI 产品经理');
    expect(result.draft.description).toBe('第一行 普通文本\n第二行');
    expect(JSON.stringify(result)).not.toMatch(/secretScript|隐藏内容|<strong>|<br/iu);
  });
});
