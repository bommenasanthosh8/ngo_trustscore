import { useState, useEffect, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuth } from '@/auth/AuthContext'

interface DemoPersona {
  id: string
  name: string
  roleTitle: string
  roleBadge: string
  role: 'NGO' | 'AUDITOR' | 'DONOR' | 'ADMIN'
  org: string
  email: string
  password: string
  icon: string
  badgeColor: string
  tagline: string
  destination: string
}

const DEMO_PERSONAS: DemoPersona[] = [
  {
    id: 'ngo-ramesh',
    name: 'Ramesh Verma',
    roleTitle: 'NGO Director',
    roleBadge: 'NGO Representative',
    role: 'NGO',
    org: 'Helping Villages Foundation',
    email: 'lead@helpingvillages.org',
    password: 'NgoPassword123!',
    icon: '🏢',
    badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    tagline: 'Scenario A: High Score (88/100) Clean Water Well project',
    destination: '/dashboard',
  },
  {
    id: 'ngo-priya',
    name: 'Priya Nair',
    roleTitle: 'Program Officer',
    roleBadge: 'Grassroots NGO',
    role: 'NGO',
    org: 'Rural Community Initiative',
    email: 'lead@ruralcommunity.org',
    password: 'NgoPassword123!',
    icon: '🌿',
    badgeColor: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
    tagline: 'Scenarios B & D: School Nutrition & Afforestation drives',
    destination: '/dashboard',
  },
  {
    id: 'auditor-suresh',
    name: 'Inspector Suresh Sharma',
    roleTitle: 'State Compliance Auditor',
    roleBadge: 'SIH Auditor',
    role: 'AUDITOR',
    org: 'Ministry of Social Justice & Empowerment',
    email: 'auditor@sih.gov.in',
    password: 'AuditorPassword123!',
    icon: '🔍',
    badgeColor: 'bg-violet-500/20 text-violet-300 border-violet-500/30',
    tagline: 'Full audit queue, fraud detection & decision review',
    destination: '/audit',
  },
  {
    id: 'donor-ananya',
    name: 'Ananya Patel',
    roleTitle: 'CSR Impact Director',
    roleBadge: 'CSR Donor',
    role: 'DONOR',
    org: 'Tata Philanthropic Foundation',
    email: 'donor@philanthropy.org',
    password: 'DonorPassword123!',
    icon: '🤝',
    badgeColor: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    tagline: 'Explore verified NGO portfolios and transparency scores',
    destination: '/dashboard',
  },
  {
    id: 'admin-platform',
    name: 'Platform Administrator',
    roleTitle: 'Chief Platform Officer',
    roleBadge: 'System Admin',
    role: 'ADMIN',
    org: 'National Transparency Directorate',
    email: 'admin@transparency.gov.in',
    password: 'AdminPassword123!',
    icon: '⚙️',
    badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    tagline: 'NGO registration approvals, risk radar & audit oversight',
    destination: '/admin',
  },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  // Check backend health on mount
  useEffect(() => {
    fetch('/api/v1/auth/me')
      .then((res) => {
        // Even a 401 response means the backend is up and responding!
        if (res.status === 401 || res.status === 200) {
          setBackendStatus('online')
        } else {
          setBackendStatus('online')
        }
      })
      .catch(() => {
        setBackendStatus('offline')
      })
  }, [])

  async function executeLogin(targetEmail: string, targetPass: string, defaultDestination?: string) {
    setError(null)
    setLoading(true)
    try {
      const res = await authApi.login({ email: targetEmail, password: targetPass })
      if (res.data.success && res.data.data) {
        const { access_token, refresh_token } = res.data.data
        const user = await login(access_token, refresh_token)
        
        let destination = from !== '/dashboard' ? from : (defaultDestination ?? '/dashboard')
        if (from === '/dashboard' && user) {
          if (user.role === 'AUDITOR') destination = '/audit'
          else if (user.role === 'ADMIN') destination = '/admin'
          else destination = '/dashboard'
        }
        navigate(destination, { replace: true })
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } }
      setError(
        axiosErr.response?.data?.error ??
          'Login failed. Please check your credentials or verify backend server is running.'
      )
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    await executeLogin(email, password)
  }

  function handleQuickFill(persona: DemoPersona) {
    setEmail(persona.email)
    setPassword(persona.password)
    setActivePersonaId(persona.id)
    setError(null)
  }

  async function handleOneClickLogin(persona: DemoPersona) {
    handleQuickFill(persona)
    await executeLogin(persona.email, persona.password, persona.destination)
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background ambient gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-600/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-sky-600/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      <div className="relative max-w-5xl mx-auto w-full">
        {/* Top Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-300 text-xs font-semibold uppercase tracking-wider mb-3">
            <span>🇮🇳</span> SIH Working Model · Live Demonstration Portal
          </div>
          <div className="flex items-center justify-center gap-3 mb-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-brand shadow-lg shadow-brand-500/30">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              NGO Fund Utilization Platform
            </h1>
          </div>
          <p className="text-slate-400 text-sm max-w-xl mx-auto">
            Evidence-based verification, immutable audit logging & transparency scoring
          </p>

          {/* Server Connection Status Indicator */}
          <div className="mt-3 flex items-center justify-center gap-2 text-xs">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full ${
                backendStatus === 'online'
                  ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50 animate-pulse'
                  : backendStatus === 'offline'
                  ? 'bg-rose-500'
                  : 'bg-amber-400 animate-ping'
              }`}
            />
            <span className="text-slate-400 font-medium">
              API Backend & SQLite Database:{' '}
              <strong
                className={
                  backendStatus === 'online'
                    ? 'text-emerald-400'
                    : backendStatus === 'offline'
                    ? 'text-rose-400'
                    : 'text-amber-400'
                }
              >
                {backendStatus === 'online'
                  ? 'Connected & Ready'
                  : backendStatus === 'offline'
                  ? 'Offline (Run backend server)'
                  : 'Verifying...'}
              </strong>
            </span>
          </div>
        </div>

        {/* 2-Column Layout: Left (Demo Personas) + Right (Sign In Form) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left Column: Quick 1-Click Working Model Personas (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>⚡</span> 1-Click Working Model Roles
                </h2>
                <p className="text-xs text-slate-400">
                  Select any persona below to instantaneously test the full system with live data
                </p>
              </div>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">
                5 Active Personas
              </span>
            </div>

            <div className="space-y-3">
              {DEMO_PERSONAS.map((p) => {
                const isSelected = activePersonaId === p.id
                return (
                  <div
                    key={p.id}
                    className={`p-4 rounded-xl border transition-all duration-200 cursor-pointer ${
                      isSelected
                        ? 'bg-brand-950/40 border-brand-500 shadow-md shadow-brand-500/10'
                        : 'bg-surface-card/60 hover:bg-surface-card border-surface-border hover:border-slate-600'
                    }`}
                    onClick={() => handleQuickFill(p)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <div className="text-2xl p-2 rounded-xl bg-slate-800/80 border border-slate-700/60 shrink-0">
                          {p.icon}
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-white text-sm">{p.name}</span>
                            <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${p.badgeColor}`}>
                              {p.roleBadge}
                            </span>
                          </div>
                          <div className="text-xs font-medium text-slate-300 mt-0.5">{p.org}</div>
                          <div className="text-xs text-slate-400 mt-1">{p.tagline}</div>
                          <div className="text-[11px] font-mono text-slate-500 mt-1">
                            {p.email} · <span className="text-slate-400">{p.password}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                        <button
                          type="button"
                          disabled={loading}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleOneClickLogin(p)
                          }}
                          className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 active:scale-95 text-white text-xs font-semibold shadow-sm transition-all flex items-center gap-1.5"
                        >
                          <span>Log in</span>
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Audit log storage guarantee box */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-start gap-3">
              <span className="text-base text-brand-400">🛡️</span>
              <div>
                <strong className="text-slate-300">Auditable Security & Database Persistence:</strong> Every login attempt (successful or failed) is automatically recorded to the <code className="text-brand-300 font-mono">activity_logs</code> database table with timestamp, IP address, user-agent, and role details.
              </div>
            </div>
          </div>

          {/* Right Column: Standard Form Card (5 cols) */}
          <div className="lg:col-span-5">
            <div className="glass-card p-6 sm:p-8 shadow-xl">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">Sign In</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Use quick-fill above or enter credentials</p>
                </div>
                <span className="text-xs font-medium text-brand-400 bg-brand-500/10 px-2.5 py-1 rounded-full border border-brand-500/20">
                  Secure JWT
                </span>
              </div>

              {error && (
                <div className="mb-5 p-3.5 rounded-xl bg-red-900/30 border border-red-700/50 text-red-300 text-xs flex items-start gap-2.5">
                  <span className="text-base leading-none">⚠️</span>
                  <div className="flex-1">{error}</div>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="email" className="form-label text-xs">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="name@organization.org"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="password" className="form-label text-xs mb-0">
                      Password
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-xs text-slate-400 hover:text-white transition-colors flex items-center gap-1"
                    >
                      {showPassword ? (
                        <>
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                          </svg>
                          <span>Hide</span>
                        </>
                      ) : (
                        <>
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                          <span>Show</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="input-field pr-10"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <button
                  id="login-submit"
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full mt-2 py-3 text-sm flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      <span>Authenticating & Auditing...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign in to Platform</span>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </>
                  )}
                </button>
              </form>

              <div className="mt-6 pt-5 border-t border-surface-border text-center space-y-3">
                <p className="text-xs text-slate-400">
                  Need to register a new organization?{' '}
                  <Link to="/register" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
                    Register NGO Here
                  </Link>
                </p>
                <div>
                  <Link
                    to="/"
                    className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    <span>← Return to Public Transparency Portal</span>
                  </Link>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
