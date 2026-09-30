import { describe, expect, it } from 'vitest';

import { formatBytes, formatClock, genderLabel, stageLabel } from './format';

describe('formatClock', () => {
  it.each([
    [0, '0:00'],
    [59.9, '0:59'],
    [61, '1:01'],
    [3725.5, '1:02:05'],
    [-3, '0:00'],
  ])('%s s → %s', (seconds, expected) => expect(formatClock(seconds)).toBe(expected));
});

describe('formatBytes', () => {
  it.each([
    [512, '512 B'],
    [2048, '2 KB'],
    [46_071_991, '43.9 MB'],
  ])('%s → %s', (bytes, expected) => expect(formatBytes(bytes)).toBe(expected));
});

describe('labels', () => {
  it('maps genders to Vietnamese and anything else to unknown', () => {
    expect(genderLabel('male')).toBe('Nam');
    expect(genderLabel('female')).toBe('Nữ');
    expect(genderLabel('unknown')).toBe('Không rõ');
  });

  it('names known stages and passes through new ones', () => {
    expect(stageLabel('diarization')).toBe('Tách người nói');
    expect(stageLabel('something_new')).toBe('something_new');
    expect(stageLabel(null)).toBe('');
  });
});
