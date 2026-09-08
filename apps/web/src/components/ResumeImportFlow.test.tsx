import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import type {
  ApiClient,
  AutofillProfile,
  ResumeImportParseResponse,
  ResumeImportConfirmResponse,
  ResumeVersion,
} from '@jobpilot/api-client';

import { ResumeImportFlow } from './ResumeImportFlow';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('parses into an editable preview without saving and masks contacts by default', async () => {
  const parseResumeImport = vi.fn().mockResolvedValue(preview());
  const confirmResumeImport = vi.fn();
  const apiClient = client({
    parseResumeImport,
    confirmResumeImport,
    getAutofillProfile: vi.fn().mockResolvedValue({ profile: currentProfile() }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);

  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx', { type: 'application/zip' })] },
  });

  expect(await screen.findByRole('heading', { name: '导入预览' })).toBeInTheDocument();
  expect(parseResumeImport).toHaveBeenCalledOnce();
  expect(confirmResumeImport).not.toHaveBeenCalled();
  expect(screen.getByLabelText('简历正文')).toHaveValue(preview().extractedText);
  expect(screen.getByText('130****0000')).toBeInTheDocument();
  expect(screen.getByText('138****8000')).toBeInTheDocument();
  expect(screen.queryByDisplayValue('13800138000')).toBeNull();
  expect(screen.getByText('未识别到明确的工作或实习经历')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '显示联系方式' }));
  expect(screen.getByLabelText('导入手机号')).toHaveValue('13800138000');
});

it('shows existing education, experience and project details beside imported candidates', async () => {
  const profile = currentProfile();
  profile.experience = [
    {
      company: '既有公司',
      position: '运营助理',
      start: '2024-01',
      end: '2024-06',
      description: null,
    },
  ];
  profile.projects = [
    {
      name: '既有项目',
      role: '成员',
      start: '2024-07',
      end: '2024-09',
      description: null,
    },
  ];
  const parsed = preview();
  parsed.profileCandidates.experience = [
    {
      company: '新增公司',
      position: '产品实习生',
      start: '2025-01',
      end: '2025-06',
      description: null,
    },
  ];
  parsed.profileCandidates.projects = [
    {
      name: '新增项目',
      role: '负责人',
      start: '2025-07',
      end: '2025-09',
      description: '完成阶段验收',
    },
  ];
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(parsed),
    confirmResumeImport: vi.fn(),
    getAutofillProfile: vi.fn().mockResolvedValue({ profile }),
  });

  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });

  await screen.findByRole('heading', { name: '导入预览' });
  expect(screen.getByRole('list', { name: '现有教育经历' })).toHaveTextContent('既有大学 · 数学');
  expect(screen.getByRole('list', { name: '现有工作或实习经历' })).toHaveTextContent(
    '既有公司 · 运营助理 · 2024-01 — 2024-06',
  );
  expect(screen.getByRole('list', { name: '现有项目经历' })).toHaveTextContent(
    '既有项目 · 成员 · 2024-07 — 2024-09',
  );
  expect(
    within(screen.getByRole('group', { name: '导入教育经历 1' })).getByLabelText('学校'),
  ).toHaveValue('新增大学');
  expect(
    within(screen.getByRole('group', { name: '导入工作经历 1' })).getByLabelText('公司'),
  ).toHaveValue('新增公司');
  expect(
    within(screen.getByRole('group', { name: '导入项目经历 1' })).getByLabelText('项目名称'),
  ).toHaveValue('新增项目');
});

