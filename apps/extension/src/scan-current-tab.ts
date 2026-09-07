import type { FormFieldDescriptor, FormScanResult } from './autofill-types';
import { scanApplicationForm } from './form-scanner';

export interface FormScanSession extends FormScanResult {
  scanToken: string;
  tabId: number;
}

export async function scanCurrentApplicationForm(): Promise<FormScanSession> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined || tab.url === undefined || !isScannableUrl(tab.url)) {
    throw new Error('当前页面不支持表单扫描');
  }

  const results = await chrome.scripting.executeScript({
    func: scanApplicationForm,
    target: { tabId: tab.id },
  });
  const result: unknown = results[0]?.result;
  if (!isFormScanResult(result)) throw new Error('未能安全读取当前表单');

  return {
    ...result,
    scanToken: crypto.randomUUID(),
    tabId: tab.id,
  };
}

function isScannableUrl(value: string): boolean {
  if (value.length > 4096) return false;
  try {
    const url = new URL(value);
    return (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      url.username === '' &&
      url.password === ''
    );
  } catch {
    return false;
  }
}

function isFormScanResult(value: unknown): value is FormScanResult {
  if (!isRecord(value) || !isScannableUrlValue(value.pageUrl) || !Array.isArray(value.fields)) {
    return false;
  }
  return value.fields.length <= 250 && value.fields.every(isFormFieldDescriptor);
}

function isFormFieldDescriptor(value: unknown): value is FormFieldDescriptor {
  return (
    isRecord(value) &&
    isBoundedString(value.ref, 8192) &&
    /^(?:id|name|path):/.test(value.ref) &&
    isBoundedString(value.label, 160) &&
    isFieldKind(value.kind) &&
    isNullableBoundedString(value.type, 50) &&
    isNullableBoundedString(value.name, 160) &&
    isNullableBoundedString(value.id, 160) &&
    typeof value.required === 'boolean' &&
    isNullableBoundedString(value.placeholder, 160) &&
    isNullableBoundedString(value.autocomplete, 160) &&
    Array.isArray(value.options) &&
    value.options.length <= 200 &&
    value.options.every(
      (option) =>
        isRecord(option) &&
        isBoundedString(option.label, 160) &&
        isBoundedString(option.value, 160),
    )
  );
}

function isFieldKind(value: unknown): boolean {
  return (
    typeof value === 'string' &&
    [
      'TEXT',
      'TEXTAREA',
      'SELECT',
      'COMBOBOX',
      'DATE',
      'RADIO',
      'CHECKBOX',
      'FILE',
      'UNKNOWN',
    ].includes(value)
  );
}

function isScannableUrlValue(value: unknown): value is string {
  return typeof value === 'string' && isScannableUrl(value);
}

function isNullableBoundedString(value: unknown, maxLength: number): boolean {
  return value === null || isBoundedString(value, maxLength);
}

function isBoundedString(value: unknown, maxLength: number): value is string {
  return typeof value === 'string' && value.length <= maxLength;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
