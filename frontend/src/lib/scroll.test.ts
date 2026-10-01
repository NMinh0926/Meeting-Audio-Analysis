import { describe, expect, it } from 'vitest';

import { isOutOfView } from './scroll';

describe('isOutOfView', () => {
  // Visible band: 120 px (under the sticky header) to 800 px (window bottom).
  it.each([
    [{ top: 300, bottom: 330 }, false],
    [{ top: 100, bottom: 140 }, false], // partly under the header, still visible
    [{ top: 780, bottom: 820 }, false], // partly below the fold
    [{ top: 60, bottom: 120 }, true], // hidden behind the header
    [{ top: -200, bottom: -170 }, true],
    [{ top: 800, bottom: 830 }, true],
  ])('%j → %s', (rect, expected) => expect(isOutOfView(rect, 120, 800)).toBe(expected));
});
