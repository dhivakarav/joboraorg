import { useState } from 'react';
import Spinner from './Spinner';

interface LoginPromptProps {
  onLogin: (email: string, password: string) => Promise<void>;
  error: string;
}

export default function LoginPrompt({ onLogin, error }: LoginPromptProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    try {
      await onLogin(email, password);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-5">
      {/* Brand header */}
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-btn bg-brand flex items-center justify-center">
          <span className="text-white text-xs font-bold">J</span>
        </div>
        <span className="font-semibold text-ink text-sm">Sign in to Jobora</span>
      </div>

      <p className="text-xs text-ink-soft leading-relaxed">
        Connect your Jobora account to score this job against your resume and save it with one click.
      </p>

      {error && (
        <div className="rounded-btn bg-err/10 border border-err/20 px-3 py-2 text-xs text-err">
          {error}
        </div>
      )}

      <form onSubmit={submit} className="flex flex-col gap-3">
        <div>
          <label className="jbr-label">Email</label>
          <input
            type="email"
            className="jbr-input"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="jbr-label">Password</label>
          <input
            type="password"
            className="jbr-input"
            placeholder="••••••••"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        <button type="submit" className="jbr-btn-primary w-full" disabled={loading}>
          {loading ? <Spinner size="sm" /> : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
