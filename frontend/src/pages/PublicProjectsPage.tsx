import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getPublicProjects } from '@/api/public'
import type { ProjectDetail } from '@/types'

const CATEGORIES = [
  'WATER_AND_SANITATION',
  'HEALTHCARE',
  'EDUCATION',
  'INFRASTRUCTURE',
  'FOOD_DISTRIBUTION',
  'ENVIRONMENT',
  'RELIEF_DISTRIBUTION',
  'OTHER',
]

const STATUSES = [
  'VERIFIED',
  'PARTIALLY_VERIFIED',
  'UNDER_VERIFICATION',
  'EVIDENCE_COLLECTION',
  'DISPUTED',
]

export default function PublicProjectsPage() {
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')
  const [selectedRisk, setSelectedRisk] = useState('')

  useEffect(() => {
    fetchProjects()
  }, [selectedCategory, selectedStatus])

  function fetchProjects() {
    setLoading(true)
    getPublicProjects({
      search: searchQuery.trim() || undefined,
      category: selectedCategory || undefined,
      status: selectedStatus || undefined,
    })
      .then((res) => {
        if (res.data) {
          setProjects(res.data)
        }
      })
      .catch((err) => console.error('Error fetching public projects:', err))
      .finally(() => setLoading(false))
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    fetchProjects()
  }

  // Filter projects by risk level locally if selected
  const filteredProjects = projects.filter((p) => {
    if (!selectedRisk) return true
    return (p.risk_level || 'LOW').toUpperCase() === selectedRisk.toUpperCase()
  })

  function getStatusBadge(status: string) {
    switch (status) {
      case 'VERIFIED':
        return <span className="badge-green text-[11px] font-semibold">✓ Verified</span>
      case 'PARTIALLY_VERIFIED':
        return <span className="badge-yellow text-[11px] font-semibold">◐ Partial</span>
      case 'DISPUTED':
        return <span className="badge-red text-[11px] font-semibold">⚠️ Disputed</span>
      case 'UNDER_VERIFICATION':
        return <span className="badge-blue text-[11px] font-semibold">⏳ In Verification</span>
      default:
        return <span className="badge-gray text-[11px] font-semibold">{status.replace(/_/g, ' ')}</span>
    }
  }

  function getRiskBadge(risk?: string | null) {
    const r = (risk || 'LOW').toUpperCase()
    if (r === 'HIGH' || r === 'CRITICAL') {
      return <span className="badge-red text-[10px] font-bold font-mono">High Risk</span>
    }
    if (r === 'MEDIUM') {
      return <span className="badge-yellow text-[10px] font-bold font-mono">Med Risk</span>
    }
    return <span className="badge-green text-[10px] font-bold font-mono">Low Risk</span>
  }

  return (
    <div className="min-h-screen bg-surface text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        {/* ── HEADER ──────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-950/60 border border-brand-500/30 text-brand-300 text-xs font-medium mb-3">
              <span>📂</span> Public Project Registry
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Verified Project Explorer
            </h1>
            <p className="text-slate-400 text-sm mt-1 max-w-2xl">
              Inspect verified milestone claims, financial expenditure documents, and tamper-evident photos for any project.
            </p>
          </div>

          <Link
            to="/public/map"
            className="btn-secondary self-start sm:self-auto flex items-center gap-2 text-xs px-4 py-2.5"
          >
            <span>🗺️</span> View Interactive Map
          </Link>
        </div>

        {/* ── FILTERS BAR ─────────────────────────────────────────────── */}
        <form
          onSubmit={handleSearchSubmit}
          className="glass-card p-5 mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end"
        >
          {/* Search */}
          <div className="lg:col-span-2">
            <label className="form-label text-xs">Search Title, ID or Location</label>
            <input
              type="text"
              placeholder="e.g. Solar Water Pump, NGO-WELL-2026..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field text-xs"
            />
          </div>

          {/* Category */}
          <div>
            <label className="form-label text-xs">Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="input-field text-xs capitalize"
            >
              <option value="">All Categories</option>
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {/* Verification Status */}
          <div>
            <label className="form-label text-xs">Verification Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="input-field text-xs capitalize"
            >
              <option value="">All Statuses</option>
              {STATUSES.map((st) => (
                <option key={st} value={st}>
                  {st.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              type="submit"
              className="btn-primary w-full text-xs py-3 flex items-center justify-center gap-1.5"
            >
              <span>🔍</span> Filter
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchQuery('')
                setSelectedCategory('')
                setSelectedStatus('')
                setSelectedRisk('')
              }}
              className="btn-secondary text-xs px-3"
              title="Reset Filters"
            >
              ✕
            </button>
          </div>
        </form>

        {/* ── PROJECT GRID ────────────────────────────────────────────── */}
        {loading ? (
          <div className="text-center py-20">
            <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-400 text-sm">Loading verified projects...</p>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <span className="text-4xl mb-3 block">📭</span>
            <h3 className="text-lg font-bold text-white mb-2">No Projects Found</h3>
            <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
              No projects matched your criteria. Try loosening your sector or verification filters.
            </p>
            <button
              onClick={() => {
                setSearchQuery('')
                setSelectedCategory('')
                setSelectedStatus('')
                setSelectedRisk('')
              }}
              className="btn-secondary text-xs"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProjects.map((p) => (
              <div
                key={p.id}
                className="glass-card p-6 flex flex-col justify-between hover:border-brand-500/40 transition-all group relative"
              >
                <div>
                  {/* Top line: Category, Status, Risk */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="text-[10px] font-mono uppercase bg-surface/80 border border-surface-border px-2 py-0.5 rounded text-slate-300">
                      {p.category.replace(/_/g, ' ')}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {getRiskBadge(p.risk_level)}
                      {getStatusBadge(p.status)}
                    </div>
                  </div>

                  {/* Title & Code */}
                  <h3 className="text-lg font-bold text-white group-hover:text-brand-300 transition-colors leading-snug">
                    {p.title}
                  </h3>
                  <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                    {p.project_code}
                  </div>

                  {/* NGO info */}
                  {p.ngo_name && (
                    <div className="text-xs text-indigo-300 font-medium mt-2 flex items-center gap-1">
                      <span>🏢</span> {p.ngo_name}
                    </div>
                  )}

                  {/* Location */}
                  {p.location_name && (
                    <div className="text-xs text-slate-400 mt-1.5 flex items-center gap-1">
                      <span>📍</span>
                      <span className="truncate">
                        {p.location_name} {p.is_sensitive && '(Approx. Area)'}
                      </span>
                    </div>
                  )}

                  {/* Financial amount */}
                  <div className="mt-3.5 p-2.5 rounded-xl bg-surface/60 border border-surface-border flex items-center justify-between text-xs">
                    <span className="text-slate-400">Target Budget:</span>
                    <span className="font-mono font-bold text-white">
                      ₹{p.target_amount ? p.target_amount.toLocaleString('en-IN') : '—'}
                    </span>
                  </div>

                  {/* Description snippet */}
                  {p.description && (
                    <p className="text-xs text-slate-300 mt-3 line-clamp-2 leading-relaxed">
                      {p.description}
                    </p>
                  )}
                </div>

                {/* Bottom line: Evidence score & inspect link */}
                <div className="mt-6 pt-4 border-t border-surface-border/50 flex items-center justify-between">
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">
                      Evidence Score
                    </div>
                    <div className="text-xl font-extrabold text-brand-300 font-mono">
                      {p.evidence_score !== undefined && p.evidence_score !== null ? (
                        <>
                          {p.evidence_score.toFixed(0)}
                          <span className="text-xs text-slate-500 font-normal">/100</span>
                        </>
                      ) : (
                        <span className="text-xs text-slate-400 font-normal">Pending</span>
                      )}
                    </div>
                  </div>

                  <Link
                    to={`/public/projects/${p.id}`}
                    className="btn-secondary text-xs px-4 py-2 group-hover:bg-brand-600 group-hover:text-white group-hover:border-transparent transition-all flex items-center gap-1"
                  >
                    Inspect Evidence →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
