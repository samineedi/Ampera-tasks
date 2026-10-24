import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BusyButton, ItemLink, Kpi, Loading, ProjectSelect, post, useApp, useFetch } from '../lib.jsx';

const SECTIONS = [['completed', 'Completed this week'], ['in_progress', 'In progress'], ['blocked', 'Blocked'],
  ['overdue', 'Overdue'], ['upcoming', 'Due in the next 7 days']];

export default function WeeklyDigest() {
  const { toast } = useApp();
  const [params, setParams] = useSearchParams();
  const project = params.get('project') || '';
  const state = useFetch('/api/digest?project=' + encodeURIComponent(project));
  const d = state.data;
  const [draft, setDraft] = useState('');
  const [note, setNote] = useState('');
  const [dry, setDry] = useState(true);

  useEffect(() => {
    if (!d) return;
    setDraft(d.draft);
    setNote(d.draft_time ? `AI draft generated ${d.draft_time}.`
      : d.llm_available ? 'Template draft shown. Click "Regenerate with AI" for a written version.'
      : 'Template draft shown. Add a GOOGLE_API_KEY to .env to enable AI wording.');
  }, [d]);

  if (!d) return <Loading state={state} />;
  const { kpis: k, risk, sections, notifications } = d;

  const regenerate = async () => {
    const r = await post('/api/digest/draft', { project });
    setDraft(r.draft);
    setNote(r.llm_used ? 'AI draft generated just now.' : 'No LLM key set, so the template was used.');
    toast(r.llm_used ? 'AI draft ready' : 'Template draft (no LLM key)');
  };
  const send = async () => {
    if (!window.confirm('Send this report?')) return;
    toast((await post('/api/digest/send', { text: draft })).message);
  };
  const notify = async () => toast((await post('/api/notifications/send', { dry_run: dry, project })).message);

  return (
    <>
      <h1>Weekly Report <small>last {d.days} days</small></h1>
      <p className="lead">Status, risks and the report draft for stakeholders. Numbers come from rules on Trello data; the AI only writes the wording.</p>

      <div className="filters">
        <ProjectSelect value={project} onChange={p => setParams(p ? { project: p } : {})} />
      </div>

      <section className="cards">
        <Kpi label="Overall health" value={k.health} cls={`health-${String(k.health).toLowerCase()}`} />
        <Kpi label="Completed this week" value={k.completed_this_week} />
        <Kpi label="In progress" value={k.in_progress} />
        <Kpi label="Blocked" value={k.blocked} />
        <Kpi label="Overdue" value={k.overdue} />
        <Kpi label="On-time rate" value={k.on_time_rate_pct == null ? 'n/a' : `${k.on_time_rate_pct}%`} />
      </section>

      <div className="card">
        <h2>Risk radar <span className="muted">stuck, blocked, overdue and moved-back items</span></h2>
        {risk.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>Severity</th><th>Item</th><th>Owner</th><th>Stage</th><th>Why</th></tr></thead>
            <tbody>
              {risk.map((r, i) => (
                <tr key={i}>
                  <td><span className={`pill ${r.severity}`}>{r.severity}</span></td>
                  <td><ItemLink item={r} /></td>
                  <td>{r.assignees.join(', ') || 'Unassigned'}</td>
                  <td>{r.stage}</td>
                  <td>{r.reasons.map((why, j) => <div key={j}>{why}</div>)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ) : <div className="empty">No risks found. Nothing is stuck, blocked or overdue.</div>}
      </div>

      <div className="grid2">
        <div className="card">
          <h2>This week at a glance</h2>
          {SECTIONS.map(([key, label]) => {
            const items = sections[key] || [];
            return (
              <details key={key} open={items.length > 0 && ['completed', 'blocked', 'overdue'].includes(key)}>
                <summary>{label} ({items.length})</summary>
                {items.length ? (
                  <ul className="items">
                    {items.map((i, n) => (
                      <li key={n}>{i.title}
                        {i.assignees?.length > 0 && <span className="muted"> ({i.assignees.join(', ')})</span>}
                        {i.due && <span className="muted"> due {i.due.slice(0, 10)}</span>}
                      </li>
                    ))}
                  </ul>
                ) : <div className="empty">None</div>}
              </details>
            );
          })}
        </div>

        <div className="card">
          <h2>Reminders and escalations <span className="muted">{notifications.length} message(s)</span></h2>
          {notifications.length === 0 && <div className="empty">Nothing to send. All clear.</div>}
          {notifications.map((m, i) => (
            <div key={i}><b>{m.kind.charAt(0).toUpperCase() + m.kind.slice(1)}</b> to {m.to}<pre className="msg">{m.body}</pre></div>
          ))}
          {notifications.length > 0 && (
            <div className="row">
              <label><input type="checkbox" checked={dry} onChange={e => setDry(e.target.checked)} /> Dry run (save to a file instead of posting to Slack)</label>
              <BusyButton className="primary" label="Send notifications" busyLabel="Sending..." onClick={notify} />
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Report draft <span className="muted">review, edit, then send</span></h2>
        <p className="muted">{note}</p>
        <textarea rows={18} value={draft} onChange={e => setDraft(e.target.value)} />
        <div className="row">
          <BusyButton label="Regenerate with AI" busyLabel="Writing..." onClick={regenerate} />
          <BusyButton className="primary" label="Approve & send report" busyLabel="Sending..." onClick={send} />
        </div>
      </div>
    </>
  );
}
