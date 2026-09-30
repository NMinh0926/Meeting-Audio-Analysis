import { describe, expect, it } from 'vitest';

import type { Turn } from '../api/types';
import { findActiveIndex, flattenUtterances } from './transcript';

const turn = (id: number, utterances: [number, number][]): Turn => ({
  id,
  speaker_id: 1,
  start: utterances[0]![0],
  end: utterances[utterances.length - 1]![1],
  text: '',
  sentiment: 'neutral',
  sentiment_confidence: 0.5,
  utterances: utterances.map(([start, end]) => ({ start, end, text: `${start}` })),
});

const turns = [turn(1, [[0, 2], [2.5, 4]]), turn(2, [[5, 7]]), turn(3, [[8, 9], [9.5, 12]])];

describe('flattenUtterances', () => {
  it('lists utterances in time order with their turn position', () => {
    expect(flattenUtterances(turns).map((r) => [r.turn, r.utterance, r.start])).toEqual([
      [0, 0, 0],
      [0, 1, 2.5],
      [1, 0, 5],
      [2, 0, 8],
      [2, 1, 9.5],
    ]);
  });
});

describe('findActiveIndex', () => {
  const refs = flattenUtterances(turns);

  it.each([
    [-1, -1],
    [0, 0],
    [1.9, 0],
    [2.2, 0], // pause between sentences keeps the previous one
    [2.5, 1],
    [6, 2],
    [11.9, 4],
    [100, 4],
  ])('at %s s → %s', (time, expected) => expect(findActiveIndex(refs, time)).toBe(expected));

  it('is -1 for an empty transcript', () => expect(findActiveIndex([], 3)).toBe(-1));
});
