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

export type CanonicalFieldKey =
  | 'name'
  | 'phone'
  | 'email'
  | 'current_city'
  | 'school'
  | 'major'
  | 'degree'
  | 'education_start'
  | 'education_end'
  | 'company'
  | 'position'
  | 'experience_start'
  | 'experience_end'
  | 'experience_description'
  | 'github'
  | 'portfolio'
  | 'homepage';

export type FillPlanStatus = 'READY' | 'REVIEW_REQUIRED' | 'MANUAL' | 'UNMAPPED';

export interface FillPlanItem {
  fieldRef: string;
  pageLabel: string;
  canonicalKey: CanonicalFieldKey | null;
  proposedValue: string | null;
  status: FillPlanStatus;
  selected: boolean;
}
