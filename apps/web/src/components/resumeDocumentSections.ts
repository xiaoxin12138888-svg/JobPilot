export type ResumeSectionKey =
  'basics' | 'education' | 'experience' | 'projects' | 'skills' | 'awards' | 'other';

interface ResumeSectionDefinition {
  key: ResumeSectionKey;
  title: string;
  aliases: string[];
}

export interface ResumeSection {
  key: ResumeSectionKey | 'document';
  title: string;
  content: string;
}

export interface EditableResumeSection {
  id: string;
  title: string;
  valueStart: number;
  valueEnd: number;
  content: string;
}

export interface EditableResumeDocument {
  source: string;
  sections: EditableResumeSection[];
}

const SECTION_DEFINITIONS: ResumeSectionDefinition[] = [
  {
    key: 'basics',
    title: '基本信息',
    aliases: [
      '基本信息',
      '个人信息',
      '个人资料',
      '联系方式',
      '个人简介',
      'basic information',
      'personal information',
      'contact information',
      'profile',
    ],
  },
  {
    key: 'education',
    title: '教育经历',
    aliases: ['教育经历', '教育背景', '学习经历', 'education', 'education background'],
  },
  {
    key: 'experience',
    title: '工作 / 实习经历',
    aliases: [
      '工作经历',
      '实习经历',
      '工作/实习经历',
      '工作及实习经历',
      '职业经历',
      'work experience',
      'internship experience',
      'professional experience',
      'experience',
    ],
  },
  {
    key: 'projects',
    title: '项目经历',
    aliases: ['项目经历', '项目经验', '项目实践', '项目作品', 'project experience', 'projects'],
  },
  {
    key: 'skills',
    title: '技能 / 证书',
    aliases: [
      '专业技能',
      '个人技能',
      '个人技能和证书',
      '个人技能及证书',
      '技能特长',
      '技能证书',
      '专业证书',
      '资格证书',
      '语言能力',
      '技能',
      '证书',
      'skills',
      'technical skills',
      'certifications',
    ],
  },
  {
    key: 'awards',
    title: '荣誉 / 奖项',
    aliases: [
      '荣誉奖项',
      '奖项荣誉',
      '获奖经历',
      '所获荣誉',
      '校园荣誉',
      '荣誉',
      '奖项',
      'awards',
      'honors',
      'honors and awards',
    ],
  },
  {
    key: 'other',
    title: '其他',
    aliases: [
      '其他',
      '自我评价',
      '个人总结',
      '校园经历',
      '社团经历',
      '兴趣爱好',
      'summary',
      'activities',
      'additional information',
    ],
  },
];

const SECTION_BY_KEY = new Map(
  SECTION_DEFINITIONS.map((definition) => [definition.key, definition] as const),
);

const SECTION_BY_ALIAS = new Map(
  SECTION_DEFINITIONS.flatMap((definition) =>
    definition.aliases.map((alias) => [normalizeHeading(alias), definition.key] as const),
  ),
);

export function sectionResumeContent(content: string): ResumeSection[] {
  const original = content.trim();
  if (!original) return [];

  const groupedLines = new Map<ResumeSectionKey, string[]>(
    SECTION_DEFINITIONS.map((definition) => [definition.key, []]),
  );
  let activeSection: ResumeSectionKey = 'basics';
  let foundHeading = false;

  for (const line of original.split(/\r?\n/)) {
    const heading = identifyHeading(line);
    if (heading) {
      foundHeading = true;
      activeSection = heading.key;
      const activeLines = groupedLines.get(activeSection)!;
      if (activeLines.some((item) => item.trim()) && activeLines.at(-1)?.trim()) {
        activeLines.push('');
      }
      if (heading.inlineContent) activeLines.push(heading.inlineContent);
      continue;
    }
    groupedLines.get(activeSection)!.push(line);
  }

  if (!foundHeading) {
    return [{ key: 'document', title: '简历正文', content: original }];
  }

  const sections = SECTION_DEFINITIONS.flatMap((definition) => {
    const sectionContent = groupedLines.get(definition.key)!.join('\n').trim();
    return sectionContent
      ? [{ key: definition.key, title: definition.title, content: sectionContent }]
      : [];
  });

  return sections.length > 0
    ? sections
    : [{ key: 'document', title: '简历正文', content: original }];
}

