import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Signup() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user && !busy) return <Navigate to="/" replace />

  const update = (field: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) {
      setError('Password must include at least one letter and one number.')
      return
    }
    setBusy(true)
    try {
      const { confirm: _confirm, ...input } = form
      await signup(input)
      navigate('/', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container section auth">
      <form className="auth-card" onSubmit={submit}>
        <h1>Create account</h1>
        <p className="muted">Save your chats and get help finding the right Yale gear.</p>
        <div className="form-row">
          <label>
            First name
            <input required maxLength={50} value={form.first_name} onChange={update('first_name')} autoComplete="given-name" />
          </label>
          <label>
            Last name
            <input required maxLength={50} value={form.last_name} onChange={update('last_name')} autoComplete="family-name" />
          </label>
        </div>
        <label>
          Email
          <input type="email" required value={form.email} onChange={update('email')} autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            maxLength={128}
            value={form.password}
            onChange={update('password')}
            autoComplete="new-password"
          />
          <small className="hint">At least 8 characters, with a letter and a number.</small>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            required
            value={form.confirm}
            onChange={update('confirm')}
            autoComplete="new-password"
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
        <p className="muted small">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
