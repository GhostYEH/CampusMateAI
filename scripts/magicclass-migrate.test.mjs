import assert from 'node:assert/strict';
import test from 'node:test';

import { replaceBrandContent, replaceBrandPath, replaceTechnicalTokens } from './magicclass-migrate.mjs';

const lower = ['open', 'maic'].join('');
const upper = lower.toUpperCase();
const title = `${lower.slice(0, 1).toUpperCase()}${lower.slice(1, 4)}${upper.slice(4)}`;

test('uses valid technical identifiers and preserves typography', () => {
  assert.equal(replaceTechnicalTokens(`${title}Client ${lower} ${upper}`), 'MagicClassClient magicclass MAGICCLASS');
  assert.equal(
    replaceBrandContent('src/example.tsx', `title: '${title}'; font-family: Literata; font-weight: 650;`),
    "title: 'magic class'; font-family: Literata; font-weight: 650;",
  );
});

test('keeps paths and imports free of display spaces', () => {
  assert.equal(replaceBrandPath(`src/${lower}/${title}Page.jsx`), 'src/magicclass/magicclassPage.jsx');
  assert.equal(
    replaceBrandContent('src/App.jsx', `import Page from './${title}Page.jsx';`),
    "import Page from './magicclassPage.jsx';",
  );
});
