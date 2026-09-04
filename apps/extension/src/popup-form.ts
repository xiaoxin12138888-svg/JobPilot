import { JOB_SOURCE_LABELS } from '@jobpilot/api-client';

import type { JobCaptureDraft } from './job-capture';
import { actionButton, setRootState, statusText } from './popup-view';

type EditableField = 'title' | 'company' | 'location' | 'salaryText' | 'description';

const MAX_LENGTHS: Readonly<Record<EditableField, number>> = {
  title: 200,
  company: 200,
  location: 300,
  salaryText: 300,
  description: 100_000,
};

export function renderPreview(
  root: HTMLElement,
  draft: JobCaptureDraft,
  warnings: readonly string[],
  validationMessage: string | undefined,
  onSave: (draft: JobCaptureDraft) => void,
): void {
  setRootState(root, 'preview');
  const form = document.createElement('form');
  form.className = 'capture-form';
  form.append(
    statusText('确认岗位信息', 'status-title'),
    statusText(`来源：${JOB_SOURCE_LABELS[draft.source]}`, 'source-label'),
    formField('职位名称', 'title', draft.title, true),
    formField('公司', 'company', draft.company, true),
    formField('地点', 'location', draft.location),
    formField('薪资', 'salaryText', draft.salaryText),
    formField('岗位描述', 'description', draft.description, false, true),
  );
  if (warnings.length > 0) form.append(warningList(warnings));
  if (validationMessage !== undefined) {
    form.append(statusText(validationMessage, 'form-error', 'alert'));
  }
  form.append(actionButton('保存到 JobPilot', 'primary-button', () => undefined, 'submit'));
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    onSave(readDraft(form, draft));
  });
  root.replaceChildren(form);
}

function warningList(warnings: readonly string[]): HTMLUListElement {
  const list = document.createElement('ul');
  list.className = 'warning-list';
  list.setAttribute('aria-label', '自动识别提示');
  for (const warning of warnings) {
    const item = document.createElement('li');
    item.textContent = warning;
    list.append(item);
  }
  return list;
}

function formField(
  labelText: string,
  name: EditableField,
  value: string,
  required = false,
  multiline = false,
): HTMLLabelElement {
  const label = document.createElement('label');
  label.className = 'form-field';
  const caption = document.createElement('span');
  caption.textContent = labelText;
  const control = multiline ? document.createElement('textarea') : document.createElement('input');
  control.name = name;
  control.value = value;
  control.required = required;
  control.maxLength = MAX_LENGTHS[name];
  if (multiline) (control as HTMLTextAreaElement).rows = 6;
  label.append(caption, control);
  return label;
}

function readDraft(form: HTMLFormElement, original: JobCaptureDraft): JobCaptureDraft {
  const data = new FormData(form);
  return {
    ...original,
    company: String(data.get('company') ?? ''),
    description: String(data.get('description') ?? ''),
    location: String(data.get('location') ?? ''),
    salaryText: String(data.get('salaryText') ?? ''),
    title: String(data.get('title') ?? ''),
  };
}
