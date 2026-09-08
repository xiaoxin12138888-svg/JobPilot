import { useId } from 'react';

import { sectionResumeContent } from './resumeDocumentSections';

interface ResumeDocumentViewProps {
  content: string;
}

export function ResumeDocumentView({ content }: ResumeDocumentViewProps) {
  const headingId = useId().replaceAll(':', '');
  const sections = sectionResumeContent(content);

  return (
    <div className="resume-document" aria-label="简历分区内容">
      {sections.map((section, index) => {
        const sectionHeadingId = `${headingId}-resume-section-${index}`;
        return (
          <section
            className="resume-document-section"
            aria-labelledby={sectionHeadingId}
            key={`${section.key}-${index}`}
          >
            <h2 id={sectionHeadingId}>{section.title}</h2>
            <div className="resume-document-content">{section.content}</div>
          </section>
        );
      })}
    </div>
  );
}
