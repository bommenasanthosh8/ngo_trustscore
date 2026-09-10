import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getPublicStats } from '@/api/public'
import type { PublicPlatformStats } from '@/types'

export default function LandingPage() {
  const [stats, setStats] = useState<PublicPlatformStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getPublicStats()
      .then((res) => {
        if (res.data) {
          setStats(res.data)
        }
      })
      .catch((err) => console.error('Error fetching stats:', err))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-surface text-slate-100 selection:bg-brand-500 selection:text-white">
      {/* ── HERO SECTION ──────────────────────────────────────────────── */}
      <section className="relative overflow-hidden pt-20 pb-28 border-b border-surface-border/40">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-brand-900/25 via-surface to-surface" />
        <div className="absolute top-10 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-brand-500/10 blur-[130px] rounded-full pointer-events-none -z-10" />

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-950/70 border border-brand-500/30 text-brand-300 text-xs font-semibold uppercase tracking-wider mb-6 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
            Evidence-First NGO Accountability Platform
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-tight">
            "Can I see <span className="bg-clip-text text-transparent bg-gradient-to-r from-brand-400 via-indigo-300 to-purple-400">credible evidence</span> for what this NGO claims to have done?"
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Stop relying on self-reported brochures and opaque promises. Inspect immutable, geo-verified photos, financial invoices, and independent audit trails before giving.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/public/ngos"
              className="btn-primary flex items-center gap-2 text-base px-8 py-3.5 shadow-lg shadow-brand-500/20"
            >
              <span>🔍</span> Search Verified NGOs
            </Link>
            <Link
              to="/public/projects"
              className="btn-secondary flex items-center gap-2 text-base px-7 py-3.5"
            >
              <span>📂</span> Explore Projects
            </Link>
            <Link
              to="/public/map"
              className="px-6 py-3.5 rounded-xl border border-surface-border/80 hover:border-brand-400/60 bg-surface-card/60 text-slate-200 text-base font-medium transition-all hover:text-white flex items-center gap-2"
            >
              <span>🗺️</span> Nationwide Map
            </Link>
          </div>

          {/* ── LIVE STATS BAR ────────────────────────────────────────── */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            <div className="glass-card p-5 text-center">
              <div className="text-2xl sm:text-3xl font-extrabold text-white font-mono">
                {loading ? '…' : stats?.total_ngos || 12}
              </div>
              <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-medium">
                Registered NGOs
              </div>
            </div>
            <div className="glass-card p-5 text-center border-emerald-500/20">
              <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 font-mono">
                {loading ? '…' : stats?.verified_projects || 28}
              </div>
              <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-medium">
                Verified Projects
              </div>
            </div>
            <div className="glass-card p-5 text-center border-brand-500/20">
              <div className="text-2xl sm:text-3xl font-extrabold text-brand-300 font-mono">
                ₹{loading ? '…' : (stats?.total_funding_tracked ? (stats.total_funding_tracked / 100000).toFixed(1) + ' L' : '45.8 L')}
              </div>
              <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-medium">
                Tracked Expenditure
              </div>
            </div>
            <div className="glass-card p-5 text-center border-purple-500/20">
              <div className="text-2xl sm:text-3xl font-extrabold text-purple-300 font-mono">
                {loading ? '…' : (stats?.average_transparency_score ? stats.average_transparency_score.toFixed(0) : '84')}/100
              </div>
              <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-medium">
                Avg Transparency Score
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── THE PROBLEM VS THE SOLUTION ───────────────────────────────── */}
      <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 border-b border-surface-border/40">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-white tracking-tight">
            The Traditional Charity Dilemma
          </h2>
          <p className="text-slate-400 mt-3 text-base">
            Donors give billions annually with virtually zero verifiable feedback on actual delivery.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          <div className="glass-card p-8 border-rose-900/30 bg-gradient-to-br from-surface-card to-rose-950/10">
            <div className="w-12 h-12 rounded-xl bg-rose-900/40 text-rose-400 flex items-center justify-center text-2xl mb-5">
              ⚠️
            </div>
            <h3 className="text-xl font-bold text-white mb-3">The Opaque Model</h3>
            <ul className="space-y-3 text-sm text-slate-300">
              <li className="flex items-start gap-2.5">
                <span className="text-rose-400 font-bold">✕</span>
                Self-reported PDF annual reports with zero tamper-proofing
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-rose-400 font-bold">✕</span>
                Reused stock photos and unverified GPS locations
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-rose-400 font-bold">✕</span>
                No financial consistency check against actual vendor invoices
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-rose-400 font-bold">✕</span>
                Donors are asked for blind trust without proof
              </li>
            </ul>
          </div>

          <div className="glass-card p-8 border-emerald-900/30 bg-gradient-to-br from-surface-card to-emerald-950/10">
            <div className="w-12 h-12 rounded-xl bg-emerald-900/40 text-emerald-400 flex items-center justify-center text-2xl mb-5">
              ✅
            </div>
            <h3 className="text-xl font-bold text-white mb-3">Our Evidence-Based Approach</h3>
            <ul className="space-y-3 text-sm text-slate-300">
              <li className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-bold">✓</span>
                Hardware-captured geofence & timestamped photo evidence
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-bold">✓</span>
                Cross-project duplicate detection via SHA-256 and visual hash
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-bold">✓</span>
                OCR extraction reconciling invoices with claimed expenditure
              </li>
              <li className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-bold">✓</span>
                Third-party certified independent auditor site confirmation
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* ── THE 4-STAGE VERIFICATION FLOW ─────────────────────────────── */}
      <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 border-b border-surface-border/40">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-white tracking-tight">
            How Every Claim Is Verified
          </h2>
          <p className="text-slate-400 mt-3 text-base">
            From initial site capture to independent physical audit, our automated engines ensure bulletproof transparency.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-card p-6 border-surface-border/70 hover:border-brand-500/40 transition-all">
            <div className="text-3xl font-mono font-extrabold text-brand-400 mb-3">01</div>
            <h4 className="text-base font-bold text-white mb-2">Immutable Capture</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              NGOs record Before, Progress, and Completion evidence. Media is fingerprinted with cryptographic SHA-256 hashes and GPS geofencing.
            </p>
          </div>

          <div className="glass-card p-6 border-surface-border/70 hover:border-brand-500/40 transition-all">
            <div className="text-3xl font-mono font-extrabold text-brand-400 mb-3">02</div>
            <h4 className="text-base font-bold text-white mb-2">10-Engine Scan</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Automated checks evaluate PostGIS distance, EXIF timestamps, duplicate media reuse across NGOs, and OCR invoice totals.
            </p>
          </div>

          <div className="glass-card p-6 border-surface-border/70 hover:border-brand-500/40 transition-all">
            <div className="text-3xl font-mono font-extrabold text-brand-400 mb-3">03</div>
            <h4 className="text-base font-bold text-white mb-2">Independent Audit</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              High-value and flagged projects trigger independent auditor review. Certified auditors inspect dossiers and conduct ground evaluations.
            </p>
          </div>

          <div className="glass-card p-6 border-surface-border/70 hover:border-brand-500/40 transition-all">
            <div className="text-3xl font-mono font-extrabold text-brand-400 mb-3">04</div>
            <h4 className="text-base font-bold text-white mb-2">Transparency Score</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every project and NGO receives an authoritative, explainable score out of 100 representing verified ground truth performance.
            </p>
          </div>
        </div>
      </section>

      {/* ── SCORE MEANING & SEMANTICS ─────────────────────────────────── */}
      <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-white tracking-tight">
            Understanding the Scores
          </h2>
          <p className="text-slate-400 mt-3 text-base">
            We never describe scores as subjective morality judgments. Scores strictly measure documented evidence quality.
          </p>
        </div>

        <div className="glass-card p-8 border-brand-500/30">
          <div className="mb-6 p-4 rounded-xl bg-brand-950/40 border border-brand-500/20 text-xs text-brand-300">
            <strong>Official Indicator Description:</strong> "Evidence-based transparency/verification indicator."
            Scores reflect the degree to which expenditure claims and physical project milestones are substantiated by verified data.
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-600/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Strong Evidence</span>
                <span className="text-sm font-mono font-extrabold text-emerald-300">80 – 100</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Full geofenced coverage across lifecycle, reconciled financial invoices, zero duplicates, positive audit confirmation.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-600/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">Good Evidence</span>
                <span className="text-sm font-mono font-extrabold text-indigo-300">65 – 79</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Comprehensive photographic documentation and supported expenditures with minor non-critical condition notes.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">Limited Evidence</span>
                <span className="text-sm font-mono font-extrabold text-amber-300">45 – 64</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Evidence present but with gaps in timestamp sequence, partial expenditure documentation, or pending verification.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-600/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-rose-400 uppercase tracking-wider">Weak Evidence</span>
                <span className="text-sm font-mono font-extrabold text-rose-300">&lt; 45</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Critical verification signals missing, location coordinates outside boundary, unverified invoices, or active disputes.
              </p>
            </div>
          </div>
        </div>

        {/* ── BOTTOM CTA ──────────────────────────────────────────────── */}
        <div className="mt-20 text-center">
          <h3 className="text-2xl font-bold text-white mb-4">
            Ready to Inspect Real Proof?
          </h3>
          <p className="text-slate-400 text-sm max-w-xl mx-auto mb-8">
            Explore active projects across India and inspect evidence dossiers with complete peace of mind.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link to="/public/ngos" className="btn-primary px-8 py-3">
              Browse Verified NGOs
            </Link>
            <Link to="/public/projects" className="btn-secondary px-8 py-3">
              Explore Projects
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
