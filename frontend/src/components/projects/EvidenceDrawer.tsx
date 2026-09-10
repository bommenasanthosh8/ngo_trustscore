import { useState, useEffect, type FormEvent } from 'react'
import { useAuth } from '@/auth/AuthContext'
import { evidenceApi, type UploadEvidencePayload } from '@/api/evidence'
import { financialApi, type UploadFinancialPayload } from '@/api/financial'
import { getProjectVerification, triggerProjectVerification } from '@/api/verification'
import LiveCameraEvidenceCapture, { type CapturedEvidenceData } from '@/components/projects/LiveCameraEvidenceCapture'
import type {
  EvidenceTimelineResponse,
  EvidenceType,
  FinancialConsistencyReport,
  FinancialDocumentType,
  FinancialEvidence,
  ProjectDetail,
  VerificationReport,
} from '@/types'

interface EvidenceDrawerProps {
  project: ProjectDetail
  isOpen: boolean
  onClose: () => void
}

const EVIDENCE_TYPES: { value: EvidenceType; label: string; desc: string }[] = [
  { value: 'BEFORE', label: 'Before / Baseline', desc: 'Pre-work conditions before project execution.' },
  { value: 'PROGRESS', label: 'Progress Milestone', desc: 'Active execution and construction photos/metrics.' },
  { value: 'COMPLETION', label: 'Completion Evidence', desc: 'Final completed outcome ready for audit.' },
  { value: 'EVENT', label: 'Event / Distribution', desc: 'Community gatherings, distribution, and beneficiary camps.' },
  { value: 'FINANCIAL', label: 'Financial / Invoice', desc: 'Verified invoices, receipts, and bank transaction slips.' },
  { value: 'OTHER', label: 'Other Supporting', desc: 'Additional permits, third-party reports, and notes.' },
]

const FINANCIAL_DOC_TYPES: { value: FinancialDocumentType; label: string }[] = [
  { value: 'INVOICE', label: 'Tax Invoice' },
  { value: 'BILL', label: 'Vendor Bill' },
  { value: 'RECEIPT', label: 'Payment Receipt' },
  { value: 'EXPENSE_STATEMENT', label: 'Expense Statement' },
  { value: 'TRANSACTION_RECORD', label: 'Bank / UPI Record' },
  { value: 'OTHER', label: 'Other Financial Document' },
]

const TYPE_COLORS: Record<EvidenceType, string> = {
  BEFORE: 'bg-purple-900/60 text-purple-300 border-purple-700/50',
  PROGRESS: 'bg-blue-900/60 text-blue-300 border-blue-700/50',
  COMPLETION: 'bg-emerald-900/60 text-emerald-300 border-emerald-700/50',
  EVENT: 'bg-amber-900/60 text-amber-300 border-amber-700/50',
  FINANCIAL: 'bg-cyan-900/60 text-cyan-300 border-cyan-700/50',
  OTHER: 'bg-slate-800 text-slate-300 border-slate-700',
}

const CONSISTENCY_BADGES: Record<string, { label: string; style: string }> = {
  CONSISTENT: { label: 'Consistent', style: 'bg-emerald-950 text-emerald-300 border-emerald-700/60' },
  MINOR_DISCREPANCY: { label: 'Minor Discrepancy', style: 'bg-amber-950 text-amber-300 border-amber-700/60' },
  MAJOR_DISCREPANCY: { label: 'Major Discrepancy', style: 'bg-rose-950 text-rose-300 border-rose-700/60' },
  INSUFFICIENT_EVIDENCE: { label: 'Insufficient Evidence', style: 'bg-slate-800 text-slate-300 border-slate-700' },
}

const ACTION_BADGES: Record<string, { label: string; desc: string; style: string }> = {
  NO_ADDITIONAL_ACTION: {
    label: 'Compliant — No Action Required',
    desc: 'All 10 verification dimensions meet high confidence thresholds. No manual intervention needed.',
    style: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/70',
  },
  MANUAL_REVIEW: {
    label: 'Manual Review Recommended',
    desc: 'Minor variances or missing optional telemetry detected. Auditor or staff review suggested.',
    style: 'bg-amber-950/80 text-amber-300 border-amber-700/70',
  },
  AUDIT_RECOMMENDED: {
    label: 'Audit Recommended',
    desc: 'Significant anomalies, cross-project signatures, or missing critical milestones detected.',
    style: 'bg-rose-950/80 text-rose-300 border-rose-700/70',
  },
}

function getCheckBadge(status: string): string {
  const s = status.toUpperCase()
  if (['MATCH', 'PASSED', 'VALID', 'VERIFIED', 'CLEAN', 'COMPATIBLE', 'AVAILABLE', 'COMPLETE', 'CONSISTENT'].includes(s)) {
    return 'bg-emerald-950/90 text-emerald-300 border-emerald-700/60'
  }
  if (['NEAR', 'WARNING', 'PARTIAL', 'MINOR_DISCREPANCY'].includes(s)) {
    return 'bg-amber-950/90 text-amber-300 border-amber-700/60'
  }
  if (['MISMATCH', 'FAILED', 'SUSPICIOUS', 'INTERNAL_DUPLICATE', 'MAJOR_DISCREPANCY', 'INCOMPLETE'].includes(s)) {
    return 'bg-rose-950/90 text-rose-300 border-rose-700/60'
  }
  return 'bg-slate-800 text-slate-300 border-slate-700'
}

