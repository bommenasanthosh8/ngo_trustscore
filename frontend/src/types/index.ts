/**
 * Shared TypeScript types mirroring backend Pydantic schemas.
 * Keep in sync with backend/app/auth/schemas.py and backend/app/projects/schemas.py
 */

// ── Roles ─────────────────────────────────────────────────────────────────────
export type UserRole = 'NGO' | 'DONOR' | 'AUDITOR' | 'ADMIN'

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface UserProfile {
  id: string
  email: string
  full_name: string
  role: UserRole
  ngo_id?: string
  organization_name?: string
  is_active: boolean
  is_verified: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  role: UserRole
  organization_name?: string
  registration_number?: string
  description?: string
  address?: string
  contact_phone?: string
  website?: string
  authorized_representative?: string
}

// ── NGO Onboarding & Verification ─────────────────────────────────────────────
export type NGOVerificationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED'

export interface NGOResponse {
  id: string
  name: string
  registration_number: string
  darpan_id?: string
  description?: string
  address?: string
  contact_email?: string
  contact_phone?: string
  website?: string
  authorized_representative?: string
  verification_status: NGOVerificationStatus
  is_verified: boolean
  rejection_reason?: string
  verified_at?: string
  created_at: string
  updated_at: string
}

export interface CreateNGORequest {
  name: string
  registration_number: string
  description?: string
  address?: string
  contact_email?: string
  contact_phone?: string
  website?: string
  authorized_representative?: string
}

export interface UpdateNGORequest {
  name?: string
  description?: string
  address?: string
  contact_email?: string
  contact_phone?: string
  website?: string
  authorized_representative?: string
}

// ── Projects ──────────────────────────────────────────────────────────────────
export type ProjectType =
  | 'WATER_AND_SANITATION'
  | 'EDUCATION'
  | 'HEALTHCARE'
  | 'INFRASTRUCTURE'
  | 'FOOD_DISTRIBUTION'
  | 'ENVIRONMENT'
  | 'RELIEF_DISTRIBUTION'
  | 'SANITATION'
  | 'OTHER'

export type ProjectStatus =
  | 'CREATED'
  | 'FUNDING'
  | 'EVIDENCE_COLLECTION'
  | 'UNDER_VERIFICATION'
  | 'VERIFIED'
  | 'PARTIALLY_VERIFIED'
  | 'PENDING'
  | 'DISPUTED'

export type VerificationModel =
  | 'PERMANENT'
  | 'ONE_TIME_EVENT'
  | 'FINANCIAL_ASSISTANCE'

export interface ProjectLocationInput {
  location_name: string
  latitude: number
  longitude: number
  geofence_radius: number
  gps_accuracy?: number
  selection_method?: string
}

export interface CreateProjectRequest {
  name: string
  category: ProjectType
  description?: string
  target_amount: number
  expected_beneficiaries?: number
  start_date?: string
  expected_completion_date?: string
  location: ProjectLocationInput
  expected_outcome?: string
  verification_model?: VerificationModel
}

export interface UpdateProjectRequest {
  name?: string
  category?: ProjectType
  description?: string
  target_amount?: number
  expected_beneficiaries?: number
  start_date?: string
  expected_completion_date?: string
  location?: ProjectLocationInput
  expected_outcome?: string
  status?: ProjectStatus
}

export interface ProjectDetail {
  id: string
  project_code: string
  title: string
  category: ProjectType
  description?: string
  verification_model: VerificationModel
  status: ProjectStatus
  target_amount?: number
  total_budget?: number
  currency: string
  expected_beneficiaries?: number
  expected_outcome?: string
  location_name?: string
  latitude?: number
  longitude?: number
  approximate_latitude?: number
  approximate_longitude?: number
  is_sensitive?: boolean
  ngo_name?: string
  risk_level?: string
  geofence_radius: number
  gps_accuracy?: number
  start_date?: string
  expected_completion_date?: string
  evidence_score?: number
  ngo_id: string
  created_by_id: string
  created_at: string
  updated_at: string
}


