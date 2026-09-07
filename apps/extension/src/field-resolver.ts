import type { AutofillProfileInput } from '@jobpilot/api-client';

import type { CanonicalFieldKey, FillPlanItem, FormFieldDescriptor } from './autofill-types';

const canonicalKeys: readonly CanonicalFieldKey[] = [
  'name',
  'phone',
  'email',
  'current_city',
  'school',
  'major',
  'degree',
  'education_start',
  'education_end',
  'company',
  'position',
  'experience_start',
  'experience_end',
  'experience_description',
  'github',
  'portfolio',
  'homepage',
];

const aliases: Readonly<Record<CanonicalFieldKey, readonly string[]>> = {
  name: ['姓名', '真实姓名', '您的姓名', '申请人姓名', '候选人姓名', 'name', 'full name'],
  phone: [
    '手机',
    '手机号',
    '手机号码',
    '联系电话',
    '移动电话',
    'mobile',
    'mobile phone',
    'phone',
    'tel',
  ],
  email: ['邮箱', '电子邮箱', '邮箱地址', 'email', 'e-mail'],
  current_city: ['当前城市', '所在城市', '居住城市', 'current city', 'city'],
  school: [
    '学校',
    '学校名称',
    '毕业院校',
    '就读院校',
    '所在院校',
    'university',
    'school',
    'college',
  ],
  major: ['专业', '所学专业', '专业名称', 'major'],
  degree: ['学历', '最高学历', '学历层次', 'degree', 'education level'],
  education_start: [
    '入学时间',
    '入学日期',
    '入学月份',
    '教育开始时间',
    'education start',
    'school start',
  ],
  education_end: [
    '毕业时间',
    '毕业日期',
    '毕业月份',
    '教育结束时间',
    'education end',
    'school end',
  ],
  company: ['公司', '公司名称', '所在公司', '雇主', 'company', 'employer'],
  position: ['职位', '职位名称', '岗位', '岗位名称', 'position', 'job title'],
  experience_start: [
    '工作开始时间',
    '任职开始时间',
    '经历开始时间',
    'experience start',
    'employment start',
  ],
  experience_end: [
    '工作结束时间',
    '任职结束时间',
    '经历结束时间',
    'experience end',
    'employment end',
  ],
  experience_description: [
    '工作内容',
    '工作描述',
    '职责描述',
    '经历描述',
    'experience description',
    'responsibilities',
  ],
  github: ['github', 'github链接', 'github主页'],
  portfolio: ['作品集', '作品集链接', 'portfolio'],
  homepage: ['个人主页', '个人网站', 'homepage', 'personal website'],
};

const sensitivePattern =
  /身份证|护照|银行卡|薪资|工资|期望待遇|民族|婚姻|政治面貌|签证|工作授权|工作许可|法律|隐私|授权|诚信|调剂|协议|条款|同意|声明|残疾|宗教|eeo|workauthorization|workpermit/iu;

export function resolveFormFields(
  fields: readonly FormFieldDescriptor[],
  profile: AutofillProfileInput | null,
): FillPlanItem[] {
  const occurrences = new Map<CanonicalFieldKey, number>();

  return fields.map((field) => {
    const pageLabel = field.label || field.name || field.id || '未命名字段';
    if (mustRemainManual(field)) return manualItem(field.ref, pageLabel);

    const hints = semanticHints(field);
    const exactKeys = matchingKeys(hints, false);
    if (exactKeys.length > 1) return unmappedItem(field.ref, pageLabel);

    let canonicalKey: CanonicalFieldKey;
    let status: FillPlanItem['status'] = 'READY';
    if (exactKeys.length === 1) {
      canonicalKey = exactKeys[0]!;
    } else {
      const fuzzyKeys = matchingKeys(hints, true);
      if (fuzzyKeys.length !== 1) return unmappedItem(field.ref, pageLabel);
      canonicalKey = fuzzyKeys[0]!;
      status = 'REVIEW_REQUIRED';
    }

    if (field.kind === 'UNKNOWN') {
      return { ...manualItem(field.ref, pageLabel), canonicalKey };
    }

    const occurrence = occurrences.get(canonicalKey) ?? 0;
    occurrences.set(canonicalKey, occurrence + 1);
    const proposedValue = profileValue(profile, canonicalKey, occurrence);
    if (proposedValue === null) {
      return {
        fieldRef: field.ref,
        pageLabel,
        canonicalKey,
        proposedValue: null,
        status: 'MANUAL',
        selected: false,
      };
    }

    return {
      fieldRef: field.ref,
      pageLabel,
      canonicalKey,
      proposedValue,
      status,
      selected: status === 'READY',
    };
  });
}

function mustRemainManual(field: FormFieldDescriptor): boolean {
  if (field.kind === 'FILE' || field.kind === 'RADIO' || field.kind === 'CHECKBOX') return true;
  return semanticHints(field).some((hint) => sensitivePattern.test(normalizeHint(hint)));
}

function semanticHints(field: FormFieldDescriptor): string[] {
  return [field.label, field.placeholder, field.name, field.id, field.autocomplete].filter(
    (value): value is string => value !== null && value.trim() !== '',
  );
}

function matchingKeys(hints: readonly string[], fuzzy: boolean): CanonicalFieldKey[] {
  const normalizedHints = hints.map(normalizeHint).filter(Boolean);
  return canonicalKeys.filter((key) =>
    aliases[key].some((alias) => {
      const normalizedAlias = normalizeHint(alias);
      return normalizedHints.some((hint) =>
        fuzzy
          ? hint !== normalizedAlias &&
            normalizedAlias.length >= 2 &&
            hint.includes(normalizedAlias)
          : hint === normalizedAlias,
      );
    }),
  );
}

function normalizeHint(value: string): string {
  return value
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[\s\p{P}\p{S}_]+/gu, '');
}

function profileValue(
  profile: AutofillProfileInput | null,
  key: CanonicalFieldKey,
  occurrence: number,
): string | null {
  if (profile === null) return null;
  const values: Record<CanonicalFieldKey, string | null | undefined> = {
    name: profile.personal.name,
    phone: profile.personal.phone,
    email: profile.personal.email,
    current_city: profile.personal.currentCity,
    school: profile.education[occurrence]?.school,
    major: profile.education[occurrence]?.major,
    degree: profile.education[occurrence]?.degree,
    education_start: profile.education[occurrence]?.start,
    education_end: profile.education[occurrence]?.end,
    company: profile.experience[occurrence]?.company,
    position: profile.experience[occurrence]?.position,
    experience_start: profile.experience[occurrence]?.start,
    experience_end: profile.experience[occurrence]?.end,
    experience_description: profile.experience[occurrence]?.description,
    github: profile.links.github,
    portfolio: profile.links.portfolio,
    homepage: profile.links.homepage,
  };
  const value = values[key]?.trim();
  return value ? value : null;
}

function manualItem(fieldRef: string, pageLabel: string): FillPlanItem {
  return {
    fieldRef,
    pageLabel,
    canonicalKey: null,
    proposedValue: null,
    status: 'MANUAL',
    selected: false,
  };
}

function unmappedItem(fieldRef: string, pageLabel: string): FillPlanItem {
  return {
    fieldRef,
    pageLabel,
    canonicalKey: null,
    proposedValue: null,
    status: 'UNMAPPED',
    selected: false,
  };
}
