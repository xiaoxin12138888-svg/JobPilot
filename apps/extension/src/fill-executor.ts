import type { FormFieldDescriptor } from './autofill-types';

export type FillFailureCode =
  | 'MISSING_REF'
  | 'STALE_FIELD'
  | 'FORBIDDEN_FIELD'
  | 'READONLY_FIELD'
  | 'NO_UNIQUE_OPTION'
  | 'UNSUPPORTED_CONTROL'
  | 'FILL_FAILED';

export interface FillInstruction {
  field: FormFieldDescriptor;
  value: string;
}

export interface FillExecutionRequest {
  pageUrl: string;
  scanToken: string;
  fields: FillInstruction[];
}

export interface FillFailure {
  fieldRef: string;
  code: FillFailureCode;
}

export interface FillExecutionResult {
  status: 'COMPLETED' | 'PARTIAL_FAILURE' | 'PAGE_CHANGED';
  attempted: number;
  filled: number;
  failures: FillFailure[];
}

export async function fillApplicationForm(
  request: FillExecutionRequest,
): Promise<FillExecutionResult> {
  type FillableControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

  const normalize = (value: string): string =>
    value
      .normalize('NFKC')
      .toLowerCase()
      .replace(/[\s\p{P}\p{S}_]+/gu, '');

  const isVisible = (element: Element): boolean => {
    for (let current: Element | null = element; current; current = current.parentElement) {
      if (
        current.hasAttribute('hidden') ||
        current.getAttribute('aria-hidden') === 'true' ||
        current.hasAttribute('data-jobpilot-ui')
      ) {
        return false;
      }
      if (current instanceof HTMLElement) {
        const style = window.getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
      }
    }
    return true;
  };

  const resolveRef = (ref: string): Element | null => {
    const separator = ref.indexOf(':');
    if (separator < 1) return null;
    const kind = ref.slice(0, separator);
    const value = ref.slice(separator + 1);
    if (!value) return null;
    if (kind === 'id' || kind === 'name') {
      const matches = Array.from(document.querySelectorAll(`[${kind}]`)).filter(
        (candidate) => candidate.getAttribute(kind) === value,
      );
      return matches.length === 1 ? matches[0]! : null;
    }
    if (
      kind !== 'path' ||
      !/^[a-z][a-z0-9-]*:nth-of-type\(\d+\)(?: > [a-z][a-z0-9-]*:nth-of-type\(\d+\))*$/i.test(value)
    ) {
      return null;
    }
    try {
      const matches = document.querySelectorAll(value);
      return matches.length === 1 ? matches[0]! : null;
    } catch {
      return null;
    }
  };

  const liveKind = (element: Element): FormFieldDescriptor['kind'] => {
    if (element.getAttribute('role') === 'combobox') return 'COMBOBOX';
    if (element instanceof HTMLTextAreaElement) return 'TEXTAREA';
    if (element instanceof HTMLSelectElement) return 'SELECT';
    if (!(element instanceof HTMLInputElement)) return 'UNKNOWN';
    if (element.type === 'date' || element.type === 'month') return 'DATE';
    if (element.type === 'radio') return 'RADIO';
    if (element.type === 'checkbox') return 'CHECKBOX';
    if (element.type === 'file') return 'FILE';
    return 'TEXT';
  };

  const matchesSignature = (element: Element, field: FormFieldDescriptor): boolean =>
    liveKind(element) === field.kind &&
    (element instanceof HTMLInputElement ? element.type : null) === field.type &&
    (element.getAttribute('name')?.trim() || null) === field.name &&
    (element.getAttribute('id')?.trim() || null) === field.id &&
    (element.hasAttribute('required') || element.getAttribute('aria-required') === 'true') ===
      field.required &&
    (element.getAttribute('placeholder')?.replace(/\s+/g, ' ').trim() || null) ===
      field.placeholder &&
    (element.getAttribute('autocomplete')?.replace(/\s+/g, ' ').trim() || null) ===
      field.autocomplete;

  const verificationPattern =
    /验证码|图形验证|captcha|verification[\s_-]*code|one[\s_-]*time[\s_-]*password|\botp\b/i;
  const sensitivePattern =
    /身份证|护照|银行卡|薪资|工资|期望待遇|民族|婚姻|政治面貌|签证|工作授权|工作许可|法律|隐私|授权|诚信|调剂|协议|条款|同意|声明|残疾|宗教|eeo|work[\s_-]*authorization|work[\s_-]*permit/iu;
  const isForbidden = (element: Element, field: FormFieldDescriptor): boolean => {
    if (['FILE', 'RADIO', 'CHECKBOX', 'UNKNOWN'].includes(field.kind)) return true;
    if (element instanceof HTMLInputElement && element.type === 'password') return true;
    const hints = [field.label, field.name, field.id, field.placeholder, field.autocomplete].join(
      ' ',
    );
    return verificationPattern.test(hints) || sensitivePattern.test(hints);
  };

  const nativeSetter = (element: FillableControl): ((value: string) => void) | null => {
    const prototype =
      element instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : element instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLSelectElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    return setter ? (value: string) => setter.call(element, value) : null;
  };

  const dispatchInputEvents = (element: FillableControl, blur = true): void => {
    element.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    if (blur) element.blur();
  };

  const setTextValue = (element: FillableControl, value: string, blur = true): boolean => {
    const setValue = nativeSetter(element);
    if (setValue === null) return false;
    element.focus();
    setValue(value);
    dispatchInputEvents(element, blur);
    return element.value === value;
  };

  const uniqueOption = (options: HTMLOptionElement[], value: string): HTMLOptionElement | null => {
    const exactValue = options.filter((option) => option.value === value);
    if (exactValue.length > 0) return exactValue.length === 1 ? exactValue[0]! : null;
    const exactLabel = options.filter((option) => option.label.trim() === value.trim());
    if (exactLabel.length > 0) return exactLabel.length === 1 ? exactLabel[0]! : null;
    const target = normalize(value);
    const normalized = options.filter(
      (option) => normalize(option.value) === target || normalize(option.label) === target,
    );
    if (normalized.length > 0) return normalized.length === 1 ? normalized[0]! : null;
    if (!target) return null;
    const contained = options.filter((option) => {
      const values = [normalize(option.value), normalize(option.label)].filter(Boolean);
      return values.some((candidate) => candidate.includes(target) || target.includes(candidate));
    });
    return contained.length === 1 ? contained[0]! : null;
  };

  const comboboxOptions = (element: Element): HTMLElement[] =>
    (element.getAttribute('aria-controls') ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => document.getElementById(id))
      .filter((root): root is HTMLElement => root !== null)
      .flatMap((root) => Array.from(root.querySelectorAll<HTMLElement>('[role="option"]')))
      .filter(
        (option) =>
          isVisible(option) &&
          option.getAttribute('aria-disabled') !== 'true' &&
          option.closest('button, input') === null,
      );

  const uniqueComboboxOption = (options: HTMLElement[], value: string): HTMLElement | null => {
    const target = normalize(value);
    const optionValues = (option: HTMLElement): string[] =>
      [option.getAttribute('data-value'), option.getAttribute('aria-label'), option.textContent]
        .filter((candidate): candidate is string => candidate !== null)
        .map(normalize)
        .filter(Boolean);
    const exact = options.filter((option) => optionValues(option).includes(target));
    if (exact.length > 0) return exact.length === 1 ? exact[0]! : null;
    if (!target) return null;
    const contained = options.filter((option) =>
      optionValues(option).some(
        (candidate) => candidate.includes(target) || target.includes(candidate),
      ),
    );
    return contained.length === 1 ? contained[0]! : null;
  };

  const fillCombobox = async (
    element: Element,
    value: string,
  ): Promise<'FILLED' | 'NO_UNIQUE_OPTION' | 'UNSUPPORTED_CONTROL'> => {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) {
      return 'UNSUPPORTED_CONTROL';
    }
    const previousValue = element.value;
    if (!setTextValue(element, value, false)) return 'UNSUPPORTED_CONTROL';
    await new Promise((resolve) => window.setTimeout(resolve, 75));
    const option = uniqueComboboxOption(comboboxOptions(element), value);
    if (option === null) {
      setTextValue(element, previousValue);
      return 'NO_UNIQUE_OPTION';
    }
    option.click();
    element.blur();
    return 'FILLED';
  };

  const fillOne = async (instruction: FillInstruction): Promise<FillFailureCode | null> => {
    const element = resolveRef(instruction.field.ref);
    if (element === null) return 'MISSING_REF';
    if (!matchesSignature(element, instruction.field)) return 'STALE_FIELD';
    if (!isVisible(element) || isForbidden(element, instruction.field)) return 'FORBIDDEN_FIELD';
    if (element.getAttribute('aria-disabled') === 'true') return 'READONLY_FIELD';
    if (
      (element instanceof HTMLInputElement ||
        element instanceof HTMLTextAreaElement ||
        element instanceof HTMLSelectElement) &&
      (element.disabled || ('readOnly' in element && element.readOnly))
    ) {
      return 'READONLY_FIELD';
    }

    if (instruction.field.kind === 'COMBOBOX') {
      const result = await fillCombobox(element, instruction.value);
      return result === 'FILLED' ? null : result;
    }
    if (instruction.field.kind === 'SELECT' && element instanceof HTMLSelectElement) {
      const option = uniqueOption(Array.from(element.options), instruction.value);
      if (option === null) return 'NO_UNIQUE_OPTION';
      return setTextValue(element, option.value) ? null : 'FILL_FAILED';
    }
    if (
      (instruction.field.kind === 'TEXT' ||
        instruction.field.kind === 'TEXTAREA' ||
        instruction.field.kind === 'DATE') &&
      (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)
    ) {
      return setTextValue(element, instruction.value) ? null : 'FILL_FAILED';
    }
    return 'UNSUPPORTED_CONTROL';
  };

  if (window.location.href !== request.pageUrl) {
    return { status: 'PAGE_CHANGED', attempted: 0, filled: 0, failures: [] };
  }

  const failures: FillFailure[] = [];
  let filled = 0;
  for (const instruction of request.fields.slice(0, 250)) {
    let code: FillFailureCode | null;
    try {
      code = await fillOne(instruction);
    } catch {
      code = 'FILL_FAILED';
    }
    if (code === null) filled += 1;
    else failures.push({ fieldRef: instruction.field.ref, code });
  }

  const attempted = Math.min(request.fields.length, 250);
  const staleCount = failures.filter(
    (failure) => failure.code === 'MISSING_REF' || failure.code === 'STALE_FIELD',
  ).length;
  const pageChanged =
    attempted > 0 && (staleCount === attempted || (staleCount >= 2 && staleCount * 2 >= attempted));
  return {
    status: pageChanged ? 'PAGE_CHANGED' : failures.length > 0 ? 'PARTIAL_FAILURE' : 'COMPLETED',
    attempted,
    filled,
    failures,
  };
}
