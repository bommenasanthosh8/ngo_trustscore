import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import { ngoApi } from '@/api/ngo'
import { projectsApi } from '@/api/projects'
import { getNGOScore } from '@/api/scores'
import { searchPublicNGOs } from '@/api/public'
import { donationsApi, type MyDonationsResponse } from '@/api/donations'
import DirectDonationModal from '@/components/donations/DirectDonationModal'
import type {
  NGOPublicSummary,
  NGOResponse,
  NGOTransparencyScoreResponse,
  ProjectDetail,
} from '@/types'

const ROLE_WELCOME: Record<string, string> = {
  NGO: 'Manage your organization profile, track evidence milestones, and monitor your Transparency Score.',
  DONOR: 'Explore verified NGO projects and transparency scores.',
  AUDITOR: 'Review assigned projects and submit audit decisions.',
  ADMIN: 'Platform administration, verification queue, and oversight.',
}

export default function Dashboard() {
  const { user } = useAuth()
  const [ngoProfile, setNgoProfile] = useState<NGOResponse | null>(null)
  const [ngoScore, setNgoScore] = useState<NGOTransparencyScoreResponse | null>(null)
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [pendingNgos, setPendingNgos] = useState<NGOResponse[]>([])
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  // Filter tab for NGO project table
  const [activeTab, setActiveTab] = useState<'ALL' | 'ACTIVE' | 'VERIFIED' | 'PENDING' | 'DISPUTED' | 'HIGH_RISK'>('ALL')
  const [searchTerm, setSearchTerm] = useState('')

  // Donor Experience Hub State
  const [donorNgos, setDonorNgos] = useState<NGOPublicSummary[]>([])
  const [loadingDonorNgos, setLoadingDonorNgos] = useState(false)
  const [donorSearch, setDonorSearch] = useState('')
  const [donorCategory, setDonorCategory] = useState('ALL')
  const [myDonations, setMyDonations] = useState<MyDonationsResponse>({
    items: [],
    total_donated: 0,
    total_donations_count: 0,
    supported_ngos_count: 0,
  })
  const [donationModalNgo, setDonationModalNgo] = useState<NGOPublicSummary | null>(null)
  const [donationModalProject, setDonationModalProject] = useState<ProjectDetail | null>(null)

  useEffect(() => {
    if (!user) return

    // If NGO user, fetch profile, transparency score, and projects
    if (user.role === 'NGO' && user.ngo_id) {
      ngoApi
        .getById(user.ngo_id)
        .then((res) => {
          if (res.data.success && res.data.data) {
            setNgoProfile(res.data.data)
          }
        })
        .catch(console.error)

      getNGOScore(user.ngo_id)
        .then((res) => {
          if (res.data) setNgoScore(res.data)
        })
        .catch(console.error)

      loadNGOProjects(user.ngo_id)
    }

    // If DONOR user, load registered NGOs, projects, and personal donation history
    if (user.role === 'DONOR') {
      loadDonorHubData()
    }

    // If ADMIN user, fetch pending NGO onboarding applications
    if (user.role === 'ADMIN') {
      loadPendingNgos()
    }
  }, [user])

  function loadDonorHubData() {
    setLoadingDonorNgos(true)
    searchPublicNGOs()
      .then((res) => {
        if (res.data) setDonorNgos(res.data)
      })
      .catch(console.error)

    projectsApi
      .list()
      .then((res) => {
        if (res.data.success && res.data.data) setProjects(res.data.data)
      })
      .catch(console.error)

    donationsApi
      .getMyDonations()
      .then((res) => {
        if (res.data.success && res.data.data) setMyDonations(res.data.data)
      })
      .catch(console.error)
      .finally(() => setLoadingDonorNgos(false))
  }

  function loadNGOProjects(ngoId: string) {
    setLoadingProjects(true)
    projectsApi
      .list({ ngo_id: ngoId })
      .then((res) => {
        if (res.data.success && res.data.data) {
          setProjects(res.data.data)
        }
      })
      .catch(console.error)
      .finally(() => setLoadingProjects(false))
  }

  function loadPendingNgos() {
    ngoApi
      .getPending()
      .then((res) => {
        if (res.data.success && res.data.data) {
          setPendingNgos(res.data.data)
        }
      })
      .catch(console.error)
  }

  async function handleVerify(id: string) {
    try {
      const res = await ngoApi.verify(id)
      if (res.data.success) {
        setActionMessage(`NGO "${res.data.data?.name}" verified successfully.`)
        loadPendingNgos()
      }
    } catch {
      setActionMessage('Failed to verify NGO.')
    }
  }

  async function handleReject(id: string) {
    try {
      const res = await ngoApi.reject(id, rejectReason || undefined)
      if (res.data.success) {
        setActionMessage(`NGO "${res.data.data?.name}" has been rejected.`)
        setRejectingId(null)
        setRejectReason('')
        loadPendingNgos()
      }
    } catch {
      setActionMessage('Failed to reject NGO.')
    }
  }

  if (!user) return null

  // ── Metric Calculations ──────────────────────────────────────────────
  const totalProjects = projects.length
  const activeProjects = projects.filter((p) =>
    ['FUNDING', 'EVIDENCE_COLLECTION', 'UNDER_VERIFICATION'].includes(p.status)
  ).length
  const verifiedProjects = projects.filter((p) => p.status === 'VERIFIED').length
  const pendingProjects = projects.filter((p) =>
    ['CREATED', 'PENDING', 'UNDER_VERIFICATION'].includes(p.status)
  ).length
  const disputedProjects = projects.filter((p) => p.status === 'DISPUTED').length
  const highRiskProjects = projects.filter((p) => {
    const r = (p.risk_level || '').toUpperCase()
    return r === 'HIGH' || r === 'CRITICAL'
  }).length

  const transparencyScoreVal = ngoScore?.final_score ?? 80

  // Filtered Projects for Table
  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      !searchTerm ||
      p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.project_code.toLowerCase().includes(searchTerm.toLowerCase())

    if (!matchesSearch) return false

    if (activeTab === 'ACTIVE') {
      return ['FUNDING', 'EVIDENCE_COLLECTION', 'UNDER_VERIFICATION'].includes(p.status)
    }
    if (activeTab === 'VERIFIED') return p.status === 'VERIFIED'
    if (activeTab === 'PENDING') {
      return ['CREATED', 'PENDING', 'UNDER_VERIFICATION'].includes(p.status)
    }
    if (activeTab === 'DISPUTED') return p.status === 'DISPUTED'
    if (activeTab === 'HIGH_RISK') {
      const r = (p.risk_level || '').toUpperCase()
      return r === 'HIGH' || r === 'CRITICAL'
    }
    return true
  })

  // Alerts
  const alertProjects = projects.filter(
    (p) =>
      p.status === 'DISPUTED' ||
      (p.risk_level || '').toUpperCase() === 'HIGH' ||
      (p.risk_level || '').toUpperCase() === 'CRITICAL'
  )

  const welcome = ROLE_WELCOME[user.role] ?? ''

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />

        <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-6">
          {/* ── WELCOME BANNER ─────────────────────────────────────────── */}
          <div className="glass-card p-6 border-l-4 border-brand-500 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-white">
                  Welcome back, {user.full_name.split(' ')[0]} 👋
                </h1>
                {ngoProfile && (
                  <span className="badge-blue text-xs font-semibold px-2.5 py-0.5">
                    {ngoProfile.name}
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-xs mt-1">{welcome}</p>
            </div>

            <div className="flex items-center gap-3 self-start sm:self-auto">
              {user.role === 'NGO' && (
                <Link
                  to="/projects"
                  className="btn-primary text-xs px-4 py-2 flex items-center gap-1.5 shadow-md shadow-brand-500/20"
                >
                  <span>+</span> Create Project
                </Link>
              )}
              <span className="badge-blue text-xs font-semibold px-3 py-1">
                {user.role}
              </span>
            </div>
          </div>

          {actionMessage && (
            <div className="p-4 rounded-xl bg-brand-950/60 border border-brand-700/50 text-brand-300 text-xs flex items-center justify-between shadow-md">
              <span>{actionMessage}</span>
              <button
                onClick={() => setActionMessage(null)}
                className="text-xs text-brand-400 hover:text-white font-bold ml-4"
              >
                ✕
              </button>
            </div>
          )}

          {(user.role === 'AUDITOR' || user.role === 'ADMIN') && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-brand-950/90 to-amber-950/70 border border-brand-700/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
              <div className="space-y-0.5">
                <div className="text-xs font-bold text-white flex items-center gap-2">
                  <span>🛡️</span>
                  <span>{user.role === 'ADMIN' ? 'Platform Governance & Administration' : 'Independent Auditor Operations Hub'}</span>
                </div>
                <p className="text-[11px] text-slate-300">
                  Manage pending audits, high-risk forensic queues, NGO approvals, disputes, and system configurations.
                </p>
              </div>
              <Link
                to={user.role === 'ADMIN' ? '/admin' : '/audit'}
                className="btn-primary text-xs px-4 py-2 font-bold whitespace-nowrap"
              >
                Open {user.role === 'ADMIN' ? 'Admin Center' : 'Auditor Hub'} →
              </Link>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* ── NGO OPERATIONS DASHBOARD ──────────────────────────────────── */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {user.role === 'NGO' && (
            <>
              {/* ── TOP METRICS ROW (7 MANDATORY PILLARS) ─────────────────── */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
                {/* 1. Transparency Score */}
                <div className="glass-card p-4 border-brand-500/40 bg-gradient-to-br from-surface-card to-brand-950/20 col-span-2 sm:col-span-1">
                  <div className="text-[10px] text-brand-400 font-semibold uppercase tracking-wider">
                    Transparency Score
                  </div>
                  <div className="text-3xl font-extrabold text-white font-mono mt-1">
                    {transparencyScoreVal.toFixed(0)}
                    <span className="text-xs text-slate-500 font-normal">/100</span>
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium mt-1 truncate">
                    {ngoScore?.historical_trend ? `Trend: ${ngoScore.historical_trend}` : 'Authoritative Score'}
                  </div>
                </div>

                {/* 2. Total Projects */}
                <div className="glass-card p-4">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                    Total Projects
                  </div>
                  <div className="text-3xl font-extrabold text-white font-mono mt-1">
                    {loadingProjects ? '…' : totalProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Registered portfolio</div>
                </div>

                {/* 3. Active Projects */}
                <div className="glass-card p-4 border-blue-500/30">
                  <div className="text-[10px] text-blue-400 font-semibold uppercase tracking-wider">
                    Active Projects
                  </div>
                  <div className="text-3xl font-extrabold text-blue-300 font-mono mt-1">
                    {loadingProjects ? '…' : activeProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">In execution</div>
                </div>

                {/* 4. Verified Projects */}
                <div className="glass-card p-4 border-emerald-500/30">
                  <div className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">
                    Verified Projects
                  </div>
                  <div className="text-3xl font-extrabold text-emerald-300 font-mono mt-1">
                    {loadingProjects ? '…' : verifiedProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Fully verified ✓</div>
                </div>

                {/* 5. Pending Projects */}
                <div className="glass-card p-4 border-amber-500/30">
                  <div className="text-[10px] text-amber-400 font-semibold uppercase tracking-wider">
                    Pending Projects
                  </div>
                  <div className="text-3xl font-extrabold text-amber-300 font-mono mt-1">
                    {loadingProjects ? '…' : pendingProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Awaiting scan ⏳</div>
                </div>

                {/* 6. Disputed Projects */}
                <div className="glass-card p-4 border-rose-500/30">
                  <div className="text-[10px] text-rose-400 font-semibold uppercase tracking-wider">
                    Disputed Projects
                  </div>
                  <div className="text-3xl font-extrabold text-rose-300 font-mono mt-1">
                    {loadingProjects ? '…' : disputedProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Formal review ⚠️</div>
                </div>

                {/* 7. High-Risk Projects */}
                <div className="glass-card p-4 border-rose-900/40 bg-rose-950/10">
                  <div className="text-[10px] text-rose-400 font-semibold uppercase tracking-wider">
                    High-Risk Projects
                  </div>
                  <div className="text-3xl font-extrabold text-white font-mono mt-1">
                    {loadingProjects ? '…' : highRiskProjects}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Audit triggered ⚡</div>
                </div>
              </div>

              {/* ── ATTENTION REQUIRED ALERTS BANNER ─────────────────────── */}
              {alertProjects.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/40 flex items-start gap-3">
                  <span className="text-2xl">⚠️</span>
                  <div className="text-xs space-y-1">
                    <h4 className="font-bold text-amber-300">
                      Portfolio Attention Required ({alertProjects.length} projects flagged)
                    </h4>
                    <p className="text-slate-300 leading-relaxed">
                      One or more projects have high-risk variance warnings or formal disputes lodged. Immediate review of milestone evidence and invoices recommended.
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {alertProjects.map((p) => (
                        <Link
                          key={p.id}
                          to={`/projects/${p.id}`}
                          className="px-2.5 py-1 rounded bg-surface border border-amber-700/50 text-amber-200 hover:text-white font-mono text-[11px] transition-colors"
                        >
                          {p.project_code} • {p.title} ({p.status}) →
                        </Link>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* ── NGO PROFILE SUMMARY & TRANSPARENCY SCORE DETAILS ────── */}
              {ngoProfile && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Organization Profile Card */}
                  <div className="glass-card p-6 space-y-3">
                    <div className="flex items-center justify-between border-b border-surface-border pb-3">
                      <div>
                        <h3 className="text-sm font-bold text-white">{ngoProfile.name}</h3>
                        <p className="text-[11px] font-mono text-slate-400">Reg: {ngoProfile.registration_number}</p>
                      </div>
                      <span
                        className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${
                          ngoProfile.verification_status === 'VERIFIED'
                            ? 'badge-green'
                            : 'badge-yellow'
                        }`}
                      >
                        {ngoProfile.verification_status}
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-300">
                      {ngoProfile.darpan_id && (
                        <div>
                          <span className="text-slate-400">DARPAN ID: </span>
                          <span className="font-mono text-white">{ngoProfile.darpan_id}</span>
                        </div>
                      )}
                      <div>
                        <span className="text-slate-400">Authorized Rep: </span>
                        <span>{ngoProfile.authorized_representative || user.full_name}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Official Contact: </span>
                        <span>{ngoProfile.contact_email || user.email}</span>
                      </div>
                      {ngoProfile.address && (
                        <div className="pt-1 text-[11px] text-slate-400">
                          📍 {ngoProfile.address}
                        </div>
                      )}
                    </div>

                    <div className="pt-2 border-t border-surface-border flex items-center justify-between">
                      <Link
                        to={`/public/ngos/${ngoProfile.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-brand-400 hover:text-brand-300 underline"
                      >
                        View Public Profile Page →
                      </Link>
                      <span className="text-[10px] text-slate-500 font-mono">Immutable ID</span>
                    </div>
                  </div>

                  {/* Score Explanation & Factors */}
                  <div className="glass-card p-6 lg:col-span-2 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-bold text-white flex items-center gap-2">
                          <span>🛡️</span> Authoritative Transparency Indicator
                        </h3>
                        <span className="badge-green text-xs font-mono font-bold">
                          {transparencyScoreVal.toFixed(0)}/100
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mb-3">
                        {ngoScore?.indicator_description ||
                          'Evidence-based transparency/verification indicator measuring documented proof quality.'}
                      </p>

                      {ngoScore && ngoScore.factors ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                          {Object.entries(ngoScore.factors).map(([key, factor]) => (
                            <div key={key} className="p-2.5 rounded-lg bg-surface/70 border border-surface-border">
                              <div className="flex items-center justify-between text-[11px] mb-1">
                                <span className="font-semibold text-slate-200">{factor.factor_name}</span>
                                <span className="font-mono text-brand-300 font-bold">
                                  {factor.raw_score.toFixed(0)}/100
                                </span>
                              </div>
                              <div className="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-brand-500"
                                  style={{ width: `${Math.min(100, Math.max(0, factor.raw_score))}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg bg-surface/50 text-xs text-slate-400">
                          Score metrics calculated across project execution, geofencing, and auditor reports.
                        </div>
                      )}
                    </div>

                    <div className="mt-4 pt-3 border-t border-surface-border text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Security: Calculated scores are immutable & derived by backend engine.</span>
                      <span className="text-emerald-400 font-medium">✓ Cryptographically Sealed</span>
                    </div>
                  </div>
                </div>
              )}

              {/* ── PROJECT PORTFOLIO MANAGEMENT SECTION ─────────────────── */}
              <div className="glass-card p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-border pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <span>📂</span> Project Portfolio & Lifecycle Management
                    </h2>
                    <p className="text-xs text-slate-400">
                      Upload milestone proof, submit financial invoices, review risk explanations, and monitor audits.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Search title or ID…"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="input-field text-xs py-1.5 w-48"
                    />
                    <Link
                      to="/projects"
                      className="btn-primary text-xs px-3.5 py-1.5 flex items-center gap-1"
                    >
                      <span>+</span> New Project
                    </Link>
                  </div>
                </div>

                {/* Filter Tabs */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <button
                    onClick={() => setActiveTab('ALL')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'ALL'
                        ? 'bg-brand-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    All ({totalProjects})
                  </button>
                  <button
                    onClick={() => setActiveTab('ACTIVE')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'ACTIVE'
                        ? 'bg-blue-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    Active ({activeProjects})
                  </button>
                  <button
                    onClick={() => setActiveTab('VERIFIED')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'VERIFIED'
                        ? 'bg-emerald-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    Verified ({verifiedProjects})
                  </button>
                  <button
                    onClick={() => setActiveTab('PENDING')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'PENDING'
                        ? 'bg-amber-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    Pending ({pendingProjects})
                  </button>
                  <button
                    onClick={() => setActiveTab('DISPUTED')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'DISPUTED'
                        ? 'bg-rose-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    Disputed ({disputedProjects})
                  </button>
                  <button
                    onClick={() => setActiveTab('HIGH_RISK')}
                    className={`px-3 py-1 rounded-lg transition-colors ${
                      activeTab === 'HIGH_RISK'
                        ? 'bg-purple-600 text-white font-semibold'
                        : 'bg-surface border border-surface-border text-slate-300 hover:text-white'
                    }`}
                  >
                    High-Risk ({highRiskProjects})
                  </button>
                </div>

                {/* Projects Table */}
                {loadingProjects ? (
                  <div className="py-12 text-center text-slate-400 text-xs">
                    Loading organization project portfolio…
                  </div>
                ) : filteredProjects.length === 0 ? (
                  <div className="py-12 text-center text-slate-400 text-xs rounded-xl border border-dashed border-surface-border">
                    No projects found under this filter criteria.{' '}
                    <Link to="/projects" className="text-brand-400 underline">
                      Create your first project →
                    </Link>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-surface-border text-slate-400">
                          <th className="pb-3 font-semibold">Project Title & Code</th>
                          <th className="pb-3 font-semibold">Sector</th>
                          <th className="pb-3 font-semibold">Target Budget</th>
                          <th className="pb-3 font-semibold">Status</th>
                          <th className="pb-3 font-semibold">Evidence Score</th>
                          <th className="pb-3 font-semibold">Risk Level</th>
                          <th className="pb-3 font-semibold text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-border/40">
                        {filteredProjects.map((p) => {
                          const isHighRisk =
                            (p.risk_level || '').toUpperCase() === 'HIGH' ||
                            (p.risk_level || '').toUpperCase() === 'CRITICAL'
                          return (
                            <tr key={p.id} className="hover:bg-white/[0.02] transition-colors">
                              <td className="py-3">
                                <Link
                                  to={`/projects/${p.id}`}
                                  className="font-semibold text-white hover:text-brand-300 transition-colors block"
                                >
                                  {p.title}
                                </Link>
                                <span className="font-mono text-[10px] text-slate-400">
                                  {p.project_code}
                                </span>
                              </td>
                              <td className="py-3">
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-surface-border text-slate-300">
                                  {p.category.replace(/_/g, ' ')}
                                </span>
                              </td>
                              <td className="py-3 font-mono font-bold text-white">
                                ₹{p.target_amount ? p.target_amount.toLocaleString('en-IN') : '—'}
                              </td>
                              <td className="py-3">
                                <span
                                  className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase ${
                                    p.status === 'VERIFIED'
                                      ? 'badge-green'
                                      : p.status === 'PARTIALLY_VERIFIED'
                                      ? 'badge-yellow'
                                      : p.status === 'DISPUTED'
                                      ? 'badge-red'
                                      : 'badge-blue'
                                  }`}
                                >
                                  {p.status.replace(/_/g, ' ')}
                                </span>
                              </td>
                              <td className="py-3 font-mono font-bold text-brand-300">
                                {p.evidence_score !== undefined && p.evidence_score !== null
                                  ? `${p.evidence_score.toFixed(0)}/100`
                                  : 'Pending'}
                              </td>
                              <td className="py-3">
                                <span
                                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                                    isHighRisk
                                      ? 'bg-rose-950 text-rose-300 border border-rose-700/60'
                                      : (p.risk_level || '').toUpperCase() === 'MEDIUM'
                                      ? 'bg-amber-950 text-amber-300 border border-amber-700/60'
                                      : 'bg-emerald-950 text-emerald-300 border border-emerald-700/60'
                                  }`}
                                >
                                  {p.risk_level || 'LOW'}
                                </span>
                              </td>
                              <td className="py-3 text-right">
                                <Link
                                  to={`/projects/${p.id}`}
                                  className="btn-primary text-xs px-3 py-1 inline-flex items-center gap-1"
                                >
                                  <span>⚙️</span> Manage Dossier →
                                </Link>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* ── DONOR TRANSPARENCY & DIRECT CONTRIBUTION HUB ─────────────── */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {user.role === 'DONOR' && (
            <div className="space-y-8">
              {/* ── Donor Impact KPI Metric Strip ── */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="stat-card border-emerald-500/30 bg-gradient-to-br from-surface-card to-emerald-950/20">
                  <div className="stat-label flex items-center justify-between">
                    <span>Total Donated</span>
                    <span className="text-emerald-400 text-base">💝</span>
                  </div>
                  <div className="stat-value text-emerald-400 font-mono mt-1">
                    ₹{myDonations.total_donated.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">Direct Disbursed Funds</div>
                </div>

                <div className="stat-card border-brand-500/30">
                  <div className="stat-label flex items-center justify-between">
                    <span>Supported NGOs</span>
                    <span className="text-brand-400 text-base">🏛️</span>
                  </div>
                  <div className="stat-value text-white font-mono mt-1">
                    {myDonations.supported_ngos_count}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">Verified Organizations</div>
                </div>

                <div className="stat-card border-blue-500/30">
                  <div className="stat-label flex items-center justify-between">
                    <span>Total Contributions</span>
                    <span className="text-blue-400 text-base">🧾</span>
                  </div>
                  <div className="stat-value text-blue-400 font-mono mt-1">
                    {myDonations.total_donations_count}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">Audited Transactions</div>
                </div>

                <div className="stat-card border-purple-500/30">
                  <div className="stat-label flex items-center justify-between">
                    <span>Tax Exemption (80G)</span>
                    <span className="text-purple-400 text-base">📜</span>
                  </div>
                  <div className="text-lg font-bold text-white font-mono mt-2">
                    100% Eligible
                  </div>
                  <div className="text-[11px] text-purple-300 mt-1">Instant IT Act Receipts</div>
                </div>
              </div>

              {/* ── Registered NGO Discovery Directory ── */}
              <div className="glass-card p-6 space-y-6 border-brand-500/40">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-surface-border pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl">🏛️</span>
                      <h2 className="text-lg font-bold text-white tracking-tight">
                        Directory of Registered NGOs
                      </h2>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-brand-950 text-brand-300 border border-brand-700/60">
                        {donorNgos.length} Registered
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Search and inspect verified NGOs on our platform. Review transparency scores, past milestones, and donate directly.
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <Link
                      to="/public/ngos"
                      className="text-xs text-brand-400 hover:text-brand-300 underline font-medium"
                    >
                      Advanced Directory Search →
                    </Link>
                  </div>
                </div>

                {/* Filter & Search Bar */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2 relative">
                    <input
                      type="text"
                      placeholder="Search by NGO name, registration code, or state..."
                      value={donorSearch}
                      onChange={(e) => setDonorSearch(e.target.value)}
                      className="input-field text-xs pl-8"
                    />
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs">
                      🔍
                    </span>
                  </div>

                  <div>
                    <select
                      value={donorCategory}
                      onChange={(e) => setDonorCategory(e.target.value)}
                      className="input-field text-xs py-2"
                    >
                      <option value="ALL">All Sectors / Causes</option>
                      <option value="WATER_AND_SANITATION">Water & Sanitation</option>
                      <option value="HEALTHCARE">Healthcare</option>
                      <option value="EDUCATION">Education</option>
                      <option value="FOOD_DISTRIBUTION">Food Distribution</option>
                      <option value="ENVIRONMENT">Environment</option>
                      <option value="INFRASTRUCTURE">Infrastructure</option>
                    </select>
                  </div>
                </div>

                {/* NGO Cards Grid */}
                {loadingDonorNgos ? (
                  <div className="py-12 text-center text-slate-400 space-y-2">
                    <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
                    <p className="text-xs">Loading verified NGO registry…</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {donorNgos
                      .filter((ngo) => {
                        if (donorSearch.trim()) {
                          const q = donorSearch.toLowerCase()
                          const matchesName = ngo.name.toLowerCase().includes(q)
                          const matchesCode = ngo.registration_number.toLowerCase().includes(q)
                          const matchesAddr = ngo.address?.toLowerCase().includes(q)
                          if (!matchesName && !matchesCode && !matchesAddr) return false
                        }
                        if (donorCategory !== 'ALL') {
                          if (!ngo.project_categories?.includes(donorCategory)) return false
                        }
                        return true
                      })
                      .map((ngo) => {
                        const score = ngo.transparency_score ?? 85.0
                        return (
                          <div
                            key={ngo.id}
                            className="p-5 rounded-2xl bg-surface-card border border-surface-border hover:border-brand-500/60 transition-all flex flex-col justify-between space-y-4 shadow-lg hover:shadow-brand-500/10"
                          >
                            <div className="space-y-3">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <h3 className="text-sm font-bold text-white leading-snug">
                                    {ngo.name}
                                  </h3>
                                  <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                                    Reg: {ngo.registration_number}
                                  </p>
                                </div>
                                <span className="badge-green text-[10px] font-bold uppercase whitespace-nowrap">
                                  ✓ Verified NGO
                                </span>
                              </div>

                              {/* Transparency Score Indicator */}
                              <div className="p-2.5 rounded-xl bg-slate-900/90 border border-surface-border flex items-center justify-between">
                                <div>
                                  <div className="text-[10px] text-slate-400 font-medium">
                                    Trust & Transparency Score
                                  </div>
                                  <div className="text-base font-extrabold text-white font-mono mt-0.5">
                                    {score.toFixed(0)} <span className="text-xs text-slate-500">/ 100</span>
                                  </div>
                                </div>
                                <span
                                  className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                                    score >= 80 ? 'badge-green' : score >= 60 ? 'badge-blue' : 'badge-yellow'
                                  }`}
                                >
                                  {score >= 80 ? '🛡️ Strong' : '✓ Good'}
                                </span>
                              </div>

                              {ngo.description && (
                                <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                                  {ngo.description}
                                </p>
                              )}

                              {/* Categories & Project Stats */}
                              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono">
                                  📂 {ngo.project_count} Projects ({ngo.verified_project_count} Verified)
                                </span>
                                {ngo.project_categories?.slice(0, 2).map((cat) => (
                                  <span
                                    key={cat}
                                    className="px-2 py-0.5 rounded text-[10px] bg-brand-950 text-brand-300 border border-brand-800/60 font-mono"
                                  >
                                    {cat.replace(/_/g, ' ')}
                                  </span>
                                ))}
                              </div>

                              {ngo.address && (
                                <div className="text-[11px] text-slate-400 truncate">
                                  📍 {ngo.address}
                                </div>
                              )}
                            </div>

                            {/* Direct Action Buttons */}
                            <div className="pt-3 border-t border-surface-border flex items-center gap-2">
                              <button
                                onClick={() => {
                                  setDonationModalNgo(ngo)
                                  setDonationModalProject(null)
                                }}
                                className="flex-1 btn-primary text-xs py-2 flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/30 text-white font-bold"
                              >
                                <span>💝</span>
                                <span>Donate Directly</span>
                              </button>

                              <Link
                                to={`/public/ngos/${ngo.id}`}
                                className="btn-secondary text-xs py-2 px-3 flex items-center justify-center"
                                title="Inspect transparency dossier"
                              >
                                Dossier →
                              </Link>
                            </div>
                          </div>
                        )
                      })}
                  </div>
                )}
              </div>

              {/* ── Active Projects Open for Direct Funding ── */}
              <div className="glass-card p-6 space-y-4 border-surface-border">
                <div className="flex items-center justify-between border-b border-surface-border pb-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <span>🎯</span> Verified NGO Projects Seeking Direct Support
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Fund specific milestones directly. Every rupee tracked with GPS coordinates & evidence dossiers.
                    </p>
                  </div>
                  <Link to="/projects" className="text-xs text-brand-400 hover:text-brand-300 font-medium">
                    View All Projects →
                  </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {projects.slice(0, 6).map((proj) => {
                    const budget = proj.target_amount || proj.total_budget || 150000
                    const targetNgo = donorNgos.find((n) => n.id === proj.ngo_id)
                    return (
                      <div
                        key={proj.id}
                        className="p-4 rounded-xl bg-surface-card border border-surface-border hover:border-brand-500/50 flex flex-col justify-between space-y-3"
                      >
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-mono text-brand-400 font-bold">
                              {proj.project_code}
                            </span>
                            <span className="badge-green text-[10px] uppercase font-bold">
                              {proj.status}
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-white line-clamp-1">{proj.title}</h4>
                          {proj.description && (
                            <p className="text-xs text-slate-400 line-clamp-2">{proj.description}</p>
                          )}
                          <div className="text-xs text-slate-300 flex items-center justify-between pt-1">
                            <span className="text-slate-400">Budget Goal:</span>
                            <span className="font-mono font-bold text-white">
                              ₹{budget.toLocaleString()} INR
                            </span>
                          </div>
                          {proj.evidence_score !== null && proj.evidence_score !== undefined && (
                            <div className="text-[11px] text-emerald-400 font-mono">
                              Verified Score: {proj.evidence_score.toFixed(1)}% Evidence Match
                            </div>
                          )}
                        </div>

                        <div className="pt-2 border-t border-surface-border flex items-center justify-between">
                          <Link
                            to={`/projects/${proj.id}`}
                            className="text-xs text-slate-400 hover:text-white underline"
                          >
                            Milestones
                          </Link>
                          <button
                            onClick={() => {
                              const ngoItem: NGOPublicSummary = targetNgo || {
                                id: proj.ngo_id,
                                name: 'Registered NGO',
                                registration_number: 'VERIFIED',
                                verification_status: 'VERIFIED',
                                is_verified: true,
                                project_count: 1,
                                verified_project_count: 1,
                                project_categories: [],
                                created_at: new Date().toISOString(),
                              }
                              setDonationModalNgo(ngoItem)
                              setDonationModalProject(proj)
                            }}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md flex items-center gap-1"
                          >
                            <span>🤝</span>
                            <span>Fund Project</span>
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* ── Donor Contribution Portfolio & Tax Receipts Table ── */}
              <div className="glass-card p-6 space-y-4 border-surface-border">
                <div className="flex items-center justify-between border-b border-surface-border pb-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <span>🧾</span> Your Contributions & 80G Tax Receipts
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Immutable record of your direct donations. Download or print Section 80G tax certificates.
                    </p>
                  </div>
                  <span className="text-xs font-mono text-emerald-400 font-bold">
                    {myDonations.items.length} Transactions
                  </span>
                </div>

                {myDonations.items.length === 0 ? (
                  <div className="py-8 text-center text-slate-400 space-y-2">
                    <p className="text-sm">✨ You haven't made any direct contributions yet.</p>
                    <p className="text-xs text-slate-500">
                      Select an NGO above to make your first transparent, 80G tax-exempt donation!
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-surface-border text-slate-400 font-mono text-[11px]">
                          <th className="py-2.5 px-3">Date</th>
                          <th className="py-2.5 px-3">Beneficiary NGO</th>
                          <th className="py-2.5 px-3">Target Allocation</th>
                          <th className="py-2.5 px-3">Amount</th>
                          <th className="py-2.5 px-3">Channel</th>
                          <th className="py-2.5 px-3">Receipt No.</th>
                          <th className="py-2.5 px-3 text-right">Tax Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-border/50 text-slate-300">
                        {myDonations.items.map((d) => (
                          <tr key={d.id} className="hover:bg-slate-900/50">
                            <td className="py-2.5 px-3 font-mono text-slate-400">
                              {d.created_at ? new Date(d.created_at).toLocaleDateString() : 'Recent'}
                            </td>
                            <td className="py-2.5 px-3 font-semibold text-white">
                              {d.ngo_name}
                            </td>
                            <td className="py-2.5 px-3 text-slate-400 truncate max-w-[180px]">
                              {d.project_title ? `🎯 ${d.project_title}` : '⭐ General NGO Fund'}
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">
                              ₹{d.amount.toLocaleString()} {d.currency}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">
                                {d.payment_method}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-xs text-brand-300">
                              {d.receipt_number}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <button
                                onClick={() => {
                                  window.alert(
                                    `80G TAX EXEMPTION CERTIFICATE\n-----------------------------------\nReceipt: ${d.receipt_number}\nTransaction ID: ${d.transaction_id}\nDonor: ${d.donor_name}\nNGO: ${d.ngo_name}\nAmount: ₹${d.amount.toLocaleString()} INR\nEligible for 50% deduction under Section 80G of the Income Tax Act.`
                                  )
                                }}
                                className="text-xs text-brand-400 hover:text-brand-300 underline font-mono"
                              >
                                Print 80G 🖨️
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Direct Donation Gateway Modal */}
          {donationModalNgo && (
            <DirectDonationModal
              ngoId={donationModalNgo.id}
              ngoName={donationModalNgo.name}
              ngoRegistrationNumber={donationModalNgo.registration_number}
              projects={projects
                .filter((p) => p.ngo_id === donationModalNgo.id)
                .map((p) => ({ id: p.id, title: p.title, project_code: p.project_code }))}
              preselectedProjectId={donationModalProject?.id || null}
              onClose={() => {
                setDonationModalNgo(null)
                setDonationModalProject(null)
              }}
              onSuccess={(d) => {
                setActionMessage(
                  `🎉 Donation of ₹${d.amount.toLocaleString()} directly to ${d.ngo_name} processed successfully! Receipt: ${d.receipt_number}`
                )
                loadDonorHubData()
              }}
            />
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* ── ADMIN VERIFICATION QUEUE ──────────────────────────────────── */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {user.role === 'ADMIN' && (
            <div className="glass-card p-6 space-y-4 border border-surface-border">
              <div className="flex items-center justify-between border-b border-surface-border pb-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">Pending NGO Verification Queue</h2>
                  <p className="text-xs text-slate-400">
                    Review and verify newly registered NGOs. Prototype admin review only.
                  </p>
                </div>
                <button
                  onClick={loadPendingNgos}
                  className="text-xs text-brand-400 hover:text-brand-300 px-3 py-1 rounded-lg border border-brand-700/40"
                >
                  Refresh Queue ({pendingNgos.length})
                </button>
              </div>

              {pendingNgos.length === 0 ? (
                <div className="py-6 text-center text-sm text-slate-400">
                  ✨ No NGOs currently pending review. All registrations are up to date!
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingNgos.map((ngo) => (
                    <div
                      key={ngo.id}
                      className="p-4 rounded-xl bg-surface-card border border-surface-border flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-brand-500/50 transition-colors"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">{ngo.name}</span>
                          <span className="text-xs font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                            {ngo.registration_number}
                          </span>
                        </div>
                        {ngo.description && (
                          <p className="text-xs text-slate-400 max-w-xl line-clamp-2">{ngo.description}</p>
                        )}
                        <div className="text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-1 pt-1">
                          {ngo.authorized_representative && (
                            <span>Rep: <strong>{ngo.authorized_representative}</strong></span>
                          )}
                          {ngo.contact_email && <span>Email: {ngo.contact_email}</span>}
                          {ngo.contact_phone && <span>Phone: {ngo.contact_phone}</span>}
                          {ngo.address && <span>Address: {ngo.address}</span>}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {rejectingId === ngo.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="Reason for rejection"
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              className="input-field text-xs py-1.5 px-2 w-48"
                            />
                            <button
                              onClick={() => handleReject(ngo.id)}
                              className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => { setRejectingId(null); setRejectReason(''); }}
                              className="px-2 py-1.5 text-xs text-slate-400 hover:text-white"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <>
                            <button
                              onClick={() => handleVerify(ngo.id)}
                              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors"
                            >
                              Verify NGO
                            </button>
                            <button
                              onClick={() => setRejectingId(ngo.id)}
                              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 border border-slate-700 text-xs transition-colors"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Notice */}
          <div className="glass-card p-4 border-dashed border-slate-700">
            <div className="flex items-center gap-3 text-slate-400">
              <svg className="w-5 h-5 text-brand-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs">
                <span className="text-white font-medium">NGO Transparency Operations Center.</span>{' '}
                Automated 10-engine verification, OCR invoice reconciliation, PostGIS boundary calculations, and independent physical audit tracks active.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