export function createEditableResumeDocument(source: string): EditableResumeDocument {
  const headings: Array<{
    key: ResumeSectionKey;
    headingStart: number;
    contentStart: number;
  }> = [];
  const linePattern = /[^\r\n]*(?:\r\n|\n|\r|$)/g;

  for (const match of source.matchAll(linePattern)) {
    const token = match[0];
    if (!token) break;
    const line = token.replace(/(?:\r\n|\n|\r)$/, '');
    const heading = identifyHeading(line);
    if (!heading) continue;

    const headingStart = match.index;
    const contentStart =
      heading.inlineContentStart === undefined
        ? headingStart + token.length
        : headingStart + heading.inlineContentStart;
    headings.push({ key: heading.key, headingStart, contentStart });
  }

  if (headings.length === 0) {
    return {
      source,
      sections: [createEditableSection('document-0', '简历正文', source, 0, source.length)],
    };
  }

  const sections: EditableResumeSection[] = [];
  if (source.slice(0, headings[0]!.headingStart).trim()) {
    sections.push(
      createEditableSection('basics-0', '基本信息', source, 0, headings[0]!.headingStart),
    );
  }

  headings.forEach((heading, index) => {
    const definition = SECTION_BY_KEY.get(heading.key)!;
    const contentEnd = headings[index + 1]?.headingStart ?? source.length;
    sections.push(
      createEditableSection(
        `${heading.key}-${index}`,
        definition.title,
        source,
        heading.contentStart,
        contentEnd,
      ),
    );
  });

  return { source, sections };
}

export function rebuildEditableResumeDocument(
  document: EditableResumeDocument,
  values: string[],
): string {
  let cursor = 0;
  let rebuilt = '';

  document.sections.forEach((section, index) => {
    rebuilt += document.source.slice(cursor, section.valueStart);
    rebuilt += values[index] ?? section.content;
    cursor = section.valueEnd;
  });

  return rebuilt + document.source.slice(cursor);
}

function createEditableSection(
  id: string,
  title: string,
  source: string,
  contentStart: number,
  contentEnd: number,
): EditableResumeSection {
  const rawContent = source.slice(contentStart, contentEnd);
  if (!rawContent.trim()) {
    return { id, title, valueStart: contentStart, valueEnd: contentStart, content: '' };
  }

  const trimmedStart = rawContent.length - rawContent.trimStart().length;
  const trimmedEnd = rawContent.trimEnd().length;
  const valueStart = contentStart + trimmedStart;
  const valueEnd = contentStart + trimmedEnd;
  return {
    id,
    title,
    valueStart,
    valueEnd,
    content: source.slice(valueStart, valueEnd),
  };
}

function identifyHeading(line: string):
  | {
      key: ResumeSectionKey;
      inlineContent?: string;
      inlineContentStart?: number;
    }
  | undefined {
  const candidate = line
    .trim()
    .replace(/^#{1,6}\s*/, '')
    .replace(/^(?:[-*•·▪●]|[0-9一-十]+[.、])\s+/, '')
    .trim();
  if (!candidate || candidate.length > 80) return undefined;

  const wholeLineKey = SECTION_BY_ALIAS.get(normalizeHeading(candidate.replace(/[：:]\s*$/, '')));
  if (wholeLineKey) return { key: wholeLineKey };

  const separatorIndex = candidate.search(/[：:]/);
  if (separatorIndex < 0) return undefined;
  const normalizedPrefix = normalizeHeading(candidate.slice(0, separatorIndex));
  if (normalizedPrefix.length < 4) return undefined;
  const key = SECTION_BY_ALIAS.get(normalizedPrefix);
  if (!key) return undefined;

  const inlineRemainder = candidate.slice(separatorIndex + 1);
  const inlineContent = inlineRemainder.trim();
  const candidateStart = line.indexOf(candidate);
  const inlineContentStart =
    candidateStart +
    separatorIndex +
    1 +
    (inlineRemainder.length - inlineRemainder.trimStart().length);
  return inlineContent ? { key, inlineContent, inlineContentStart } : { key };
}

function normalizeHeading(value: string): string {
  return value.trim().replace(/\s+/g, '').toLowerCase();
}
