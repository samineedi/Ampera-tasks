import { useState } from 'react';
import { BusyButton, post, useApp } from '../lib.jsx';

const COLS = [['title', 'text'], ['assignee', 'text'], ['skills', 'text'], ['estimate_days', 'number'], ['priority', 'text'], ['due', 'date']];
const HEADS = ['Task', 'Assignee', 'Skills', 'Est (days)', 'Priority', 'Due'];
const DEFAULT_TEAM = `Asha Rao: design, frontend, development
Ravi Kumar: backend, development, devops
Meena Iyer: testing, analysis`;

let nextId = 1;
const toRow = (t = {}) => ({
  _id: nextId++, description: t.description || '', title: t.title || '', assignee: t.assignee || '',
  skills: (t.skills || []).join(', '), estimate_days: t.estimate_days ?? '', priority: t.priority || '', due: t.due || '',
});

export default function Planning() {
  const { toast } = useApp();
  const [project, setProject] = useState('');
  const [brief, setBrief] = useState('');
  const [team, setTeam] = useState(DEFAULT_TEAM);
  const [rows, setRows] = useState(null);
  const [note, setNote] = useState('');
  const [dry, setDry] = useState(true);

  const generate = async () => {
    const r = await post('/api/plan', { brief, team_text: team });
    setRows(r.plan.map(toRow));
    setNote(r.llm_used ? 'Tasks proposed by the AI.' : 'No LLM key set: standard phases plus one task per sentence of the brief.');
  };
  const edit = (id, k, val) => setRows(rs => rs.map(r => (r._id === id ? { ...r, [k]: val } : r)));
  const readPlan = () => rows.filter(r => r.title.trim()).map(r => ({
    description: r.description, title: r.title, priority: r.priority,
    estimate_days: Number(r.estimate_days || 0),
    skills: r.skills.split(',').map(s => s.trim()).filter(Boolean),
    due: r.due || null, assignee: r.assignee || 'Unassigned',
  }));
  const create = async () => {
    if (!dry && !window.confirm('Create these cards in Trello now?')) return;
    toast((await post('/api/plan/create', { plan: readPlan(), dry_run: dry, project })).message);
  };

  return (
    <>
      <h1>Planning</h1>
      <p className="lead">Paste a project brief and your team. The agent proposes tasks; code assigns them by skill and workload and sets due dates. You review before anything reaches Trello.</p>

      <div className="card">
        <label className="f" style={{ marginBottom: 12 }}>Project name (cards get the label "Project: ...")
          <input type="text" value={project} onChange={e => setProject(e.target.value)} placeholder="e.g. Project 3" /></label>
        <label className="f">Project brief
          <textarea rows={6} value={brief} onChange={e => setBrief(e.target.value)} placeholder="Describe the goal, main features and deadline..." /></label>
        <label className="f" style={{ marginTop: 12 }}>Team (one per line: Name: skill, skill)
          <textarea rows={4} value={team} onChange={e => setTeam(e.target.value)} /></label>
        <div className="row">
          <BusyButton className="primary" label="Generate plan" busyLabel="Planning..." onClick={generate} />
          <span className="muted">{note}</span>
        </div>
      </div>

      {rows && (
        <div className="card">
          <h2>Plan <span className="muted">edit anything, add or remove rows</span></h2>
          <div className="table-wrap"><table>
            <thead><tr>{HEADS.map(h => <th key={h}>{h}</th>)}<th /></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r._id}>
                  {COLS.map(([k, type]) => (
                    <td key={k}><input type={type} value={r[k]} onChange={e => edit(r._id, k, e.target.value)} /></td>
                  ))}
                  <td><button className="ghost" title="Remove row" onClick={() => setRows(rs => rs.filter(x => x._id !== r._id))}>{'✕'}</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <div className="row">
            <button className="ghost" onClick={() => setRows(rs => [...rs, toRow()])}>+ Add row</button>
            <label><input type="checkbox" checked={dry} onChange={e => setDry(e.target.checked)} /> Dry run (don't write to Trello)</label>
            <BusyButton className="primary" label="Create cards in Trello" busyLabel="Creating..." onClick={create} />
          </div>
          <p className="muted">Cards are created in your To Do list. A card is assigned only if the name matches a board member's full name.</p>
        </div>
      )}
    </>
  );
}
