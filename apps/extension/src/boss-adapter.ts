import type { JobCaptureResult } from './job-capture';

export function captureBossJobFromPage(pageUrl = window.location.href): JobCaptureResult {
  const singleLine = (element: Element | null): string => {
    const text = visibleText(element);
    return stripControlCharacters(text).replace(/\s+/gu, ' ').trim();
  };
  const descriptionText = (element: Element | null): string => {
    if (element === null || isHidden(element)) return '';
    const htmlElement = element as HTMLElement;
    if (typeof htmlElement.innerText === 'string') {
      return stripControlCharacters(htmlElement.innerText)
        .replace(/\r\n?/gu, '\n')
        .split('\n')
        .map((line) => line.replace(/[^\S\n]+/gu, ' ').trim())
        .filter(Boolean)
        .join('\n');
    }
    const clone = element.cloneNode(true) as Element;
    clone
      .querySelectorAll('script, style, noscript, template, [hidden], [aria-hidden="true"]')
      .forEach((node) => node.remove());
    clone.querySelectorAll('br').forEach((node) => node.replaceWith('\uE000'));
    return stripControlCharacters(clone.textContent ?? '')
      .split('\uE000')
      .map((line) => line.replace(/\s+/gu, ' ').trim())
      .filter(Boolean)
      .join('\n');
  };
  const visibleText = (element: Element | null): string => {
    if (element === null || isHidden(element)) return '';
    const htmlElement = element as HTMLElement;
    return typeof htmlElement.innerText === 'string'
      ? htmlElement.innerText
      : (element.textContent ?? '');
  };
  const isHidden = (element: Element): boolean => {
    if (
      element.closest('script, style, noscript, template, [hidden], [aria-hidden="true"]') !== null
    ) {
      return true;
    }
    const style = getComputedStyle(element);
    return style.display === 'none' || style.visibility === 'hidden';
  };
  const stripControlCharacters = (value: string): string =>
    [...value]
      .filter((character) => {
        const codePoint = character.codePointAt(0) ?? -1;
        return !(
          codePoint <= 8 ||
          (codePoint >= 11 && codePoint <= 12) ||
          (codePoint >= 14 && codePoint <= 31) ||
          (codePoint >= 127 && codePoint <= 159)
        );
      })
      .join('');

  let url: URL;
  try {
    url = new URL(pageUrl);
  } catch {
    return { status: 'unsupported' };
  }
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.hostname !== 'www.zhipin.com' ||
    url.port !== '' ||
    url.username !== '' ||
    url.password !== '' ||
    !/^\/job_detail\/[A-Za-z0-9_-]+\.html$/u.test(url.pathname)
  ) {
    return { status: 'unsupported' };
  }

  const jobPrimary = document.querySelector('.job-primary');
  const companyCard = [...document.querySelectorAll('.sider-company')].find(
    (element) => singleLine(element.querySelector(':scope > .title')) === '公司基本信息',
  );
  const descriptionSection = [...document.querySelectorAll('.job-detail .job-detail-section')].find(
    (element) => singleLine(element.querySelector('.detail-content-header > h3')) === '职位描述',
  );
  if (jobPrimary === null || companyCard === undefined || descriptionSection === undefined) {
    return { status: 'unsupported' };
  }

  const company =
    [...companyCard.querySelectorAll('.company-info a')]
      .map((element) => singleLine(element))
      .find(Boolean) ?? '';
  const draft = {
    company,
    description: descriptionText(descriptionSection.querySelector('.job-sec-text')),
    location: singleLine(jobPrimary.querySelector('.text-desc.text-city')),
    salaryText: singleLine(jobPrimary.querySelector('.name > .salary')),
    source: 'boss' as const,
    sourceUrl: `${url.protocol}//${url.hostname}${url.pathname}`,
    title: singleLine(jobPrimary.querySelector('.name > h1')),
  };
  const warnings: string[] = [];
  if (draft.title === '') warnings.push('未识别职位名称，请手动补充');
  if (draft.company === '') warnings.push('未识别公司名称，请手动补充');
  if (draft.location === '') warnings.push('未识别工作地点，请确认');
  if (draft.salaryText === '') warnings.push('未识别薪资，请确认');
  if (draft.description === '') warnings.push('未识别职位描述，请确认');
  return { draft, warnings };
}