export interface ProjectSummary {
  id: string
  project_code: string
  title: string
  category: ProjectType
  verification_model: VerificationModel
  status: ProjectStatus
  location_name?: string
  latitude?: number
  longitude?: number
  geofence_radius: number
  target_amount?: number
  currency: string
  expected_beneficiaries?: number
  evidence_score?: number
  start_date?: string
  expected_completion_date?: string
  created_at: string
}

export interface LocationSearchResult {
  location_name: string
  display_name: string
  latitude: number
  longitude: number
  state?: string
  country: string
}

// ── Evidence Collection ────────────────────────────────────────────────────────
export type EvidenceType =
  | 'BEFORE'
  | 'PROGRESS'
  | 'COMPLETION'
  | 'EVENT'
  | 'FINANCIAL'
  | 'OTHER'

export type LocationStatus = 'CAPTURED' | 'LOCATION_UNAVAILABLE'

export interface Evidence {
  id: string
  project_id: string
  submitted_by_id: string
  uploader?: {
    id: string
    email: string
    full_name: string
    role: string
  }
  evidence_type: EvidenceType
  title: string
  description?: string
  storage_key: string
  original_filename: string
  mime_type: string
  file_size: number
  file_hash_sha256: string
  captured_at?: string
  uploaded_at: string
  created_at: string
  latitude?: number
  longitude?: number
  gps_accuracy?: number
  location_status: LocationStatus
  metadata_summary?: Record<string, any>
  supersedes_id?: string
  verification_status: 'PENDING' | 'VERIFIED' | 'FLAGGED' | 'REJECTED'
}

export interface EvidenceTimelineItem {
  id: string
  title: string
  evidence_type: EvidenceType
  description?: string
  original_filename: string
  file_hash_sha256: string
  captured_at?: string
  uploaded_at: string
  effective_timestamp: string
  location_status: LocationStatus
  latitude?: number
  longitude?: number
  gps_accuracy?: number
  verification_status: 'PENDING' | 'VERIFIED' | 'FLAGGED' | 'REJECTED'
  supersedes_id?: string
  is_revision: boolean
  uploader_name?: string
}

export interface EvidenceTimelineResponse {
  project_id: string
  project_title: string
  timeline: EvidenceTimelineItem[]
  milestone_summary: Record<string, number>
}

export type EvidenceResponse = Evidence

export interface EvidenceListResponse {
  items: Evidence[]
  total: number
  project_id: string
}

// ── Financial Evidence & Consistency ──────────────────────────────────────────
export type FinancialDocumentType =
  | 'INVOICE'
  | 'BILL'
  | 'RECEIPT'
  | 'EXPENSE_STATEMENT'
  | 'TRANSACTION_RECORD'
  | 'OTHER'

export type OCRStatus =
  | 'PENDING'
  | 'COMPLETED'
  | 'FAILED'
  | 'UNSUPPORTED_FORMAT'
  | 'SKIPPED'

export type FinancialValidationStatus =
  | 'VALID'
  | 'AMOUNT_MISMATCH'
  | 'DUPLICATE_DOCUMENT'
  | 'SUSPICIOUS_REPEATED'
  | 'PENDING'

export type FinancialConsistencyStatus =
  | 'CONSISTENT'
  | 'MINOR_DISCREPANCY'
  | 'MAJOR_DISCREPANCY'
  | 'INSUFFICIENT_EVIDENCE'

export interface FinancialEvidence {
  id: string
  project_id: string
  submitted_by_id: string
  uploader?: {
    id: string
    email: string
    full_name: string
    role: string
  }
  document_type: FinancialDocumentType
  claimed_amount: number
  extracted_amount?: number
  currency: string
  document_date?: string
  vendor_name?: string
  description?: string
  invoice_number?: string
  storage_key: string
  original_filename: string
  mime_type: string
  file_size: number
  document_hash: string
  ocr_status: OCRStatus
  ocr_engine?: string
  ocr_metadata?: Record<string, any>
  validation_status: FinancialValidationStatus
  validation_flags?: string[]
  verification_status: 'PENDING' | 'VERIFIED' | 'FLAGGED' | 'REJECTED'
  uploaded_at: string
  created_at: string
}

export interface FinancialConsistencyReport {
  project_id: string
  project_target_amount: number
  claimed_total: number
  supported_total: number
  difference: number
  difference_percentage: number
  status: FinancialConsistencyStatus
  flags: string[]
  items_count: number
  summary_notes: string
}

