import { afterEach, describe, expect, it } from 'vitest';

import { captureNowcoderJobFromPage } from './nowcoder-adapter';
import validNowcoderJobDetail from './fixtures/nowcoder-job-detail.html?raw';

const canonicalUrl = 'https://www.nowcoder.com/jobs/detail/448241';

function renderFixture(html = validNowcoderJobDetail): void {
  document.body.innerHTML = html;
}

function requireCapture(result: ReturnType<typeof captureNowcoderJobFromPage>) {
  expect(result).not.toHaveProperty('status');
  if ('status' in result) throw new Error('Expected a captured Nowcoder job');
  return result;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe('captureNowcoderJobFromPage', () => {
  it('extracts only the current Nowcoder job detail fields and keeps the active-tab URL', () => {
    renderFixture();
    const pageUrl = `${canonicalUrl}?deliverSource=21&pageSource=5021&channel=mainSiteSearch#apply`;

    const result = requireCapture(captureNowcoderJobFromPage(pageUrl));

    expect(result).toEqual({
      draft: {
        company: '示例科技有限公司',
        description:
          '岗位职责：\n负责用户需求收集\n推进产品功能上线\n\n' +
          '岗位要求\n本科及以上\n良好沟通能力',
        location: '武汉',
        salaryText: '300-500元/天',
        source: 'nowcoder',
        sourceUrl: pageUrl,
        title: '产品经理',
      },
      warnings: [],
    });
    expect(JSON.stringify(result)).not.toMatch(
      /推荐产品经理|900-1000元\/天|推荐岗位描述|增长产品/iu,
    );
  });

  it.each([
    ['Nowcoder home', 'https://www.nowcoder.com/'],
    ['Nowcoder search', 'https://www.nowcoder.com/search/job?query=产品经理'],
    ['Nowcoder non-numeric detail', 'https://www.nowcoder.com/jobs/detail/not-a-number'],
    ['non-Nowcoder page', 'https://example.com/jobs/detail/448241'],
    ['unsafe scheme', 'javascript:alert(1)'],
    ['malformed URL', 'not a url'],
  ])('rejects an unsupported %s URL', (_label, url) => {
    renderFixture();

    expect(captureNowcoderJobFromPage(url)).toEqual({ status: 'unsupported' });
  });

  it('requires real job-detail structure in addition to a matching URL', () => {
    renderFixture('<main><h1 class="title">列表中的岗位标题</h1></main>');

    expect(captureNowcoderJobFromPage(canonicalUrl)).toEqual({ status: 'unsupported' });
  });

  it('leaves missing required fields editable and returns explicit warnings', () => {
    renderFixture();
    document.querySelector('.job-detail-wrap h1.title')?.remove();
    document.querySelector('.job-detail-wrap .tw-whitespace-pre-wrap')?.remove();

    const result = requireCapture(captureNowcoderJobFromPage(canonicalUrl));

    expect(result.draft.title).toBe('');
    expect(result.draft.company).toBe('');
    expect(result.warnings).toEqual(['未识别职位名称，请手动补充', '未识别公司名称，请手动补充']);
  });

  it('returns warnings when optional fields are absent', () => {
    renderFixture();
    document.querySelector('.job-detail-wrap .el-tooltip')?.remove();
    document.querySelector('.job-detail-wrap .salary')?.remove();
    document
      .querySelector('.job-detail-word')
      ?.replaceChildren(
        Object.assign(document.createElement('div'), { className: 'job-detail-infos' }),
      );

    const result = requireCapture(captureNowcoderJobFromPage(canonicalUrl));

    expect(result.draft.location).toBe('');
    expect(result.draft.salaryText).toBe('');
    expect(result.draft.description).toBe('');
    expect(result.warnings).toEqual([
      '未识别工作地点，请确认',
      '未识别薪资，请确认',
      '未识别职位描述，请确认',
    ]);
  });

  it('normalizes unusual whitespace and treats markup as plain visible text', () => {
    renderFixture();
    const title = document.querySelector('.job-detail-wrap h1.title');
    const description = document.querySelector('.job-detail-word .pre-line');
    if (title === null || description === null) throw new Error('Fixture is incomplete');
    title.textContent = '  AI\u0000   产品经理  ';
    description.innerHTML =
      ' 第一行\r\n <strong>普通文本</strong><br>第二行' +
      '<script>secretScript()</script><span hidden>隐藏内容</span>';

    const result = requireCapture(captureNowcoderJobFromPage(canonicalUrl));

    expect(result.draft.title).toBe('AI 产品经理');
    expect(result.draft.description).toBe(
      '第一行 普通文本\n第二行\n\n岗位要求\n本科及以上\n良好沟通能力',
    );
    expect(JSON.stringify(result)).not.toMatch(/secretScript|隐藏内容|<strong>|<br/iu);
  });
});
