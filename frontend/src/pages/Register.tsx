import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuth } from '@/auth/AuthContext'
import type { UserRole } from '@/types'

const ROLES: { value: UserRole; label: string; desc: string }[] = [
  { value: 'NGO', label: 'NGO / Organization', desc: 'Submit projects and evidence' },
  { value: 'DONOR', label: 'Donor', desc: 'Browse verified projects' },
  { value: 'AUDITOR', label: 'Independent Auditor', desc: 'Review assigned projects' },
]

export default function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState<1 | 2>(1)
  const [role, setRole] = useState<UserRole>('NGO')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgName, setOrgName] = useState('')
  const [regNumber, setRegNumber] = useState('')
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [website, setWebsite] = useState('')
  const [authorizedRepresentative, setAuthorizedRepresentative] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    // Pre-flight validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (!/[a-zA-Z]/.test(password)) {
      setError('Password must contain at least one letter.')
      return
    }
    if (!/\d/.test(password)) {
      setError('Password must contain at least one number.')
      return
    }

    setLoading(true)
    try {
      const res = await authApi.register({
        email: email.trim().toLowerCase(),
        password,
        full_name: fullName.trim(),
        role,
        organization_name: role === 'NGO' ? orgName.trim() : undefined,
        registration_number: role === 'NGO' ? regNumber.trim() : undefined,
        description: role === 'NGO' ? description.trim() : undefined,
        address: role === 'NGO' ? address.trim() : undefined,
        contact_phone: role === 'NGO' ? contactPhone.trim() : undefined,
        website: role === 'NGO' ? website.trim() : undefined,
        authorized_representative: role === 'NGO' ? (authorizedRepresentative.trim() || fullName.trim()) : undefined,
      })
      if (res.data.success) {
        // Auto-login after registration
        try {
          const loginRes = await authApi.login({ email: email.trim().toLowerCase(), password })
          if (loginRes.data.success && loginRes.data.data) {
            const { access_token, refresh_token } = loginRes.data.data
            await login(access_token, refresh_token)
            navigate('/dashboard', { replace: true })
            return
          }
        } catch {
          // If auto-login fails, redirect to login page with prefilled hint
          navigate('/login', { replace: true })
          return
        }
      }
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: {
          data?: {
            error?: string
            message?: string
            detail?: string | Array<{ msg?: string; loc?: string[] }>
            details?: Array<{ message?: string }>
          }
        }
      }
      const data = axiosErr.response?.data
      let message = 'Registration failed. Please check your details and try again.'
      if (data?.error) message = data.error
      else if (data?.message) message = data.message
      else if (typeof data?.detail === 'string') message = data.detail
      else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
        message = data.detail.map((d) => d.msg).join('; ')
      } else if (Array.isArray(data?.details) && data.details[0]?.message) {
        message = data.details.map((d) => d.message).join('; ')
      }
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-brand-600/20 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-brand mb-4 shadow-lg shadow-brand-500/30">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">Create your account</h1>
          <p className="text-slate-400 mt-1 text-sm">Join the transparency platform</p>
        </div>

        <div className="glass-card p-8">
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-900/40 border border-red-700/50 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {step === 1 && (
              <>
                <div>
                  <p className="form-label">I am a…</p>
                  <div className="grid gap-3">
                    {ROLES.map((r) => (
                      <button
                        key={r.value}
                        type="button"
                        onClick={() => setRole(r.value)}
                        className={`w-full text-left p-4 rounded-xl border transition-all duration-150 ${
                          role === r.value
                            ? 'border-brand-500 bg-brand-900/30 text-white'
                            : 'border-surface-border bg-surface-card text-slate-300 hover:border-brand-600'
                        }`}
                      >
                        <div className="font-medium">{r.label}</div>
                        <div className="text-xs text-slate-400 mt-0.5">{r.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="btn-primary w-full"
                >
                  Continue
                </button>
              </>
            )}

            {step === 2 && (
              <>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1 mb-2"
                >
                  ← Back
                </button>

                <div>
                  <label htmlFor="fullName" className="form-label">Full name</label>
                  <input
                    id="fullName"
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="input-field"
                    placeholder="Your name"
                  />
                </div>

                <div>
                  <label htmlFor="reg-email" className="form-label">Email address</label>
                  <input
                    id="reg-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label htmlFor="reg-password" className="form-label">Password *</label>
                    <span className="text-[11px] text-slate-400">Min 8 chars, 1 letter & 1 digit</span>
                  </div>
                  <input
                    id="reg-password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field"
                    placeholder="e.g. SecurePass123!"
                  />
                  {password && (
                    <div className="flex items-center gap-3 mt-1.5 text-[11px]">
                      <span className={password.length >= 8 ? 'text-emerald-400' : 'text-slate-500'}>
                        {password.length >= 8 ? '✓' : '○'} 8+ chars
                      </span>
                      <span className={/[a-zA-Z]/.test(password) ? 'text-emerald-400' : 'text-slate-500'}>
                        {/[a-zA-Z]/.test(password) ? '✓' : '○'} Letter
                      </span>
                      <span className={/\d/.test(password) ? 'text-emerald-400' : 'text-slate-500'}>
                        {/\d/.test(password) ? '✓' : '○'} Number
                      </span>
                    </div>
                  )}
                </div>

                {role === 'NGO' && (
                  <div className="space-y-4 pt-2 border-t border-surface-border/60">
                    <div className="p-3 rounded-xl bg-brand-950/40 border border-brand-800/40 text-xs text-brand-300">
                      <span className="font-semibold block mb-0.5">Prototype Admin Verification Notice</span>
                      NGO verification is reviewed by platform administrators for evaluation. Status begins as <strong>PENDING</strong>. No external government integration is claimed.
                    </div>

                    <div>
                      <label htmlFor="orgName" className="form-label">Organization name *</label>
                      <input
                        id="orgName"
                        type="text"
                        required={role === 'NGO'}
                        value={orgName}
                        onChange={(e) => setOrgName(e.target.value)}
                        className="input-field"
                        placeholder="e.g. Clean Water Initiative"
                      />
                    </div>

                    <div>
                      <label htmlFor="regNumber" className="form-label">Registration / Legal number *</label>
                      <input
                        id="regNumber"
                        type="text"
                        required={role === 'NGO'}
                        value={regNumber}
                        onChange={(e) => setRegNumber(e.target.value)}
                        className="input-field"
                        placeholder="e.g. NGO-IND-2024-8891"
                      />
                    </div>

                    <div>
                      <label htmlFor="description" className="form-label">Organization description</label>
                      <textarea
                        id="description"
                        rows={2}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        className="input-field resize-none"
                        placeholder="Brief summary of your mission and activities"
                      />
                    </div>

                    <div>
                      <label htmlFor="address" className="form-label">Registered address</label>
                      <input
                        id="address"
                        type="text"
                        value={address}
                        onChange={(e) => setAddress(e.target.value)}
                        className="input-field"
                        placeholder="Official physical address"
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label htmlFor="contactPhone" className="form-label">Contact phone</label>
                        <input
                          id="contactPhone"
                          type="tel"
                          value={contactPhone}
                          onChange={(e) => setContactPhone(e.target.value)}
                          className="input-field"
                          placeholder="+91-9876543210"
                        />
                      </div>
                      <div>
                        <label htmlFor="website" className="form-label">Website (optional)</label>
                        <input
                          id="website"
                          type="url"
                          value={website}
                          onChange={(e) => setWebsite(e.target.value)}
                          className="input-field"
                          placeholder="https://example.org"
                        />
                      </div>
                    </div>

                    <div>
                      <label htmlFor="authRep" className="form-label">Authorized representative</label>
                      <input
                        id="authRep"
                        type="text"
                        value={authorizedRepresentative}
                        onChange={(e) => setAuthorizedRepresentative(e.target.value)}
                        className="input-field"
                        placeholder="Name of authorized officer (defaults to full name)"
                      />
                    </div>
                  </div>
                )}

                <button
                  id="register-submit"
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full mt-2"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      Creating account…
                    </span>
                  ) : 'Create account'}
                </button>
              </>
            )}
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
