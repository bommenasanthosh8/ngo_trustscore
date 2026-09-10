import { useState, useEffect, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import MapLocationPicker from '@/components/projects/MapLocationPicker'
import { projectsApi } from '@/api/projects'
import type {
  CreateProjectRequest,
  ProjectDetail,
  ProjectLocationInput,
  ProjectStatus,
  ProjectType,
} from '@/types'

const CATEGORIES: { value: ProjectType | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'All Sectors' },
  { value: 'WATER_AND_SANITATION', label: 'Water & Sanitation' },
  { value: 'EDUCATION', label: 'Education' },
  { value: 'HEALTHCARE', label: 'Healthcare' },
  { value: 'INFRASTRUCTURE', label: 'Infrastructure' },
  { value: 'FOOD_DISTRIBUTION', label: 'Food Distribution' },
  { value: 'ENVIRONMENT', label: 'Environment' },
  { value: 'RELIEF_DISTRIBUTION', label: 'Disaster Relief' },
]

const STATUSES: { value: ProjectStatus | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'All Statuses' },
  { value: 'CREATED', label: 'Created' },
  { value: 'FUNDING', label: 'Funding' },
  { value: 'EVIDENCE_COLLECTION', label: 'Evidence Collection' },
  { value: 'UNDER_VERIFICATION', label: 'Under Verification' },
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'PARTIALLY_VERIFIED', label: 'Partially Verified' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'DISPUTED', label: 'Disputed' },
]

const STATUS_COLORS: Record<ProjectStatus, string> = {
  CREATED: 'bg-purple-950/60 border-purple-700/50 text-purple-300',
  FUNDING: 'bg-blue-950/60 border-blue-700/50 text-blue-300',
  EVIDENCE_COLLECTION: 'bg-cyan-950/60 border-cyan-700/50 text-cyan-300',
  UNDER_VERIFICATION: 'bg-amber-950/60 border-amber-700/50 text-amber-300',
  VERIFIED: 'bg-emerald-950/60 border-emerald-700/50 text-emerald-300',
  PARTIALLY_VERIFIED: 'bg-teal-950/60 border-teal-700/50 text-teal-300',
  PENDING: 'bg-amber-950/60 border-amber-700/50 text-amber-300',
  DISPUTED: 'bg-rose-950/60 border-rose-700/50 text-rose-300',
}

const DEFAULT_LOCATION: ProjectLocationInput = {
  location_name: '',
  latitude: 0,
  longitude: 0,
  geofence_radius: 500,
  selection_method: 'GPS_DEVICE',
}

