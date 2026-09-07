export type FormFieldKind =
  'TEXT' | 'TEXTAREA' | 'SELECT' | 'COMBOBOX' | 'DATE' | 'RADIO' | 'CHECKBOX' | 'FILE' | 'UNKNOWN';

export interface FormFieldOption {
  label: string;
  value: string;
}

export interface FormFieldDescriptor {
  ref: string;
  label: string;
  kind: FormFieldKind;
  type: string | null;
  name: string | null;
  id: string | null;
  required: boolean;
  placeholder: string | null;
  autocomplete: string | null;
  options: FormFieldOption[];
}

export interface FormScanResult {
  pageUrl: string;
  fields: FormFieldDescriptor[];
}
