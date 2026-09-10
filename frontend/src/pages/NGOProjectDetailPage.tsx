import { useState, useEffect, type FormEvent } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import { projectsApi } from '@/api/projects'
import { evidenceApi, type UploadEvidencePayload } from '@/api/evidence'
import { financialApi, type UploadFinancialPayload } from '@/api/financial'
import { getPublicVerificationSummary } from '@/api/public'
import { getProjectScore } from '@/api/scores'
import LiveCameraEvidenceCapture, { type CapturedEvidenceData } from '@/components/projects/LiveCameraEvidenceCapture'
import type {
  EvidenceTimelineResponse,
  EvidenceType,
  FinancialConsistencyReport,
  FinancialDocumentType,
  FinancialEvidence,
  ProjectAuditItem,
  ProjectDetail,
  ProjectDisputeItem,
  ProjectRiskReport,
  ProjectScoreResponse,
  ProjectStatus,
  ProjectVerificationSummary,
  VerificationReport,
} from '@/types'

const LIFECYCLE_STEPS: { key: string; label: string; desc: string; icon: string }[] = [
  { key: 'CREATED', label: '1. Created', desc: 'Project registered & site geofenced', icon: '📝' },
  { key: 'FUNDING', label: '2. Funding', desc: 'Budget allocated & donor campaign', icon: '💰' },
  { key: 'EVIDENCE_COLLECTION', label: '3. Evidence Collection', desc: 'Baseline & milestone photos', icon: '📷' },
  { key: 'UNDER_VERIFICATION', label: '4. Verification', desc: '10-engine automated scan', icon: '⚡' },
  { key: 'AUDIT', label: '5. Audit (If Required)', desc: 'Independent physical inspection', icon: '🔍' },
  { key: 'FINAL', label: '6. Final Status', desc: 'Authoritative outcome & score', icon: '🏆' },
]

function getStepIndex(status: ProjectStatus, hasAudit: boolean): number {
  switch (status) {
    case 'CREATED':
      return 0
    case 'FUNDING':
      return 1
    case 'EVIDENCE_COLLECTION':
      return 2
    case 'UNDER_VERIFICATION':
      return 3
    case 'DISPUTED':
      return 4
    case 'VERIFIED':
    case 'PARTIALLY_VERIFIED':
      return hasAudit ? 5 : 5
    default:
      return 2
  }
}

