import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8');

describe('Extension popup layout', () => {
  it('uses a stable Chrome popup width instead of a viewport-relative width', () => {
    expect(styles).toMatch(/body\s*{[^}]*\bwidth:\s*24rem;/s);
    expect(styles).not.toContain('width: min(24rem, 100vw)');
  });
});