export interface ProjectFinancialEvidenceListResponse {
  project_id: string
  items: FinancialEvidence[]
  consistency_report: FinancialConsistencyReport
  total: number
}

// ── Verification Engine Types ───────────────────────────────────────────────
export type RecommendedAction = 'NO_ADDITIONAL_ACTION' | 'MANUAL_REVIEW' | 'AUDIT_RECOMMENDED'

export interface VerificationCheckResult {
  check_name: string
  status: string
  score: number
  explanation: string
  risk_flags: string[]
  details: Record<string, any>
}

export interface VerificationReport {
  project_id: string
  project_code: string
  overall_score: number
  overall_quality: 'HIGH_QUALITY' | 'MEDIUM_QUALITY' | 'LOW_QUALITY'
  recommended_action: RecommendedAction
  risk_flags: string[]
  missing_evidence: string[]
  individual_checks: VerificationCheckResult[]
  evaluated_at: string
  evidence_count: number
  financial_evidence_count: number
  target_evidence_id?: string
}


// ── Risk Assessment Engine Types ───────────────────────────────────────────
export interface RiskSignalResult {
  signal_name: string
  triggered: boolean
  weight: number
  score_contribution: number
  explanation?: string
  details: Record<string, any>
}

export interface AuditTriggerInfo {
  audit_recommended: boolean
  triggers: string[]
  trigger_reasons: string[]
}

export interface RiskAssessmentResponse {
  project_id: string
  project_code: string
  risk_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  reasons: string[]
  signals: RiskSignalResult[]
  audit_trigger: AuditTriggerInfo
  assessed_at: string
  factors_summary: Record<string, any>
}


// ── API Response envelopes ────────────────────────────────────────────────────
export interface APIResponse<T> {
  success: boolean
  data?: T
  message?: string
}

export interface APIErrorResponse {
  success: false
  error: string
  details?: { field?: string; message: string }[]
}

// ── Independent Audit Module Types ──────────────────────────────────────────
export type AuditDecisionType = 'CONFIRMED' | 'PARTIALLY_CONFIRMED' | 'REJECTED' | 'DISCREPANCY'
export type AuditStatus = 'INITIATED' | 'IN_PROGRESS' | 'COMPLETED' | 'DISPUTED'
export type AuditSelectionReason = 'HIGH_RISK' | 'HIGH_VALUE' | 'RANDOM_SAMPLE' | 'MANUAL_ASSIGNMENT'
export type DisputeStatus = 'OPEN' | 'UNDER_REVIEW' | 'RESOLVED' | 'REJECTED'

export interface AuditSummary {
  id: string
  project_id: string
  project_code: string
  project_title: string
  ngo_id?: string
  ngo_name?: string
  selection_reason: AuditSelectionReason
  status: AuditStatus
  assigned_auditor_id?: string
  auditor_id?: string
  auditor_name?: string
  project_category?: string
  project_status?: string
  target_amount?: number
  total_budget?: number
  risk_score?: number
  risk_level?: string
  created_at: string
  latest_decision?: AuditDecisionType
}

export interface AuditDecision {
  id: string
  audit_id: string
  decision: AuditDecisionType
  findings: string
  notes?: string
  supporting_evidence?: Record<string, any>[] | Record<string, any> | null
  is_superseded: boolean
  superseded_by_id?: string | null
  decided_by_id?: string | null
  decided_by_name?: string
  decided_at: string
}

export interface AuditDossier {
  audit_id: string
  status: AuditStatus
  selection_reason: AuditSelectionReason
  scope?: string
  assigned_auditor_id?: string
  project_id: string
  project_code: string
  project_title: string
  project_category: string
  project_status: string
  verification_model: string
  location_name?: string
  latitude?: number
  longitude?: number
  geofence_radius: number
  ngo_id: string
  ngo_name: string
  target_amount: number
  total_budget: number
  expected_beneficiaries: number
  project_description?: string
  start_date?: string
  expected_completion_date?: string
  evidence_timeline: Record<string, any>[]
  financial_evidence: Record<string, any>[]
  financial_consistency?: Record<string, any> | null
  verification_report?: Record<string, any> | null
  risk_assessment?: Record<string, any> | null
  evidence_score?: number | null
  evidence_score_status?: string | null
  evidence_score_breakdown?: Record<string, any> | null
  decisions_history: AuditDecision[]
  disputes: Dispute[]
  integrity_report?: ProjectIntegrityReport | null
}

