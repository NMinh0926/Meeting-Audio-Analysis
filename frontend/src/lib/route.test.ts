import { describe, expect, it } from 'vitest';

import { meetingHref, parseRoute } from './route';

const id = '01d808fc-f69e-4cab-bec2-ce0642dc51fd';

describe('parseRoute', () => {
  it('opens a meeting from its hash', () => {
    expect(parseRoute(meetingHref(id))).toEqual({ page: 'meeting', id });
    expect(parseRoute(`#/meetings/${id.toUpperCase()}`)).toEqual({ page: 'meeting', id });
  });

  it.each(['', '#/', '#/meetings/', '#/meetings/not-an-id', `#/meetings/${id}/x`])('%s → list', (hash) =>
    expect(parseRoute(hash)).toEqual({ page: 'list' }),
  );
});
