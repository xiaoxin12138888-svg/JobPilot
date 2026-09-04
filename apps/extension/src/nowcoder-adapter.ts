import type { JobCaptureResult } from './job-capture';

export function captureNowcoderJobFromPage(pageUrl = window.location.href): JobCaptureResult {
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
  const isHidden = (element: Element): boolean => {
    if (
      element.closest('script, style, noscript, template, [hidden], [aria-hidden="true"]') !== null
    ) {
      return true;
    }
    const style = getComputedStyle(element);
    return style.display === 'none' || style.visibility === 'hidden';
  };
  const visibleText = (element: Element | null): string => {
    if (element === null || isHidden(element)) return '';
    const htmlElement = element as HTMLElement;
    return typeof htmlElement.innerText === 'string'
      ? htmlElement.innerText
      : (element.textContent ?? '');
  };
  const singleLine = (element: Element | null): string =>
    stripControlCharacters(visibleText(element)).replace(/\s+/gu, ' ').trim();
  const descriptionText = (element: Element): string => {
    if (isHidden(element)) return '';
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

  let url: URL;
  try {
    url = new URL(pageUrl);
  } catch {
    return { status: 'unsupported' };
  }
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.hostname !== 'www.nowcoder.com' ||
    url.port !== '' ||
    url.username !== '' ||
    url.password !== '' ||
    !/^\/jobs\/detail\/[0-9]+$/u.test(url.pathname)
  ) {
    return { status: 'unsupported' };
  }

  const jobCard = document.querySelector('.job-detail-wrap');
  const detailInfo = document.querySelector('.job-detail-word .job-detail-infos');
  if (jobCard === null || detailInfo === null) return { status: 'unsupported' };

  const rawCompany = singleLine(jobCard.querySelector('.tw-whitespace-pre-wrap'));
  const company = rawCompany.replace(/[·•]\s*(?:HR|招聘(?:者|专员|经理)?|人事)\s*$/iu, '').trim();
  const description = ['岗位职责', '岗位要求']
    .map((heading) => [...detailInfo.children].find((element) => singleLine(element) === heading))
    .map((heading) => heading?.nextElementSibling)
    .filter((element): element is Element => element !== null && element !== undefined)
    .map((element) => descriptionText(element))
    .filter(Boolean)
    .join('\n\n');
  const draft = {
    company,
    description,
    location: singleLine(jobCard.querySelector('.info > .extra .el-tooltip')),
    salaryText: singleLine(jobCard.querySelector('.info .salary')),
    source: 'nowcoder' as const,
    sourceUrl: pageUrl,
    title: singleLine(jobCard.querySelector('.info h1.title')),
  };
  const warnings: string[] = [];
  if (draft.title === '') warnings.push('未识别职位名称，请手动补充');
  if (draft.company === '') warnings.push('未识别公司名称，请手动补充');
  if (draft.location === '') warnings.push('未识别工作地点，请确认');
  if (draft.salaryText === '') warnings.push('未识别薪资，请确认');
  if (draft.description === '') warnings.push('未识别职位描述，请确认');
  return { draft, warnings };
}