// ── Prototype Anti-Manipulation & Integrity Types ────────────────────────────
export interface IntegrityFlagItem {
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  explanation: string
  signal_code: string
}

export interface ThreatEvaluation {
  threat_number: number
  threat_name: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  triggered: boolean
  status: 'CLEAR' | 'WARNING' | 'FLAGGED'
  explanation: string
  is_probabilistic_signal: boolean
  disclaimer?: string | null
  details?: Record<string, any>
}

export interface SubmissionAttemptSummary {
  total_submissions: number
  verified_count: number
  failed_count: number
  duplicate_count: number
  revisions_count: number
  superseded_count: number
}

export interface ProjectIntegrityReport {
  project_id: string
  project_code: string
  project_title: string
  overall_risk_level: string
  risk_score: number
  audit_recommended: boolean
  active_flags: IntegrityFlagItem[]
  threats_matrix: ThreatEvaluation[]
  submission_history: SubmissionAttemptSummary
  disclaimers: string[]
}

export interface Dispute {
  id: string
  project_id: string
  project_code?: string
  raised_by_id: string
  reason: string
  status: DisputeStatus
  resolution_notes?: string
  created_at: string
}

export interface AuditDecisionCreateRequest {
  decision: AuditDecisionType
  findings: string
  notes?: string
  supporting_evidence?: Record<string, any>[]
}

export interface CreateDisputeRequest {
  reason: string
  supporting_notes?: string
}

export interface ResolveDisputeRequest {
  action: 'UPHOLD_DECISION' | 'REVISE_DECISION' | 'SCHEDULE_REAUDIT'
  resolution_notes: string
  revised_decision?: AuditDecisionType
  revised_findings?: string
}

// ── Project Evidence Score Engine Types ─────────────────────────────────────
export type ScoreStatus = 'STRONG_EVIDENCE' | 'GOOD_EVIDENCE' | 'LIMITED_EVIDENCE' | 'WEAK_EVIDENCE'

export interface ScoreFactorResult {
  factor_name: string
  earned_points: number
  maximum_points: number
  percentage: number
  explanation: string
  source_verification_results: Record<string, any>
}

export interface ProjectScoreResponse {
  project_id: string
  project_code: string
  project_title: string
  final_score: number
  status: ScoreStatus
  is_disputed: boolean
  dispute_status?: DisputeStatus | null
  explanation: string
  factors: {
    location_consistency: ScoreFactorResult
    timeline_timestamp: ScoreFactorResult
    media_evidence: ScoreFactorResult
    financial_evidence: ScoreFactorResult
    project_identity: ScoreFactorResult
    independent_audit: ScoreFactorResult
    [key: string]: ScoreFactorResult
  }
  calculated_at: string
}

// ── NGO Transparency Score Engine Types ─────────────────────────────────────
export type HistoricalTrend = 'IMPROVING' | 'STABLE' | 'DECLINING' | 'INSUFFICIENT_DATA'

export interface NGOTransparencyFactor {
  factor_name: string
  weight: number
  raw_score: number
  weighted_score: number
  explanation: string
  details: Record<string, any>
}

export interface NGOTransparencyScoreResponse {
  ngo_id: string
  ngo_name: string
  final_score: number
  indicator_description: string
  project_count: number
  verified_count: number
  partially_verified_count: number
  pending_count: number
  disputed_count: number
  weighted_evidence_quality: number
  audit_performance: number
  historical_trend: HistoricalTrend | string
  explanation: string[]
  factors: {
    evidence_quality: NGOTransparencyFactor
    value_verification: NGOTransparencyFactor
    audit_performance: NGOTransparencyFactor
    dispute_impact: NGOTransparencyFactor
    historical_trend: NGOTransparencyFactor
    [key: string]: NGOTransparencyFactor
  }
  calculated_at: string
  snapshot_id?: string | null
}

export interface NGOScoreSnapshotResponse {
  id: string
  ngo_id: string
  composite_score: number
  breakdown?: Record<string, any> | null
  calculated_at: string
}

