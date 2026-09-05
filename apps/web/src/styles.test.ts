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
});
