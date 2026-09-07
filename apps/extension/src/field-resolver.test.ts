import type { AutofillProfileInput } from '@jobpilot/api-client';
import { describe, expect, it } from 'vitest';

import type { FormFieldDescriptor, FormFieldKind } from './autofill-types';
import { resolveFormFields } from './field-resolver';

const profile: AutofillProfileInput = {
  personal: {
    name: '示例用户',
    phone: '13800000000',
    email: 'candidate@example.test',
    currentCity: '示例市',
  },
  education: [
    { school: '示例大学', major: '信息工程', degree: '本科', start: '2022-09', end: '2026-06' },
    { school: '示例研究院', major: '产品设计', degree: '硕士', start: '2026-09', end: '2029-06' },
  ],
  experience: [
    {
      company: '示例科技',
      position: '产品实习生',
      start: '2025-07',
      end: '2025-12',
      description: '参与需求分析与验证。',
    },
  ],
  links: {
    github: 'https://github.com/example-candidate',
    portfolio: 'https://portfolio.example.test',
    homepage: null,
  },
};

function field(label: string, overrides: Partial<FormFieldDescriptor> = {}): FormFieldDescriptor {
  const kind: FormFieldKind = overrides.kind ?? 'TEXT';
  return {
    ref: overrides.ref ?? `id:field-${label}`,
    label,
    kind,
    type: overrides.type ?? (kind === 'DATE' ? 'month' : 'text'),
    name: overrides.name ?? null,
    id: overrides.id ?? null,
    required: overrides.required ?? false,
    placeholder: overrides.placeholder ?? null,
    autocomplete: overrides.autocomplete ?? null,
    options: overrides.options ?? [],
  };
}

describe('resolveFormFields', () => {
  it('marks exact aliases ready and selects them by default', () => {
    const items = resolveFormFields(
      [
        field('申请人姓名'),
        field('手机号码'),
        field('当前城市'),
        field('毕业院校'),
        field('入学月份', { kind: 'DATE' }),
        field('GitHub'),
      ],
      profile,
    );

    expect(items).toEqual([
      expect.objectContaining({ canonicalKey: 'name', proposedValue: '示例用户' }),
      expect.objectContaining({ canonicalKey: 'phone', proposedValue: '13800000000' }),
      expect.objectContaining({ canonicalKey: 'current_city', proposedValue: '示例市' }),
      expect.objectContaining({ canonicalKey: 'school', proposedValue: '示例大学' }),
      expect.objectContaining({ canonicalKey: 'education_start', proposedValue: '2022-09' }),
      expect.objectContaining({
        canonicalKey: 'github',
        proposedValue: 'https://github.com/example-candidate',
      }),
    ]);
    expect(items.every((item) => item.status === 'READY' && item.selected)).toBe(true);
  });

  it('uses normalized labels and semantic attributes for exact matching', () => {
    const items = resolveFormFields(
      [
        field('E-mail：'),
        field('', { autocomplete: 'name' }),
        field('联系方式', { name: 'phone' }),
      ],
      profile,
    );

    expect(items.map((item) => [item.canonicalKey, item.status])).toEqual([
      ['email', 'READY'],
      ['name', 'READY'],
      ['phone', 'READY'],
    ]);
  });

  it('maps repeated education fields to profile entries in DOM order', () => {
    const items = resolveFormFields(
      [
        field('毕业院校', { ref: 'id:school-1' }),
        field('毕业院校', { ref: 'id:school-2' }),
        field('专业', { ref: 'id:major-1' }),
        field('专业', { ref: 'id:major-2' }),
      ],
      profile,
    );

    expect(items.map((item) => item.proposedValue)).toEqual([
      '示例大学',
      '示例研究院',
      '信息工程',
      '产品设计',
    ]);
  });

  it('requires review for a unique fuzzy match and leaves it unselected', () => {
    const [item] = resolveFormFields([field('专业方向')], profile);

    expect(item).toEqual({
      fieldRef: 'id:field-专业方向',
      pageLabel: '专业方向',
      canonicalKey: 'major',
      proposedValue: '信息工程',
      status: 'REVIEW_REQUIRED',
      selected: false,
    });
  });

  it.each([
    ['期望薪资', 'TEXT'],
    ['身份证号码', 'TEXT'],
    ['是否同意隐私条款', 'CHECKBOX'],
    ['是否接受调剂', 'RADIO'],
    ['上传简历', 'FILE'],
  ] as const)('keeps %s manual and never proposes or selects a value', (label, kind) => {
    const [item] = resolveFormFields([field(label, { kind })], profile);

    expect(item).toEqual(
      expect.objectContaining({
        canonicalKey: null,
        proposedValue: null,
        selected: false,
        status: 'MANUAL',
      }),
    );
  });

  it('keeps recognized fields manual when the profile value is missing', () => {
    const [item] = resolveFormFields([field('个人主页')], {
      ...profile,
      links: { ...profile.links, homepage: null },
    });

    expect(item).toEqual(
      expect.objectContaining({
        canonicalKey: 'homepage',
        proposedValue: null,
        selected: false,
        status: 'MANUAL',
      }),
    );
  });

  it('leaves unknown and ambiguous labels unmapped', () => {
    const items = resolveFormFields([field('最喜欢的颜色'), field('公司职位')], profile);

    expect(items).toEqual([
      expect.objectContaining({ canonicalKey: null, status: 'UNMAPPED', selected: false }),
      expect.objectContaining({ canonicalKey: null, status: 'UNMAPPED', selected: false }),
    ]);
  });

  it('does not prepare values when no local profile exists', () => {
    const [item] = resolveFormFields([field('姓名')], null);

    expect(item).toEqual(
      expect.objectContaining({
        canonicalKey: 'name',
        proposedValue: null,
        selected: false,
        status: 'MANUAL',
      }),
    );
  });
});