// ── Public Transparency Experience Types ─────────────────────────────────────
export interface PublicPlatformStats {
  total_ngos: number
  verified_ngos: number
  total_projects: number
  verified_projects: number
  total_funding_tracked: number
  average_transparency_score: number
  total_evidence_items: number
}

export interface PublicMapPoint {
  id: string
  project_code: string
  title: string
  category: ProjectType | string
  status: ProjectStatus | string
  target_amount: number
  currency: string
  evidence_score?: number | null
  risk_level: string
  ngo_id: string
  ngo_name: string
  location_name: string
  latitude: number
  longitude: number
  is_sensitive: boolean
}

export interface VerificationCheckSummaryItem {
  title: string
  passed: boolean
  status: string
  explanation: string
}

export interface ProjectVerificationSummary {
  project_id: string
  project_code: string
  title: string
  evidence_score?: number | null
  checklist: VerificationCheckSummaryItem[]
  overall_status: string
}

export interface NGOPublicSummary {
  id: string
  name: string
  registration_number: string
  description?: string | null
  address?: string | null
  website?: string | null
  verification_status: NGOVerificationStatus
  is_verified: boolean
  project_count: number
  verified_project_count: number
  transparency_score?: number | null
  project_categories: string[]
  created_at: string
}

// ── Project Audit & Decisions ──────────────────────────────────────────
export interface ProjectAuditDecisionItem {
  id: string
  decision: 'CONFIRMED' | 'PARTIALLY_CONFIRMED' | 'REJECTED' | 'DISCREPANCY' | string
  notes?: string | null
  findings?: string | null
  decided_at?: string | null
}

export interface ProjectAuditItem {
  id: string
  project_id: string
  selection_reason: 'HIGH_RISK' | 'HIGH_VALUE' | 'RANDOM_SAMPLE' | string
  status: 'INITIATED' | 'IN_PROGRESS' | 'COMPLETED' | 'DISPUTED' | string
  scope?: string | null
  findings?: string | null
  created_at?: string | null
  decisions: ProjectAuditDecisionItem[]
}

export interface ProjectDisputeItem {
  id: string
  project_id: string
  reason: string
  status: 'PENDING' | 'UNDER_REVIEW' | 'RESOLVED' | 'DISMISSED' | string
  created_at?: string | null
  resolution_notes?: string | null
}

export interface ProjectRiskSignal {
  signal_name: string
  score_penalty: number
  triggered: boolean
  explanation: string
}

export interface ProjectRiskReport {
  project_id: string
  project_code?: string
  risk_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string
  audit_recommended: boolean
  narrative_reasons: string[]
  risk_factors?: Record<string, any>
  signals?: ProjectRiskSignal[]
  evaluated_at?: string
}

// ── Auditor & Admin Operations Types ──────────────────────────────────────────
export interface AuditQueueGroup {
  pending_audits: AuditSummary[]
  high_risk: AuditSummary[]
  high_value: AuditSummary[]
  random_queue: AuditSummary[]
  disputed: AuditSummary[]
  recently_verified: AuditSummary[]
  counts: Record<string, number>
}

export interface AuditConfig {
  high_project_value_threshold: number
  audit_random_sample_rate: number
  high_risk_threshold: number
  auto_audit_enabled: boolean
  scoring_weights: Record<string, number>
  updated_at?: string | null
}

export interface AdminDisputeItem {
  id: string
  project_id: string
  project_code?: string | null
  project_title?: string | null
  ngo_name?: string | null
  raised_by_id: string
  raised_by_email?: string | null
  reason: string
  status: string
  resolution_notes?: string | null
  created_at: string
}

export interface ActivityLogItem {
  id: string
  action: string
  actor_id?: string | null
  actor_role?: string | null
  actor_email?: string | null
  resource_type?: string | null
  resource_id?: string | null
  detail?: Record<string, any> | null
  success: boolean
  ip_address?: string | null
  created_at: string
}

export interface SystemStats {
  ngos: Record<string, number>
  projects: Record<string, number>
  audits: Record<string, number>
  disputes: Record<string, number>
  total_funding_volume: number
  avg_transparency_score: number
  generated_at: string
}
