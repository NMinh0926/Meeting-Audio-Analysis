/** Hash routes: `#/` is the meeting list, `#/meetings/<id>` one meeting. */
export type Route = { page: 'list' } | { page: 'meeting'; id: string };

const MEETING = /^#\/meetings\/([0-9a-f-]{36})$/i;

export function parseRoute(hash: string): Route {
  const match = MEETING.exec(hash);
  return match ? { page: 'meeting', id: match[1]!.toLowerCase() } : { page: 'list' };
}

export const meetingHref = (id: string): string => `#/meetings/${id}`;