it('confirms only selected fields and rows while preventing duplicate clicks', async () => {
  let resolveConfirm: ((value: ResumeImportConfirmResponse) => void) | undefined;
  const confirmResumeImport = vi.fn(
    () =>
      new Promise<ResumeImportConfirmResponse>((resolve) => {
        resolveConfirm = resolve;
      }),
  );
  const onConfirmed = vi.fn();
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(preview()),
    confirmResumeImport,
    getAutofillProfile: vi.fn().mockResolvedValue({ profile: currentProfile() }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={onConfirmed} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });
  await screen.findByRole('heading', { name: '导入预览' });

  fireEvent.click(screen.getByRole('checkbox', { name: '更新求职资料' }));
  fireEvent.click(screen.getByRole('button', { name: '显示联系方式' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '使用导入的手机号' }));
  const education = screen.getByRole('group', { name: '导入教育经历 1' });
  expect(within(education).getByRole('checkbox', { name: '添加这条教育经历' })).toBeChecked();
  fireEvent.click(screen.getByRole('button', { name: '确认导入' }));
  fireEvent.click(screen.getByRole('button', { name: '正在导入…' }));

  expect(confirmResumeImport).toHaveBeenCalledOnce();
  expect(confirmResumeImport).toHaveBeenCalledWith({
    resumeVersion: {
      name: expect.stringMatching(/^导入简历 /),
      content: preview().extractedText,
    },
    profileImport: {
      personal: { phone: '13800138000' },
      education: [
        { school: '新增大学', major: '信息管理', degree: null, start: '2022-09', end: null },
      ],
      experience: [],
      projects: [
        {
          name: 'JobPilot',
          role: '产品负责人',
          start: '2025-07',
          end: '2025-09',
          description: '本地求职工作台',
        },
      ],
      links: {},
    },
  });

  const result = { resumeVersion: savedResume(), profile: currentProfile() };
  resolveConfirm?.(result);
  expect(await screen.findByRole('heading', { name: '导入完成' })).toBeInTheDocument();
  expect(onConfirmed).toHaveBeenCalledWith(result);
});

it('keeps preview edits available after a confirm failure so the user can retry', async () => {
  const confirmResumeImport = vi.fn().mockRejectedValue(new Error('本机数据库暂时忙碌'));
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(preview()),
    confirmResumeImport,
    getAutofillProfile: vi.fn().mockResolvedValue({ profile: null }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });
  await screen.findByRole('heading', { name: '导入预览' });
  fireEvent.change(screen.getByLabelText('简历正文'), { target: { value: '用户修改后的正文' } });

  fireEvent.click(screen.getByRole('button', { name: '确认导入' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('本机数据库暂时忙碌');
  expect(screen.getByLabelText('简历正文')).toHaveValue('用户修改后的正文');
  expect(screen.getByRole('button', { name: '确认导入' })).toBeEnabled();
});

it('marks normalized duplicate rows as review-only and renders hostile-looking text as text', async () => {
  const duplicatePreview = preview();
  duplicatePreview.extractedText = '<img src=x onerror=alert(1)>\n简历正文';
  duplicatePreview.profileCandidates.education[0]!.school = ' 既有 大学 ';
  const profile = currentProfile();
  profile.education = [
    {
      school: '既有大学',
      major: '信息管理',
      degree: null,
      start: '2022-09',
      end: null,
    },
  ];
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(duplicatePreview),
    confirmResumeImport: vi.fn(),
    getAutofillProfile: vi.fn().mockResolvedValue({ profile }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });

  await screen.findByRole('heading', { name: '导入预览' });
  expect(screen.queryByRole('img')).toBeNull();
  expect(screen.getByLabelText('简历正文')).toHaveValue(duplicatePreview.extractedText);
  fireEvent.click(screen.getByRole('checkbox', { name: '更新求职资料' }));
  const education = screen.getByRole('group', { name: '导入教育经历 1' });
  expect(within(education).getByText('可能与现有经历重复')).toBeInTheDocument();
  expect(within(education).getByRole('checkbox', { name: '添加这条教育经历' })).not.toBeChecked();
});

it('marks normalized duplicate projects as review-only', async () => {
  const duplicatePreview = preview();
  duplicatePreview.profileCandidates.projects[0]!.name = ' Job Pilot ';
  const profile = currentProfile();
  profile.projects = [
    {
      name: 'JobPilot',
      role: '产品负责人',
      start: '2025-07',
      end: '2025-09',
      description: null,
    },
  ];
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(duplicatePreview),
    confirmResumeImport: vi.fn(),
    getAutofillProfile: vi.fn().mockResolvedValue({ profile }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });

  await screen.findByRole('heading', { name: '导入预览' });
  fireEvent.click(screen.getByRole('checkbox', { name: '更新求职资料' }));
  const project = screen.getByRole('group', { name: '导入项目经历 1' });
  expect(within(project).getByText('可能与现有经历重复')).toBeInTheDocument();
  expect(within(project).getByRole('checkbox', { name: '添加这条项目经历' })).not.toBeChecked();
});

