import { useEffect, useState } from 'react';

import MeetingListPage from './components/MeetingListPage';
import MeetingPage from './components/MeetingPage';
import { parseRoute } from './lib/route';

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  return route.page === 'meeting' ? <MeetingPage key={route.id} id={route.id} /> : <MeetingListPage />;
}
