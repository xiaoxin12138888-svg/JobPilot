import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import fixture from './fixtures/autofill-form.html?raw';
import { scanApplicationForm } from './form-scanner';

beforeEach(() => {
  document.body.innerHTML = fixture;
  window.history.replaceState(null, '', '/apply?source=fixture');
});

afterEach(() => {
  document.body.replaceChildren();
  window.history.replaceState(null, '', '/');
});

describe('scanApplicationForm', () => {
  it('describes visible controls with bounded semantic hints and no current values', () => {
    const result = scanApplicationForm();

    expect(result.pageUrl).toBe('http://localhost:3000/apply?source=fixture');
    expect(result.fields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          ref: 'id:full-name',
          label: '姓名',
          kind: 'TEXT',
          name: 'candidate_name',
          required: true,
        }),
        expect.objectContaining({
          ref: 'name:phone',
          label: '手机号码',
          kind: 'TEXT',
          type: 'tel',
        }),
        expect.objectContaining({ label: '电子邮箱', autocomplete: null }),
        expect.objectContaining({ label: '毕业院校', placeholder: '毕业院校' }),
        expect.objectContaining({ label: '个人介绍', kind: 'TEXTAREA' }),
        expect.objectContaining({
          label: '学历',
          kind: 'SELECT',
          options: [
            { label: '请选择', value: '' },
            { label: '本科', value: 'bachelor' },
            { label: '硕士', value: 'master' },
          ],
        }),
        expect.objectContaining({ label: '入学月份', kind: 'DATE', type: 'month' }),
        expect.objectContaining({
          label: '当前城市',
          kind: 'COMBOBOX',
          options: [{ label: '示例市', value: '示例市' }],
        }),
        expect.objectContaining({ kind: 'CHECKBOX', name: 'agreement' }),
        expect.objectContaining({ kind: 'RADIO', name: 'relocate' }),
        expect.objectContaining({ kind: 'FILE', name: 'resume_file' }),
      ]),
    );
    expect(result.fields.every((field) => !('value' in field))).toBe(true);
  });

  it('ignores password, verification, hidden, disabled, submit and JobPilot controls', () => {
    const names = scanApplicationForm().fields.map((field) => field.name);

    expect(names).not.toContain('password');
    expect(names).not.toContain('verification_code');
    expect(names).not.toContain('hidden_token');
    expect(names).not.toContain('visually_hidden');
    expect(names).not.toContain('disabled_field');
    expect(names).not.toContain('jobpilot-control');
    expect(scanApplicationForm().fields.some((field) => field.type === 'submit')).toBe(false);
  });

  it('creates unique round-trip refs using id, unique name and then a DOM path', () => {
    const fields = scanApplicationForm().fields;
    const refs = fields.map((field) => field.ref);

    expect(new Set(refs).size).toBe(refs.length);
    expect(refs).toContain('id:full-name');
    expect(refs).toContain('name:phone');
    expect(fields.find((field) => field.kind === 'TEXTAREA')?.ref).toMatch(/^path:/);
  });
});
