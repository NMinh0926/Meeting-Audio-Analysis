/** Keys that scroll the page; arrow keys and Space are player shortcuts and do not. */
export const SCROLL_KEYS = new Set(['PageUp', 'PageDown', 'Home', 'End']);

/** A scroll counts as the user's for this long after their wheel, touch, key or scrollbar input. */
export const USER_SCROLL_MS = 1000;

/** True when an element lies wholly outside the visible band between the sticky header and the window bottom. */
export function isOutOfView(rect: { top: number; bottom: number }, viewTop: number, viewBottom: number): boolean {
  return rect.bottom <= viewTop || rect.top >= viewBottom;
}
