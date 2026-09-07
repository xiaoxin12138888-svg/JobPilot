import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const API_LOOPBACK_ORIGIN = 'http://127.0.0.1:8000';
const WEB_LOOPBACK_ORIGIN = 'http://127.0.0.1:5173';
const EXPECTED_EXTENSION_ID = 'lgchonbleblfegkckndaaandoaekmgjf';
const EXPECTED_CSP =
  "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; " +
  `connect-src ${API_LOOPBACK_ORIGIN}; base-uri 'none'`;
const distDirectory = fileURLToPath(new URL('../dist/', import.meta.url));

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const absolutePath = path.join(directory, entry.name);
      return entry.isDirectory() ? listFiles(absolutePath) : [absolutePath];
    }),
  );
  return files.flat();
}

const absoluteFiles = await listFiles(distDirectory);
const artifactFiles = absoluteFiles
  .map((file) => path.relative(distDirectory, file).replaceAll('\\', '/'))
  .sort();

assert(artifactFiles.includes('manifest.json'), 'Extension artifact is missing manifest.json');
assert(artifactFiles.includes('popup.html'), 'Extension artifact is missing popup.html');
for (const file of artifactFiles) {
  assert.match(
    file,
    /^(?:manifest\.json|popup\.html|assets\/[^/]+\.(?:css|js))$/u,
    `Unexpected Extension artifact file: ${file}`,
  );
}

const manifest = JSON.parse(await readFile(path.join(distDirectory, 'manifest.json'), 'utf8'));
assert.equal(manifest.manifest_version, 3);
assert.equal(manifest.action?.default_popup, 'popup.html');
assert.deepEqual(manifest.permissions, ['activeTab', 'scripting']);
assert.deepEqual(manifest.host_permissions, [`${API_LOOPBACK_ORIGIN}/*`]);
assert.equal(manifest.content_security_policy?.extension_pages, EXPECTED_CSP);
const extensionId = [...createHash('sha256').update(Buffer.from(manifest.key, 'base64')).digest()]
  .slice(0, 16)
  .flatMap((byte) => [byte >> 4, byte & 0x0f])
  .map((nibble) => String.fromCharCode('a'.charCodeAt(0) + nibble))
  .join('');
assert.equal(extensionId, EXPECTED_EXTENSION_ID, 'Extension public key changed its fixed ID');

for (const forbiddenKey of [
  'optional_permissions',
  'optional_host_permissions',
  'background',
  'content_scripts',
  'oauth2',
  'externally_connectable',
  'web_accessible_resources',
]) {
  assert(!(forbiddenKey in manifest), `Forbidden manifest surface: ${forbiddenKey}`);
}

const sourceByFile = new Map(
  await Promise.all(
    absoluteFiles.map(async (absoluteFile) => [
      path.relative(distDirectory, absoluteFile).replaceAll('\\', '/'),
      await readFile(absoluteFile, 'utf8'),
    ]),
  ),
);
const popupHtml = sourceByFile.get('popup.html') ?? '';
const scriptTags = [...popupHtml.matchAll(/<script\b([^>]*)>/giu)];
assert(scriptTags.length > 0, 'Extension Popup has no bundled script');
for (const [, attributes] of scriptTags) {
  assert.match(attributes, /\bsrc=["']\/assets\/[^"']+\.js["']/u, 'Popup script must be local');
}

const artifactSource = [...sourceByFile.values()].join('\n');
const withoutApprovedLoopback = artifactSource
  .replaceAll(`${API_LOOPBACK_ORIGIN}/*`, '')
  .replaceAll(API_LOOPBACK_ORIGIN, '')
  .replaceAll(WEB_LOOPBACK_ORIGIN, '');
assert.doesNotMatch(withoutApprovedLoopback, /https?:\/\//iu, 'Remote runtime URL detected');
assert.doesNotMatch(
  artifactSource,
  /unsafe-eval|<all_urls>|chrome\.(?:cookies|history|identity|proxy|storage|webRequest)|\b(?:auth0|logto|oauth|oidc|pkce|telemetry|analytics|sentry)\b/iu,
  'Forbidden Extension runtime capability detected',
);
assert.doesNotMatch(
  artifactSource,
  /document\.cookie|\b(?:localStorage|sessionStorage)\b|\bhistory\s*\.|\.submit\s*\(|requestSubmit\s*\(|__reactFiber|__reactInternalInstance|__vue__/u,
  'Forbidden page access or auto-submit behavior detected',
);
assert.doesNotMatch(
  artifactSource,
  /JOBPILOT_LLM|API[_-]?KEY/iu,
  'Secret-bearing configuration detected in Extension artifact',
);

console.log(`Extension artifact security gate PASS (${artifactFiles.length} files)`);
