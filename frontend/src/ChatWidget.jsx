import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { post } from './lib.jsx';

const STARTERS = ["What's overdue?", 'Which cards are blocked?', 'Summarize project health'];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [params] = useSearchParams();
  const project = params.get('project') || '';
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [msgs, busy, open]);

  const send = async (raw) => {
    const message = raw.trim();
    if (!message || busy) return;
    const history = msgs.filter(m => !m.error).slice(-10).map(({ role, content }) => ({ role, content }));
    setMsgs(m => [...m, { role: 'user', content: message }]);
    setText('');
    setBusy(true);
    try {
      const r = await post('/api/chat', { message, history, project });
      setMsgs(m => [...m, { role: 'assistant', content: r.answer, tools: r.tools_used }]);
    } catch (e) {
      setMsgs(m => [...m, { role: 'assistant', content: e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {open && (
        <div className="chat-panel" role="dialog" aria-label="PMO assistant">
          <div className="chat-head"><b>PMO assistant</b>
            <button onClick={() => setOpen(false)} aria-label="Close chat">&times;</button></div>
          <div className="chat-msgs">
            {!msgs.length && (
              <div className="chat-starters">
                <p className="muted">Ask about the board{project ? ` (${project})` : ''}:</p>
                {STARTERS.map(s => <button key={s} onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}${m.error ? ' err' : ''}`}>
                {m.content}
                {m.tools?.length > 0 && <div className="chat-tools muted">Looked at: {m.tools.join(', ')}</div>}
              </div>
            ))}
            {busy && <div className="chat-msg assistant muted">Thinking&hellip;</div>}
            <div ref={endRef} />
          </div>
          <form className="chat-input" onSubmit={e => { e.preventDefault(); send(text); }}>
            <textarea rows={1} value={text} placeholder="Ask a question…" onChange={e => setText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text); } }} />
            <button className="primary" disabled={busy || !text.trim()}>Send</button>
          </form>
        </div>
      )}
      <button className="chat-bubble primary" onClick={() => setOpen(o => !o)} aria-label="Open chat">
        {open ? '×' : '💬'}
      </button>
    </>
  );
}