function getCheckIcon(checkName: string): string {
  switch (checkName) {
    case 'LocationCheck': return '📍'
    case 'TimestampCheck': return '⏱️'
    case 'TimelineCheck': return '🔄'
    case 'DuplicateMediaCheck': return '🔍'
    case 'ImageSimilarityCheck': return '🖼️'
    case 'MetadataCheck': return '🏷️'
    case 'OCRCheck': return '📄'
    case 'FinancialConsistencyCheck': return '💳'
    case 'ProjectIdentityCheck': return '🛡️'
    case 'EvidenceCompletenessCheck': return '📋'
    default: return '✓'
  }
}

export default function EvidenceDrawer({ project, isOpen, onClose }: EvidenceDrawerProps) {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<'MILESTONES' | 'FINANCIALS' | 'VERIFICATION'>('MILESTONES')

  // Milestone Timeline State
  const [timelineData, setTimelineData] = useState<EvidenceTimelineResponse | null>(null)
  const [loadingTimeline, setLoadingTimeline] = useState(true)
  const [selectedFilter, setSelectedFilter] = useState<EvidenceType | 'ALL'>('ALL')
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  // Financial State
  const [financialItems, setFinancialItems] = useState<FinancialEvidence[]>([])
  const [consistencyReport, setConsistencyReport] = useState<FinancialConsistencyReport | null>(null)
  const [loadingFinancials, setLoadingFinancials] = useState(false)

  // Verification Engine State
  const [verificationReport, setVerificationReport] = useState<VerificationReport | null>(null)
  const [loadingVerification, setLoadingVerification] = useState(false)
  const [verifying, setVerifying] = useState(false)

  // Upload Milestone Modal State
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Upload Financial Modal State
  const [showFinUploadModal, setShowFinUploadModal] = useState(false)
  const [finUploading, setFinUploading] = useState(false)
  const [finUploadError, setFinUploadError] = useState<string | null>(null)

  // Milestone Form Fields
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('PROGRESS')
  const [description, setDescription] = useState('')
  const [capturedAt, setCapturedAt] = useState('')
  const [latitude, setLatitude] = useState<number | undefined>(undefined)
  const [longitude, setLongitude] = useState<number | undefined>(undefined)
  const [gpsAccuracy, setGpsAccuracy] = useState<number | undefined>(undefined)
  const [isRevision, setIsRevision] = useState(false)
  const [supersedesId, setSupersedesId] = useState<string>('')
  const [capturedPreviewUrl, setCapturedPreviewUrl] = useState<string | null>(null)
  const [capturedLocationDisplay, setCapturedLocationDisplay] = useState<string>('')
  const [capturedDateTimeDisplay, setCapturedDateTimeDisplay] = useState<string>('')

  // Financial Form Fields
  const [finFile, setFinFile] = useState<File | null>(null)
  const [claimedAmount, setClaimedAmount] = useState('')
  const [finDocType, setFinDocType] = useState<FinancialDocumentType>('INVOICE')
  const [vendorName, setVendorName] = useState('')
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [finDescription, setFinDescription] = useState('')

  // Determine if current user can upload
  const canUpload =
    user &&
    (user.role === 'ADMIN' ||
      (user.role === 'NGO' && user.ngo_id && user.ngo_id === project.ngo_id))

  useEffect(() => {
    if (isOpen) {
      loadTimeline()
      loadFinancials()
      loadVerification()
    }
  }, [isOpen, project.id])

  function loadTimeline() {
    setLoadingTimeline(true)
    evidenceApi
      .getTimeline(project.id)
      .then((res) => {
        if (res.data.success && res.data.data) {
          setTimelineData(res.data.data)
        }
      })
      .catch((err) => console.error('Failed to load evidence timeline', err))
      .finally(() => setLoadingTimeline(false))
  }

  function loadFinancials() {
    setLoadingFinancials(true)
    financialApi
      .list(project.id)
      .then((res) => {
        if (res.data.success && res.data.data) {
          setFinancialItems(res.data.data.items)
          setConsistencyReport(res.data.data.consistency_report)
        }
      })
      .catch((err) => console.error('Failed to load project financials', err))
      .finally(() => setLoadingFinancials(false))
  }

  function loadVerification() {
    setLoadingVerification(true)
    getProjectVerification(project.id)
      .then((res) => {
        if (res.success && res.data) {
          setVerificationReport(res.data)
        }
      })
      .catch((err) => console.error('Failed to load verification report', err))
      .finally(() => setLoadingVerification(false))
  }

  async function handleRunVerification() {
    setVerifying(true)
    try {
      const res = await triggerProjectVerification(project.id)
      if (res.success && res.data) {
        setVerificationReport(res.data)
        setActionMessage('Evidence verification completed. 10 independent checks evaluated.')
        setTimeout(() => setActionMessage(null), 5000)
      }
    } catch (err: any) {
      console.error('Verification failed', err)
    } finally {
      setVerifying(false)
    }
  }

  async function handleUploadSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) {
      setUploadError('Please select an evidence file to upload.')
      return
    }

    setUploading(true)
    setUploadError(null)

    const payload: UploadEvidencePayload = {
      file,
      title: title.trim(),
      evidence_type: evidenceType,
      description: description.trim() || undefined,
      captured_at: capturedAt ? new Date(capturedAt).toISOString() : undefined,
      latitude,
      longitude,
      gps_accuracy: gpsAccuracy,
      supersedes_id: isRevision && supersedesId ? supersedesId : undefined,
    }

    try {
      const res = await evidenceApi.upload(project.id, payload)
      if (res.data.success) {
        setActionMessage('Evidence uploaded successfully. Immutable hash generated.')
        setTimeout(() => setActionMessage(null), 5000)
        setShowUploadModal(false)
        resetUploadForm()
        loadTimeline()
      }
    } catch (err: any) {
      setUploadError(err.response?.data?.error || err.message || 'Evidence upload failed.')
    } finally {
      setUploading(false)
    }
  }

  async function handleFinancialUploadSubmit(e: FormEvent) {
    e.preventDefault()
    if (!finFile) {
      setFinUploadError('Please select a document to upload.')
      return
    }
    const amt = parseFloat(claimedAmount)
    if (isNaN(amt) || amt <= 0) {
      setFinUploadError('Please enter a valid positive claimed amount.')
      return
    }

    setFinUploading(true)
    setFinUploadError(null)

    const payload: UploadFinancialPayload = {
      file: finFile,
      claimed_amount: amt,
      document_type: finDocType,
      vendor_name: vendorName.trim() || undefined,
      invoice_number: invoiceNumber.trim() || undefined,
      document_date: documentDate ? new Date(documentDate).toISOString() : undefined,
      description: finDescription.trim() || undefined,
    }

    try {
      const res = await financialApi.upload(project.id, payload)
      if (res.data.success) {
        setActionMessage('Financial document uploaded. OCR extraction & duplicate check completed.')
        setTimeout(() => setActionMessage(null), 5000)
        setShowFinUploadModal(false)
        resetFinUploadForm()
        loadFinancials()
      }
    } catch (err: any) {
      setFinUploadError(err.response?.data?.error || err.message || 'Financial upload failed.')
    } finally {
      setFinUploading(false)
    }
  }

  function resetUploadForm() {
    setFile(null)
    setTitle('')
    setEvidenceType('PROGRESS')
    setDescription('')
    setCapturedAt('')
    setLatitude(undefined)
    setLongitude(undefined)
    setGpsAccuracy(undefined)
    setIsRevision(false)
    setSupersedesId('')
    setUploadError(null)
    if (capturedPreviewUrl) {
      URL.revokeObjectURL(capturedPreviewUrl)
    }
    setCapturedPreviewUrl(null)
    setCapturedLocationDisplay('')
    setCapturedDateTimeDisplay('')
  }

  async function handleEvidenceCaptured(data: CapturedEvidenceData) {
    setFile(data.file)
    setCapturedPreviewUrl(data.previewUrl)
    setLatitude(data.latitude)
    setLongitude(data.longitude)
    setGpsAccuracy(data.accuracy)
    setCapturedAt(data.capturedAt)
    setCapturedLocationDisplay(data.locationDisplay)
    setCapturedDateTimeDisplay(`${data.formattedDate} · ${data.formattedTime}`)

    const finalTitle =
      title.trim() ||
      `[${evidenceType}] In-Situ Verification Evidence - ${data.formattedDate}`
    setTitle(finalTitle)

    setUploading(true)
    setUploadError(null)

    const payload: UploadEvidencePayload = {
      file: data.file,
      title: finalTitle,
      evidence_type: evidenceType,
      description: description.trim() || `Direct hardware camera capture at ${data.locationDisplay}`,
      captured_at: data.capturedAt,
      latitude: data.latitude,
      longitude: data.longitude,
      gps_accuracy: data.accuracy,
      supersedes_id: isRevision && supersedesId ? supersedesId : undefined,
    }

    try {
      const res = await evidenceApi.upload(project.id, payload)
      if (res.data.success) {
        setActionMessage(`Photo evidence "${finalTitle}" successfully stamped, saved to database, and scored!`)
        setTimeout(() => setActionMessage(null), 5000)
        setShowUploadModal(false)
        resetUploadForm()
        loadTimeline()
      }
    } catch (err: any) {
      setUploadError(err.response?.data?.error || err.message || 'Evidence upload failed.')
    } finally {
      setUploading(false)
    }
  }

  function resetFinUploadForm() {
    setFinFile(null)
    setClaimedAmount('')
    setFinDocType('INVOICE')
    setVendorName('')
    setInvoiceNumber('')
    setDocumentDate('')
    setFinDescription('')
    setFinUploadError(null)
  }

  async function handleDownloadFile(evidenceId: string, filename: string) {
    try {
      const res = await evidenceApi.downloadFile(evidenceId)
      const contentType = (res.headers['content-type'] as string) || 'application/octet-stream'
      const blob = new Blob([res.data], { type: contentType })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert('Failed to download evidence file. Check your authentication and access rights.')
    }
  }

  if (!isOpen) return null

  const items = timelineData?.timeline || []
  const filteredItems =
    selectedFilter === 'ALL'
      ? items
      : items.filter((it) => it.evidence_type === selectedFilter)

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/75 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="w-full max-w-4xl bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl overflow-hidden">
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-800 bg-slate-950 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono font-bold tracking-wider px-2.5 py-1 rounded bg-teal-950/80 text-teal-300 border border-teal-700/50">
                {project.project_code}
              </span>
              <span className="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {project.category}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-2">{project.title}</h2>
            <div className="flex items-center gap-4 mt-3">
              <button
                onClick={() => setActiveTab('MILESTONES')}
                className={`text-xs font-semibold pb-1.5 border-b-2 transition ${
                  activeTab === 'MILESTONES'
                    ? 'border-teal-400 text-teal-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                📁 Milestone Evidence Timeline ({items.length})
              </button>
              <button
                onClick={() => setActiveTab('FINANCIALS')}
                className={`text-xs font-semibold pb-1.5 border-b-2 transition flex items-center gap-1.5 ${
                  activeTab === 'FINANCIALS'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>💳 Financial Consistency & Auditing ({financialItems.length})</span>
                {consistencyReport && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded border ${
                      CONSISTENCY_BADGES[consistencyReport.status]?.style || ''
                    }`}
                  >
                    {consistencyReport.status.replace('_', ' ')}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab('VERIFICATION')}
                className={`text-xs font-semibold pb-1.5 border-b-2 transition flex items-center gap-1.5 ${
                  activeTab === 'VERIFICATION'
                    ? 'border-emerald-400 text-emerald-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>⚖️ Verification Engine (10 Checks)</span>
                {verificationReport && (
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.5 rounded border font-semibold ${
                      verificationReport.overall_score >= 80
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-700/60'
                        : verificationReport.overall_score >= 50
                        ? 'bg-amber-950 text-amber-300 border-amber-700/60'
                        : 'bg-rose-950 text-rose-300 border-rose-700/60'
                    }`}
                  >
                    {verificationReport.overall_score.toFixed(0)}%
                  </span>
                )}
              </button>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition"
          >
            ✕
          </button>
        </div>

        {/* Action Notice */}
        {actionMessage && (
          <div className="bg-emerald-950/80 border-b border-emerald-700/60 text-emerald-300 px-6 py-2.5 text-sm flex items-center justify-between">
            <span>✓ {actionMessage}</span>
            <button onClick={() => setActionMessage(null)} className="text-emerald-400 hover:text-white">
              ✕
            </button>
          </div>
        )}

        {activeTab === 'MILESTONES' && (
          <>
            {/* Milestone Tracker Bar */}
            <div className="p-6 border-b border-slate-800 bg-slate-900/50">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Project Evidence Milestones
                </h3>
                {canUpload && (
                  <button
                    onClick={() => setShowUploadModal(true)}
                    className="text-xs px-3.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium shadow transition flex items-center gap-1.5"
                  >
                    + Upload Evidence
                  </button>
                )}
              </div>

              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                {(['BEFORE', 'PROGRESS', 'COMPLETION', 'EVENT', 'FINANCIAL', 'OTHER'] as EvidenceType[]).map(
                  (type) => {
                    const count = timelineData?.milestone_summary?.[type] || 0
                    return (
                      <button
                        key={type}
                        onClick={() => setSelectedFilter(selectedFilter === type ? 'ALL' : type)}
                        className={`p-2.5 rounded-lg border text-left transition ${
                          selectedFilter === type
                            ? 'border-teal-500 bg-teal-950/40 text-white'
                            : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 text-slate-400'
                        }`}
                      >
                        <div className="text-[10px] font-medium tracking-wide uppercase">{type}</div>
                        <div className="text-lg font-bold text-white mt-0.5">{count}</div>
                      </button>
                    )
                  }
                )}
              </div>
            </div>

            {/* Timeline Stream */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingTimeline ? (
                <div className="py-20 text-center text-slate-500 text-sm">
                  Loading verified evidence records...
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="py-20 text-center">
                  <div className="text-4xl mb-3">📁</div>
                  <h3 className="text-base font-semibold text-white">No Evidence Uploaded Yet</h3>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                    {canUpload
                      ? 'Start by submitting baseline photos (BEFORE) or initial site inspection logs.'
                      : 'The project owner has not submitted evidence for this category yet.'}
                  </p>
                  {canUpload && (
                    <button
                      onClick={() => setShowUploadModal(true)}
                      className="mt-4 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow"
                    >
                      Submit Initial Evidence
                    </button>
                  )}
                </div>
              ) : (
                <div className="relative border-l-2 border-slate-800 ml-4 pl-6 space-y-6">
                  {filteredItems.map((item) => (
                    <div key={item.id} className="relative group">
                      {/* Timeline dot */}
                      <div className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full bg-teal-500 ring-4 ring-slate-900" />

                      {/* Evidence Card */}
                      <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded border uppercase ${
                                TYPE_COLORS[item.evidence_type]
                              }`}
                            >
                              {item.evidence_type}
                            </span>
                            {item.is_revision && (
                              <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700/50">
                                Correction / Revision
                              </span>
                            )}
                            <span className="text-xs text-slate-500 font-mono">
                              {new Date(item.effective_timestamp).toLocaleString('en-IN', {
                                dateStyle: 'medium',
                                timeStyle: 'short',
                              })}
                            </span>
                          </div>

                          <button
                            onClick={() => handleDownloadFile(item.id, item.original_filename)}
                            className="text-xs font-medium px-3 py-1 rounded bg-slate-800 hover:bg-teal-900/60 hover:text-teal-300 text-slate-300 border border-slate-700 transition flex items-center gap-1.5"
                          >
                            ⬇ Download File
                          </button>
                        </div>

                        <h4 className="text-base font-semibold text-white mt-2">{item.title}</h4>
                        {item.description && (
                          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{item.description}</p>
                        )}

                        {/* Metadata & Audit Attributes */}
                        <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                          {/* GPS Section */}
                          <div className="flex items-center gap-2">
                            <span className="text-slate-500">GPS:</span>
                            {item.location_status === 'CAPTURED' ? (
                              <span className="text-emerald-400 font-mono text-[11px] flex items-center gap-1">
                                📍 {item.latitude?.toFixed(4)}, {item.longitude?.toFixed(4)}{' '}
                                {item.gps_accuracy && `(±${item.gps_accuracy.toFixed(1)}m)`}
                              </span>
                            ) : (
                              <span className="text-amber-400/90 text-[11px] italic">
                                LOCATION_UNAVAILABLE
                              </span>
                            )}
                          </div>

                          {/* Timestamps */}
                          <div className="flex items-center gap-2">
                            <span className="text-slate-500">Captured:</span>
                            <span className="text-slate-300 text-[11px]">
                              {item.captured_at
                                ? new Date(item.captured_at).toLocaleDateString('en-IN')
                                : 'Not recorded on capture'}
                            </span>
                          </div>

                          {/* SHA-256 Hash */}
                          <div className="sm:col-span-2 flex items-center gap-2 font-mono text-[11px] text-slate-400">
                            <span className="text-slate-500 shrink-0">SHA-256:</span>
                            <span className="truncate bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-300 select-all">
                              {item.file_hash_sha256}
                            </span>
                          </div>

                          {/* Supersedes audit trace */}
                          {item.supersedes_id && (
                            <div className="sm:col-span-2 text-[11px] text-amber-400/90">
                              ℹ Replaces prior evidence item (ID: {item.supersedes_id}). Original record preserved.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === 'FINANCIALS' && (
          /* ── Financial Consistency & Documents Tab ────────────────────── */
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Consistency Overview Card */}
            {consistencyReport && (
              <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                      Financial Consistency Analysis
                    </h3>
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${
                        CONSISTENCY_BADGES[consistencyReport.status]?.style || ''
                      }`}
                    >
                      {consistencyReport.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  {canUpload && (
                    <button
                      onClick={() => setShowFinUploadModal(true)}
                      className="text-xs px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium shadow transition flex items-center gap-1.5"
                    >
                      + Upload Invoice / Bill
                    </button>
                  )}
                </div>

                {/* 4-Metric Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 text-[10px] block uppercase">Target Budget</span>
                    <span className="text-base font-bold text-white mt-1 block">
                      ₹{consistencyReport.project_target_amount.toLocaleString()}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 text-[10px] block uppercase">Claimed Total</span>
                    <span className="text-base font-bold text-cyan-300 mt-1 block">
                      ₹{consistencyReport.claimed_total.toLocaleString()}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 text-[10px] block uppercase">Supported Documented</span>
                    <span className="text-base font-bold text-emerald-300 mt-1 block">
                      ₹{consistencyReport.supported_total.toLocaleString()}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 text-[10px] block uppercase">Variance (Difference)</span>
                    <span
                      className={`text-base font-bold mt-1 block ${
                        consistencyReport.difference_percentage > 10.0
                          ? 'text-rose-400'
                          : consistencyReport.difference_percentage > 2.0
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      ₹{consistencyReport.difference.toLocaleString()} ({consistencyReport.difference_percentage}%)
                    </span>
                  </div>
                </div>

                {/* Explanatory summary notes (objective, non-accusatory) */}
                <p className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-lg border border-slate-800 leading-relaxed">
                  ℹ {consistencyReport.summary_notes}
                </p>

                {/* Active Validation Flags */}
                {consistencyReport.flags.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-xs text-slate-400">System Flags:</span>
                    {consistencyReport.flags.map((flag) => (
                      <span
                        key={flag}
                        className="text-[10px] font-mono px-2.5 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/60"
                      >
                        ⚠ {flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Financial Documents List */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Submitted Financial Documents ({financialItems.length})
              </h4>

              {loadingFinancials ? (
                <div className="py-10 text-center text-slate-500 text-sm">Loading financial documents...</div>
              ) : financialItems.length === 0 ? (
                <div className="py-12 text-center p-6 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-3xl mb-2">🧾</div>
                  <h4 className="text-sm font-semibold text-white">No Financial Documents Uploaded</h4>
                  <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                    Upload invoices, vendor bills, and transaction slips to support claimed expenditure.
                  </p>
                  {canUpload && (
                    <button
                      onClick={() => setShowFinUploadModal(true)}
                      className="mt-3 px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow"
                    >
                      + Upload Invoice / Bill
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {financialItems.map((fin) => (
                    <div
                      key={fin.id}
                      className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition space-y-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/50 uppercase">
                            {fin.document_type}
                          </span>
                          {fin.invoice_number && (
                            <span className="text-xs font-mono text-slate-300 font-semibold">
                              #{fin.invoice_number}
                            </span>
                          )}
                          {fin.vendor_name && (
                            <span className="text-xs text-slate-400">· {fin.vendor_name}</span>
                          )}
                        </div>

                        <div className="text-right">
                          <div className="text-sm font-bold text-white">
                            Claimed: ₹{fin.claimed_amount.toLocaleString()}
                          </div>
                          {fin.extracted_amount !== undefined && fin.extracted_amount !== null && (
                            <div className="text-[11px] font-mono text-emerald-400">
                              Extracted: ₹{fin.extracted_amount.toLocaleString()}
                            </div>
                          )}
                        </div>
                      </div>

                      {fin.description && <p className="text-xs text-slate-400">{fin.description}</p>}

                      {/* Document Details & OCR Bar */}
                      <div className="pt-2 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-400">
                        <div>
                          <span className="text-slate-500">File: </span>
                          <span className="text-slate-300 truncate">{fin.original_filename}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">OCR: </span>
                          <span
                            className={`text-[11px] font-mono ${
                              fin.ocr_status === 'COMPLETED' ? 'text-emerald-400' : 'text-slate-400'
                            }`}
                          >
                            {fin.ocr_status}
                          </span>
                          <span className="text-[10px] text-slate-500 ml-1">(Mock Adapter)</span>
                        </div>
                        <div>
                          <span className="text-slate-500">Validation: </span>
                          <span
                            className={`text-[11px] font-mono ${
                              fin.validation_status === 'VALID'
                                ? 'text-emerald-400'
                                : 'text-amber-400 font-bold'
                            }`}
                          >
                            {fin.validation_status}
                          </span>
                        </div>
                      </div>

                      {/* Flags Banner */}
                      {fin.validation_flags && fin.validation_flags.length > 0 && (
                        <div className="text-[11px] text-rose-300 bg-rose-950/40 px-2.5 py-1 rounded border border-rose-800/50 flex items-center gap-2">
                          <span>⚠ Flags:</span>
                          <span>{fin.validation_flags.join(', ')}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 10-Point Verification Engine Tab ─────────────────────────── */}
        {activeTab === 'VERIFICATION' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Header & Quality Scorecard Card */}
            <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 border border-slate-800 shadow-xl space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-white tracking-wide">
                      Evidence Verification Scorecard
                    </h3>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 font-semibold">
                      10-Point Multi-Vector Engine
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 max-w-xl">
                    Independent telemetry verification across geospatial, chronological, perceptual visual,
                    cryptographic, EXIF, OCR, and ledger consistency checks.
                  </p>
                </div>

                <button
                  onClick={handleRunVerification}
                  disabled={verifying}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950/50 transition flex items-center gap-2 cursor-pointer"
                >
                  {verifying ? (
                    <>
                      <span className="animate-spin text-sm">⏳</span>
                      <span>Evaluating 10 Dimensions...</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Run Verification Engine</span>
                    </>
                  )}
                </button>
              </div>

              {loadingVerification ? (
                <div className="py-12 text-center text-slate-400 text-sm animate-pulse">
                  Analyzing verification telemetry across 10 checks...
                </div>
              ) : verificationReport ? (
                <>
                  {/* Score & Action Summary Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-800/80">
                    <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center gap-3.5">
                      <div
                        className={`w-14 h-14 rounded-xl flex items-center justify-center text-lg font-black font-mono border shadow-inner ${
                          verificationReport.overall_score >= 80
                            ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60'
                            : verificationReport.overall_score >= 50
                            ? 'bg-amber-950/80 text-amber-300 border-amber-700/60'
                            : 'bg-rose-950/80 text-rose-300 border-rose-700/60'
                        }`}
                      >
                        {verificationReport.overall_score.toFixed(0)}%
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                          Overall Quality Score
                        </div>
                        <div className="text-sm font-bold text-white mt-0.5">
                          {verificationReport.overall_quality.replace('_', ' ')}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {verificationReport.individual_checks.length} Checks Evaluated
                        </div>
                      </div>
                    </div>

                    <div className="sm:col-span-2 p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-center">
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                        Recommended Action
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`text-xs font-bold px-3 py-1 rounded-full border shadow-sm ${
                            ACTION_BADGES[verificationReport.recommended_action]?.style || ''
                          }`}
                        >
                          {ACTION_BADGES[verificationReport.recommended_action]?.label ||
                            verificationReport.recommended_action}
                        </span>
                        <span className="text-xs text-slate-400">
                          {ACTION_BADGES[verificationReport.recommended_action]?.desc}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Active Risk Flags Banner */}
                  {verificationReport.risk_flags.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 space-y-1.5">
                      <div className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                        <span>⚠ Detected Risk Signals ({verificationReport.risk_flags.length}):</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {verificationReport.risk_flags.map((flag) => (
                          <span
                            key={flag}
                            className="text-[11px] font-mono px-2 py-0.5 rounded bg-rose-900/60 text-rose-200 border border-rose-700/50"
                          >
                            {flag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Missing Evidence Banner */}
                  {verificationReport.missing_evidence.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/60 flex items-center justify-between gap-2">
                      <div className="text-xs text-amber-300">
                        <span className="font-bold">Missing Project Milestones: </span>
                        <span>{verificationReport.missing_evidence.join(', ')}</span>
                      </div>
                      <span className="text-[11px] text-amber-400 font-semibold">
                        Stage Incomplete
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <div className="py-8 text-center text-slate-400 text-sm">
                  Click "Run Verification Engine" above to trigger a 10-point audit evaluation.
                </div>
              )}
            </div>

            {/* 10 Independent Check Cards Grid */}
            {verificationReport && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Independent Verification Vectors ({verificationReport.individual_checks.length})
                  </h4>
                  <span className="text-[11px] text-slate-400">
                    Evaluated: {new Date(verificationReport.evaluated_at).toLocaleTimeString()}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {verificationReport.individual_checks.map((check) => (
                    <div
                      key={check.check_name}
                      className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 hover:border-slate-700/90 transition flex flex-col justify-between space-y-3 shadow-md"
                    >
                      {/* Card Header */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-base">{getCheckIcon(check.check_name)}</span>
                            <h5 className="text-xs font-bold text-white tracking-wide">
                              {check.check_name}
                            </h5>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase ${getCheckBadge(
                                check.status
                              )}`}
                            >
                              {check.status}
                            </span>
                            <span className="text-xs font-mono font-bold text-slate-300">
                              {check.score.toFixed(0)}/100
                            </span>
                          </div>
                        </div>

                        {/* Explanation */}
                        <p className="text-xs text-slate-300 leading-relaxed">
                          {check.explanation}
                        </p>
                      </div>

                      {/* Detail Metrics Breakdown */}
                      <div className="pt-2 border-t border-slate-900 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                        {check.check_name === 'LocationCheck' && (
                          <>
                            <span>
                              Distance:{' '}
                              <strong className="text-slate-200">
                                {check.details.distance_meters !== null && check.details.distance_meters !== undefined
                                  ? `${check.details.distance_meters}m`
                                  : 'N/A'}
                              </strong>
                            </span>
                            <span>
                              Geofence:{' '}
                              <strong className="text-slate-200">{check.details.geofence_radius}m</strong>
                            </span>
                            <span className="text-slate-500 text-[10px]">Site Coordinates (Excl. Office)</span>
                          </>
                        )}

                        {check.check_name === 'TimestampCheck' && (
                          <>
                            <span>
                              Items:{' '}
                              <strong className="text-slate-200">{check.details.evaluated_count ?? 0}</strong>
                            </span>
                            <span>
                              Violations:{' '}
                              <strong className="text-slate-200">{check.details.out_of_bounds_count ?? 0}</strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'TimelineCheck' && (
                          <>
                            <span>
                              Model: <strong className="text-slate-200">{check.details.verification_model}</strong>
                            </span>
                            <span>
                              Category: <strong className="text-slate-200">{check.details.project_category}</strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'DuplicateMediaCheck' && (
                          <>
                            <span>
                              Cross-Project Dupes:{' '}
                              <strong className="text-slate-200">
                                {check.details.cross_project_duplicate_count ?? 0}
                              </strong>
                            </span>
                            <span>
                              Internal Dupes:{' '}
                              <strong className="text-slate-200">{check.details.duplicate_count ?? 0}</strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'ImageSimilarityCheck' && (
                          <div className="w-full text-[10px] text-slate-400 bg-slate-900/70 p-1.5 rounded border border-slate-800/80">
                            {check.details.adapter_info?.notes ||
                              'Prototype adapter active. Different camera angles permitted.'}
                          </div>
                        )}

                        {check.check_name === 'MetadataCheck' && (
                          <>
                            <span>
                              Available:{' '}
                              <strong className="text-slate-200">{check.details.available_count ?? 0}</strong>
                            </span>
                            <span>
                              Missing (Not Fraud):{' '}
                              <strong className="text-slate-200">{check.details.missing_count ?? 0}</strong>
                            </span>
                            <span>
                              Suspicious:{' '}
                              <strong className="text-slate-200">{check.details.suspicious_count ?? 0}</strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'OCRCheck' && (
                          <>
                            <span>
                              Scanned Docs:{' '}
                              <strong className="text-slate-200">{check.details.scanned_documents ?? 0}</strong>
                            </span>
                            <span>
                              ID Mismatches:{' '}
                              <strong className="text-slate-200">
                                {check.details.project_id_mismatches?.length ?? 0}
                              </strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'FinancialConsistencyCheck' && (
                          <>
                            <span>
                              Claimed:{' '}
                              <strong className="text-slate-200">
                                ₹{check.details.claimed_total?.toLocaleString() ?? 0}
                              </strong>
                            </span>
                            <span>
                              Supported:{' '}
                              <strong className="text-slate-200">
                                ₹{check.details.supported_total?.toLocaleString() ?? 0}
                              </strong>
                            </span>
                            <span>
                              Variance:{' '}
                              <strong className="text-slate-200">
                                {check.details.difference_percentage ?? 0}%
                              </strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'ProjectIdentityCheck' && (
                          <>
                            <span>
                              Project Code:{' '}
                              <strong className="text-slate-200 font-mono">{check.details.project_code}</strong>
                            </span>
                            <span>
                              Verified Items:{' '}
                              <strong className="text-slate-200">{check.details.verified_items_count ?? 0}</strong>
                            </span>
                          </>
                        )}

                        {check.check_name === 'EvidenceCompletenessCheck' && (
                          <>
                            <span>
                              Ratio:{' '}
                              <strong className="text-slate-200 font-mono">
                                {check.details.completeness_ratio}
                              </strong>
                            </span>
                            <span>
                              Required:{' '}
                              <strong className="text-slate-200">
                                {check.details.required_stages?.join(', ')}
                              </strong>
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Milestone Upload Modal — Live In-App Camera Only */}
        {showUploadModal && (
          <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in">
              <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>📷</span> In-App Live Milestone Evidence Capture
                  </h3>
                  <p className="text-xs text-slate-400">
                    Project {project.project_code} · Direct hardware camera capture only. File uploads from disk are prohibited.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowUploadModal(false)
                    resetUploadForm()
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              {uploadError && (
                <div className="bg-rose-950/80 border-b border-rose-800/80 text-rose-300 px-5 py-2.5 text-xs">
                  {uploadError}
                </div>
              )}

              <div className="p-5 max-h-[82vh] overflow-y-auto space-y-4">
                {!file ? (
                  /* ── Step 1: Live Camera Viewfinder ── */
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Evidence Type *</label>
                        <select
                          value={evidenceType}
                          onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                        >
                          {EVIDENCE_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label} ({t.desc})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Evidence Title</label>
                        <input
                          type="text"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          placeholder="e.g. Foundation excavation milestone"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                        />
                      </div>
                    </div>

                    <LiveCameraEvidenceCapture
                      projectCode={project.project_code}
                      projectTitle={project.title}
                      milestoneType={evidenceType}
                      onCaptureComplete={handleEvidenceCaptured}
                      onCancel={() => {
                        setShowUploadModal(false)
                        resetUploadForm()
                      }}
                    />
                  </div>
                ) : (
                  /* ── Step 2: Review Captured Photo & Verified Telemetry ── */
                  <form onSubmit={handleUploadSubmit} className="space-y-4">
                    {/* Image Preview with Watermark */}
                    <div className="relative rounded-2xl overflow-hidden border-2 border-emerald-500 shadow-2xl bg-black">
                      {capturedPreviewUrl && (
                        <img
                          src={capturedPreviewUrl}
                          alt="Captured Project Milestone"
                          className="w-full h-auto max-h-[360px] object-contain mx-auto"
                        />
                      )}
                      <div className="absolute top-3 right-3 bg-emerald-950/90 border border-emerald-500 text-emerald-300 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 shadow-lg">
                        <span>✓</span> Live Camera Captured
                      </div>
                    </div>

                    {/* Verified Location & Timestamp Details */}
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                      <div className="text-xs font-bold text-white flex items-center gap-1.5">
                        <span className="text-emerald-400">🛡️</span> Verified In-Situ Telemetry (Stamped on Image)
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                        <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
                          <span className="text-[11px] text-slate-400">Real Geographic Location:</span>
                          <div className="font-mono font-bold text-emerald-300 flex items-center gap-1">
                            <span>📍</span>
                            {latitude !== undefined && longitude !== undefined
                              ? `${latitude.toFixed(6)}° N, ${longitude.toFixed(6)}° E`
                              : 'Location Unavailable'}
                          </div>
                          {gpsAccuracy !== undefined && (
                            <div className="text-[10px] text-slate-400">
                              Hardware Accuracy: ±{gpsAccuracy} meters
                            </div>
                          )}
                          {capturedLocationDisplay && (
                            <div className="text-[10px] text-slate-400 truncate">{capturedLocationDisplay}</div>
                          )}
                        </div>

                        <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
                          <span className="text-[11px] text-slate-400">Captured Date & Time:</span>
                          <div className="font-mono font-bold text-sky-300 flex items-center gap-1">
                            <span>🕒</span>
                            {capturedDateTimeDisplay || (capturedAt ? new Date(capturedAt).toLocaleString() : 'Just now')}
                          </div>
                          <div className="text-[10px] text-slate-400">
                            Source: <strong>Direct App Camera (No File Upload)</strong>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Evidence Title *</label>
                        <input
                          type="text"
                          required
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          placeholder="e.g. Drilling rig foundation test"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">Milestone Stage *</label>
                        <select
                          value={evidenceType}
                          onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                        >
                          {EVIDENCE_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label} ({t.desc})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Detailed Notes / Observations
                      </label>
                      <textarea
                        rows={2}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Specify depth, serial numbers, community attendance..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                      />
                    </div>

                    <div className="pt-2 border-t border-slate-800 space-y-2">
                      <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                        <input
                          type="checkbox"
                          checked={isRevision}
                          onChange={(e) => setIsRevision(e.target.checked)}
                          className="rounded border-slate-700 bg-slate-950 text-teal-600 focus:ring-teal-500"
                        />
                        <span>Is this a corrected file replacement?</span>
                      </label>

                      {isRevision && (
                        <div>
                          <select
                            value={supersedesId}
                            onChange={(e) => setSupersedesId(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-teal-500 focus:outline-none"
                          >
                            <option value="">-- Choose existing evidence --</option>
                            {timelineData?.timeline.map((it) => (
                              <option key={it.id} value={it.id}>
                                [{it.evidence_type}] {it.title} ({it.original_filename})
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>

                    <div className="pt-4 flex justify-between items-center border-t border-slate-800">
                      <button
                        type="button"
                        onClick={() => {
                          if (capturedPreviewUrl) URL.revokeObjectURL(capturedPreviewUrl)
                          setFile(null)
                          setCapturedPreviewUrl(null)
                        }}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-rose-300 hover:text-rose-200 transition flex items-center gap-1.5"
                      >
                        <span>🔄</span> Retake Photo
                      </button>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setShowUploadModal(false)
                            resetUploadForm()
                          }}
                          className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={uploading}
                          className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-semibold text-white shadow transition flex items-center gap-1.5"
                        >
                          <span>✓</span>
                          <span>{uploading ? 'Registering...' : 'Upload & Register'}</span>
                        </button>
                      </div>
                    </div>
                  </form>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Financial Upload Modal */}
        {showFinUploadModal && (
          <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in">
              <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white">Upload Financial Document</h3>
                  <p className="text-xs text-slate-400">
                    Expenditure claim document for Project {project.project_code}
                  </p>
                </div>
                <button onClick={() => setShowFinUploadModal(false)} className="text-slate-400 hover:text-white">
                  ✕
                </button>
              </div>

              {finUploadError && (
                <div className="bg-rose-950/80 border-b border-rose-800/80 text-rose-300 px-5 py-2.5 text-xs">
                  {finUploadError}
                </div>
              )}

              <form onSubmit={handleFinancialUploadSubmit} className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Invoice / Bill Document File * (PDF, Images, CSV, XLSX)
                  </label>
                  <input
                    type="file"
                    required
                    onChange={(e) => setFinFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-600 file:text-white hover:file:bg-cyan-500 cursor-pointer bg-slate-950 p-1.5 rounded-lg border border-slate-800"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Claimed Amount (INR) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={claimedAmount}
                      onChange={(e) => setClaimedAmount(e.target.value)}
                      placeholder="e.g. 45000"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Document Type *</label>
                    <select
                      value={finDocType}
                      onChange={(e) => setFinDocType(e.target.value as FinancialDocumentType)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                    >
                      {FINANCIAL_DOC_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Vendor / Supplier</label>
                    <input
                      type="text"
                      value={vendorName}
                      onChange={(e) => setVendorName(e.target.value)}
                      placeholder="e.g. Apex Construction Supplies"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Invoice / Bill #</label>
                    <input
                      type="text"
                      value={invoiceNumber}
                      onChange={(e) => setInvoiceNumber(e.target.value)}
                      placeholder="e.g. INV-2026-0042"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Document Date</label>
                  <input
                    type="date"
                    value={documentDate}
                    onChange={(e) => setDocumentDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Expense Description</label>
                  <textarea
                    rows={2}
                    value={finDescription}
                    onChange={(e) => setFinDescription(e.target.value)}
                    placeholder="Brief description of items or labor procured..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                <p className="text-[10px] text-slate-500 bg-slate-950 p-2 rounded border border-slate-800">
                  ℹ Document will be processed via the OCR service abstraction to extract and verify amounts.
                  Supporting documents do not automatically prove honesty; they establish transparent claims for verification.
                </p>

                <div className="pt-4 flex justify-end gap-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowFinUploadModal(false)}
                    className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={finUploading}
                    className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-xs font-semibold text-white shadow transition"
                  >
                    {finUploading ? 'Processing OCR & Checking...' : 'Upload & Verify'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
