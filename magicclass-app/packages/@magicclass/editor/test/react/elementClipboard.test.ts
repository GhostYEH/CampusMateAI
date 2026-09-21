import { describe, expect, it } from 'vitest';
import { parseElementClipboardPayload } from '../../src/react/elementClipboard';

const element = {
  id: 'text-1',
  type: 'text',
  left: 10,
  top: 20,
  width: 100,
  height: 40,
  rotate: 0,
  content: '<p>Clipboard</p>',
  defaultFontName: 'Arial',
  defaultColor: '#333333',
};

describe('element clipboard payload compatibility', () => {
  it.each(['magicclass/renderer-elements', 'magicclass/editor-elements'])(
    'reads %s payloads',
    (kind) => {
      expect(
        parseElementClipboardPayload(JSON.stringify({ kind, version: 1, elements: [element] })),
      ).toEqual([element]);
    },
  );

  it('rejects unrelated clipboard data', () => {
    expect(parseElementClipboardPayload('{"kind":"other","version":1,"elements":[]}')).toBeNull();
  });

  it('rejects branded payloads whose elements violate the DSL contract', () => {
    expect(
      parseElementClipboardPayload(
        JSON.stringify({
          kind: 'magicclass/editor-elements',
          version: 1,
          elements: [{ ...element, left: '10' }],
        }),
      ),
    ).toBeNull();
  });
});
