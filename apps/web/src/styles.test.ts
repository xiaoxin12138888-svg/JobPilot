import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('responsive page shell', () => {
  it('does not force the body wider than the usable viewport', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8');
    const bodyRule = css.match(/body\s*\{(?<declarations>[^}]*)\}/)?.groups?.declarations;

    expect(bodyRule).toBeDefined();
    expect(bodyRule).toMatch(/min-width:\s*0/);
  });

  it('keeps Resume sections in one reading column at every viewport width', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8');
    const resumeDocumentRule = css.match(/\.resume-document\s*\{(?<declarations>[^}]*)\}/)?.groups
      ?.declarations;

    expect(resumeDocumentRule).toBeDefined();
    expect(resumeDocumentRule).toMatch(/grid-template-columns:\s*1fr/);
  });
});
