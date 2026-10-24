import { useState } from 'react';
import { post } from '../lib.jsx';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onLogin(await post('/api/login', { username, password }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <main className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <div className="brand">PMO Automation<span>Trello</span></div>
        <h2>Sign in</h2>
        <label className="f">Username
          <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" autoFocus required />
        </label>
        <label className="f">Password
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Signing in...' : 'Sign in'}</button>
      </form>
    </main>
  );
}
