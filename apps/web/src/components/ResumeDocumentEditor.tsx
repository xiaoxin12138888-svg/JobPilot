import { useState } from 'react';

import {
  createEditableResumeDocument,
  rebuildEditableResumeDocument,
} from './resumeDocumentSections';

interface ResumeDocumentEditorProps {
  content: string;
  disabled: boolean;
  onChange(content: string): void;
}

export function ResumeDocumentEditor({ content, disabled, onChange }: ResumeDocumentEditorProps) {
  const [document] = useState(() => createEditableResumeDocument(content));
  const [values, setValues] = useState(() => document.sections.map((section) => section.content));

  function updateSection(index: number, value: string) {
    const nextValues = values.map((currentValue, currentIndex) =>
      currentIndex === index ? value : currentValue,
    );
    setValues(nextValues);
    onChange(rebuildEditableResumeDocument(document, nextValues));
  }

  return (
    <div className="resume-document-editor" aria-label="分区编辑简历">
      {document.sections.map((section, index) => (
        <label className="resume-section-editor" key={section.id}>
          <span>{section.title}</span>
          <textarea
            maxLength={100_000}
            rows={Math.max(3, Math.min(12, values[index]!.split(/\r?\n/).length + 1))}
            value={values[index]}
            disabled={disabled}
            onChange={(event) => updateSection(index, event.target.value)}
          />
        </label>
      ))}
    </div>
  );
}