export default function Projects() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState<ProjectType | 'ALL'>('ALL')
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | 'ALL'>('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formSubmitting, setFormSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  // Project Form State
  const [name, setName] = useState('')
  const [category, setCategory] = useState<ProjectType>('WATER_AND_SANITATION')
  const [description, setDescription] = useState('')
  const [targetAmount, setTargetAmount] = useState('')
  const [beneficiaries, setBeneficiaries] = useState('')
  const [expectedOutcome, setExpectedOutcome] = useState('')
  const [startDate, setStartDate] = useState('')
  const [completionDate, setCompletionDate] = useState('')
  const [location, setLocation] = useState<ProjectLocationInput>(DEFAULT_LOCATION)

  useEffect(() => {
    fetchProjects()
  }, [categoryFilter, statusFilter])

  function fetchProjects() {
    setLoading(true)
    projectsApi
      .list({
        category: categoryFilter !== 'ALL' ? categoryFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        search: searchTerm.trim() || undefined,
      })
      .then((res) => {
        if (res.data.success && res.data.data) {
          setProjects(res.data.data)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault()
    fetchProjects()
  }

  async function handleCreateProject(e: FormEvent) {
    e.preventDefault()
    setFormError(null)

    if (!name.trim()) {
      setFormError('Please enter a project title.')
      return
    }

    if (!location.location_name.trim()) {
      setFormError('Please select or specify a project site location name.')
      return
    }

    if (!location.latitude || !location.longitude || location.latitude === 0) {
      setFormError('Please pinpoint valid non-zero GPS coordinates for the project site.')
      return
    }

    setFormSubmitting(true)
    try {
      const payload: CreateProjectRequest = {
        name: name.trim(),
        category,
        description: description.trim() || undefined,
        target_amount: parseFloat(targetAmount) || 100000,
        expected_beneficiaries: beneficiaries ? parseInt(beneficiaries, 10) : undefined,
        expected_outcome: expectedOutcome.trim() || undefined,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        expected_completion_date: completionDate ? new Date(completionDate).toISOString() : undefined,
        location,
      }

      const res = await projectsApi.create(payload)
      if (res.data.success && res.data.data) {
        setActionMessage(`Project "${res.data.data.title}" [${res.data.data.project_code}] created in CREATED state!`)
        setShowCreateModal(false)
        resetForm()
        fetchProjects()
      }
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: {
          data?: {
            error?: string
            message?: string
            detail?: string | Array<{ msg?: string }>
          }
        }
      }
      const data = axiosErr.response?.data
      let message = 'Failed to create project. Please check form values.'
      if (data?.error) message = data.error
      else if (data?.message) message = data.message
      else if (typeof data?.detail === 'string') message = data.detail
      else if (Array.isArray(data?.detail) && data.detail[0]?.msg) message = data.detail[0].msg

      setFormError(message)
    } finally {
      setFormSubmitting(false)
    }
  }

  function resetForm() {
    setName('')
    setCategory('WATER_AND_SANITATION')
    setDescription('')
    setTargetAmount('')
    setBeneficiaries('')
    setExpectedOutcome('')
    setStartDate('')
    setCompletionDate('')
    setLocation(DEFAULT_LOCATION)
    setFormError(null)
  }

  const canCreate = user && (user.role === 'NGO' || user.role === 'ADMIN')

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />

        <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-6">
          {/* Official Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Projects Directory</h1>
              <p className="text-slate-400 text-sm mt-0.5">
                Official registry of registered NGO projects, milestone tracking, and verified field sites.
              </p>
            </div>
            {canCreate && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn-primary flex items-center gap-2"
              >
                <span>+</span> Create Project
              </button>
            )}
          </div>

          {actionMessage && (
            <div className="p-3.5 rounded-xl bg-brand-950/60 border border-brand-700/50 text-brand-300 text-sm flex items-center justify-between">
              <span>{actionMessage}</span>
              <button onClick={() => setActionMessage(null)} className="text-xs text-brand-400 hover:text-white">
                Dismiss
              </button>
            </div>
          )}

          {/* Unified Official Filter Toolbar */}
          <div className="glass-card p-4">
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
              <form onSubmit={handleSearchSubmit} className="sm:col-span-6 flex gap-2">
                <input
                  type="text"
                  placeholder="Search projects by title, code, or location..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="input-field text-sm"
                />
                <button type="submit" className="btn-secondary text-sm px-4">
                  Search
                </button>
              </form>

              <div className="sm:col-span-3">
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value as ProjectType | 'ALL')}
                  className="input-field text-sm w-full cursor-pointer"
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sm:col-span-3">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as ProjectStatus | 'ALL')}
                  className="input-field text-sm w-full cursor-pointer"
                >
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Projects Grid */}
          {loading ? (
            <div className="py-12 text-center text-slate-400 animate-pulse">Loading projects…</div>
          ) : projects.length === 0 ? (
            <div className="glass-card p-12 text-center space-y-3">
              <span className="text-3xl block">🔍</span>
              <h3 className="text-base font-semibold text-white">No projects found</h3>
              <p className="text-sm text-slate-400">
                Try adjusting your search filters or register a new project.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((proj) => (
                <div
                  key={proj.id}
                  className="glass-card p-5 flex flex-col justify-between space-y-4 hover:border-brand-500/40 transition-all duration-200"
                >
                  <div className="space-y-3">
                    {/* Project Code & Status */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-brand-400 border border-slate-700">
                        {proj.project_code}
                      </span>
                      <span
                        className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                          STATUS_COLORS[proj.status] || 'text-slate-300'
                        }`}
                      >
                        {proj.status.replace(/_/g, ' ')}
                      </span>
                    </div>

                    {/* Title & Category */}
                    <div>
                      <h3 className="text-base font-semibold text-white line-clamp-1">{proj.title}</h3>
                      <span className="text-xs text-brand-300/80 font-medium">
                        {proj.category.replace(/_/g, ' ')}
                      </span>
                    </div>

                    {proj.description && (
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">{proj.description}</p>
                    )}

                    {/* Location Site */}
                    {proj.location_name && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                        <span>📍</span>
                        <span className="truncate flex-1">{proj.location_name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          (±{proj.geofence_radius}m)
                        </span>
                      </div>
                    )}

                    {/* Target Budget & Beneficiaries */}
                    <div className="grid grid-cols-2 gap-2 pt-1 text-xs border-t border-surface-border/50">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Target Budget</span>
                        <span className="text-white font-medium">
                          {proj.currency} {(proj.target_amount || proj.total_budget || 0).toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Beneficiaries</span>
                        <span className="text-white font-medium">
                          {proj.expected_beneficiaries ? proj.expected_beneficiaries.toLocaleString() : '—'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Primary Official Action */}
                  <div className="pt-2 border-t border-surface-border/40">
                    <Link
                      to={`/projects/${proj.id}`}
                      className="w-full py-2 px-3 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-sm"
                    >
                      <span>View Details & Milestones</span>
                      <span>→</span>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* ── Create Project Modal ────────────────────────────────────── */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto">
          <div className="relative w-full max-w-2xl rounded-2xl bg-surface-card border border-surface-border p-6 shadow-2xl space-y-5 my-8">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div>
                <h2 className="text-lg font-bold text-white">Create New Project</h2>
                <p className="text-xs text-slate-400">
                  Register project site with PostGIS geofenced coordinates.
                </p>
              </div>
              <button
                onClick={() => { setShowCreateModal(false); resetForm(); }}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-xl bg-red-950/60 border border-red-700/50 text-red-300 text-xs">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="form-label">Project Name / Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Rampur Solar Borewell & Community Water Center"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-field text-sm"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="form-label">Category / Sector *</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value as ProjectType)}
                    className="input-field text-sm cursor-pointer"
                  >
                    {CATEGORIES.filter((c) => c.value !== 'ALL').map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Target Funding Amount (INR) *</label>
                  <input
                    type="number"
                    min="1000"
                    required
                    placeholder="e.g. 500000"
                    value={targetAmount}
                    onChange={(e) => setTargetAmount(e.target.value)}
                    className="input-field text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="form-label">Description</label>
                <textarea
                  rows={2}
                  placeholder="Comprehensive details on project scope, activities, and implementation plan"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="input-field text-sm resize-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="form-label">Expected Beneficiaries</label>
                  <input
                    type="number"
                    min="0"
                    placeholder="e.g. 1500"
                    value={beneficiaries}
                    onChange={(e) => setBeneficiaries(e.target.value)}
                    className="input-field text-sm"
                  />
                </div>
                <div>
                  <label className="form-label">Expected Measurable Outcome</label>
                  <input
                    type="text"
                    placeholder="e.g. 20,000L/day potable water supply"
                    value={expectedOutcome}
                    onChange={(e) => setExpectedOutcome(e.target.value)}
                    className="input-field text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="form-label">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="input-field text-sm"
                  />
                </div>
                <div>
                  <label className="form-label">Expected Completion Date</label>
                  <input
                    type="date"
                    value={completionDate}
                    onChange={(e) => setCompletionDate(e.target.value)}
                    className="input-field text-sm"
                  />
                </div>
              </div>

              {/* ── Map Selection Component ─────────────────────────── */}
              <div className="pt-2 border-t border-surface-border">
                <label className="form-label mb-2">Project Site Location & Geofence *</label>
                <MapLocationPicker value={location} onChange={setLocation} />
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-surface-border">
                <button
                  type="button"
                  onClick={() => { setShowCreateModal(false); resetForm(); }}
                  className="btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="btn-primary text-xs px-5 py-2"
                >
                  {formSubmitting ? 'Creating Project…' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}