it('rechecks duplicate status after candidate edits and disables every preview control while saving', async () => {
  let resolveConfirm: ((value: ResumeImportConfirmResponse) => void) | undefined;
  const confirmResumeImport = vi.fn(
    () =>
      new Promise<ResumeImportConfirmResponse>((resolve) => {
        resolveConfirm = resolve;
      }),
  );
  const parsed = preview();
  parsed.profileCandidates.links.github = 'https://github.com/imported';
  const apiClient = client({
    parseResumeImport: vi.fn().mockResolvedValue(parsed),
    confirmResumeImport,
    getAutofillProfile: vi.fn().mockResolvedValue({ profile: currentProfile() }),
  });
  render(<ResumeImportFlow apiClient={apiClient} onCancel={vi.fn()} onConfirmed={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('选择 PDF 或 DOCX 简历'), {
    target: { files: [new File(['resume'], 'resume.docx')] },
  });
  await screen.findByRole('heading', { name: '导入预览' });
  fireEvent.click(screen.getByRole('checkbox', { name: '更新求职资料' }));

  const education = screen.getByRole('group', { name: '导入教育经历 1' });
  fireEvent.change(within(education).getByLabelText('学校'), { target: { value: '既有大学' } });
  fireEvent.change(within(education).getByLabelText('专业'), { target: { value: '数学' } });
  fireEvent.change(within(education).getByLabelText('开始月份'), { target: { value: '' } });

  expect(within(education).getByText('可能与现有经历重复')).toBeInTheDocument();
  expect(within(education).getByRole('checkbox', { name: '添加这条教育经历' })).not.toBeChecked();

  fireEvent.click(screen.getByRole('button', { name: '确认导入' }));

  expect(screen.getByRole('button', { name: '显示联系方式' })).toBeDisabled();
  expect(screen.getByLabelText('导入GitHub')).toBeDisabled();
  resolveConfirm?.({ resumeVersion: savedResume(), profile: currentProfile() });
  expect(await screen.findByRole('heading', { name: '导入完成' })).toBeInTheDocument();
});

function client(overrides: Partial<ApiClient>): ApiClient {
  return overrides as ApiClient;
}

function preview(): ResumeImportParseResponse {
  return {
    fileType: 'DOCX',
    extractedText: '基本信息\n示例用户\n教育经历\n学校：新增大学',
    blocks: [],
    sections: [
      { type: 'BASIC', heading: '基本信息', text: '示例用户' },
      { type: 'EDUCATION', heading: '教育经历', text: '学校：新增大学' },
    ],
    profileCandidates: {
      personal: {
        name: '示例用户',
        phone: '13800138000',
        email: 'candidate@example.invalid',
        currentCity: null,
      },
      education: [
        {
          school: '新增大学',
          major: '信息管理',
          degree: null,
          start: '2022-09',
          end: null,
        },
      ],
      experience: [],
      projects: [
        {
          name: 'JobPilot',
          role: '产品负责人',
          start: '2025-07',
          end: '2025-09',
          description: '本地求职工作台',
        },
      ],
      links: { github: null, portfolio: null, homepage: null },
    },
    warnings: [{ code: 'EXPERIENCE_NOT_DETECTED', message: '未识别到明确的工作或实习经历' }],
    metrics: {
      fileSizeBytes: 1024,
      pageCount: null,
      parseLatencyMs: 12,
      extractedCharacterCount: 26,
    },
  };
}

function currentProfile(): AutofillProfile {
  return {
    personal: {
      name: '当前姓名',
      phone: '13000000000',
      email: 'current@example.invalid',
      currentCity: '北京',
    },
    education: [{ school: '既有大学', major: '数学', degree: null, start: null, end: null }],
    experience: [],
    projects: [],
    links: { github: null, portfolio: null, homepage: null },
    createdAt: '2026-09-01T00:00:00Z',
    updatedAt: '2026-09-01T00:00:00Z',
  };
}

function savedResume(): ResumeVersion {
  return {
    id: 'resume-imported',
    name: '导入简历 2026-09-07',
    content: preview().extractedText,
    applicationCount: 0,
    createdAt: '2026-09-07T00:00:00Z',
    updatedAt: '2026-09-07T00:00:00Z',
  };
}