export default function NGOProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [score, setScore] = useState<ProjectScoreResponse | null>(null)
  const [verificationReport, setVerificationReport] = useState<VerificationReport | null>(null)
  const [verificationSummary, setVerificationSummary] = useState<ProjectVerificationSummary | null>(null)
  const [riskReport, setRiskReport] = useState<ProjectRiskReport | null>(null)
  const [audits, setAudits] = useState<ProjectAuditItem[]>([])
  const [disputes, setDisputes] = useState<ProjectDisputeItem[]>([])
  const [timeline, setTimeline] = useState<EvidenceTimelineResponse | null>(null)
  const [financials, setFinancials] = useState<FinancialEvidence[]>([])
  const [consistencyReport, setConsistencyReport] = useState<FinancialConsistencyReport | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [runningVerification, setRunningVerification] = useState(false)

  // Modals
  const [showEvidenceModal, setShowEvidenceModal] = useState(false)
  const [showFinancialModal, setShowFinancialModal] = useState(false)
  const [showDisputeModal, setShowDisputeModal] = useState(false)
  const [submittingEvidence, setSubmittingEvidence] = useState(false)
  const [submittingFinancial, setSubmittingFinancial] = useState(false)
  const [submittingDispute, setSubmittingDispute] = useState(false)

  // Evidence Form
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null)
  const [evidenceTitle, setEvidenceTitle] = useState('')
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('PROGRESS')
  const [evidenceDesc, setEvidenceDesc] = useState('')
  const [capturedAt, setCapturedAt] = useState('')
  const [latitude, setLatitude] = useState<number | undefined>(undefined)
  const [longitude, setLongitude] = useState<number | undefined>(undefined)
  const [gpsAccuracy, setGpsAccuracy] = useState<number | undefined>(undefined)
  const [supersedesId, setSupersedesId] = useState('')
  const [capturedPreviewUrl, setCapturedPreviewUrl] = useState<string | null>(null)
  const [capturedLocationDisplay, setCapturedLocationDisplay] = useState<string>('')
  const [capturedDateTimeDisplay, setCapturedDateTimeDisplay] = useState<string>('')

  // Financial Form
  const [financialFile, setFinancialFile] = useState<File | null>(null)
  const [claimedAmount, setClaimedAmount] = useState('')
  const [docType, setDocType] = useState<FinancialDocumentType>('INVOICE')
  const [vendorName, setVendorName] = useState('')
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [docDate, setDocDate] = useState('')
  const [financialDesc, setFinancialDesc] = useState('')

  // Dispute Form
  const [disputeReason, setDisputeReason] = useState('')

  useEffect(() => {
    if (!id) return
    loadAllProjectData()
  }, [id])

  async function loadAllProjectData() {
    if (!id) return
    setLoading(true)
    setError(null)

    try {
      const projRes = await projectsApi.getById(id)
      if (projRes.data.success && projRes.data.data) {
        setProject(projRes.data.data)
      } else {
        setError('Project not found.')
        setLoading(false)
        return
      }

      // Parallel fetch supporting modules
      await Promise.allSettled([
        getProjectScore(id).then((r) => r.data && setScore(r.data)),
        projectsApi.getVerification(id).then((r) => r.data.data && setVerificationReport(r.data.data)),
        getPublicVerificationSummary(id).then((r) => r.data && setVerificationSummary(r.data)),
        projectsApi.getRisk(id).then((r) => r.data.data && setRiskReport(r.data.data)),
        projectsApi.getAudits(id).then((r) => r.data.data && setAudits(r.data.data)),
        projectsApi.getDisputes(id).then((r) => r.data.data && setDisputes(r.data.data)),
        evidenceApi.getTimeline(id).then((r) => r.data.data && setTimeline(r.data.data)),
        financialApi.list(id).then((r) => {
          if (r.data.data) {
            setFinancials(r.data.data.items)
            setConsistencyReport(r.data.data.consistency_report)
          }
        }),
      ])
    } catch (err: any) {
      console.error('Failed to load project dossier:', err)
      setError('Error loading project management details.')
    } finally {
      setLoading(false)
    }
  }

  // Trigger verification engine
  async function handleRunVerification() {
    if (!id) return
    setRunningVerification(true)
    try {
      const res = await projectsApi.triggerVerification(id)
      if (res.data.success) {
        setActionMessage('10-point Evidence Verification Engine completed successfully!')
        await loadAllProjectData()
      }
    } catch {
      setActionMessage('Failed to run verification engine. Check server connection.')
    } finally {
      setRunningVerification(false)
    }
  }

  // Handle Evidence upload
  async function handleUploadEvidence(e: FormEvent) {
    e.preventDefault()
    if (!id || !evidenceFile || !evidenceTitle.trim()) return

    setSubmittingEvidence(true)
    try {
      const payload: UploadEvidencePayload = {
        file: evidenceFile,
        title: evidenceTitle.trim(),
        evidence_type: evidenceType,
        description: evidenceDesc.trim() || undefined,
        captured_at: capturedAt ? new Date(capturedAt).toISOString() : undefined,
        latitude,
        longitude,
        gps_accuracy: gpsAccuracy,
        supersedes_id: supersedesId.trim() || undefined,
      }

      const res = await evidenceApi.upload(id, payload)
      if (res.data.success) {
        setActionMessage('Evidence uploaded and fingerprinted with SHA-256.')
        setShowEvidenceModal(false)
        resetEvidenceForm()
        await loadAllProjectData()
      }
    } catch (err: any) {
      setActionMessage(err.response?.data?.message || 'Failed to upload evidence.')
    } finally {
      setSubmittingEvidence(false)
    }
  }

  // Handle Financial upload
  async function handleUploadFinancial(e: FormEvent) {
    e.preventDefault()
    if (!id || !financialFile || !claimedAmount) return

    setSubmittingFinancial(true)
    try {
      const payload: UploadFinancialPayload = {
        file: financialFile,
        claimed_amount: parseFloat(claimedAmount),
        document_type: docType,
        vendor_name: vendorName.trim() || undefined,
        invoice_number: invoiceNumber.trim() || undefined,
        document_date: docDate ? new Date(docDate).toISOString() : undefined,
        description: financialDesc.trim() || undefined,
      }

      const res = await financialApi.upload(id, payload)
      if (res.data.success) {
        setActionMessage('Financial invoice registered & submitted to OCR extractor.')
        setShowFinancialModal(false)
        resetFinancialForm()
        await loadAllProjectData()
      }
    } catch (err: any) {
      setActionMessage(err.response?.data?.message || 'Failed to upload financial invoice.')
    } finally {
      setSubmittingFinancial(false)
    }
  }

  // Handle Lodge Dispute
  async function handleLodgeDispute(e: FormEvent) {
    e.preventDefault()
    if (!id || !disputeReason.trim()) return

    setSubmittingDispute(true)
    try {
      const res = await projectsApi.raiseDispute(id, disputeReason.trim())
      if (res.data.success) {
        setActionMessage('Formal dispute lodged successfully. Project status updated to DISPUTED.')
        setShowDisputeModal(false)
        setDisputeReason('')
        await loadAllProjectData()
      }
    } catch (err: any) {
      setActionMessage(err.response?.data?.message || 'Failed to submit dispute.')
    } finally {
      setSubmittingDispute(false)
    }
  }

  function resetEvidenceForm() {
    setEvidenceFile(null)
    setEvidenceTitle('')
    setEvidenceType('PROGRESS')
    setEvidenceDesc('')
    setCapturedAt('')
    setLatitude(undefined)
    setLongitude(undefined)
    setGpsAccuracy(undefined)
    setSupersedesId('')
    if (capturedPreviewUrl) {
      URL.revokeObjectURL(capturedPreviewUrl)
    }
    setCapturedPreviewUrl(null)
    setCapturedLocationDisplay('')
    setCapturedDateTimeDisplay('')
  }

  async function handleEvidenceCaptured(data: CapturedEvidenceData) {
    if (!id) return
    setEvidenceFile(data.file)
    setCapturedPreviewUrl(data.previewUrl)
    setLatitude(data.latitude)
    setLongitude(data.longitude)
    setGpsAccuracy(data.accuracy)
    setCapturedAt(data.capturedAt)
    setCapturedLocationDisplay(data.locationDisplay)
    setCapturedDateTimeDisplay(`${data.formattedDate} · ${data.formattedTime}`)

    const finalTitle =
      evidenceTitle.trim() ||
      `[${evidenceType}] In-Situ Verification Evidence - ${data.formattedDate}`

    setSubmittingEvidence(true)
    try {
      const payload: UploadEvidencePayload = {
        file: data.file,
        title: finalTitle,
        evidence_type: evidenceType,
        description: evidenceDesc.trim() || `Direct hardware camera capture at ${data.locationDisplay}`,
        captured_at: data.capturedAt,
        latitude: data.latitude,
        longitude: data.longitude,
        gps_accuracy: data.accuracy,
        supersedes_id: supersedesId.trim() || undefined,
        metadata_summary: {
          capture_method: 'IN_APP_HARDWARE_CAMERA',
          formatted_time: data.formattedTime,
          formatted_date: data.formattedDate,
          location_label: data.locationDisplay,
          tamper_evident_overlay_stamped: true,
        },
      }

      const res = await evidenceApi.upload(id, payload)
      if (res.data.success) {
        setActionMessage(
          `Photo evidence "${finalTitle}" successfully watermarked with GPS & timestamp, persisted, and scored!`
        )
        setShowEvidenceModal(false)
        resetEvidenceForm()
        await loadAllProjectData()
      }
    } catch (err: any) {
      setActionMessage(
        err.response?.data?.error ||
          err.response?.data?.message ||
          'Failed to upload evidence to database. Please check your connection.'
      )
    } finally {
      setSubmittingEvidence(false)
    }
  }

  function resetFinancialForm() {
    setFinancialFile(null)
    setClaimedAmount('')
    setDocType('INVOICE')
    setVendorName('')
    setInvoiceNumber('')
    setDocDate('')
    setFinancialDesc('')
  }

  if (loading) {
    return (
      <div className="flex h-screen bg-surface items-center justify-center text-slate-400">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm">Loading Project Management Dossier...</p>
        </div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="flex h-screen bg-surface">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Navbar />
          <div className="p-8 max-w-md mx-auto text-center my-auto">
            <span className="text-4xl mb-3 block">⚠️</span>
            <h2 className="text-xl font-bold text-white mb-2">{error || 'Project Not Found'}</h2>
            <p className="text-slate-400 text-xs mb-6">Unable to access the requested project dossier.</p>
            <Link to="/projects" className="btn-primary text-xs px-6 py-2.5">
              ← Return to Project Portfolio
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Compute Missing Evidence Items
  const timelineItems = timeline?.timeline || []
  const hasBefore = timelineItems.some((i) => i.evidence_type === 'BEFORE')
  const hasProgress = timelineItems.some((i) => i.evidence_type === 'PROGRESS')
  const hasCompletion = timelineItems.some((i) => i.evidence_type === 'COMPLETION')
  const hasFinancial = financials.length > 0

  const missingItems: string[] = []
  if (!hasBefore) missingItems.push('Baseline Photo (BEFORE stage)')
  if (!hasProgress) missingItems.push('Progress Milestone Evidence (PROGRESS stage)')
  if (!hasCompletion) missingItems.push('Completion Proof (COMPLETION stage)')
  if (!hasFinancial) missingItems.push('Financial Invoices & Vendor Receipts')

  const currentStep = getStepIndex(project.status, audits.length > 0)
  const isOwner = user?.role === 'ADMIN' || (user?.role === 'NGO' && user?.ngo_id === project.ngo_id)

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />

        <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-6">
          {/* ── BREADCRUMB & READ-ONLY ENFORCEMENT CALLOUT ────────────── */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-slate-400">
              <Link to="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
              <span>/</span>
              <Link to="/projects" className="hover:text-white transition-colors">Projects</Link>
              <span>/</span>
              <span className="text-slate-200 font-mono font-medium truncate">{project.project_code}</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 font-mono text-[11px]">
                🛡️ Deterministic Score Engine Active
              </span>
              <Link
                to={`/public/projects/${project.id}`}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary text-xs px-3 py-1 flex items-center gap-1"
              >
                <span>🌐</span> Public Donor View
              </Link>
            </div>
          </div>

          {actionMessage && (
            <div className="p-4 rounded-xl bg-brand-950/80 border border-brand-700/60 text-brand-300 text-xs flex items-center justify-between shadow-lg">
              <span>{actionMessage}</span>
              <button onClick={() => setActionMessage(null)} className="text-xs text-brand-400 hover:text-white font-bold ml-4">
                ✕
              </button>
            </div>
          )}

          {/* ── PROJECT HEADER & HERO ─────────────────────────────────── */}
          <div className="glass-card p-6 border-l-4 border-brand-500 relative overflow-hidden">
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
              <div className="space-y-3 flex-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-xs uppercase font-mono px-2.5 py-0.5 rounded bg-surface border border-surface-border text-slate-300">
                    {project.category.replace(/_/g, ' ')}
                  </span>
                  <span
                    className={`text-xs font-bold px-3 py-0.5 rounded-full uppercase ${
                      project.status === 'VERIFIED'
                        ? 'badge-green'
                        : project.status === 'PARTIALLY_VERIFIED'
                        ? 'badge-yellow'
                        : project.status === 'DISPUTED'
                        ? 'badge-red'
                        : 'badge-blue'
                    }`}
                  >
                    {project.status.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    ID: {project.project_code}
                  </span>
                </div>

                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {project.title}
                </h1>

                {project.description && (
                  <p className="text-slate-300 text-xs leading-relaxed max-w-3xl">
                    {project.description}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 pt-1">
                  {project.location_name && (
                    <span className="flex items-center gap-1">
                      <span>📍</span> Site: {project.location_name}
                    </span>
                  )}
                  {project.geofence_radius && (
                    <span className="flex items-center gap-1 font-mono text-[11px]">
                      Radius: {project.geofence_radius}m
                    </span>
                  )}
                  {project.start_date && (
                    <span className="flex items-center gap-1">
                      <span>📅</span> Start: {new Date(project.start_date).toLocaleDateString()}
                    </span>
                  )}
                  {project.expected_completion_date && (
                    <span className="flex items-center gap-1">
                      <span>🏁</span> Target: {new Date(project.expected_completion_date).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons & Score Box */}
              <div className="flex flex-col sm:flex-row lg:flex-col items-end gap-3 min-w-[200px]">
                <div className="bg-surface/90 border border-brand-500/40 rounded-2xl p-4 text-center w-full shadow-lg">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Evidence Score</div>
                  <div className="text-4xl font-extrabold text-white font-mono my-1">
                    {score?.final_score !== undefined
                      ? score.final_score.toFixed(0)
                      : project.evidence_score !== undefined && project.evidence_score !== null
                      ? project.evidence_score.toFixed(0)
                      : '—'}
                    <span className="text-xs text-slate-500 font-normal">/100</span>
                  </div>
                  <div className="text-[10px] font-bold text-emerald-400 uppercase">
                    {score?.status?.replace(/_/g, ' ') || 'CALCULATED BY ENGINE'}
                  </div>
                </div>

                {isOwner && (
                  <div className="flex flex-col gap-2 w-full">
                    <button
                      onClick={() => setShowEvidenceModal(true)}
                      className="btn-primary text-xs py-2.5 w-full flex items-center justify-center gap-1.5 shadow-md shadow-brand-500/20"
                    >
                      <span>📷</span> Submit Milestone Evidence
                    </button>
                    <button
                      onClick={() => setShowFinancialModal(true)}
                      className="btn-secondary text-xs py-2.5 w-full flex items-center justify-center gap-1.5"
                    >
                      <span>🧾</span> Submit Financial Document
                    </button>
                    <button
                      onClick={handleRunVerification}
                      disabled={runningVerification}
                      className="px-4 py-2 rounded-xl bg-indigo-950/70 border border-indigo-700/50 hover:bg-indigo-900 text-indigo-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      <span>⚡</span> {runningVerification ? 'Running 10-Engine Scan…' : 'Run Verification Engine'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── COMPLETE LIFECYCLE STEPPER (VISUAL PIPELINE) ─────────── */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <span>🔄</span> Complete Project Lifecycle Progression
            </h3>

            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {LIFECYCLE_STEPS.map((step, idx) => {
                const isPassed = idx < currentStep
                const isCurrent = idx === currentStep
                return (
                  <div
                    key={step.key}
                    className={`p-3.5 rounded-xl border transition-all ${
                      isCurrent
                        ? 'bg-brand-950/80 border-brand-500 shadow-md shadow-brand-500/20 ring-1 ring-brand-400'
                        : isPassed
                        ? 'bg-emerald-950/30 border-emerald-700/50'
                        : 'bg-surface/50 border-surface-border opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-lg">{step.icon}</span>
                      {isPassed ? (
                        <span className="w-4 h-4 rounded-full bg-emerald-500 text-black text-[10px] font-bold flex items-center justify-center">
                          ✓
                        </span>
                      ) : isCurrent ? (
                        <span className="w-2.5 h-2.5 rounded-full bg-brand-400 animate-ping" />
                      ) : null}
                    </div>
                    <div className={`text-xs font-bold leading-tight ${isCurrent ? 'text-brand-300' : isPassed ? 'text-white' : 'text-slate-400'}`}>
                      {step.label}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1 leading-snug">
                      {step.desc}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── MISSING EVIDENCE WARNINGS BANNER ─────────────────────── */}
          {missingItems.length > 0 && (
            <div className="p-5 rounded-2xl bg-amber-950/30 border border-amber-600/40">
              <div className="flex items-start gap-3">
                <span className="text-2xl mt-0.5">⚠️</span>
                <div className="space-y-2 flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-amber-300">
                      Missing Required Verification Evidence ({missingItems.length})
                    </h4>
                    <span className="text-[10px] font-mono text-amber-400 bg-amber-950/70 border border-amber-700/60 px-2 py-0.5 rounded">
                      Action Required for Full Score
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    The platform verification engine requires complete photographic and invoice coverage across project milestones to achieve full verification:
                  </p>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs">
                    {missingItems.map((item, idx) => (
                      <li key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-surface/70 border border-surface-border">
                        <span className="text-amber-400 font-bold">✕</span>
                        <span className="text-slate-200">{item}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="pt-2 flex flex-wrap gap-2">
                    <button
                      onClick={() => setShowEvidenceModal(true)}
                      className="btn-primary text-xs px-4 py-1.5"
                    >
                      + Upload Missing Milestone
                    </button>
                    {!hasFinancial && (
                      <button
                        onClick={() => setShowFinancialModal(true)}
                        className="btn-secondary text-xs px-4 py-1.5"
                      >
                        + Submit Invoices
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── 6-DIMENSION SCORE BREAKDOWN & 10-POINT CHECKLIST ─────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Score Breakdown */}
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>📊</span> 6-Dimension Score Breakdown
                </h3>
                <span className="text-xs font-mono text-brand-300 font-bold">
                  {score ? `${score.final_score.toFixed(0)}/100` : '—'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-4">
                Points calculated by authoritative verification score engines. Read-only.
              </p>

              {score && score.factors ? (
                <div className="space-y-3.5">
                  {Object.entries(score.factors).map(([key, factor]) => (
                    <div key={key} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200">{factor.factor_name}</span>
                        <span className="font-mono text-brand-300 font-bold">
                          {factor.earned_points.toFixed(1)} / {factor.maximum_points.toFixed(0)}
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-brand-500 transition-all duration-500"
                          style={{ width: `${Math.min(100, Math.max(0, factor.percentage))}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-400 leading-snug">
                        {factor.explanation}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-400 py-6 text-center">
                  Score breakdown accumulating. Run verification engine to update.
                </div>
              )}
            </div>

            {/* 10-Point Verification Checklist */}
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>🛡️</span> 10-Point Engine Checklist
                </h3>
                <button
                  onClick={handleRunVerification}
                  disabled={runningVerification}
                  className="text-[11px] text-brand-400 hover:text-brand-300 underline"
                >
                  {runningVerification ? 'Running…' : 'Re-run Scan'}
                </button>
              </div>
              <p className="text-xs text-slate-400 mb-4">
                Automated multi-engine evaluation checks:
              </p>

              {verificationReport?.individual_checks && verificationReport.individual_checks.length > 0 ? (
                <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
                  {verificationReport.individual_checks.map((chk, idx) => {
                    const isPassed = ['MATCH', 'VALID', 'CLEAN', 'VERIFIED', 'CONSISTENT'].includes(chk.status.toUpperCase())
                    const isWarning = ['NEAR', 'WARNING', 'PARTIAL', 'MINOR_DISCREPANCY'].includes(chk.status.toUpperCase())
                    return (
                      <div key={idx} className="p-2.5 rounded-lg bg-surface/70 border border-surface-border flex items-start justify-between gap-3">
                        <div className="space-y-0.5">
                          <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                            <span>{isPassed ? '✓' : isWarning ? '!' : '✕'}</span>
                            {chk.check_name.replace(/([A-Z])/g, ' $1').trim()}
                          </div>
                          <div className="text-[10px] text-slate-400">
                            {chk.explanation || chk.details?.message || chk.details?.reason || (chk.details ? JSON.stringify(chk.details).slice(0, 70) : '')}
                          </div>
                        </div>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-mono uppercase font-semibold border ${
                            isPassed
                              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60'
                              : isWarning
                              ? 'bg-amber-950/80 text-amber-300 border-amber-700/60'
                              : 'bg-rose-950/80 text-rose-300 border-rose-700/60'
                          }`}
                        >
                          {chk.status}
                        </span>
                      </div>
                    )
                  })}
                </div>
              ) : verificationSummary?.checklist ? (
                <div className="space-y-2">
                  {verificationSummary.checklist.map((c, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-surface/70 border border-surface-border flex items-center justify-between">
                      <div className="text-xs text-slate-200">
                        {c.passed ? '✓' : '⚠️'} {c.title}
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${c.passed ? 'badge-green' : 'badge-yellow'}`}>
                        {c.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-400 py-6 text-center">
                  Checklist pending execution. Click "Run Verification Engine" above.
                </div>
              )}
            </div>
          </div>

          {/* ── RISK EXPLANATIONS & INDEPENDENT AUDIT STATUS ─────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Warnings & Explanations */}
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>⚠️</span> Multi-Factor Risk Assessment
                </h3>
                <span
                  className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full uppercase ${
                    (riskReport?.risk_level || project.risk_level || 'LOW').toUpperCase() === 'HIGH'
                      ? 'badge-red'
                      : (riskReport?.risk_level || project.risk_level || 'LOW').toUpperCase() === 'MEDIUM'
                      ? 'badge-yellow'
                      : 'badge-green'
                  }`}
                >
                  {riskReport?.risk_level || project.risk_level || 'LOW'} Risk
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-4">
                Automated anomaly signals evaluated by backend risk engine.
              </p>

              {riskReport ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-xl bg-surface/80 border border-surface-border flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Risk Score:</span>
                    <span className="text-lg font-bold text-white">
                      {riskReport.risk_score.toFixed(1)} / 100
                    </span>
                  </div>

                  {riskReport.narrative_reasons && riskReport.narrative_reasons.length > 0 ? (
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-semibold text-amber-300">Detected Warnings:</div>
                      {riskReport.narrative_reasons.map((reason, idx) => (
                        <div key={idx} className="p-2 rounded-lg bg-amber-950/20 border border-amber-800/30 text-xs text-amber-200 flex items-start gap-2">
                          <span>⚡</span>
                          <span>{reason}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-800/30 text-xs text-emerald-300 flex items-center gap-2">
                      <span>✓</span> Zero critical risk anomalies detected across evidence signatures.
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-xs text-slate-400 py-4 text-center">
                  Standard baseline risk level. Zero active fraud flags.
                </div>
              )}
            </div>

            {/* Independent Audit Status & Requests */}
            <div className="glass-card p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🏛️</span> Independent Audit Status & Requests
                  </h3>
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-surface border border-surface-border text-slate-300">
                    {audits.length} Case{audits.length === 1 ? '' : 's'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mb-4">
                  Third-party physical audits triggered by risk or budget thresholds.
                </p>

                {audits.length === 0 ? (
                  <div className="p-4 rounded-xl bg-surface/60 border border-surface-border text-center space-y-1">
                    <div className="text-xs font-semibold text-slate-300">No Physical Audit Required</div>
                    <div className="text-[11px] text-slate-400">
                      Automated 10-engine verification governs this project. Field audit not currently queued.
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {audits.map((a) => (
                      <div key={a.id} className="p-3.5 rounded-xl bg-surface/80 border border-surface-border space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">
                            Audit Case: {a.id.slice(0, 8)}…
                          </span>
                          <span className="badge-blue text-[10px] font-mono font-semibold">
                            {a.status}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          Trigger: <strong className="text-slate-200">{a.selection_reason}</strong>
                          {a.scope && <span> • Scope: {a.scope}</span>}
                        </div>

                        {a.decisions && a.decisions.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-surface-border/60 space-y-1">
                            <div className="text-[11px] font-semibold text-slate-300">Auditor Decisions:</div>
                            {a.decisions.map((d) => (
                              <div key={d.id} className="text-xs p-2 rounded bg-surface border border-surface-border flex items-center justify-between">
                                <span className="font-semibold text-white">{d.decision}</span>
                                <span className="text-[10px] text-slate-400">
                                  {d.decided_at ? new Date(d.decided_at).toLocaleDateString() : ''}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {disputes.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-surface-border/60 space-y-2">
                    <div className="text-[11px] font-semibold text-rose-400 flex items-center gap-1">
                      <span>⚖️</span> Lodged Disputes ({disputes.length}):
                    </div>
                    {disputes.map((d) => (
                      <div key={d.id} className="p-2.5 rounded-lg bg-rose-950/20 border border-rose-800/40 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-slate-300">ID: {d.id.slice(0, 8)}…</span>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-700">
                            {d.status}
                          </span>
                        </div>
                        <p className="text-slate-300 text-[11px]">{d.reason}</p>
                        {d.resolution_notes && (
                          <div className="text-[10px] text-slate-400 pt-1 border-t border-rose-800/30">
                            <strong>Resolution:</strong> {d.resolution_notes}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Dispute Action for Unfavorable Decisions */}
              <div className="mt-4 pt-3 border-t border-surface-border flex items-center justify-between">
                <span className="text-[11px] text-slate-400">Disagree with an audit finding?</span>
                <button
                  onClick={() => setShowDisputeModal(true)}
                  className="px-3 py-1 rounded-lg border border-rose-700/50 hover:bg-rose-950/50 text-rose-300 text-xs transition-colors"
                >
                  Lodge Formal Dispute
                </button>
              </div>
            </div>
          </div>

          {/* ── VISUAL CHRONOLOGICAL EVIDENCE TIMELINE ───────────────── */}
          <div className="glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>⏳</span> Visual Chronological Evidence Timeline
                </h3>
                <p className="text-xs text-slate-400">
                  Immutable milestone progression with cryptographic SHA-256 hashes and GPS coordinates.
                </p>
              </div>
              <button
                onClick={() => setShowEvidenceModal(true)}
                className="btn-secondary text-xs px-3.5 py-1.5 flex items-center gap-1"
              >
                <span>+</span> Add Milestone
              </button>
            </div>

            {timelineItems.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs rounded-xl border border-dashed border-surface-border">
                No milestone evidence uploaded yet. Click "+ Add Milestone" to register Before, Progress, or Completion items.
              </div>
            ) : (
              <div className="space-y-6 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-surface-border">
                {timelineItems.map((item, idx) => (
                  <div key={item.id} className="relative flex items-start gap-4 pl-1">
                    <div className="w-6 h-6 rounded-full bg-brand-900 border border-brand-500 text-brand-300 flex items-center justify-center text-[10px] font-mono font-bold z-10">
                      {idx + 1}
                    </div>
                    <div className="flex-1 glass-card p-4 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white">{item.title}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-surface-border text-brand-300 uppercase">
                            {item.evidence_type}
                          </span>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded font-mono uppercase font-semibold ${
                              item.verification_status === 'VERIFIED'
                                ? 'badge-green'
                                : 'badge-blue'
                            }`}
                          >
                            {item.verification_status}
                          </span>
                        </div>
                      </div>

                      {item.description && (
                        <p className="text-xs text-slate-300 leading-relaxed">{item.description}</p>
                      )}

                      <div className="pt-2 border-t border-surface-border/50 text-[10px] font-mono text-slate-400 flex flex-wrap gap-4">
                        <span>Captured: {item.captured_at ? new Date(item.captured_at).toLocaleString() : 'N/A'}</span>
                        <span>Uploaded: {new Date(item.uploaded_at).toLocaleString()}</span>
                        <span>SHA-256: {item.file_hash_sha256.slice(0, 12)}…</span>
                        <span>Location: {item.location_status}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── FINANCIAL EVIDENCE & INVOICE RECONCILIATION ───────────── */}
          <div className="glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>🧾</span> Financial Documents & OCR Reconciliation
                </h3>
                <p className="text-xs text-slate-400">
                  Vendor invoices reconciled against claimed budget. Evaluated for duplicate reuse.
                </p>
              </div>
              <button
                onClick={() => setShowFinancialModal(true)}
                className="btn-secondary text-xs px-3.5 py-1.5 flex items-center gap-1"
              >
                <span>+</span> Upload Financial Document
              </button>
            </div>

            {consistencyReport && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                <div className="p-3 rounded-xl bg-surface/70 border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase">Target Budget</div>
                  <div className="text-sm font-bold text-white font-mono mt-0.5">
                    ₹{project.target_amount ? project.target_amount.toLocaleString('en-IN') : '—'}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface/70 border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase">Documented Total</div>
                  <div className="text-sm font-bold text-emerald-400 font-mono mt-0.5">
                    ₹{consistencyReport.supported_total.toLocaleString('en-IN')}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface/70 border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase">Consistency Status</div>
                  <div className="text-xs font-bold text-brand-300 font-mono mt-1">
                    {consistencyReport.status}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface/70 border border-surface-border">
                  <div className="text-[10px] text-slate-400 uppercase">Variance Discrepancy</div>
                  <div className="text-sm font-bold text-white font-mono mt-0.5">
                    {consistencyReport.difference_percentage !== undefined
                      ? `${consistencyReport.difference_percentage.toFixed(1)}%`
                      : '0.0%'}
                  </div>
                </div>
              </div>
            )}

            {financials.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs rounded-xl border border-dashed border-surface-border">
                No financial documents uploaded yet. Submit vendor bills, invoices, or payment slips to verify expenditure.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-surface-border text-slate-400">
                      <th className="pb-2.5 font-semibold">Doc Type</th>
                      <th className="pb-2.5 font-semibold">Vendor / Notes</th>
                      <th className="pb-2.5 font-semibold">Claimed Amount</th>
                      <th className="pb-2.5 font-semibold">Extracted OCR</th>
                      <th className="pb-2.5 font-semibold">OCR Status</th>
                      <th className="pb-2.5 font-semibold">Validation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border/40">
                    {financials.map((fin) => (
                      <tr key={fin.id} className="hover:bg-white/[0.02]">
                        <td className="py-2.5 font-mono text-[11px] text-brand-300">
                          {fin.document_type}
                        </td>
                        <td className="py-2.5 text-slate-200">
                          {fin.vendor_name || fin.description || '—'}
                        </td>
                        <td className="py-2.5 font-mono font-bold text-white">
                          ₹{fin.claimed_amount.toLocaleString('en-IN')}
                        </td>
                        <td className="py-2.5 font-mono text-emerald-400">
                          {fin.extracted_amount ? `₹${fin.extracted_amount.toLocaleString('en-IN')}` : '—'}
                        </td>
                        <td className="py-2.5">
                          <span className="badge-blue text-[10px] font-mono">
                            {fin.ocr_status || 'COMPLETED'}
                          </span>
                        </td>
                        <td className="py-2.5">
                          <span className="badge-green text-[10px] font-mono">
                            {fin.validation_status || 'VALID'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* ── MODAL: SUBMIT EVIDENCE (LIVE CAMERA CAPTURE ONLY) ────────── */}
      {showEvidenceModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card max-w-2xl w-full p-6 space-y-4 border-brand-500/40 relative max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div>
                <h4 className="text-base font-bold text-white flex items-center gap-2">
                  <span>📷</span> In-App Live Evidence Capture
                </h4>
                <p className="text-[11px] text-slate-400">
                  Direct hardware camera capture only. File uploads from disk or gallery are restricted to prevent fraud.
                </p>
              </div>
              <button
                onClick={() => {
                  setShowEvidenceModal(false)
                  resetEvidenceForm()
                }}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            {!evidenceFile ? (
              /* ── Step 1: In-App Live Camera Capture ── */
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="form-label text-xs">Milestone Stage *</label>
                    <select
                      value={evidenceType}
                      onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                      className="input-field text-xs"
                    >
                      <option value="BEFORE">BEFORE (Pre-work baseline)</option>
                      <option value="PROGRESS">PROGRESS (Milestone execution)</option>
                      <option value="COMPLETION">COMPLETION (Final deliverable)</option>
                      <option value="EVENT">EVENT (Distribution / Camp)</option>
                      <option value="OTHER">OTHER (Supporting Document)</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label text-xs">Evidence Title</label>
                    <input
                      type="text"
                      placeholder="e.g. Pump Foundation Laid"
                      value={evidenceTitle}
                      onChange={(e) => setEvidenceTitle(e.target.value)}
                      className="input-field text-xs"
                    />
                  </div>
                </div>

                {submittingEvidence ? (
                  <div className="p-12 text-center text-slate-300 space-y-3 bg-slate-900/80 rounded-2xl border border-surface-border">
                    <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
                    <p className="text-sm font-semibold text-white">Persisting Tamper-Proof Evidence & Calculating Score…</p>
                    <p className="text-xs text-slate-400">Fingerprinting SHA-256 and evaluating GPS geofence compliance.</p>
                  </div>
                ) : (
                  <LiveCameraEvidenceCapture
                    projectCode={project?.project_code || 'PROJECT'}
                    projectTitle={project?.title || 'Project Site'}
                    milestoneType={evidenceType}
                    onCaptureComplete={handleEvidenceCaptured}
                    onCancel={() => {
                      setShowEvidenceModal(false)
                      resetEvidenceForm()
                    }}
                  />
                )}
              </div>
            ) : (
              /* ── Step 2: Review Captured Photo with Geolocation & Timestamp ── */
              <form onSubmit={handleUploadEvidence} className="space-y-4 text-xs">
                {/* Captured Photo Preview */}
                <div className="relative rounded-2xl overflow-hidden border-2 border-emerald-500 shadow-2xl bg-black">
                  {capturedPreviewUrl && (
                    <img
                      src={capturedPreviewUrl}
                      alt="Captured Project Evidence"
                      className="w-full h-auto max-h-[360px] object-contain mx-auto"
                    />
                  )}
                  <div className="absolute top-3 right-3 bg-emerald-950/90 border border-emerald-500 text-emerald-300 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 shadow-lg">
                    <span>✓</span> Live Camera Captured
                  </div>
                </div>

                {/* Captured Geographic Location & Time Panel */}
                <div className="p-4 rounded-xl bg-slate-900/90 border border-surface-border space-y-2.5">
                  <div className="font-bold text-white text-xs uppercase tracking-wider flex items-center gap-2">
                    <span className="text-emerald-400">🛡️</span> Verified Capture Telemetry (Embedded on Image)
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 text-slate-300">
                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                      <div className="text-[11px] text-slate-400 font-medium">Real Geographic Location:</div>
                      <div className="font-bold text-emerald-400 font-mono text-xs flex items-center gap-1.5">
                        <span>📍</span>
                        {latitude !== undefined && longitude !== undefined
                          ? `${latitude.toFixed(6)}° N, ${longitude.toFixed(6)}° E`
                          : 'Location Unavailable'}
                      </div>
                      {gpsAccuracy !== undefined && (
                        <div className="text-[10px] text-slate-400">
                          GPS Sensor Accuracy: <strong>±{gpsAccuracy} meters</strong>
                        </div>
                      )}
                      {capturedLocationDisplay && (
                        <div className="text-[10px] text-slate-400 truncate">{capturedLocationDisplay}</div>
                      )}
                    </div>

                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                      <div className="text-[11px] text-slate-400 font-medium">Date & Time Captured:</div>
                      <div className="font-bold text-sky-400 font-mono text-xs flex items-center gap-1.5">
                        <span>🕒</span>
                        {capturedDateTimeDisplay || (capturedAt ? new Date(capturedAt).toLocaleString() : 'Just now')}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Method: <strong>Direct App Camera Sensor (No File Picker)</strong>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Form fields */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="form-label text-xs">Title *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Pump Foundation Laid"
                      value={evidenceTitle}
                      onChange={(e) => setEvidenceTitle(e.target.value)}
                      className="input-field text-xs"
                    />
                  </div>
                  <div>
                    <label className="form-label text-xs">Milestone Stage *</label>
                    <select
                      value={evidenceType}
                      onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                      className="input-field text-xs"
                    >
                      <option value="BEFORE">BEFORE (Pre-work baseline)</option>
                      <option value="PROGRESS">PROGRESS (Milestone execution)</option>
                      <option value="COMPLETION">COMPLETION (Final deliverable)</option>
                      <option value="EVENT">EVENT (Distribution / Camp)</option>
                      <option value="OTHER">OTHER (Supporting Document)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="form-label text-xs">Description / Observations</label>
                  <textarea
                    rows={2}
                    placeholder="Details of physical deliverables and inspection status..."
                    value={evidenceDesc}
                    onChange={(e) => setEvidenceDesc(e.target.value)}
                    className="input-field text-xs"
                  />
                </div>

                <div>
                  <label className="form-label text-xs">Supersedes Evidence ID (Optional Correction)</label>
                  <input
                    type="text"
                    placeholder="UUID of previous evidence to supersede"
                    value={supersedesId}
                    onChange={(e) => setSupersedesId(e.target.value)}
                    className="input-field text-xs font-mono"
                  />
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-surface-border">
                  <button
                    type="button"
                    onClick={() => {
                      if (capturedPreviewUrl) URL.revokeObjectURL(capturedPreviewUrl)
                      setEvidenceFile(null)
                      setCapturedPreviewUrl(null)
                    }}
                    className="btn-secondary text-xs px-4 py-2 flex items-center gap-1.5 text-rose-300 hover:text-rose-200"
                  >
                    <span>🔄</span> Retake Photo
                  </button>

                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setShowEvidenceModal(false)
                        resetEvidenceForm()
                      }}
                      className="btn-secondary text-xs px-4 py-2"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submittingEvidence}
                      className="btn-primary text-xs px-6 py-2 bg-emerald-600 hover:bg-emerald-500"
                    >
                      {submittingEvidence ? 'Uploading & Hashing…' : 'Submit Evidence'}
                    </button>
                  </div>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ── MODAL: SUBMIT FINANCIAL DOCUMENT ─────────────────────────── */}
      {showFinancialModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-4 border-brand-500/40 relative max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>🧾</span> Submit Financial Document
              </h4>
              <button onClick={() => setShowFinancialModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleUploadFinancial} className="space-y-3.5 text-xs">
              <div>
                <label className="form-label text-xs">Document File (Bill / Invoice / Receipt / Statement) *</label>
                <input
                  type="file"
                  required
                  accept="image/*,.pdf"
                  onChange={(e) => setFinancialFile(e.target.files?.[0] || null)}
                  className="input-field text-xs file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:bg-brand-600 file:text-white file:text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="form-label text-xs">Claimed Amount (INR ₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="e.g. 45000"
                    value={claimedAmount}
                    onChange={(e) => setClaimedAmount(e.target.value)}
                    className="input-field text-xs font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="form-label text-xs">Document Type *</label>
                  <select
                    value={docType}
                    onChange={(e) => setDocType(e.target.value as FinancialDocumentType)}
                    className="input-field text-xs"
                  >
                    <option value="INVOICE">Tax Invoice</option>
                    <option value="BILL">Vendor Bill</option>
                    <option value="RECEIPT">Payment Receipt</option>
                    <option value="EXPENSE_STATEMENT">Expense Statement</option>
                    <option value="TRANSACTION_RECORD">Bank / UPI Record</option>
                    <option value="OTHER">Other Financial Document</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="form-label text-xs">Vendor / Beneficiary Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Acme Solar Solutions"
                    value={vendorName}
                    onChange={(e) => setVendorName(e.target.value)}
                    className="input-field text-xs"
                  />
                </div>
                <div>
                  <label className="form-label text-xs">Invoice / Receipt #</label>
                  <input
                    type="text"
                    placeholder="e.g. INV-2026-891"
                    value={invoiceNumber}
                    onChange={(e) => setInvoiceNumber(e.target.value)}
                    className="input-field text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="form-label text-xs">Document Date</label>
                <input
                  type="date"
                  value={docDate}
                  onChange={(e) => setDocDate(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div>
                <label className="form-label text-xs">Notes / Line Item Description</label>
                <textarea
                  rows={2}
                  placeholder="Description of purchased equipment or services..."
                  value={financialDesc}
                  onChange={(e) => setFinancialDesc(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
                <button
                  type="button"
                  onClick={() => setShowFinancialModal(false)}
                  className="btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingFinancial}
                  className="btn-primary text-xs px-6 py-2"
                >
                  {submittingFinancial ? 'Uploading & Extracting OCR…' : 'Submit Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: LODGE FORMAL DISPUTE ──────────────────────────────── */}
      {showDisputeModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-4 border-rose-500/40 relative">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>⚠️</span> Lodge Formal Audit Dispute
              </h4>
              <button onClick={() => setShowDisputeModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleLodgeDispute} className="space-y-3.5 text-xs">
              <p className="text-slate-300">
                Lodging a dispute flags this project for administrative review by senior audit officers. Project status will update to <strong>DISPUTED</strong>.
              </p>

              <div>
                <label className="form-label text-xs">Dispute Grounds & Detailed Justification *</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Explain why the audit decision or discrepancy finding is incorrect, citing specific evidence or invoices..."
                  value={disputeReason}
                  onChange={(e) => setDisputeReason(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
                <button
                  type="button"
                  onClick={() => setShowDisputeModal(false)}
                  className="btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingDispute}
                  className="px-6 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-all disabled:opacity-50"
                >
                  {submittingDispute ? 'Lodging Dispute…' : 'Submit Formal Dispute'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
