import React, { useState, useEffect } from 'react'
import { useAuth } from '../auth/AuthContext'
import { getAuditDashboardQueues, getAuditLogs } from '../api/audit'
import adminApi from '../api/admin'
import {
  ActivityLogItem,
  AdminDisputeItem,
  AuditConfig,
  AuditQueueGroup,
  AuditSummary,
  NGOResponse,
  SystemStats,
} from '../types'
import AuditReviewModal from '../components/audit/AuditReviewModal'

type DashboardTab =
  | 'PENDING'
  | 'HIGH_RISK'
  | 'HIGH_VALUE'
  | 'RANDOM'
  | 'DISPUTED'
  | 'VERIFIED'
  | 'LOGS'
  | 'NGO_REVIEW'
  | 'CONFIG'
  | 'DISPUTES_ADMIN'
  | 'STATS'

export default function AuditorAdminDashboard() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'ADMIN'

  const [activeTab, setActiveTab] = useState<DashboardTab>('PENDING')
  const [queues, setQueues] = useState<AuditQueueGroup | null>(null)
  const [logs, setLogs] = useState<ActivityLogItem[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)

  // Audit Review modal
  const [reviewAuditId, setReviewAuditId] = useState<string | null>(null)

  // Admin states
  const [pendingNgos, setPendingNgos] = useState<NGOResponse[]>([])
  const [rejectingNgoId, setRejectingNgoId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState<string>('')

  const [auditConfig, setAuditConfig] = useState<AuditConfig | null>(null)
  const [configSaving, setConfigSaving] = useState<boolean>(false)
  const [configForm, setConfigForm] = useState({
    high_project_value_threshold: 1000000,
    audit_random_sample_rate: 0.05,
    high_risk_threshold: 60,
  })

  const [allDisputes, setAllDisputes] = useState<AdminDisputeItem[]>([])
  const [resolvingDispute, setResolvingDispute] = useState<AdminDisputeItem | null>(null)
  const [resolutionAction, setResolutionAction] = useState<'UPHOLD_DECISION' | 'REVISE_DECISION' | 'SCHEDULE_REAUDIT'>('UPHOLD_DECISION')
  const [resolutionNotes, setResolutionNotes] = useState<string>('')

  const [stats, setStats] = useState<SystemStats | null>(null)

  useEffect(() => {
    loadDashboardData()
  }, [])

  async function loadDashboardData() {
    setLoading(true)
    setError(null)
    try {
      // 1. Fetch audit queues
      const queueRes = await getAuditDashboardQueues()
      if (queueRes.success && queueRes.data) {
        setQueues(queueRes.data)
      }

      // 2. Fetch activity logs
      const logRes = await getAuditLogs({ limit: 40 })
      if (logRes.success && logRes.data) {
        setLogs(logRes.data)
      }

      // 3. Admin-only data
      if (isAdmin) {
        await Promise.allSettled([
          adminApi.getPendingNgos().then((r) => r.data.data && setPendingNgos(r.data.data)),
          adminApi.getAuditConfig().then((r) => {
            if (r.data.data) {
              setAuditConfig(r.data.data)
              setConfigForm({
                high_project_value_threshold: r.data.data.high_project_value_threshold,
                audit_random_sample_rate: r.data.data.audit_random_sample_rate,
                high_risk_threshold: r.data.data.high_risk_threshold,
              })
            }
          }),
          adminApi.getDisputes().then((r) => r.data.data && setAllDisputes(r.data.data)),
          adminApi.getStats().then((r) => r.data.data && setStats(r.data.data)),
        ])
      }
    } catch (err: any) {
      console.error('Error loading auditor dashboard data:', err)
      setError('Error loading operational queue data.')
    } finally {
      setLoading(false)
    }
  }

  // Admin NGO handlers
  async function handleVerifyNgo(id: string, name: string) {
    try {
      const res = await adminApi.verifyNgo(id)
      if (res.data.success) {
        setActionNotice(`NGO "${name}" verified successfully.`)
        setPendingNgos((prev) => prev.filter((n) => n.id !== id))
      }
    } catch {
      setError('Failed to verify NGO onboarding application.')
    }
  }

  async function handleRejectNgo() {
    if (!rejectingNgoId) return
    try {
      const res = await adminApi.rejectNgo(rejectingNgoId, rejectReason || undefined)
      if (res.data.success) {
        setActionNotice('NGO application rejected.')
        setPendingNgos((prev) => prev.filter((n) => n.id !== rejectingNgoId))
        setRejectingNgoId(null)
        setRejectReason('')
      }
    } catch {
      setError('Failed to reject NGO onboarding application.')
    }
  }

  // Admin Config handlers
  async function handleSaveConfig(e: React.FormEvent) {
    e.preventDefault()
    setConfigSaving(true)
    try {
      const res = await adminApi.updateAuditConfig(configForm)
      if (res.data.success && res.data.data) {
        setAuditConfig(res.data.data)
        setActionNotice('Audit system configuration thresholds updated successfully.')
      }
    } catch {
      setError('Failed to update audit configuration.')
    } finally {
      setConfigSaving(false)
    }
  }

  // Admin Dispute handlers
  async function handleResolveDispute(e: React.FormEvent) {
    e.preventDefault()
    if (!resolvingDispute) return
    if (!resolutionNotes.trim()) {
      setError('Resolution findings and justification notes are required.')
      return
    }

    try {
      const res = await adminApi.resolveDispute(resolvingDispute.id, {
        action: resolutionAction,
        resolution_notes: resolutionNotes.trim(),
      })
      if (res.data.success) {
        setActionNotice(`Dispute for ${resolvingDispute.project_code || 'Project'} resolved successfully.`)
        setResolvingDispute(null)
        setResolutionNotes('')
        // Refresh disputes & queues
        loadDashboardData()
      }
    } catch {
      setError('Failed to resolve dispute.')
    }
  }

  const counts = queues?.counts || {
    pending_audits: 0,
    high_risk: 0,
    high_value: 0,
    random_queue: 0,
    disputed: 0,
    recently_verified: 0,
    total_all: 0,
  }

  return (
    <div className="min-h-screen bg-surface-dark text-slate-100 p-4 sm:p-6 lg:p-8 space-y-6">
      {/* ── TOP HEADER & ROLE BADGE ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-border">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-3xl">🛡️</span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-black text-white tracking-tight">
                  {isAdmin ? 'Platform Governance & Audit Center' : 'Independent Auditor Operations Hub'}
                </h1>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-extrabold uppercase border ${
                    isAdmin
                      ? 'bg-amber-950/80 text-amber-300 border-amber-600/60'
                      : 'bg-brand-950/80 text-brand-300 border-brand-600/60'
                  }`}
                >
                  {user?.role || 'AUDITOR'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time forensic verification, automated queue management, and immutable audit logs.
              </p>
            </div>
          </div>
        </div>

        {/* Quick Ticker */}
        <div className="flex items-center gap-3 text-xs">
          <div className="px-3 py-1.5 rounded-xl bg-surface border border-surface-border">
            <div className="text-[10px] text-slate-400 uppercase">Pending Audits</div>
            <div className="text-base font-bold text-amber-400 font-mono">{counts.pending_audits}</div>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-surface border border-surface-border">
            <div className="text-[10px] text-slate-400 uppercase">High-Risk Flags</div>
            <div className="text-base font-bold text-rose-400 font-mono">{counts.high_risk}</div>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-surface border border-surface-border">
            <div className="text-[10px] text-slate-400 uppercase">Active Disputes</div>
            <div className="text-base font-bold text-purple-400 font-mono">{counts.disputed}</div>
          </div>
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="px-3 py-2 rounded-xl bg-surface border border-surface-border text-slate-300 hover:text-white hover:bg-surface-border text-xs flex items-center gap-1.5"
          >
            <span>🔄</span> {loading ? 'Syncing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {actionNotice && (
        <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-700/60 text-emerald-300 text-xs flex items-center justify-between">
          <span>✓ {actionNotice}</span>
          <button onClick={() => setActionNotice(null)} className="text-emerald-400 font-bold">✕</button>
        </div>
      )}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-700/60 text-rose-300 text-xs flex items-center justify-between">
          <span>✕ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 font-bold">✕</button>
        </div>
      )}

      {/* ── NAVIGATION TABS ── */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-surface-border">
        <button
          onClick={() => setActiveTab('PENDING')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'PENDING'
              ? 'bg-brand-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>⏳</span> Pending Audits ({counts.pending_audits})
        </button>

        <button
          onClick={() => setActiveTab('HIGH_RISK')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'HIGH_RISK'
              ? 'bg-rose-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>⚠️</span> High-Risk Projects ({counts.high_risk})
        </button>

        <button
          onClick={() => setActiveTab('HIGH_VALUE')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'HIGH_VALUE'
              ? 'bg-amber-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>💰</span> High-Value Projects ({counts.high_value})
        </button>

        <button
          onClick={() => setActiveTab('RANDOM')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'RANDOM'
              ? 'bg-indigo-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>🎲</span> Random Audit Queue ({counts.random_queue})
        </button>

        <button
          onClick={() => setActiveTab('DISPUTED')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'DISPUTED'
              ? 'bg-purple-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>⚖️</span> Disputed Projects ({counts.disputed})
        </button>

        <button
          onClick={() => setActiveTab('VERIFIED')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'VERIFIED'
              ? 'bg-emerald-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>✓</span> Recently Verified ({counts.recently_verified})
        </button>

        <button
          onClick={() => setActiveTab('LOGS')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'LOGS'
              ? 'bg-slate-600 text-white'
              : 'bg-surface text-slate-400 hover:text-white hover:bg-surface-border'
          }`}
        >
          <span>📜</span> Activity Logs ({logs.length})
        </button>

        {/* Admin Exclusive Tabs */}
        {isAdmin && (
          <>
            <div className="h-5 w-px bg-surface-border mx-1" />
            <button
              onClick={() => setActiveTab('NGO_REVIEW')}
              className={`px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'NGO_REVIEW'
                  ? 'bg-amber-600 text-white'
                  : 'bg-amber-950/40 text-amber-300 border border-amber-800/50 hover:bg-amber-900/60'
              }`}
            >
              <span>🏢</span> NGO Approvals ({pendingNgos.length})
            </button>

            <button
              onClick={() => setActiveTab('CONFIG')}
              className={`px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'CONFIG'
                  ? 'bg-cyan-600 text-white'
                  : 'bg-cyan-950/40 text-cyan-300 border border-cyan-800/50 hover:bg-cyan-900/60'
              }`}
            >
              <span>⚙️</span> Audit Config
            </button>

            <button
              onClick={() => setActiveTab('DISPUTES_ADMIN')}
              className={`px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'DISPUTES_ADMIN'
                  ? 'bg-rose-600 text-white'
                  : 'bg-rose-950/40 text-rose-300 border border-rose-800/50 hover:bg-rose-900/60'
              }`}
            >
              <span>🏛️</span> Dispute Desk ({allDisputes.length})
            </button>

            <button
              onClick={() => setActiveTab('STATS')}
              className={`px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'STATS'
                  ? 'bg-teal-600 text-white'
                  : 'bg-teal-950/40 text-teal-300 border border-teal-800/50 hover:bg-teal-900/60'
              }`}
            >
              <span>📊</span> Platform KPIs
            </button>
          </>
        )}
      </div>

      {/* ── TAB CONTENT PANELS ── */}
      {loading ? (
        <div className="py-24 text-center">
          <div className="inline-block animate-spin text-3xl mb-3">⚙️</div>
          <p className="text-sm text-slate-400">Loading platform queues & audit dossiers…</p>
        </div>
      ) : (
        <>
          {/* SECTION 1: Pending Audits */}
          {activeTab === 'PENDING' && (
            <QueueTable
              title="Pending Audit Cases"
              subtitle="Projects queued for field or forensic desk audit by trigger selection."
              items={queues?.pending_audits || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 2: High-Risk Projects */}
          {activeTab === 'HIGH_RISK' && (
            <QueueTable
              title="High-Risk Projects Queue"
              subtitle="Projects flagged with anomaly signals, budget runaway, or duplicate media."
              items={queues?.high_risk || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 3: High-Value Projects */}
          {activeTab === 'HIGH_VALUE' && (
            <QueueTable
              title="High-Value Projects Queue"
              subtitle="Projects exceeding statutory budget thresholds (₹10,00,000+)."
              items={queues?.high_value || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 4: Random Audit Queue */}
          {activeTab === 'RANDOM' && (
            <QueueTable
              title="Random Sampling Queue"
              subtitle="Statistically selected spot-checks enforcing compliance across all project sizes."
              items={queues?.random_queue || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 5: Disputed Projects */}
          {activeTab === 'DISPUTED' && (
            <QueueTable
              title="Contested / Disputed Projects"
              subtitle="Audits where NGOs have formally challenged discrepancies or negative decisions."
              items={queues?.disputed || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 6: Recently Verified Projects */}
          {activeTab === 'VERIFIED' && (
            <QueueTable
              title="Recently Verified Projects"
              subtitle="Projects concluded with confirmed physical inspection or forensic proof."
              items={queues?.recently_verified || []}
              onReview={(auditId) => setReviewAuditId(auditId)}
            />
          )}

          {/* SECTION 7: Activity Logs */}
          {activeTab === 'LOGS' && (
            <div className="glass-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>📜</span> Tamper-Evident System Activity Trail
                  </h3>
                  <p className="text-xs text-slate-400">
                    Cryptographically recorded audit actions, score recalculations, and status transitions.
                  </p>
                </div>
                <span className="text-xs font-mono text-slate-400">Total events: {logs.length}</span>
              </div>

              {logs.length === 0 ? (
                <div className="text-center py-12 text-slate-400 text-xs">No activity logs recorded yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-surface-border text-slate-400 uppercase text-[10px]">
                        <th className="py-2.5 px-3">Timestamp</th>
                        <th className="py-2.5 px-3">Action</th>
                        <th className="py-2.5 px-3">Actor</th>
                        <th className="py-2.5 px-3">Resource</th>
                        <th className="py-2.5 px-3">Details</th>
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border/50 font-mono">
                      {logs.map((log) => (
                        <tr key={log.id} className="hover:bg-surface/50">
                          <td className="py-2 px-3 text-slate-400 text-[11px]">
                            {new Date(log.created_at).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 font-semibold text-brand-300">{log.action}</td>
                          <td className="py-2 px-3 text-slate-300">
                            {log.actor_role || 'SYSTEM'}{' '}
                            {log.actor_email && <span className="text-slate-500 font-sans text-[10px]">({log.actor_email})</span>}
                          </td>
                          <td className="py-2 px-3 text-slate-400">
                            {log.resource_type}: {log.resource_id?.slice(0, 8)}…
                          </td>
                          <td className="py-2 px-3 text-[11px] text-slate-300 truncate max-w-xs font-sans">
                            {log.detail ? JSON.stringify(log.detail).slice(0, 90) : '—'}
                          </td>
                          <td className="py-2 px-3">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${log.success ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'}`}>
                              {log.success ? 'SUCCESS' : 'FAILED'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── ADMIN ONLY SECTIONS ── */}
          {isAdmin && activeTab === 'NGO_REVIEW' && (
            <div className="glass-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🏢</span> NGO Onboarding Verification Queue
                  </h3>
                  <p className="text-xs text-slate-400">
                    Review pending NGO onboarding applications. Requires platform administrator sign-off.
                  </p>
                </div>
                <span className="badge-amber text-xs">{pendingNgos.length} Pending</span>
              </div>

              {pendingNgos.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  Zero pending NGO registration applications. All onboarding requests verified.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-surface-border text-slate-400 uppercase text-[10px]">
                        <th className="py-2.5 px-3">NGO Name</th>
                        <th className="py-2.5 px-3">Registration Number</th>
                        <th className="py-2.5 px-3">Contact</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3 text-right">Administrative Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border/50">
                      {pendingNgos.map((ngo) => (
                        <tr key={ngo.id} className="hover:bg-surface/50">
                          <td className="py-3 px-3 font-semibold text-white">{ngo.name}</td>
                          <td className="py-3 px-3 font-mono text-slate-300">{ngo.registration_number}</td>
                          <td className="py-3 px-3 text-slate-400">{ngo.contact_email || '—'}</td>
                          <td className="py-3 px-3">
                            <span className="badge-amber text-[10px]">{ngo.verification_status}</span>
                          </td>
                          <td className="py-3 px-3 text-right space-x-2">
                            <button
                              onClick={() => handleVerifyNgo(ngo.id, ngo.name)}
                              className="px-3 py-1 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-700 hover:bg-emerald-900 text-xs font-semibold"
                            >
                              Verify NGO
                            </button>
                            <button
                              onClick={() => setRejectingNgoId(ngo.id)}
                              className="px-3 py-1 rounded-lg bg-rose-950 text-rose-300 border border-rose-700 hover:bg-rose-900 text-xs font-semibold"
                            >
                              Reject
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {isAdmin && activeTab === 'CONFIG' && (
            <div className="glass-card p-6 max-w-2xl mx-auto space-y-6">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>⚙️</span> Platform Audit Configuration
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Adjust algorithmic thresholds that govern automated audit queuing and fraud trigger flags.
                </p>
              </div>

              <form onSubmit={handleSaveConfig} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    High-Value Project Trigger Threshold (₹):
                  </label>
                  <input
                    type="number"
                    min="100000"
                    step="50000"
                    value={configForm.high_project_value_threshold}
                    onChange={(e) =>
                      setConfigForm({ ...configForm, high_project_value_threshold: parseFloat(e.target.value) })
                    }
                    className="w-full bg-surface border border-surface-border rounded-xl px-3 py-2 text-xs text-white"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Projects with target budget at or above this value are automatically queued for physical audit.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Random Audit Sampling Probability (0.00 to 1.00):
                  </label>
                  <input
                    type="number"
                    min="0.01"
                    max="1.0"
                    step="0.01"
                    value={configForm.audit_random_sample_rate}
                    onChange={(e) =>
                      setConfigForm({ ...configForm, audit_random_sample_rate: parseFloat(e.target.value) })
                    }
                    className="w-full bg-surface border border-surface-border rounded-xl px-3 py-2 text-xs text-white"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Current rate is {Math.round(configForm.audit_random_sample_rate * 100)}% random sampling.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    High-Risk Anomaly Threshold Score (0 to 100):
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    step="5"
                    value={configForm.high_risk_threshold}
                    onChange={(e) =>
                      setConfigForm({ ...configForm, high_risk_threshold: parseFloat(e.target.value) })
                    }
                    className="w-full bg-surface border border-surface-border rounded-xl px-3 py-2 text-xs text-white"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Projects with risk score at or exceeding this threshold trigger mandatory field audits.
                  </p>
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400">
                    Last updated:{' '}
                    {auditConfig?.updated_at ? new Date(auditConfig.updated_at).toLocaleString() : 'System Default'}
                  </span>
                  <button
                    type="submit"
                    disabled={configSaving}
                    className="btn-primary text-xs px-5 py-2 font-bold"
                  >
                    {configSaving ? 'Saving…' : 'Save Configuration'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {isAdmin && activeTab === 'DISPUTES_ADMIN' && (
            <div className="glass-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🏛️</span> Platform Dispute Resolution Center
                  </h3>
                  <p className="text-xs text-slate-400">
                    Review and resolve NGO disputes challenging adverse audit decisions.
                  </p>
                </div>
                <span className="badge-purple text-xs">{allDisputes.length} Disputes</span>
              </div>

              {allDisputes.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  Zero active disputes lodged by NGOs across the platform.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-surface-border text-slate-400 uppercase text-[10px]">
                        <th className="py-2.5 px-3">Project & NGO</th>
                        <th className="py-2.5 px-3">Reason For Dispute</th>
                        <th className="py-2.5 px-3">Lodged By</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border/50">
                      {allDisputes.map((disp) => (
                        <tr key={disp.id} className="hover:bg-surface/50">
                          <td className="py-3 px-3">
                            <div className="font-semibold text-white">{disp.project_title || disp.project_code}</div>
                            <div className="text-[10px] text-brand-300">{disp.ngo_name}</div>
                          </td>
                          <td className="py-3 px-3 text-slate-300 max-w-sm truncate">{disp.reason}</td>
                          <td className="py-3 px-3 font-mono text-[10px] text-slate-400">
                            {disp.raised_by_email || disp.raised_by_id.slice(0, 8)}
                          </td>
                          <td className="py-3 px-3">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                              disp.status === 'RESOLVED'
                                ? 'bg-emerald-950 text-emerald-300'
                                : 'bg-purple-950 text-purple-300'
                            }`}>
                              {disp.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right">
                            {disp.status !== 'RESOLVED' ? (
                              <button
                                onClick={() => setResolvingDispute(disp)}
                                className="px-3 py-1 rounded-lg bg-brand-950 text-brand-300 border border-brand-700 hover:bg-brand-900 text-xs font-semibold"
                              >
                                Resolve Dispute
                              </button>
                            ) : (
                              <span className="text-[10px] text-slate-500 italic">Concluded</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {isAdmin && activeTab === 'STATS' && stats && (
            <div className="space-y-6">
              {/* Stat Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-surface border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">Total Volume</div>
                  <div className="text-xl font-extrabold text-emerald-400 font-mono mt-1">
                    ₹{stats.total_funding_volume.toLocaleString('en-IN')}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Across all platform projects</div>
                </div>

                <div className="p-4 rounded-xl bg-surface border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">Avg Transparency</div>
                  <div className="text-xl font-extrabold text-brand-400 font-mono mt-1">
                    {stats.avg_transparency_score}/100
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Weighted integrity index</div>
                </div>

                <div className="p-4 rounded-xl bg-surface border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">NGO Portfolio</div>
                  <div className="text-xl font-extrabold text-white font-mono mt-1">
                    {stats.ngos['TOTAL'] || 0}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {stats.ngos['VERIFIED'] || 0} Verified • {stats.ngos['PENDING'] || 0} Pending
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-surface border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">Audits Concluded</div>
                  <div className="text-xl font-extrabold text-white font-mono mt-1">
                    {stats.audits['CONCLUDED'] || 0}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {stats.audits['TOTAL'] || 0} Total Cases Enrolled
                  </div>
                </div>
              </div>

              {/* Breakdown Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-4 space-y-2">
                  <div className="text-xs font-bold text-white">Projects by Status</div>
                  <div className="space-y-1 text-xs">
                    {Object.entries(stats.projects).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between p-2 rounded bg-surface/70 border border-surface-border">
                        <span className="font-mono text-slate-300">{k}</span>
                        <span className="font-bold text-white font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="glass-card p-4 space-y-2">
                  <div className="text-xs font-bold text-white">Audits by Status</div>
                  <div className="space-y-1 text-xs">
                    {Object.entries(stats.audits).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between p-2 rounded bg-surface/70 border border-surface-border">
                        <span className="font-mono text-slate-300">{k}</span>
                        <span className="font-bold text-white font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── AUDIT REVIEW DOSSIER MODAL ── */}
      {reviewAuditId && (
        <AuditReviewModal
          auditId={reviewAuditId}
          isOpen={Boolean(reviewAuditId)}
          onClose={() => setReviewAuditId(null)}
          onDecisionSubmitted={() => {
            loadDashboardData()
          }}
        />
      )}

      {/* ── ADMIN REJECT NGO MODAL ── */}
      {rejectingNgoId && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-surface-dark border border-surface-border rounded-2xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-sm font-bold text-rose-400">Reject NGO Application</h3>
            <p className="text-xs text-slate-400">
              Provide an administrative reason explaining why this application was rejected.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection (e.g., missing certification, invalid registration number)…"
              rows={3}
              className="w-full bg-surface border border-surface-border rounded-xl p-3 text-xs text-white"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setRejectingNgoId(null)
                  setRejectReason('')
                }}
                className="px-3 py-1.5 rounded-lg bg-surface text-slate-400 hover:text-white text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleRejectNgo}
                className="px-4 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-bold hover:bg-rose-500"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── ADMIN RESOLVE DISPUTE MODAL ── */}
      {resolvingDispute && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <form
            onSubmit={handleResolveDispute}
            className="bg-surface-dark border border-surface-border rounded-2xl p-6 max-w-lg w-full space-y-4"
          >
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>🏛️</span> Resolve Dispute: {resolvingDispute.project_code}
            </h3>
            <div className="p-3 rounded-xl bg-surface text-xs space-y-1">
              <div className="text-[10px] text-slate-400">NGO Claim Reason:</div>
              <p className="text-slate-200">{resolvingDispute.reason}</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Resolution Action:
              </label>
              <select
                value={resolutionAction}
                onChange={(e) => setResolutionAction(e.target.value as 'UPHOLD_DECISION' | 'REVISE_DECISION' | 'SCHEDULE_REAUDIT')}
                className="w-full bg-surface border border-surface-border rounded-xl p-2 text-xs text-white"
              >
                <option value="UPHOLD_DECISION">UPHOLD_DECISION (Confirm original auditor finding)</option>
                <option value="REVISE_DECISION">REVISE_DECISION (Accept NGO clarification & update status)</option>
                <option value="SCHEDULE_REAUDIT">SCHEDULE_REAUDIT (Assign secondary auditor for site re-inspection)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Resolution Findings & Justification:
              </label>
              <textarea
                required
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                rows={3}
                placeholder="Official findings, evidence reviewed, and rationale for this resolution…"
                className="w-full bg-surface border border-surface-border rounded-xl p-3 text-xs text-white"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setResolvingDispute(null)}
                className="px-3 py-1.5 rounded-lg bg-surface text-slate-400 hover:text-white text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary text-xs px-4 py-2 font-bold"
              >
                Submit Dispute Resolution
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

// ── SUB-COMPONENT: Reusable Queue Table ──
interface QueueTableProps {
  title: string
  subtitle: string
  items: AuditSummary[]
  onReview: (auditId: string) => void
}

function QueueTable({ title, subtitle, items, onReview }: QueueTableProps) {
  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">{title}</h3>
          <p className="text-xs text-slate-400">{subtitle}</p>
        </div>
        <span className="font-mono text-xs text-slate-400">{items.length} Cases</span>
      </div>

      {items.length === 0 ? (
        <div className="py-12 text-center text-slate-400 text-xs">
          No projects currently in this operational queue.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-surface-border text-slate-400 uppercase text-[10px]">
                <th className="py-2.5 px-3">Project</th>
                <th className="py-2.5 px-3">NGO</th>
                <th className="py-2.5 px-3">Budget</th>
                <th className="py-2.5 px-3">Audit Trigger</th>
                <th className="py-2.5 px-3">Risk Level</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-surface/50">
                  <td className="py-3 px-3">
                    <div className="font-semibold text-white">{item.project_title}</div>
                    <div className="font-mono text-[10px] text-slate-400">{item.project_code}</div>
                  </td>
                  <td className="py-3 px-3 text-slate-300">{item.ngo_name || 'Designated NGO'}</td>
                  <td className="py-3 px-3 font-mono font-bold text-white">
                    ₹{(item.target_amount ?? item.total_budget ?? 0).toLocaleString('en-IN')}
                  </td>
                  <td className="py-3 px-3">
                    <span className="badge-blue text-[10px] font-mono">{item.selection_reason}</span>
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                        item.risk_level === 'HIGH' || item.risk_level === 'CRITICAL'
                          ? 'bg-rose-950 text-rose-300'
                          : 'bg-emerald-950 text-emerald-300'
                      }`}
                    >
                      {item.risk_level || 'LOW'} ({item.risk_score ?? 0})
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className="font-mono text-[10px] text-slate-300">{item.status}</span>
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      onClick={() => onReview(item.id)}
                      className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors inline-flex items-center gap-1.5 ${
                        item.risk_level === 'HIGH' || item.risk_level === 'CRITICAL'
                          ? 'bg-rose-700 hover:bg-rose-600 text-white shadow-sm shadow-rose-900/40'
                          : 'bg-brand-600 hover:bg-brand-500 text-white'
                      }`}
                    >
                      {(item.risk_level === 'HIGH' || item.risk_level === 'CRITICAL') && (
                        <span className="text-amber-300 animate-pulse">⚠</span>
                      )}
                      <span>Review Dossier & Flags</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
