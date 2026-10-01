import { describe, expect, it } from 'vitest';

import { type KeyLike, clampTime, nextRate, shortcutFor } from './player';

describe('clampTime', () => {
  it.each([
    [-3, 100, 0],
    [42, 100, 42],
    [105, 100, 100],
    [105, Number.NaN, 105], // duration not loaded yet
    [-1, Number.NaN, 0],
    [7, 0, 7],
  ])('%s s in a %s s recording → %s', (seconds, duration, expected) =>
    expect(clampTime(seconds, duration)).toBe(expected),
  );
});

describe('nextRate', () => {
  it.each([
    [0.75, 1],
    [1, 1.25],
    [1.5, 2],
    [2, 0.75],
    [1.1, 1],
  ])('%s → %s', (current, expected) => expect(nextRate(current)).toBe(expected));
});

describe('shortcutFor', () => {
  const press = (key: string, target: KeyLike['target'] = { tagName: 'BODY' }, extra: Partial<KeyLike> = {}) =>
    shortcutFor({ key, ctrlKey: false, altKey: false, metaKey: false, target, ...extra });

  it.each([
    ['ArrowLeft', 'back'],
    ['ArrowRight', 'forward'],
    ['ArrowUp', 'previous'],
    ['ArrowDown', 'next'],
    [' ', 'toggle'],
    ['a', null],
    ['Enter', null],
  ])('%j → %s', (key, expected) => expect(press(key)).toBe(expected));

  it('ignores keys while typing', () => {
    expect(press('ArrowLeft', { tagName: 'INPUT', type: 'text' })).toBeNull();
    expect(press(' ', { tagName: 'INPUT' })).toBeNull();
    expect(press(' ', { tagName: 'TEXTAREA' })).toBeNull();
    expect(press(' ', { tagName: 'DIV', isContentEditable: true })).toBeNull();
  });

  it('keeps shortcuts on the seek slider, checkboxes and buttons', () => {
    expect(press('ArrowRight', { tagName: 'INPUT', type: 'range' })).toBe('forward');
    expect(press(' ', { tagName: 'INPUT', type: 'checkbox' })).toBe('toggle');
    expect(press(' ', { tagName: 'BUTTON' })).toBe('toggle');
  });

  it('leaves browser shortcuts alone', () => {
    expect(press('ArrowLeft', undefined, { altKey: true })).toBeNull();
    expect(press('ArrowRight', undefined, { ctrlKey: true })).toBeNull();
    expect(press('ArrowLeft', undefined, { metaKey: true })).toBeNull();
  });

  it('works without a target', () => expect(press('ArrowDown', null)).toBe('next'));
});
