import React, { useState, useEffect } from 'react'
import { getAuditDossier, recordAuditDecision } from '../../api/audit'
import { AuditDecisionType, AuditDossier } from '../../types'
import { IntegrityFlagsView } from './IntegrityFlagsView'

interface AuditReviewModalProps {
  auditId: string
  isOpen: boolean
  onClose: () => void
  onDecisionSubmitted?: () => void
}

export default function AuditReviewModal({
  auditId,
  isOpen,
  onClose,
  onDecisionSubmitted,
}: AuditReviewModalProps) {
  const [dossier, setDossier] = useState<AuditDossier | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Decision form
  const [selectedDecision, setSelectedDecision] = useState<AuditDecisionType>('CONFIRMED')
  const [findings, setFindings] = useState<string>('')
  const [notes, setNotes] = useState<string>('')
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && auditId) {
      loadDossier()
    }
  }, [isOpen, auditId])

  async function loadDossier() {
    setLoading(true)
    setError(null)
    try {
      const res = await getAuditDossier(auditId)
      if (res.success && res.data) {
        setDossier(res.data)
      } else {
        setError(res.message || 'Failed to load audit dossier.')
      }
    } catch (err: any) {
      console.error('Error fetching audit dossier:', err)
      setError(err?.response?.data?.detail || 'Failed to fetch comprehensive audit dossier.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmitDecision(e: React.FormEvent) {
    e.preventDefault()
    if (!findings.trim() || findings.trim().length < 5) {
      setError('Auditor findings/reason is strictly required (minimum 5 characters).')
      return
    }

    setSubmitting(true)
    setError(null)
    setActionSuccess(null)

    try {
      const res = await recordAuditDecision(auditId, {
        decision: selectedDecision,
        findings: findings.trim(),
        notes: notes.trim() || undefined,
      })

      if (res.success) {
        setActionSuccess(`Audit decision "${selectedDecision}" recorded immutably. Score has been recalculated.`)
        if (onDecisionSubmitted) {
          onDecisionSubmitted()
        }
        // Refresh dossier to show the new immutable decision and recalculated score
        await loadDossier()
        setFindings('')
        setNotes('')
      } else {
        setError(res.message || 'Failed to record audit decision.')
      }
    } catch (err: any) {
      console.error('Failed to submit audit decision:', err)
      setError(err?.response?.data?.detail || 'Failed to submit audit decision.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!isOpen) return null

  const isFormValid = findings.trim().length >= 5

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4">
      <div className="relative w-full max-w-6xl bg-surface-dark border border-surface-border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-4 bg-surface/90 border-b border-surface-border flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🏛️</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">Independent Audit Dossier</h2>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800">
                  Case {auditId.slice(0, 8)}…
                </span>
              </div>
              <p className="text-xs text-slate-400">
                10-dimension forensic review ledger with immutable decision recording.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-surface text-xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-24 text-center">
              <div className="inline-block animate-spin text-3xl mb-3">⚙️</div>
              <p className="text-sm text-slate-400">Assembling comprehensive audit dossier & telemetry…</p>
            </div>
          ) : error && !dossier ? (
            <div className="p-6 rounded-xl bg-rose-950/40 border border-rose-800/60 text-center space-y-2">
              <div className="text-rose-400 font-bold">Failed to load dossier</div>
              <p className="text-xs text-slate-300">{error}</p>
              <button
                onClick={loadDossier}
                className="px-3 py-1.5 rounded-lg bg-surface border border-surface-border text-xs text-white hover:bg-surface-border"
              >
                Retry
              </button>
            </div>
          ) : dossier ? (
            <>
              {/* Alert Feedback */}
              {actionSuccess && (
                <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-700/60 text-emerald-300 text-xs flex items-center justify-between">
                  <span>✓ {actionSuccess}</span>
                  <button onClick={() => setActionSuccess(null)} className="text-emerald-400 font-bold">✕</button>
                </div>
              )}
              {error && (
                <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-700/60 text-rose-300 text-xs flex items-center justify-between">
                  <span>✕ {error}</span>
                  <button onClick={() => setError(null)} className="text-rose-400 font-bold">✕</button>
                </div>
              )}

              {/* Anti-Manipulation & Integrity Defense Layer */}
              {dossier.integrity_report && (
                <div className="border-b border-surface-border pb-4">
                  <IntegrityFlagsView report={dossier.integrity_report} />
                </div>
              )}

              {/* Top Banner: NGO, Project, Score & Value */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Project & NGO */}
                <div className="p-4 rounded-xl bg-surface/70 border border-surface-border space-y-1 md:col-span-2">
                  <div className="text-[10px] text-slate-400 uppercase font-mono tracking-wider">Project & NGO</div>
                  <div className="text-base font-bold text-white">{dossier.project_title}</div>
                  <div className="text-xs text-slate-300 flex items-center gap-2">
                    <span className="font-semibold text-brand-300">🏢 {dossier.ngo_name}</span>
                    <span>•</span>
                    <span className="font-mono text-slate-400">{dossier.project_code}</span>
                  </div>
                  <div className="flex items-center gap-2 pt-1 text-[11px]">
                    <span className="badge-blue text-[10px]">{dossier.project_category}</span>
                    <span className="badge-purple text-[10px]">{dossier.verification_model}</span>
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-surface border border-surface-border text-slate-300">
                      Status: {dossier.project_status}
                    </span>
                  </div>
                </div>

                {/* 2. Project Value */}
                <div className="p-4 rounded-xl bg-surface/70 border border-surface-border space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase font-mono tracking-wider">Project Value</div>
                  <div className="text-xl font-extrabold text-emerald-400 font-mono">
                    ₹{dossier.target_amount.toLocaleString('en-IN')}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Total Budget: <span className="text-slate-200">₹{dossier.total_budget.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Beneficiaries: <strong className="text-white">{dossier.expected_beneficiaries}</strong>
                  </div>
                </div>

                {/* 3. Current Evidence Score (Strictly Read-Only) */}
                <div className="p-4 rounded-xl bg-surface/70 border border-surface-border space-y-1">
                  <div className="text-[10px] text-slate-400 uppercase font-mono tracking-wider flex items-center justify-between">
                    <span>Evidence Score</span>
                    <span className="text-[9px] text-amber-300">Read-Only</span>
                  </div>
                  <div className="text-2xl font-black text-brand-400 font-mono">
                    {dossier.evidence_score !== null && dossier.evidence_score !== undefined
                      ? `${dossier.evidence_score}/100`
                      : 'N/A'}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Status: <strong className="text-slate-200">{dossier.evidence_score_status || 'EVALUATED'}</strong>
                  </div>
                  <div className="text-[9px] text-slate-500 italic">
                    Calculated automatically by backend engine
                  </div>
                </div>
              </div>

              {/* Claim & Location Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Claim */}
                <div className="p-4 rounded-xl bg-surface/50 border border-surface-border space-y-1.5">
                  <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <span>🎯</span> Claimed Objective & Scope
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {dossier.project_description || 'No objective description provided.'}
                  </p>
                  <div className="text-[11px] text-slate-400 pt-2 border-t border-surface-border/50">
                    Audit Trigger Reason:{' '}
                    <strong className="text-brand-300 font-mono">{dossier.selection_reason}</strong>
                  </div>
                </div>

                {/* Location & Geofence */}
                <div className="p-4 rounded-xl bg-surface/50 border border-surface-border space-y-1.5">
                  <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <span>📍</span> Verified Location & Geofencing
                  </div>
                  <div className="text-xs text-white font-medium">
                    {dossier.location_name || 'Designated Project Zone'}
                  </div>
                  <div className="font-mono text-xs text-slate-400">
                    Lat: {dossier.latitude ?? 'N/A'}, Lng: {dossier.longitude ?? 'N/A'}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Permitted Geofence Radius: <strong className="text-slate-200">{dossier.geofence_radius} meters</strong>
                  </div>
                </div>
              </div>

              {/* 10-Point Verification Results & Risk Narrative */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Verification Engine Results */}
                <div className="p-4 rounded-xl bg-surface/60 border border-surface-border space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>✓</span> 10-Engine Automated Checks
                    </div>
                    {dossier.verification_report && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        {dossier.verification_report.overall_quality}
                      </span>
                    )}
                  </div>

                  {dossier.verification_report?.individual_checks && dossier.verification_report.individual_checks.length > 0 ? (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                      {dossier.verification_report.individual_checks.map((chk: any, idx: number) => (
                        <div key={idx} className="p-2 rounded bg-surface border border-surface-border text-xs flex items-center justify-between">
                          <span className="text-slate-200">{chk.check_name.replace(/([A-Z])/g, ' $1').trim()}</span>
                          <span className={`font-mono text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                            ['MATCH', 'VALID', 'CLEAN', 'VERIFIED'].includes(chk.status)
                              ? 'bg-emerald-950 text-emerald-300'
                              : 'bg-amber-950 text-amber-300'
                          }`}>
                            {chk.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400 py-3 text-center">
                      Automated engine check results compiled. All baseline integrity checks valid.
                    </div>
                  )}
                </div>

                {/* Risk Reasons & Indicators */}
                <div className="p-4 rounded-xl bg-surface/60 border border-surface-border space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>⚠️</span> Multi-Factor Risk Assessment
                    </div>
                    {dossier.risk_assessment && (
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                        dossier.risk_assessment.risk_level === 'HIGH' || dossier.risk_assessment.risk_level === 'CRITICAL'
                          ? 'bg-rose-950 text-rose-300 border-rose-800'
                          : 'bg-emerald-950 text-emerald-300 border-emerald-800'
                      }`}>
                        {dossier.risk_assessment.risk_level} (Score: {dossier.risk_assessment.risk_score})
                      </span>
                    )}
                  </div>

                  {dossier.risk_assessment?.narrative_reasons && dossier.risk_assessment.narrative_reasons.length > 0 ? (
                    <ul className="space-y-1 text-xs text-slate-300 list-disc list-inside max-h-48 overflow-y-auto">
                      {dossier.risk_assessment.narrative_reasons.map((r: string, idx: number) => (
                        <li key={idx} className="text-amber-300">{r}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-slate-400 py-3 text-center">
                      No active high-risk fraud signals detected. Standard operational profile.
                    </div>
                  )}
                </div>
              </div>

              {/* Evidence Timeline & Financial Documents */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Evidence Timeline */}
                <div className="p-4 rounded-xl bg-surface/60 border border-surface-border space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>📸</span> Evidence Submissions ({dossier.evidence_timeline.length})
                    </div>
                  </div>

                  {dossier.evidence_timeline.length === 0 ? (
                    <div className="text-xs text-slate-400 py-4 text-center">No media evidence submitted yet.</div>
                  ) : (
                    <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                      {dossier.evidence_timeline.map((ev: any) => (
                        <div key={ev.id} className="p-2.5 rounded bg-surface border border-surface-border text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-white">{ev.title}</span>
                            <span className="text-[10px] font-mono text-emerald-400 font-semibold">{ev.verification_status}</span>
                          </div>
                          <div className="text-[10px] font-mono text-slate-400 truncate">
                            SHA-256: {ev.file_hash_sha256}
                          </div>
                          <div className="text-[10px] text-slate-400 flex items-center justify-between">
                            <span>GPS: {ev.latitude?.toFixed(4)}, {ev.longitude?.toFixed(4)}</span>
                            <span>{new Date(ev.effective_timestamp || ev.uploaded_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Financial Documents & Consistency */}
                <div className="p-4 rounded-xl bg-surface/60 border border-surface-border space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>🧾</span> Financial Documents ({dossier.financial_evidence.length})
                    </div>
                    {dossier.financial_consistency && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800">
                        {dossier.financial_consistency.status}
                      </span>
                    )}
                  </div>

                  {dossier.financial_evidence.length === 0 ? (
                    <div className="text-xs text-slate-400 py-4 text-center">No invoices/bills uploaded yet.</div>
                  ) : (
                    <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                      {dossier.financial_evidence.map((fin: any) => (
                        <div key={fin.id} className="p-2.5 rounded bg-surface border border-surface-border text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-white">{fin.vendor_name || 'Vendor Document'}</span>
                            <span className="font-mono text-emerald-400 font-bold">
                              ₹{(fin.extracted_amount || fin.claimed_amount || 0).toLocaleString('en-IN')}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400 flex items-center justify-between">
                            <span>Invoice #{fin.invoice_number || 'N/A'}</span>
                            <span className="font-mono text-slate-500">{fin.consistency_status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Decisions History */}
              {dossier.decisions_history && dossier.decisions_history.length > 0 && (
                <div className="p-4 rounded-xl bg-surface/60 border border-surface-border space-y-2">
                  <div className="text-xs font-bold text-white">Prior Auditor Decisions History</div>
                  <div className="space-y-2">
                    {dossier.decisions_history.map((dec) => (
                      <div key={dec.id} className="p-2.5 rounded bg-surface border border-surface-border text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-brand-300">{dec.decision}</span>
                          <span className="text-[10px] text-slate-400">{new Date(dec.decided_at).toLocaleString()}</span>
                        </div>
                        <p className="text-slate-300 text-[11px]">{dec.findings}</p>
                        {dec.is_superseded && (
                          <div className="text-[10px] text-amber-400 italic">Superseded by subsequent review</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ── AUDITOR DECISION SUBMISSION FORM ── */}
              <div className="p-6 rounded-2xl bg-surface border-2 border-brand-700/50 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>⚖️</span> Record Authoritative Auditor Decision
                    </h3>
                    <p className="text-xs text-slate-400">
                      Decisions are immutable. Submitting a decision triggers automated backend score recalculation.
                    </p>
                  </div>
                  <div className="text-[11px] px-2.5 py-1 rounded-lg bg-brand-950/80 border border-brand-700/60 text-brand-300 font-mono">
                    Score Overwrite: Blocked (System Recalculates)
                  </div>
                </div>

                <form onSubmit={handleSubmitDecision} className="space-y-4">
                  {/* Action Selection Buttons */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-2">
                      Decision Action:
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedDecision('CONFIRMED')}
                        className={`p-3 rounded-xl border text-xs font-bold transition-all flex flex-col items-center gap-1 ${
                          selectedDecision === 'CONFIRMED'
                            ? 'bg-emerald-950 border-emerald-500 text-emerald-200 ring-2 ring-emerald-500/30'
                            : 'bg-surface-dark border-surface-border text-slate-400 hover:text-white'
                        }`}
                      >
                        <span className="text-base">✓</span>
                        CONFIRM
                        <span className="text-[9px] font-normal opacity-80">Full delivery verified</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setSelectedDecision('PARTIALLY_CONFIRMED')}
                        className={`p-3 rounded-xl border text-xs font-bold transition-all flex flex-col items-center gap-1 ${
                          selectedDecision === 'PARTIALLY_CONFIRMED'
                            ? 'bg-amber-950 border-amber-500 text-amber-200 ring-2 ring-amber-500/30'
                            : 'bg-surface-dark border-surface-border text-slate-400 hover:text-white'
                        }`}
                      >
                        <span className="text-base">⚠️</span>
                        PARTIALLY CONFIRM
                        <span className="text-[9px] font-normal opacity-80">Conditional approval</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setSelectedDecision('REJECTED')}
                        className={`p-3 rounded-xl border text-xs font-bold transition-all flex flex-col items-center gap-1 ${
                          selectedDecision === 'REJECTED'
                            ? 'bg-rose-950 border-rose-500 text-rose-200 ring-2 ring-rose-500/30'
                            : 'bg-surface-dark border-surface-border text-slate-400 hover:text-white'
                        }`}
                      >
                        <span className="text-base">✕</span>
                        REJECT
                        <span className="text-[9px] font-normal opacity-80">Evidence insufficient</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setSelectedDecision('DISCREPANCY')}
                        className={`p-3 rounded-xl border text-xs font-bold transition-all flex flex-col items-center gap-1 ${
                          selectedDecision === 'DISCREPANCY'
                            ? 'bg-purple-950 border-purple-500 text-purple-200 ring-2 ring-purple-500/30'
                            : 'bg-surface-dark border-surface-border text-slate-400 hover:text-white'
                        }`}
                      >
                        <span className="text-base">🚩</span>
                        FLAG DISCREPANCY
                        <span className="text-[9px] font-normal opacity-80">Mark project disputed</span>
                      </button>
                    </div>
                  </div>

                  {/* Mandatory Findings Input */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1 flex items-center justify-between">
                      <span>Auditor Findings & Justification (Mandatory):</span>
                      <span className={`text-[10px] ${findings.trim().length >= 5 ? 'text-emerald-400' : 'text-rose-400 font-mono'}`}>
                        {findings.trim().length >= 5 ? '✓ Valid' : 'Min 5 chars required'}
                      </span>
                    </label>
                    <textarea
                      required
                      value={findings}
                      onChange={(e) => setFindings(e.target.value)}
                      rows={3}
                      placeholder="Detailed physical findings, geo-validation notes, vendor confirmation, or reason for discrepancy…"
                      className="w-full bg-surface-dark border border-surface-border rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                    />
                  </div>

                  {/* Optional Notes */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Internal Advisory Notes (Optional):
                    </label>
                    <input
                      type="text"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="References, council signoffs, or follow-up suggestions…"
                      className="w-full bg-surface-dark border border-surface-border rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                    />
                  </div>

                  {/* Submit Button */}
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[11px] text-slate-400">
                      Cannot be undone. Will create an immutable SHA-linked review entry.
                    </span>
                    <button
                      type="submit"
                      disabled={!isFormValid || submitting}
                      className="btn-primary text-xs px-6 py-2.5 font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {submitting ? 'Recording Decision…' : `Submit ${selectedDecision} Decision`}
                    </button>
                  </div>
                </form>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
