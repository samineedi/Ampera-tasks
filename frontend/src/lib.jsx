import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

export async function request(url, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const r = await fetch(url, opts);
  let j = {};
  try { j = await r.json(); } catch (e) { /* non-JSON error body */ }
  if (r.status === 401 && !url.startsWith('/api/login') && !url.startsWith('/api/session')) {
    window.dispatchEvent(new Event('auth-required'));      // session expired: App shows the login page
  }
  if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
  return j;
}
export const post = (url, body) => request(url, body || {});

// App-wide state: toast and refresh counter (bumped after Refresh so pages reload).
export const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef();
  const show = useCallback((msg, isError) => {
    setToast({ msg, isError });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 5000);
  }, []);
  return [toast, show];
}

// GET a JSON endpoint; reloads when `url` or the refresh counter changes.
export function useFetch(url) {
  const { version } = useApp();
  const [state, setState] = useState({ data: null, error: null });
  useEffect(() => {
    let live = true;
    request(url)
      .then(data => live && setState({ data, error: null }))
      .catch(e => live && setState({ data: null, error: e.message }));
    return () => { live = false; };
  }, [url, version]);
  return state;
}

// Button that disables itself and shows a label while an async action runs; errors become toasts.
export function BusyButton({ label, busyLabel, onClick, className, disabled }) {
  const { toast } = useApp();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { await onClick(); } catch (e) { toast(e.message, true); } finally { setBusy(false); }
  };
  return <button className={className} disabled={busy || disabled} onClick={run}>{busy ? busyLabel : label}</button>;
}

export function Kpi({ label, value, cls = '' }) {
  return <div className={`kpi ${cls}`}><span>{label}</span><b>{value}</b></div>;
}

export function ItemLink({ item }) {
  return item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a> : item.title;
}

export function Loading({ state }) {
  if (state.error) return (
    <div className="card"><h2>Something went wrong</h2><p>{state.error}</p>
      <p className="muted">If this is the first load, check your Trello settings in <code>.env</code>.</p></div>
  );
  return <div className="empty">Loading...</div>;
}

// Dropdown of the board's projects (from "Project: ..." labels). Empty value = all projects.
export function ProjectSelect({ value, onChange }) {
  const { data } = useFetch('/api/projects');
  return (
    <label className="f">Project
      <select value={value} onChange={e => onChange(e.target.value)}>
        <option value="">All projects</option>
        {(data?.projects || []).map(p => <option key={p} value={p}>{p}</option>)}
      </select>
    </label>
  );
}
