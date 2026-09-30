import { describe, expect, it } from 'vitest';

import { errorMessage, exportUrl } from './client';

describe('errorMessage', () => {
  it('uses the API detail string', () => {
    expect(errorMessage(409, '{"detail":"Meeting is not processed yet"}')).toBe('Meeting is not processed yet');
  });

  it('uses the first validation message', () => {
    expect(errorMessage(422, '{"detail":[{"msg":"String should have at least 1 character"}]}')).toBe(
      'String should have at least 1 character',
    );
  });

  it('falls back to the status for non-JSON bodies', () => {
    expect(errorMessage(502, '<html>Bad Gateway</html>')).toBe('Lỗi 502');
  });
});

it('builds export URLs', () => {
  expect(exportUrl('abc', 'srt')).toBe('/api/v1/meetings/abc/export?format=srt');
});
