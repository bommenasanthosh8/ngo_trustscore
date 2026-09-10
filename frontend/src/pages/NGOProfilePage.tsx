import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getPublicNGOProfile, getPublicProjects } from '@/api/public'
import { getNGOScore, getNGOScoreHistory } from '@/api/scores'
import DirectDonationModal from '@/components/donations/DirectDonationModal'
import type {
  NGOResponse,
  NGOTransparencyScoreResponse,
  NGOScoreSnapshotResponse,
  ProjectDetail,
} from '@/types'

export default function NGOProfilePage() {
  const { id } = useParams<{ id: string }>()
  const [ngo, setNgo] = useState<NGOResponse | null>(null)
  const [score, setScore] = useState<NGOTransparencyScoreResponse | null>(null)
  const [history, setHistory] = useState<NGOScoreSnapshotResponse[]>([])
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDonationModal, setShowDonationModal] = useState(false)
  const [donationSuccessMsg, setDonationSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return

    setLoading(true)
    setError(null)

    Promise.all([
      getPublicNGOProfile(id),
      getNGOScore(id),
      getNGOScoreHistory(id),
      getPublicProjects({ ngo_id: id }),
    ])
      .then(([ngoRes, scoreRes, histRes, projRes]) => {
        if (ngoRes.data) setNgo(ngoRes.data)
        if (scoreRes.data) setScore(scoreRes.data)
        if (histRes.data) setHistory(histRes.data)
        if (projRes.data) setProjects(projRes.data)
      })
      .catch((err) => {
        console.error('Error fetching NGO profile data:', err)
        setError('Failed to load NGO transparency profile. Please verify the ID or try again.')
      })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center text-slate-400">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm">Loading NGO Credibility Profile...</p>
        </div>
      </div>
    )
  }

  if (error || !ngo) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <div className="glass-card p-8 max-w-md text-center">
          <span className="text-4xl mb-3 block">⚠️</span>
          <h2 className="text-xl font-bold text-white mb-2">NGO Not Found</h2>
          <p className="text-sm text-slate-400 mb-6">{error || 'The requested NGO could not be loaded.'}</p>
          <Link to="/public/ngos" className="btn-primary text-xs px-6 py-2.5">
            ← Back to NGO Directory
          </Link>
        </div>
      </div>
    )
  }

  const finalScore = score?.final_score ?? 80

  return (
    <div className="min-h-screen bg-surface text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* ── BREADCRUMB ──────────────────────────────────────────────── */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Link to="/" className="hover:text-white transition-colors">Home</Link>
          <span>/</span>
          <Link to="/public/ngos" className="hover:text-white transition-colors">NGO Directory</Link>
          <span>/</span>
          <span className="text-slate-200 font-medium truncate">{ngo.name}</span>
        </div>

        {/* ── NGO HEADER ──────────────────────────────────────────────── */}
        <div className="glass-card p-8 relative overflow-hidden border-brand-500/30">
          <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 blur-[100px] pointer-events-none -z-10" />

          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="space-y-3 flex-1">
              <div className="flex flex-wrap items-center gap-2.5">
                {ngo.is_verified || ngo.verification_status === 'VERIFIED' ? (
                  <span className="badge-green text-xs font-semibold px-3 py-1 flex items-center gap-1.5">
                    <span>✓</span> Platform Verified NGO
                  </span>
                ) : (
                  <span className="badge-yellow text-xs font-semibold px-3 py-1 flex items-center gap-1.5">
                    <span>⏳</span> Verification Pending
                  </span>
                )}
                <span className="text-xs text-slate-400 font-mono">
                  Reg: {ngo.registration_number}
                </span>
                {ngo.darpan_id && (
                  <span className="text-xs text-slate-400 font-mono bg-surface/60 px-2 py-0.5 rounded border border-surface-border">
                    DARPAN: {ngo.darpan_id}
                  </span>
                )}
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                {ngo.name}
              </h1>

              {ngo.description && (
                <p className="text-slate-300 text-sm max-w-3xl leading-relaxed">
                  {ngo.description}
                </p>
              )}

              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 pt-2">
                {ngo.address && (
                  <span className="flex items-center gap-1.5">
                    <span>📍</span> {ngo.address}
                  </span>
                )}
                {ngo.website && (
                  <a
                    href={ngo.website.startsWith('http') ? ngo.website : `https://${ngo.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-brand-400 hover:text-brand-300 underline"
                  >
                    <span>🌐</span> Official Website
                  </a>
                )}
                {ngo.authorized_representative && (
                  <span className="flex items-center gap-1.5">
                    <span>👤</span> Authorized Rep: {ngo.authorized_representative}
                  </span>
                )}
              </div>
            </div>

            {/* ── AUTHORITATIVE TRANSPARENCY SCORE CALLOUT ────────────── */}
            <div className="bg-surface/90 border border-brand-500/40 rounded-2xl p-6 text-center min-w-[220px] self-start md:self-auto shadow-xl shadow-brand-950/40">
              <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1">
                Transparency Score
              </div>
              <div className="text-5xl font-extrabold text-white font-mono tracking-tight my-2">
                {finalScore.toFixed(0)}
                <span className="text-lg text-slate-500 font-normal">/100</span>
              </div>
              <div className="text-[11px] text-emerald-400 font-medium mb-3">
                {score?.historical_trend ? `Trajectory: ${score.historical_trend}` : 'Authoritative Score'}
              </div>
              <div className="text-[10px] text-slate-400 leading-tight pt-2 border-t border-surface-border">
                {score?.indicator_description || 'Evidence-based transparency/verification indicator.'}
              </div>
              <button
                onClick={() => setShowDonationModal(true)}
                className="w-full mt-3 btn-primary text-xs py-2.5 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/30 text-white font-bold"
              >
                <span>💝</span>
                <span>Donate Directly to NGO</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── PROJECT STATISTICS (4 PILLARS) ───────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-5 border-emerald-500/30 bg-emerald-950/10">
            <div className="flex items-center justify-between text-xs text-emerald-400 uppercase tracking-wider font-semibold mb-1">
              <span>Verified Projects</span>
              <span className="text-base">✓</span>
            </div>
            <div className="text-3xl font-extrabold text-white font-mono">
              {score?.verified_count ?? projects.filter((p) => p.status === 'VERIFIED').length}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Fully verified with complete geofence & financial evidence
            </p>
          </div>

          <div className="glass-card p-5 border-amber-500/30 bg-amber-950/10">
            <div className="flex items-center justify-between text-xs text-amber-400 uppercase tracking-wider font-semibold mb-1">
              <span>Partially Verified</span>
              <span className="text-base">◐</span>
            </div>
            <div className="text-3xl font-extrabold text-white font-mono">
              {score?.partially_verified_count ?? projects.filter((p) => p.status === 'PARTIALLY_VERIFIED').length}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Substantial evidence documented; minor conditions noted
            </p>
          </div>

          <div className="glass-card p-5 border-blue-500/30 bg-blue-950/10">
            <div className="flex items-center justify-between text-xs text-blue-400 uppercase tracking-wider font-semibold mb-1">
              <span>Pending Review</span>
              <span className="text-base">⏳</span>
            </div>
            <div className="text-3xl font-extrabold text-white font-mono">
              {score?.pending_count ?? projects.filter((p) => !['VERIFIED', 'PARTIALLY_VERIFIED', 'DISPUTED'].includes(p.status)).length}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Under active evidence collection or automated check execution
            </p>
          </div>

          <div className="glass-card p-5 border-rose-500/30 bg-rose-950/10">
            <div className="flex items-center justify-between text-xs text-rose-400 uppercase tracking-wider font-semibold mb-1">
              <span>Disputed</span>
              <span className="text-base">⚠️</span>
            </div>
            <div className="text-3xl font-extrabold text-white font-mono">
              {score?.disputed_count ?? projects.filter((p) => p.status === 'DISPUTED').length}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Projects undergoing formal administrative dispute review
            </p>
          </div>
        </div>

        {/* ── EXPLAINABLE SCORE BREAKDOWN & BULLETS ──────────────────────── */}
        {score && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Narrative Explanation Bullets */}
            <div className="lg:col-span-1 glass-card p-6 flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                  <span>📋</span> Score Explanation
                </h3>
                <p className="text-xs text-slate-400 mb-4">
                  Why this NGO holds a {score.final_score.toFixed(0)}/100 rating:
                </p>

                <ul className="space-y-3">
                  {score.explanation.map((bullet, idx) => (
                    <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-200 leading-relaxed">
                      <span className="text-emerald-400 font-bold mt-0.5">•</span>
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 pt-4 border-t border-surface-border text-[11px] text-slate-400">
                Calculated: {new Date(score.calculated_at).toLocaleDateString()} • Verified on-chain
              </div>
            </div>

            {/* Dimension Breakdown Bars */}
            <div className="lg:col-span-2 glass-card p-6">
              <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                <span>📊</span> 5-Factor Dimension Breakdown
              </h3>
              <p className="text-xs text-slate-400 mb-6">
                Configurable weighted assessment across portfolio performance.
              </p>

              <div className="space-y-5">
                {Object.entries(score.factors).map(([key, factor]) => (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-200">
                        {factor.factor_name}
                      </span>
                      <span className="font-mono text-brand-300 font-bold">
                        {factor.raw_score.toFixed(0)}/100{' '}
                        <span className="text-[10px] text-slate-400 font-normal">
                          (weight: {(factor.weight * 100).toFixed(0)}%)
                        </span>
                      </span>
                    </div>
                    <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          factor.raw_score >= 80
                            ? 'bg-emerald-500'
                            : factor.raw_score >= 60
                            ? 'bg-brand-500'
                            : factor.raw_score >= 40
                            ? 'bg-amber-500'
                            : 'bg-rose-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, factor.raw_score))}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      {factor.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── HISTORICAL SCORE TREND ────────────────────────────────────── */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span>📈</span> Historical Score Trend
              </h3>
              <p className="text-xs text-slate-400">
                Immutable chronological record of past ScoreSnapshots.
              </p>
            </div>
            {score?.historical_trend && (
              <span className="badge-blue text-xs font-mono font-bold">
                Trend: {score.historical_trend}
              </span>
            )}
          </div>

          {history.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">
              Only initial baseline assessment recorded. Historical snapshots accumulate automatically over subsequent evaluations.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-surface-border text-slate-400">
                    <th className="pb-3 font-semibold">Assessment Date</th>
                    <th className="pb-3 font-semibold">Transparency Score</th>
                    <th className="pb-3 font-semibold">Snapshot ID</th>
                    <th className="pb-3 font-semibold">Trajectory</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/40">
                  {history.map((h, idx) => (
                    <tr key={h.id} className="hover:bg-white/[0.02]">
                      <td className="py-3 text-slate-300">
                        {new Date(h.calculated_at).toLocaleString()}
                      </td>
                      <td className="py-3 font-mono font-bold text-white">
                        {h.composite_score.toFixed(1)} / 100
                      </td>
                      <td className="py-3 font-mono text-[11px] text-slate-400">
                        {h.id.slice(0, 8)}…
                      </td>
                      <td className="py-3">
                        {idx === 0 ? (
                          <span className="text-emerald-400 font-semibold">Latest</span>
                        ) : (
                          <span className="text-slate-400 font-mono">Archived</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── NGO'S PROJECTS DIRECTORY ─────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-2xl font-bold text-white tracking-tight">
                Project Portfolio ({projects.length})
              </h3>
              <p className="text-slate-400 text-xs">
                Inspect evidence dossiers, geotagged photos, and verified expenditure for each project.
              </p>
            </div>
          </div>

          {projects.length === 0 ? (
            <div className="glass-card p-10 text-center text-slate-400 text-xs">
              No projects created yet for this organization.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((p) => (
                <div
                  key={p.id}
                  className="glass-card p-6 flex flex-col justify-between hover:border-brand-500/40 transition-all group"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-surface border border-surface-border text-slate-300">
                        {p.category.replace(/_/g, ' ')}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                          p.status === 'VERIFIED'
                            ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-700/40'
                            : p.status === 'PARTIALLY_VERIFIED'
                            ? 'bg-amber-950/80 text-amber-400 border border-amber-700/40'
                            : p.status === 'DISPUTED'
                            ? 'bg-rose-950/80 text-rose-400 border border-rose-700/40'
                            : 'bg-slate-800 text-slate-300'
                        }`}
                      >
                        {p.status.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <h4 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors leading-snug">
                      {p.title}
                    </h4>
                    <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                      {p.project_code}
                    </div>

                    {p.location_name && (
                      <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                        <span>📍</span>
                        <span className="truncate">{p.location_name}</span>
                      </div>
                    )}

                    {p.description && (
                      <p className="text-xs text-slate-300 mt-2.5 line-clamp-2 leading-relaxed">
                        {p.description}
                      </p>
                    )}
                  </div>

                  <div className="mt-6 pt-4 border-t border-surface-border flex items-center justify-between">
                    <div>
                      <div className="text-[10px] text-slate-400 uppercase font-medium">Evidence Score</div>
                      <div className="text-base font-extrabold text-brand-300 font-mono">
                        {p.evidence_score ? `${p.evidence_score.toFixed(0)}/100` : '—'}
                      </div>
                    </div>

                    <Link
                      to={`/public/projects/${p.id}`}
                      className="btn-secondary text-xs px-3.5 py-1.5 group-hover:bg-brand-600 group-hover:text-white group-hover:border-transparent transition-all"
                    >
                      Inspect Evidence →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── ACTION NOTIFICATION ── */}
        {donationSuccessMsg && (
          <div className="fixed bottom-6 right-6 z-40 p-4 rounded-xl bg-emerald-950/90 border border-emerald-500 text-emerald-200 text-xs shadow-2xl flex items-center gap-3">
            <span>🎉 {donationSuccessMsg}</span>
            <button
              onClick={() => setDonationSuccessMsg(null)}
              className="text-emerald-400 hover:text-white font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* ── DIRECT DONATION GATEWAY MODAL ── */}
        {showDonationModal && ngo && (
          <DirectDonationModal
            ngoId={ngo.id}
            ngoName={ngo.name}
            ngoRegistrationNumber={ngo.registration_number}
            projects={projects.map((p) => ({
              id: p.id,
              title: p.title,
              project_code: p.project_code,
            }))}
            onClose={() => setShowDonationModal(false)}
            onSuccess={(d) => {
              setDonationSuccessMsg(
                `Donation of ₹${d.amount.toLocaleString()} directly to ${d.ngo_name} successful! Receipt: ${d.receipt_number}`
              )
            }}
          />
        )}
      </div>
    </div>
  )
}
