import { useState } from 'react';
import { BusyButton, Kpi, ProjectSelect, post, useApp } from '../lib.jsx';

export default function Closure() {
  const { toast } = useApp();
  const [proj, setProj] = useState('');
  const [res, setRes] = useState(null);
  const [report, setReport] = useState('');
  const [dry, setDry] = useState(true);
  const [confirmed, setConfirmed] = useState(false);

  const run = async () => {
    const r = await post('/api/closure/run', { project: proj, project_name: proj || 'All projects' });
    setRes(r); setReport(r.draft);
  };
  const send = async () => {
    if (!window.confirm('Send the closure report?')) return;
    toast((await post('/api/closure/send', { text: report, project_name: proj || 'All projects' })).message);
  };
  const archive = async () => {
    if (!dry && !window.confirm('Archive the Trello board?')) return;
    toast((await post('/api/closure/archive', { confirm: confirmed, dry_run: dry })).message);
  };

  const k = res?.kpis;
  return (
    <>
      <h1>Closure</h1>
      <p className="lead">Checks whether all work is finished, drafts the closure report with lessons learned, and (only when everything is done) lets you archive the board.</p>

      <div className="card">
        <div className="row" style={{ marginTop: 0 }}>
          <ProjectSelect value={proj} onChange={setProj} />
          <BusyButton className="primary" label="Run closure check" busyLabel="Checking..." onClick={run} />
        </div>
      </div>

      {res && (
        <>
          <section className="cards">
            <Kpi label="Completion" value={`${k.completion_pct}%`} />
            <Kpi label="Done / total" value={`${k.done}/${k.total}`} />
            <Kpi label="Open items" value={k.open} />
            <Kpi label="Late deliveries" value={k.late_deliveries} />
            <Kpi label="Ready to close" value={res.ready ? 'Yes' : 'No'} />
          </section>
          {res.outstanding.length > 0 && (
            <div className="card"><h2>Still open</h2>
              <ul className="items">{res.outstanding.map((t, i) => <li key={i}>{t}</li>)}</ul></div>
          )}
          <div className="card">
            <h2>Closure report <span className="muted">review, edit, then send</span></h2>
            <textarea rows={18} value={report} onChange={e => setReport(e.target.value)} />
            <div className="row"><BusyButton className="primary" label="Approve & send closure report" busyLabel="Sending..." onClick={send} /></div>
          </div>
          <div className="card">
            <h2>Archive the Trello board</h2>
            <p className="muted">Archiving closes the whole board, so it needs every project on it to be finished. {res.ready ? "This selection is complete. Archiving can be undone from Trello's closed boards." : 'Disabled: open items remain.'}</p>
            <div className="row">
              <label><input type="checkbox" checked={dry} onChange={e => setDry(e.target.checked)} /> Dry run</label>
              <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> I confirm the project is finished</label>
              <BusyButton label="Archive board" busyLabel="Archiving..." onClick={archive} disabled={!(res.ready && confirmed)} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
