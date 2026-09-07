import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FormFieldDescriptor } from './autofill-types';
import { type FillExecutionRequest, fillApplicationForm } from './fill-executor';
import fixture from './fixtures/autofill-form.html?raw';
import { scanApplicationForm } from './form-scanner';

beforeEach(() => {
  document.body.innerHTML = fixture;
  window.history.replaceState(null, '', '/apply?source=fixture');
});

afterEach(() => {
  document.body.replaceChildren();
  window.history.replaceState(null, '', '/');
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function descriptor(ref: string): FormFieldDescriptor {
  const found = scanApplicationForm().fields.find((field) => field.ref === ref);
  if (found === undefined) throw new Error(`Missing fixture descriptor: ${ref}`);
  return found;
}

function request(
  fields: Array<{ field: FormFieldDescriptor; value: string }>,
): FillExecutionRequest {
  return {
    pageUrl: window.location.href,
    scanToken: 'fixture-scan-token',
    fields,
  };
}

describe('fillApplicationForm', () => {
  it('fills text and textarea controls with the standard minimal event chain', async () => {
    const input = document.getElementById('full-name') as HTMLInputElement;
    const textarea = document.querySelector('textarea') as HTMLTextAreaElement;
    const inputEvents: string[] = [];
    const textareaEvents: string[] = [];
    for (const eventName of ['focus', 'input', 'change', 'blur']) {
      input.addEventListener(eventName, () => inputEvents.push(eventName));
      textarea.addEventListener(eventName, () => textareaEvents.push(eventName));
    }

    const result = await fillApplicationForm(
      request([
        { field: descriptor('id:full-name'), value: '示例候选人' },
        {
          field: scanApplicationForm().fields.find((field) => field.kind === 'TEXTAREA')!,
          value: '示例个人介绍',
        },
      ]),
    );

    expect(input.value).toBe('示例候选人');
    expect(textarea.value).toBe('示例个人介绍');
    expect(inputEvents).toEqual(['focus', 'input', 'change', 'blur']);
    expect(textareaEvents).toEqual(['focus', 'input', 'change', 'blur']);
    expect(result).toEqual({ status: 'COMPLETED', attempted: 2, filled: 2, failures: [] });
  });

  it('uses the native input setter instead of an element-level framework override', async () => {
    const input = document.getElementById('full-name') as HTMLInputElement;
    const nativeValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!;
    Object.defineProperty(input, 'value', {
      configurable: true,
      get: () => nativeValue.get!.call(input) as string,
      set: () => {
        throw new Error('element-level setter must not run');
      },
    });

    await expect(
      fillApplicationForm(
        request([{ field: descriptor('id:full-name'), value: '受控输入兼容值' }]),
      ),
    ).resolves.toEqual(expect.objectContaining({ status: 'COMPLETED', filled: 1 }));
    expect(input.value).toBe('受控输入兼容值');
  });

  it('fills native select by unique value and a month input with exact standard values', async () => {
    const select = document.getElementById('degree') as HTMLSelectElement;
    const month = document.getElementById('education-start') as HTMLInputElement;

    const result = await fillApplicationForm(
      request([
        { field: descriptor('id:degree'), value: 'master' },
        { field: descriptor('id:education-start'), value: '2026-09' },
      ]),
    );

    expect(select.value).toBe('master');
    expect(month.value).toBe('2026-09');
    expect(result).toEqual({ status: 'COMPLETED', attempted: 2, filled: 2, failures: [] });
  });

  it('fills a combobox only by clicking one unique safe option', async () => {
    const combobox = document.getElementById('city-combobox') as HTMLInputElement;
    const option = document.querySelector<HTMLElement>('[role="option"]')!;
    const optionClick = vi.fn();
    option.addEventListener('click', optionClick);

    const result = await fillApplicationForm(
      request([{ field: descriptor('id:city-combobox'), value: '示例市' }]),
    );

    expect(combobox.value).toBe('示例市');
    expect(optionClick).toHaveBeenCalledOnce();
    expect(result).toEqual({ status: 'COMPLETED', attempted: 1, filled: 1, failures: [] });
  });

  it('does not guess ambiguous select or combobox options and restores combobox text', async () => {
    const select = document.getElementById('degree') as HTMLSelectElement;
    select.append(new Option('硕士项目', 'master-program'), new Option('硕士预科', 'master-prep'));
    const combobox = document.getElementById('city-combobox') as HTMLInputElement;
    combobox.value = '原有城市';
    const listbox = document.getElementById('city-options')!;
    listbox.replaceChildren(
      Object.assign(document.createElement('div'), { role: 'option', textContent: '示例市一区' }),
      Object.assign(document.createElement('div'), { role: 'option', textContent: '示例市二区' }),
    );

    const result = await fillApplicationForm(
      request([
        { field: descriptor('id:degree'), value: '硕士项' },
        { field: descriptor('id:city-combobox'), value: '示例市' },
      ]),
    );

    expect(select.value).toBe('');
    expect(combobox.value).toBe('原有城市');
    expect(result).toEqual({
      status: 'PARTIAL_FAILURE',
      attempted: 2,
      filled: 0,
      failures: [
        { fieldRef: 'id:degree', code: 'NO_UNIQUE_OPTION' },
        { fieldRef: 'id:city-combobox', code: 'NO_UNIQUE_OPTION' },
      ],
    });
  });

  it('rejects missing and type-changed refs without filling a replacement element', async () => {
    const scanned = descriptor('id:full-name');
    document.getElementById('full-name')?.remove();
    const replacement = document.createElement('input');
    replacement.id = 'full-name';
    replacement.name = 'different-name';
    replacement.type = 'number';
    document.getElementById('application-form')?.prepend(replacement);

    const result = await fillApplicationForm(
      request([
        { field: { ...scanned, ref: 'id:missing' }, value: '不得填写' },
        { field: scanned, value: '也不得填写' },
      ]),
    );

    expect(replacement.value).toBe('');
    expect(result.status).toBe('PAGE_CHANGED');
    expect(result.failures).toEqual([
      { fieldRef: 'id:missing', code: 'MISSING_REF' },
      { fieldRef: 'id:full-name', code: 'STALE_FIELD' },
    ]);
  });

  it('keeps a uniquely identified field valid when only mutable form hints change', async () => {
    const scanned = descriptor('id:full-name');
    const input = document.getElementById('full-name') as HTMLInputElement;
    input.required = false;
    input.placeholder = '页面校验更新后的提示';
    input.autocomplete = 'off';

    const result = await fillApplicationForm(request([{ field: scanned, value: '示例候选人' }]));

    expect(input.value).toBe('示例候选人');
    expect(result).toEqual({ status: 'COMPLETED', attempted: 1, filled: 1, failures: [] });
  });

  it('keeps an id-identified field valid when a framework rewrites its auxiliary name', async () => {
    vi.useFakeTimers();
    const scanned = descriptor('id:full-name');
    const input = document.getElementById('full-name') as HTMLInputElement;
    input.name = 'framework_generated_name';

    const pendingResult = fillApplicationForm(request([{ field: scanned, value: '示例候选人' }]));
    await vi.advanceTimersByTimeAsync(1_000);
    const result = await pendingResult;

    expect(input.value).toBe('示例候选人');
    expect(result).toEqual({ status: 'COMPLETED', attempted: 1, filled: 1, failures: [] });
  });

  it('waits for a uniquely identified field that is briefly replaced during rerender', async () => {
    vi.useFakeTimers();
    const scanned = descriptor('id:full-name');
    const original = document.getElementById('full-name') as HTMLInputElement;
    const replacement = original.cloneNode() as HTMLInputElement;
    replacement.removeAttribute('value');
    original.remove();
    window.setTimeout(() => document.getElementById('application-form')?.prepend(replacement), 400);

    const pendingResult = fillApplicationForm(request([{ field: scanned, value: '示例候选人' }]));
    await vi.advanceTimersByTimeAsync(1_000);
    const result = await pendingResult;

    expect(replacement.value).toBe('示例候选人');
    expect(result).toEqual({ status: 'COMPLETED', attempted: 1, filled: 1, failures: [] });
  });

  it('rejects a changed page URL before touching any field', async () => {
    const input = document.getElementById('full-name') as HTMLInputElement;
    const changedPage = request([{ field: descriptor('id:full-name'), value: '不得填写' }]);
    changedPage.pageUrl = 'https://careers.example.test/a-different-form';

    const result = await fillApplicationForm(changedPage);

    expect(input.value).toBe('不应读取的现有姓名');
    expect(result).toEqual({ status: 'PAGE_CHANGED', attempted: 0, filled: 0, failures: [] });
  });

  it('never fills forbidden controls or triggers form submission', async () => {
    const formSubmit = vi.spyOn(HTMLFormElement.prototype, 'submit');
    const requestSubmit = vi.spyOn(HTMLFormElement.prototype, 'requestSubmit');
    const buttonClick = vi.spyOn(HTMLButtonElement.prototype, 'click');
    const password = document.querySelector<HTMLInputElement>('[name="password"]')!;
    const file = document.querySelector<HTMLInputElement>('[name="resume_file"]')!;
    const checkbox = document.querySelector<HTMLInputElement>('[name="agreement"]')!;

    const unsafeFields: FormFieldDescriptor[] = [
      { ...descriptor('id:full-name'), ref: 'name:password', type: 'password', name: 'password' },
      { ...descriptor('name:resume_file'), kind: 'FILE', type: 'file' },
      { ...descriptor('name:agreement'), kind: 'CHECKBOX', type: 'checkbox' },
    ];
    const result = await fillApplicationForm(
      request(unsafeFields.map((field) => ({ field, value: '不得填写' }))),
    );

    expect(password.value).toBe('');
    expect(file.files).toHaveLength(0);
    expect(checkbox.checked).toBe(false);
    expect(result.filled).toBe(0);
    expect(formSubmit).not.toHaveBeenCalled();
    expect(requestSubmit).not.toHaveBeenCalled();
    expect(buttonClick).not.toHaveBeenCalled();
  });

  it('enforces the sensitive-field policy again at the final write boundary', async () => {
    const salaryLabel = document.createElement('label');
    salaryLabel.htmlFor = 'expected-salary';
    salaryLabel.textContent = '期望薪资';
    const salary = document.createElement('input');
    salary.id = 'expected-salary';
    salary.name = 'expected_salary';
    document.getElementById('application-form')?.append(salaryLabel, salary);
    const salaryField = descriptor('id:expected-salary');

    const result = await fillApplicationForm(
      request([{ field: salaryField, value: '不得在此边界写入' }]),
    );

    expect(salary.value).toBe('');
    expect(result).toEqual({
      status: 'PARTIAL_FAILURE',
      attempted: 1,
      filled: 0,
      failures: [{ fieldRef: 'id:expected-salary', code: 'FORBIDDEN_FIELD' }],
    });
  });
});
