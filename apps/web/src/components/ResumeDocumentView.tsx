import { useId } from 'react';

type ResumeSectionKey =
  'basics' | 'education' | 'experience' | 'projects' | 'skills' | 'awards' | 'other';

interface ResumeSectionDefinition {
  key: ResumeSectionKey;
  title: string;
  aliases: string[];
}

interface ResumeSection {
  key: ResumeSectionKey | 'document';
  title: string;
  content: string;
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

const SECTION_BY_ALIAS = new Map(
  SECTION_DEFINITIONS.flatMap((definition) =>
    definition.aliases.map((alias) => [normalizeHeading(alias), definition.key] as const),
  ),
);

interface ResumeDocumentViewProps {
  content: string;
}

export function ResumeDocumentView({ content }: ResumeDocumentViewProps) {
  const headingId = useId().replaceAll(':', '');
  const sections = sectionResumeContent(content);

  return (
    <div className="resume-document" aria-label="简历分区内容">
      {sections.map((section, index) => {
        const sectionHeadingId = `${headingId}-resume-section-${index}`;
        return (
          <section
            className="resume-document-section"
            aria-labelledby={sectionHeadingId}
            key={`${section.key}-${index}`}
          >
            <h2 id={sectionHeadingId}>{section.title}</h2>
            <div className="resume-document-content">{section.content}</div>
          </section>
        );
      })}
    </div>
  );
}

function sectionResumeContent(content: string): ResumeSection[] {
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

function identifyHeading(
  line: string,
): { key: ResumeSectionKey; inlineContent?: string } | undefined {
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

  const inlineContent = candidate.slice(separatorIndex + 1).trim();
  return inlineContent ? { key, inlineContent } : { key };
}

function normalizeHeading(value: string): string {
  return value.trim().replace(/\s+/g, '').toLocaleLowerCase();
}
