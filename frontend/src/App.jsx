import { useCallback, useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AppCtx, BusyButton, post, request, useToast } from './lib.jsx';
import Dashboard from './pages/Dashboard.jsx';
import WeeklyDigest from './pages/WeeklyDigest.jsx';
import Planning from './pages/Planning.jsx';
import Closure from './pages/Closure.jsx';
import ChatWidget from './ChatWidget.jsx';

const NAV = [
  ['/dashboard', 'Dashboard', 'dashboard'],
  ['/weekly-report', 'Weekly Report', 'digest'],
  ['/planning', 'Planning', 'planning'],
  ['/closure', 'Closure', 'closure'],
];

export default function App() {
  const [toastState, toast] = useToast();
  const [version, setVersion] = useState(0);
  const [meta, setMeta] = useState({ fetched_at: 'not loaded' });
  const { pathname } = useLocation();
  const module = (NAV.find(n => n[0] === pathname) || [])[2] || 'dashboard';

  const loadMeta = useCallback(() => request('/api/meta').then(setMeta).catch(() => {}), []);
  useEffect(() => { loadMeta(); }, [loadMeta, version]);

  const refresh = async () => {
    await post('/api/refresh/' + module);
    setVersion(v => v + 1);
  };

  return (
    <AppCtx.Provider value={{ toast, version }}>
      <header className="topbar">
        <div className="brand">PMO Automation<span>Trello</span></div>
        <nav>
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>{label}</NavLink>
          ))}
        </nav>
        <div className="meta">
          <span className="badge trello">Live Trello</span>
          <span className="muted">Updated {meta.fetched_at}</span>
          <BusyButton label="Refresh" busyLabel="Refreshing..." onClick={refresh} />
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/weekly-report" element={<WeeklyDigest />} />
          <Route path="/planning" element={<Planning />} />
          <Route path="/closure" element={<Closure />} />
          <Route path="*" element={<div className="card"><h2>Page not found</h2></div>} />
        </Routes>
      </main>
      <ChatWidget />
      <div id="toast" className={toastState ? 'show' + (toastState.isError ? ' err' : '') : ''}>{toastState?.msg}</div>
    </AppCtx.Provider>
  );
}
