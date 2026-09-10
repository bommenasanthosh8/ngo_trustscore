import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { searchPublicNGOs } from '@/api/public'
import type { NGOPublicSummary } from '@/types'
import DirectDonationModal from '@/components/donations/DirectDonationModal'

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

export default function NGOSearchPage() {
  const [ngos, setNgos] = useState<NGOPublicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [searchName, setSearchName] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [locationQuery, setLocationQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedDonationNgo, setSelectedDonationNgo] = useState<NGOPublicSummary | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  useEffect(() => {
    fetchNGOs()
  }, [selectedCategory, statusFilter])

  function fetchNGOs() {
    setLoading(true)
    searchPublicNGOs({
      search: searchName.trim() || undefined,
      category: selectedCategory || undefined,
      location: locationQuery.trim() || undefined,
      status: statusFilter || undefined,
    })
      .then((res) => {
        if (res.data) {
          setNgos(res.data)
        }
      })
      .catch((err) => console.error('Error fetching NGOs:', err))
      .finally(() => setLoading(false))
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    fetchNGOs()
  }

  function getScoreBadge(score?: number | null) {
    if (score === null || score === undefined) {
      return (
        <span className="badge-gray text-[11px] font-mono">
          Pending Assessment
        </span>
      )
    }
    if (score >= 80) {
      return (
        <span className="badge-green text-xs font-mono font-bold px-2.5 py-1">
          🛡️ {score.toFixed(0)}/100 • Strong
        </span>
      )
    }
    if (score >= 65) {
      return (
        <span className="badge-blue text-xs font-mono font-bold px-2.5 py-1">
          ✓ {score.toFixed(0)}/100 • Good
        </span>
      )
    }
    if (score >= 45) {
      return (
        <span className="badge-yellow text-xs font-mono font-bold px-2.5 py-1">
          ⚠️ {score.toFixed(0)}/100 • Moderate
        </span>
      )
    }
    return (
      <span className="badge-red text-xs font-mono font-bold px-2.5 py-1">
        ✕ {score.toFixed(0)}/100 • Limited
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-surface text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        {/* ── HEADER ──────────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-950/60 border border-brand-500/30 text-brand-300 text-xs font-medium mb-3">
            <span>🏛️</span> Verified Directory
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Search Credible NGOs
          </h1>
          <p className="text-slate-400 text-sm mt-1 max-w-2xl">
            Find organizations, inspect their historical transparency indicators, and verify past project execution before committing funds.
          </p>
        </div>

        {/* ── FILTERS BAR ─────────────────────────────────────────────── */}
        <form
          onSubmit={handleSearchSubmit}
          className="glass-card p-5 mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end"
        >
          {/* NGO Name search */}
          <div className="lg:col-span-2">
            <label className="form-label text-xs">NGO Name / Keyword</label>
            <input
              type="text"
              placeholder="e.g. Swachh Bharat Trust, Health Foundation..."
              value={searchName}
              onChange={(e) => setSearchName(e.target.value)}
              className="input-field text-xs"
            />
          </div>

          {/* Category */}
          <div>
            <label className="form-label text-xs">Sector / Category</label>
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

          {/* Location */}
          <div>
            <label className="form-label text-xs">Location (State / City)</label>
            <input
              type="text"
              placeholder="e.g. Tamil Nadu, Varanasi..."
              value={locationQuery}
              onChange={(e) => setLocationQuery(e.target.value)}
              className="input-field text-xs"
            />
          </div>

          {/* Search Button */}
          <div className="flex gap-2">
            <button
              type="submit"
              className="btn-primary w-full text-xs py-3 flex items-center justify-center gap-1.5"
            >
              <span>🔍</span> Search
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchName('')
                setSelectedCategory('')
                setLocationQuery('')
                setStatusFilter('')
              }}
              className="btn-secondary text-xs px-3"
              title="Reset Filters"
            >
              ✕
            </button>
          </div>
        </form>

        {/* ── RESULTS ─────────────────────────────────────────────────── */}
        {loading ? (
          <div className="text-center py-20">
            <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-400 text-sm">Searching registered NGOs...</p>
          </div>
        ) : ngos.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <span className="text-4xl mb-3 block">🏢</span>
            <h3 className="text-lg font-bold text-white mb-2">No NGOs Found</h3>
            <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
              No registered organizations matched your filter criteria. Try broadening your keyword or location search.
            </p>
            <button
              onClick={() => {
                setSearchName('')
                setSelectedCategory('')
                setLocationQuery('')
                setStatusFilter('')
              }}
              className="btn-secondary text-xs"
            >
              Clear All Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {ngos.map((ngo) => (
              <div
                key={ngo.id}
                className="glass-card p-6 flex flex-col justify-between hover:border-brand-500/40 transition-all group"
              >
                <div>
                  {/* Top line: verification badge & score */}
                  <div className="flex items-start justify-between gap-2 mb-3">
                    {ngo.is_verified || ngo.verification_status === 'VERIFIED' ? (
                      <span className="badge-green text-[11px] font-semibold flex items-center gap-1">
                        <span>✓</span> Verified NGO
                      </span>
                    ) : (
                      <span className="badge-yellow text-[11px] font-semibold flex items-center gap-1">
                        <span>⏳</span> Pending Verification
                      </span>
                    )}

                    {getScoreBadge(ngo.transparency_score)}
                  </div>

                  <h3 className="text-lg font-bold text-white group-hover:text-brand-300 transition-colors leading-snug">
                    {ngo.name}
                  </h3>

                  <div className="text-[11px] font-mono text-slate-400 mt-1">
                    Reg: {ngo.registration_number}
                  </div>

                  {ngo.address && (
                    <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                      <span>📍</span>
                      <span className="truncate">{ngo.address}</span>
                    </div>
                  )}

                  {ngo.description && (
                    <p className="text-xs text-slate-300 mt-3 line-clamp-3 leading-relaxed">
                      {ngo.description}
                    </p>
                  )}

                  {/* Categories tag pills */}
                  {ngo.project_categories && ngo.project_categories.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-4">
                      {ngo.project_categories.slice(0, 3).map((cat) => (
                        <span
                          key={cat}
                          className="text-[10px] bg-surface/80 border border-surface-border px-2 py-0.5 rounded-md text-slate-300 capitalize"
                        >
                          {cat.toLowerCase().replace(/_/g, ' ')}
                        </span>
                      ))}
                      {ngo.project_categories.length > 3 && (
                        <span className="text-[10px] text-slate-400 px-1 py-0.5">
                          +{ngo.project_categories.length - 3} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Bottom line: project count & action */}
                <div className="mt-6 pt-4 border-t border-surface-border/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="text-xs text-slate-400">
                    <span className="font-bold text-white text-sm font-mono">
                      {ngo.project_count}
                    </span>{' '}
                    project{ngo.project_count === 1 ? '' : 's'} (
                    <span className="text-emerald-400 font-semibold">
                      {ngo.verified_project_count} verified
                    </span>
                    )
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedDonationNgo(ngo)}
                      className="btn-primary text-xs px-3.5 py-1.5 flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/30 text-white font-bold"
                    >
                      <span>💝</span>
                      <span>Donate</span>
                    </button>

                    <Link
                      to={`/public/ngos/${ngo.id}`}
                      className="btn-secondary text-xs px-3.5 py-1.5 group-hover:bg-brand-600 group-hover:text-white group-hover:border-transparent transition-all"
                    >
                      Dossier →
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── ACTION NOTIFICATION ── */}
        {actionMessage && (
          <div className="fixed bottom-6 right-6 z-40 p-4 rounded-xl bg-emerald-950/90 border border-emerald-500 text-emerald-200 text-xs shadow-2xl flex items-center gap-3">
            <span>🎉 {actionMessage}</span>
            <button
              onClick={() => setActionMessage(null)}
              className="text-emerald-400 hover:text-white font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* ── DIRECT DONATION GATEWAY MODAL ── */}
        {selectedDonationNgo && (
          <DirectDonationModal
            ngoId={selectedDonationNgo.id}
            ngoName={selectedDonationNgo.name}
            ngoRegistrationNumber={selectedDonationNgo.registration_number}
            onClose={() => setSelectedDonationNgo(null)}
            onSuccess={(d) => {
              setActionMessage(
                `Donation of ₹${d.amount.toLocaleString()} to ${d.ngo_name} completed! Official Receipt: ${d.receipt_number}`
              )
            }}
          />
        )}
      </div>
    </div>
  )
}
