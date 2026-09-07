import type {
  FormFieldDescriptor,
  FormFieldKind,
  FormFieldOption,
  FormScanResult,
} from './autofill-types';

export function scanApplicationForm(): FormScanResult {
  const maxHintLength = 160;
  const ignoredInputTypes = new Set(['hidden', 'submit', 'button', 'reset', 'image', 'password']);

  const normalizedText = (value: string | null | undefined): string =>
    (value ?? '').replace(/\s+/g, ' ').trim().slice(0, maxHintLength);

  const textWithoutControls = (element: Element | null): string => {
    if (!element) return '';
    const copy = element.cloneNode(true) as Element;
    copy
      .querySelectorAll('input, textarea, select, option, button')
      .forEach((node) => node.remove());
    return normalizedText(copy.textContent);
  };

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

  const explicitLabel = (element: Element): string => {
    const id = normalizedText(element.getAttribute('id'));
    if (!id) return '';
    const label = Array.from(document.querySelectorAll<HTMLLabelElement>('label[for]')).find(
      (candidate) => candidate.htmlFor === id,
    );
    return textWithoutControls(label ?? null);
  };

  const labelledByText = (element: Element): string => {
    const ids = (element.getAttribute('aria-labelledby') ?? '').split(/\s+/).filter(Boolean);
    return normalizedText(
      ids
        .map((id) => normalizedText(document.getElementById(id)?.textContent))
        .filter(Boolean)
        .join(' '),
    );
  };

  const formItemLabel = (element: Element): string => {
    const group = element.closest('.form-item, .form-group, [role="group"]');
    if (!group) return '';
    return textWithoutControls(group.querySelector('label, [class*="label"]'));
  };

  const precedingText = (element: Element): string => {
    const previous = element.previousElementSibling;
    if (!previous || !previous.matches('label, span, p, div')) return '';
    return textWithoutControls(previous);
  };

  const fieldLabel = (element: Element): string => {
    const candidates = [
      explicitLabel(element),
      labelledByText(element),
      normalizedText(element.getAttribute('aria-label')),
      textWithoutControls(element.closest('label')),
      normalizedText(element.getAttribute('placeholder')),
      normalizedText(element.getAttribute('name')),
      normalizedText(element.getAttribute('id')),
      formItemLabel(element),
      precedingText(element),
      normalizedText(element.getAttribute('data-label')),
      normalizedText(element.getAttribute('data-field-name')),
    ];
    return candidates.find(Boolean) ?? '';
  };

  const isVerificationField = (element: Element, label: string): boolean => {
    const hint = [
      label,
      element.getAttribute('name'),
      element.getAttribute('id'),
      element.getAttribute('placeholder'),
      element.getAttribute('autocomplete'),
    ]
      .map(normalizedText)
      .join(' ');
    return /验证码|图形验证|captcha|verification[\s_-]*code|one[\s_-]*time[\s_-]*password|\botp\b/i.test(
      hint,
    );
  };

  const fieldKind = (element: Element): FormFieldKind => {
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

  const fieldOptions = (element: Element): FormFieldOption[] => {
    if (element instanceof HTMLSelectElement) {
      return Array.from(element.options).map((option) => ({
        label: normalizedText(option.label || option.textContent),
        value: option.value,
      }));
    }
    if (element.getAttribute('role') !== 'combobox') return [];
    const optionRoots = (element.getAttribute('aria-controls') ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => document.getElementById(id))
      .filter((root): root is HTMLElement => root !== null);
    return optionRoots.flatMap((root) =>
      Array.from(root.querySelectorAll('[role="option"]')).map((option) => {
        const label = normalizedText(option.getAttribute('aria-label') || option.textContent);
        return {
          label,
          value: normalizedText(option.getAttribute('data-value')) || label,
        };
      }),
    );
  };

  const uniqueAttributeValue = (attribute: 'id' | 'name', value: string): boolean =>
    Array.from(document.querySelectorAll(`[${attribute}]`)).filter(
      (candidate) => candidate.getAttribute(attribute) === value,
    ).length === 1;

  const domPath = (element: Element): string => {
    const segments: string[] = [];
    for (let current: Element | null = element; current; current = current.parentElement) {
      const tag = current.tagName.toLowerCase();
      const siblings = current.parentElement
        ? Array.from(current.parentElement.children).filter(
            (candidate) => candidate.tagName === current.tagName,
          )
        : [current];
      segments.unshift(`${tag}:nth-of-type(${siblings.indexOf(current) + 1})`);
    }
    return segments.join(' > ');
  };

  const fieldRef = (element: Element): string => {
    const id = normalizedText(element.getAttribute('id'));
    if (id && uniqueAttributeValue('id', id)) return `id:${id}`;
    const name = normalizedText(element.getAttribute('name'));
    if (name && uniqueAttributeValue('name', name)) return `name:${name}`;
    return `path:${domPath(element)}`;
  };

  const candidates = Array.from(
    document.querySelectorAll('input, textarea, select, [role="combobox"]'),
  );
  const fields: FormFieldDescriptor[] = [];

  for (const element of candidates) {
    if (element instanceof HTMLInputElement && ignoredInputTypes.has(element.type)) continue;
    if (
      (element instanceof HTMLInputElement ||
        element instanceof HTMLTextAreaElement ||
        element instanceof HTMLSelectElement) &&
      element.disabled
    ) {
      continue;
    }
    if (!isVisible(element)) continue;

    const label = fieldLabel(element);
    if (isVerificationField(element, label)) continue;

    fields.push({
      ref: fieldRef(element),
      label,
      kind: fieldKind(element),
      type: element instanceof HTMLInputElement ? element.type : null,
      name: normalizedText(element.getAttribute('name')) || null,
      id: normalizedText(element.getAttribute('id')) || null,
      required:
        element.hasAttribute('required') || element.getAttribute('aria-required') === 'true',
      placeholder: normalizedText(element.getAttribute('placeholder')) || null,
      autocomplete: normalizedText(element.getAttribute('autocomplete')) || null,
      options: fieldOptions(element),
    });
  }

  return { pageUrl: window.location.href, fields };
}
