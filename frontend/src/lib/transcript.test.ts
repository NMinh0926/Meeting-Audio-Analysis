import { describe, expect, it } from 'vitest';

import type { Turn } from '../api/types';
import { findActiveIndex, flattenUtterances, sentenceStart, talkTime } from './transcript';

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

describe('sentenceStart', () => {
  const refs = flattenUtterances(turns); // starts 0, 2.5, 5, 8, 9.5

  it.each([
    [-1, 0],
    [0, 2.5],
    [3, 5],
    [7.9, 8],
    [11, null],
  ])('next from %s s → %s', (time, expected) => expect(sentenceStart(refs, time, 'next')).toBe(expected));

  it.each([
    [-1, null],
    [0.5, 0], // first sentence: back to its start
    [2.6, 0], // just started: the sentence before
    [5.4, 2.5],
    [6.6, 5], // well into it: its own start
    [11, 8], // exactly 1.5 s in still counts as just started
    [11.5, 9.5],
  ])('previous from %s s → %s', (time, expected) => expect(sentenceStart(refs, time, 'previous')).toBe(expected));

  it('is null for an empty transcript', () => {
    expect(sentenceStart([], 3, 'next')).toBeNull();
    expect(sentenceStart([], 3, 'previous')).toBeNull();
  });
});

describe('talkTime', () => {
  it('sums turn lengths per speaker', () => {
    const mixed = [turn(1, [[0, 2]]), { ...turn(2, [[3, 7]]), speaker_id: 2 }, turn(3, [[8, 9.5]])];
    expect([...talkTime(mixed)]).toEqual([
      [1, 3.5],
      [2, 4],
    ]);
  });

  it('is empty without turns', () => expect(talkTime([]).size).toBe(0));
});
