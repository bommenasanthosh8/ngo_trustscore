import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getPublicMapPoints } from '@/api/public'
import type { PublicMapPoint } from '@/types'

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

export default function PublicMapPage() {
  const [points, setPoints] = useState<PublicMapPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPoint, setSelectedPoint] = useState<PublicMapPoint | null>(null)
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')

  // Map viewport boundary (India bounding box approximation: lat 8 to 36, lon 68 to 97)
  const minLat = 6.0
  const maxLat = 37.0
  const minLon = 68.0
  const maxLon = 98.0

  useEffect(() => {
    setLoading(true)
    getPublicMapPoints({
      category: selectedCategory || undefined,
      status: selectedStatus || undefined,
    })
      .then((res) => {
        if (res.data) {
          setPoints(res.data)
          if (res.data.length > 0) {
            setSelectedPoint(res.data[0])
          } else {
            setSelectedPoint(null)
          }
        }
      })
      .catch((err) => console.error('Error fetching map points:', err))
      .finally(() => setLoading(false))
  }, [selectedCategory, selectedStatus])

  function getPinColor(status: string) {
    switch (status) {
      case 'VERIFIED':
        return 'bg-emerald-500 text-white border-emerald-300 shadow-emerald-500/40'
      case 'PARTIALLY_VERIFIED':
        return 'bg-amber-500 text-white border-amber-300 shadow-amber-500/40'
      case 'DISPUTED':
        return 'bg-rose-500 text-white border-rose-300 shadow-rose-500/40'
      default:
        return 'bg-brand-500 text-white border-brand-300 shadow-brand-500/40'
    }
  }

  // Convert geo-coordinates to percentage on the canvas
  function getCanvasCoords(lat: number, lon: number) {
    const x = Math.max(5, Math.min(95, ((lon - minLon) / (maxLon - minLon)) * 100))
    const y = Math.max(5, Math.min(95, (1 - (lat - minLat) / (maxLat - minLat)) * 100))
    return { x, y }
  }

  return (
    <div className="min-h-screen bg-surface text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── HEADER ──────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-950/60 border border-brand-500/30 text-brand-300 text-xs font-medium mb-2">
              <span>🗺️</span> Nationwide Geographic Registry
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Interactive Transparency Map
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Geolocated project sites verified via PostGIS boundary checks and independent auditor dossiers.
            </p>
          </div>

          <div className="flex items-center gap-2.5 text-xs">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Verified
            </span>
            <span className="flex items-center gap-1.5 text-amber-400">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Partially Verified
            </span>
            <span className="flex items-center gap-1.5 text-brand-400">
              <span className="w-2.5 h-2.5 rounded-full bg-brand-500" /> Under Verification
            </span>
            <span className="flex items-center gap-1.5 text-rose-400">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Disputed
            </span>
          </div>
        </div>

        {/* ── FILTERS BAR ─────────────────────────────────────────────── */}
        <div className="glass-card p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="input-field text-xs py-2 w-48 capitalize"
            >
              <option value="">All Sectors</option>
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.replace(/_/g, ' ')}
                </option>
              ))}
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="input-field text-xs py-2 w-48 capitalize"
            >
              <option value="">All Verification Statuses</option>
              <option value="VERIFIED">Verified Only</option>
              <option value="PARTIALLY_VERIFIED">Partially Verified</option>
              <option value="UNDER_VERIFICATION">Under Verification</option>
              <option value="DISPUTED">Disputed</option>
            </select>

            {(selectedCategory || selectedStatus) && (
              <button
                onClick={() => {
                  setSelectedCategory('')
                  setSelectedStatus('')
                }}
                className="text-xs text-brand-400 hover:text-brand-300 underline"
              >
                Clear Filters
              </button>
            )}
          </div>

          <div className="text-xs text-slate-400 font-mono">
            Showing <strong className="text-white">{points.length}</strong> site marker{points.length === 1 ? '' : 's'}
          </div>
        </div>

        {/* ── MAP CONTAINER & DETAIL DRAWER ───────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map Canvas */}
          <div className="lg:col-span-2 glass-card p-4 min-h-[520px] relative overflow-hidden flex flex-col justify-between">
            <div className="relative w-full h-[520px] bg-slate-950 rounded-xl overflow-hidden border border-surface-border">
              {/* Background Map Grid Pattern */}
              <div
                className="absolute inset-0 opacity-40"
                style={{
                  backgroundImage: `
                    radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.15) 0%, rgba(15, 23, 42, 1) 100%),
                    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px)
                  `,
                  backgroundSize: '100% 100%, 30px 30px, 30px 30px',
                }}
              />

              {/* Geographic Region Label Overlay */}
              <div className="absolute top-4 left-4 z-10 bg-surface/80 border border-surface-border px-3 py-1.5 rounded-lg text-[11px] font-mono text-slate-400">
                Region: India (Lat 8°N–37°N • Lon 68°E–98°E)
              </div>

              {/* Privacy indicator */}
              <div className="absolute top-4 right-4 z-10 bg-surface/80 border border-brand-500/30 px-3 py-1.5 rounded-lg text-[11px] font-mono text-brand-300">
                🔒 Sensitive Sites: Approximate Area
              </div>

              {/* Map Pins */}
              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : points.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-xs">
                  No project sites matched your filter.
                </div>
              ) : (
                points.map((pt) => {
                  const { x, y } = getCanvasCoords(pt.latitude, pt.longitude)
                  const isSelected = selectedPoint?.id === pt.id

                  return (
                    <button
                      key={pt.id}
                      onClick={() => setSelectedPoint(pt)}
                      className={`absolute -translate-x-1/2 -translate-y-1/2 z-20 group transition-all duration-200 focus:outline-none`}
                      style={{ left: `${x}%`, top: `${y}%` }}
                      title={`${pt.title} (${pt.status})`}
                    >
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-[9px] font-bold shadow-lg transition-transform ${getPinColor(
                          pt.status
                        )} ${isSelected ? 'scale-150 ring-4 ring-white/40 z-30' : 'group-hover:scale-125'}`}
                      >
                        📍
                      </div>
                      {/* Hover Tooltip */}
                      <span className="absolute left-1/2 -translate-x-1/2 bottom-6 hidden group-hover:block bg-surface border border-surface-border text-white text-[10px] whitespace-nowrap px-2.5 py-1 rounded shadow-xl pointer-events-none z-40">
                        {pt.title}
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </div>

          {/* Selected Project Card Drawer */}
          <div className="lg:col-span-1">
            {selectedPoint ? (
              <div className="glass-card p-6 space-y-4 border-brand-500/40 sticky top-6">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-mono uppercase bg-surface/80 border border-surface-border px-2 py-0.5 rounded text-slate-300">
                      {selectedPoint.category.replace(/_/g, ' ')}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase ${
                        selectedPoint.status === 'VERIFIED'
                          ? 'badge-green'
                          : selectedPoint.status === 'PARTIALLY_VERIFIED'
                          ? 'badge-yellow'
                          : selectedPoint.status === 'DISPUTED'
                          ? 'badge-red'
                          : 'badge-blue'
                      }`}
                    >
                      {selectedPoint.status.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-white leading-snug">
                    {selectedPoint.title}
                  </h3>
                  <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                    {selectedPoint.project_code}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-surface/60 border border-surface-border space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Operating NGO:</span>
                    <span className="text-indigo-300 font-semibold">{selectedPoint.ngo_name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Site Location:</span>
                    <span className="text-slate-200 font-medium">{selectedPoint.location_name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Target Budget:</span>
                    <span className="font-mono font-bold text-white">
                      ₹{selectedPoint.target_amount.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Evidence Score:</span>
                    <span className="font-mono font-bold text-brand-300 text-sm">
                      {selectedPoint.evidence_score ? `${selectedPoint.evidence_score.toFixed(0)}/100` : '—'}
                    </span>
                  </div>
                </div>

                {selectedPoint.is_sensitive && (
                  <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-800/40 text-[11px] text-amber-300">
                    🛡️ <strong>Privacy Protection Active:</strong> Exact GPS coordinates are approximated on this map to safeguard vulnerable beneficiaries and shelter facilities.
                  </div>
                )}

                <div className="pt-2">
                  <Link
                    to={`/public/projects/${selectedPoint.id}`}
                    className="btn-primary w-full text-xs py-3 flex items-center justify-center gap-1.5"
                  >
                    <span>🔍</span> Inspect Evidence Dossier →
                  </Link>
                </div>
              </div>
            ) : (
              <div className="glass-card p-8 text-center text-slate-400 text-xs">
                Click any marker on the map to inspect project credibility details.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
