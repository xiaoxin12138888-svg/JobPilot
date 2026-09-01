import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const LOOPBACK_ORIGIN = 'http://127.0.0.1:8000';
const EXPECTED_CSP =
  "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; " +
  `connect-src ${LOOPBACK_ORIGIN}; base-uri 'none'`;
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
assert.deepEqual(manifest.host_permissions, [`${LOOPBACK_ORIGIN}/*`]);
assert.equal(manifest.content_security_policy?.extension_pages, EXPECTED_CSP);

for (const forbiddenKey of [
  'permissions',
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
  .replaceAll(`${LOOPBACK_ORIGIN}/*`, '')
  .replaceAll(LOOPBACK_ORIGIN, '');
assert.doesNotMatch(withoutApprovedLoopback, /https?:\/\//iu, 'Remote runtime URL detected');
assert.doesNotMatch(
  artifactSource,
  /unsafe-eval|<all_urls>|chrome\.(?:identity|storage|tabs|proxy)|\b(?:auth0|logto|oauth|oidc|pkce|telemetry|analytics|sentry)\b/iu,
  'Forbidden Extension runtime capability detected',
);

console.log(`Extension artifact security gate PASS (${artifactFiles.length} files)`);
