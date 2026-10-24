import { useSearchParams } from 'react-router-dom';
import { ItemLink, Kpi, Loading, ProjectSelect, useFetch } from '../lib.jsx';

const STAGES = ['Backlog', 'Development', 'Testing', 'Done'];

export default function Dashboard() {
  const [params, setParams] = useSearchParams();
  const project = params.get('project') || '';
  const state = useFetch('/api/dashboard?project=' + encodeURIComponent(project));
  const v = state.data;
  if (!v) return <Loading state={state} />;
  const t = v.totals;

  return (
    <>
      <h1>Project Dashboard</h1>
      <p className="lead">How much of the project is complete and where the work sits in the pipeline.</p>

      <div className="filters">
        <ProjectSelect value={project} onChange={p => setParams(p ? { project: p } : {})} />
      </div>

      <section className="cards">
        <Kpi label="Project completion" value={`${t.completion_pct}%`} />
        <Kpi label="Tasks done" value={`${t.done}/${t.total}`} />
        <Kpi label="In progress" value={t.in_progress} />
        <Kpi label="Blocked" value={t.blocked} />
        <Kpi label="Overdue" value={t.overdue} />
        <Kpi label="On-time delivery" value={v.on_time_pct == null ? 'n/a' : `${v.on_time_pct}%`} />
      </section>

      {!project && v.projects.length > 1 && (
        <div className="card">
          <h2>Projects <span className="muted">completion of each project on the board</span></h2>
          {v.projects.map(p => (
            <div className="prog" key={p.name}>
              <div className="head"><b><a href={`?project=${encodeURIComponent(p.name)}`} onClick={e => { e.preventDefault(); setParams({ project: p.name }); }}>{p.name}</a></b>
                <span>{p.completion_pct}% &middot; {p.done}/{p.total} tasks done
                  {p.blocked > 0 && <> &middot; <span className="pill bad">{p.blocked} blocked</span></>}</span></div>
              <div className="bar"><div style={{ width: `${p.completion_pct}%` }} /></div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2>{project ? `${project} - progress` : 'Overall progress'} <span className="muted">Backlog &rarr; Development &rarr; Testing &rarr; Done</span></h2>
        {t.total === 0 ? <div className="empty">No cards on the board yet.</div> : (
          <>
            <div className="prog">
              <div className="head"><b>Completion</b><span>{t.completion_pct}% &middot; {t.done} of {t.total} tasks done</span></div>
              <div className="bar"><div style={{ width: `${t.completion_pct}%` }} /></div>
            </div>
            <div className="legend">{STAGES.map(s => <span key={s}><i className={`seg ${s}`} />{s} ({t.stages[s]})</span>)}</div>
            <div className="stack">
              {STAGES.filter(s => t.stages[s]).map(s => (
                <span key={s} className={`seg ${s}`} style={{ width: `${(t.stages[s] / t.total * 100).toFixed(1)}%` }}>{t.stages[s]}</span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>Planned vs actual dates</h2>
        {v.schedule.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>Task</th><th>Stage</th><th>Owner</th><th>Planned</th><th>Actual</th><th>Status</th></tr></thead>
            <tbody>
              {v.schedule.map((r, i) => (
                <tr key={i}>
                  <td><ItemLink item={r} /></td>
                  <td>{r.stage}</td>
                  <td>{r.assignees.join(', ') || 'Unassigned'}</td>
                  <td>{r.planned || '-'}</td><td>{r.actual || '-'}</td>
                  <td><span className={`pill ${r.tone}`}>{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ) : <div className="empty">Nothing to show.</div>}
      </div>
    </>
  );
}
