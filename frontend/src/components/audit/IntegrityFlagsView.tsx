import React, { useState } from 'react'
import { ProjectIntegrityReport } from '../../types'

interface IntegrityFlagsViewProps {
  report: ProjectIntegrityReport
  compact?: boolean
}

function ShieldAlertIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}

function AlertTriangleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

function CheckCircleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  )
}

function InfoIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

function ClockIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function LayersIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  )
}

function ChevronDownIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function ChevronUpIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="18 15 12 9 6 15" />
    </svg>
  )
}

export const IntegrityFlagsView: React.FC<IntegrityFlagsViewProps> = ({
  report,
  compact = false,
}) => {
  const [expandedThreat, setExpandedThreat] = useState<number | null>(null)
  const [showAllThreats, setShowAllThreats] = useState<boolean>(!compact)

  const hasHighRisk = report.active_flags.some((f) => f.severity === 'HIGH')
  const hasAnyFlags = report.active_flags.length > 0

  return (
    <div className="space-y-6">
      {/* ── 1. PROMINENT INTEGRITY WARNING BANNER ──────────────────────── */}
      {hasAnyFlags ? (
        <div
          className={`rounded-xl border p-5 transition-all shadow-sm ${
            hasHighRisk
              ? 'border-red-500/40 bg-red-950/25 text-red-100'
              : 'border-amber-500/40 bg-amber-950/25 text-amber-100'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              <div
                className={`p-2.5 rounded-lg ${
                  hasHighRisk ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
                }`}
              >
                <ShieldAlertIcon className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span
                    className={`text-xs font-black uppercase tracking-widest px-2.5 py-0.5 rounded ${
                      hasHighRisk ? 'bg-red-500/30 text-red-300 border border-red-500/40' : 'bg-amber-500/30 text-amber-300 border border-amber-500/40'
                    }`}
                  >
                    {hasHighRisk ? 'HIGH RISK' : 'MEDIUM RISK'}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {report.active_flags.length} active integrity signal{report.active_flags.length > 1 ? 's' : ''} detected
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white mt-1">
                  Suspicious Anti-Manipulation Flags
                </h3>
              </div>
            </div>

            <div className="text-right">
              <div className="text-2xl font-black text-white">
                {report.risk_score.toFixed(0)}
                <span className="text-sm font-normal text-zinc-400">/100</span>
              </div>
              <div className="text-xs text-zinc-400">Composite Risk</div>
            </div>
          </div>

          {/* Prominent Flag List */}
          <div className="mt-4 space-y-2.5 border-t border-white/10 pt-3">
            {report.active_flags.map((flag, idx) => (
              <div
                key={idx}
                className="flex items-start space-x-3 bg-black/40 rounded-lg p-3 border border-white/5"
              >
                <AlertTriangleIcon
                  className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                    flag.severity === 'HIGH' ? 'text-red-400' : 'text-amber-400'
                  }`}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <span className="text-amber-400">⚠</span> {flag.title}
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded ${
                        flag.severity === 'HIGH'
                          ? 'bg-red-500/20 text-red-300'
                          : 'bg-amber-500/20 text-amber-300'
                      }`}
                    >
                      {flag.signal_code}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-300 mt-1 leading-relaxed">
                    {flag.explanation}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-4 text-emerald-100 flex items-center space-x-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg text-emerald-400">
            <CheckCircleIcon className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-emerald-400">
              LOW RISK • ALL INTEGRITY CHECKS CLEAR
            </div>
            <div className="text-sm text-zinc-300">
              No cross-project collisions, GPS spoofing, or financial discrepancies detected.
            </div>
          </div>
        </div>
      )}

      {/* ── 2. PROTOTYPE TRANSPARENCY DISCLAIMERS ───────────────────────── */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-4 space-y-2 text-xs text-blue-200">
        <div className="flex items-center space-x-2 font-semibold text-blue-300">
          <InfoIcon className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>Anti-Manipulation Layer Transparency Guarantees</span>
        </div>
        <ul className="space-y-1.5 pl-6 list-disc text-zinc-300">
          <li>
            <strong className="text-blue-200">GPS Signal Notice:</strong> GPS coordinates are evaluated as a corroborating signal only. Prototype software cannot completely prevent hardware-level GPS spoofing. GPS does not guarantee physical authenticity.
          </li>
          <li>
            <strong className="text-blue-200">AI / Metadata Heuristic Notice:</strong> Automated media and metadata analysis are heuristic risk indicators, not definitive proof of manipulation.
          </li>
          <li>
            <strong className="text-blue-200">Audit Protocol:</strong> The platform surfaces suspicious behavior rather than silently accepting it, routing high-risk anomalies to independent human auditors.
          </li>
        </ul>
      </div>

      {/* ── 3. FORENSIC SUBMISSION ATTEMPT HISTORY ──────────────────────── */}
      {report.submission_history && (
        <div className="bg-zinc-900/60 rounded-xl border border-zinc-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              <ClockIcon className="w-4 h-4 text-purple-400" />
              Submission Attempt History
            </h4>
            <span className="text-xs text-zinc-400">
              Total Recorded: {report.submission_history.total_submissions} items
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5 text-center text-xs">
            <div className="bg-zinc-800/60 rounded-lg p-2.5 border border-zinc-700/50">
              <div className="text-zinc-400">Verified</div>
              <div className="text-lg font-bold text-emerald-400 mt-0.5">
                {report.submission_history.verified_count}
              </div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg p-2.5 border border-zinc-700/50">
              <div className="text-zinc-400">Failed/Rejected</div>
              <div className="text-lg font-bold text-red-400 mt-0.5">
                {report.submission_history.failed_count}
              </div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg p-2.5 border border-zinc-700/50">
              <div className="text-zinc-400">Duplicates</div>
              <div className="text-lg font-bold text-amber-400 mt-0.5">
                {report.submission_history.duplicate_count}
              </div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg p-2.5 border border-zinc-700/50">
              <div className="text-zinc-400">Revisions</div>
              <div className="text-lg font-bold text-blue-400 mt-0.5">
                {report.submission_history.revisions_count}
              </div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg p-2.5 border border-zinc-700/50">
              <div className="text-zinc-400">Superseded</div>
              <div className="text-lg font-bold text-purple-400 mt-0.5">
                {report.submission_history.superseded_count}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 4. 10-THREAT DEFENSE MATRIX ─────────────────────────────────── */}
      <div className="bg-zinc-900/60 rounded-xl border border-zinc-800 overflow-hidden">
        <div
          className="flex items-center justify-between p-4 bg-zinc-800/30 cursor-pointer hover:bg-zinc-800/50 transition-colors"
          onClick={() => setShowAllThreats(!showAllThreats)}
        >
          <div className="flex items-center space-x-2">
            <LayersIcon className="w-4 h-4 text-emerald-400" />
            <h4 className="text-sm font-semibold text-white">
              10-Threat Defense Matrix
            </h4>
            <span className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full">
              {report.threats_matrix.filter((t) => t.triggered).length} Triggered
            </span>
          </div>
          <button className="text-xs text-zinc-400 flex items-center space-x-1 hover:text-white">
            <span>{showAllThreats ? 'Collapse' : 'Expand Matrix'}</span>
            {showAllThreats ? <ChevronUpIcon className="w-3.5 h-3.5" /> : <ChevronDownIcon className="w-3.5 h-3.5" />}
          </button>
        </div>

        {showAllThreats && (
          <div className="divide-y divide-zinc-800/60 text-xs">
            {report.threats_matrix.map((threat) => {
              const isExpanded = expandedThreat === threat.threat_number
              return (
                <div key={threat.threat_number} className="p-3.5 hover:bg-zinc-800/20 transition-colors">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedThreat(isExpanded ? null : threat.threat_number)}
                  >
                    <div className="flex items-center space-x-3">
                      <span className="font-mono text-zinc-500 w-5">
                        #{threat.threat_number}
                      </span>
                      <span className="font-medium text-white">
                        {threat.threat_name}
                      </span>
                      {threat.is_probabilistic_signal && (
                        <span className="text-[10px] bg-blue-950/60 text-blue-300 border border-blue-800/50 px-1.5 py-0.5 rounded">
                          Signal Only
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-2">
                      <span
                        className={`font-semibold uppercase text-[10px] px-2 py-0.5 rounded ${
                          threat.status === 'FLAGGED'
                            ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                            : threat.status === 'WARNING'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {threat.status}
                      </span>
                      {isExpanded ? <ChevronUpIcon className="w-3.5 h-3.5 text-zinc-400" /> : <ChevronDownIcon className="w-3.5 h-3.5 text-zinc-400" />}
                    </div>
                  </div>

                  <p className="text-zinc-400 mt-1.5 pl-8 text-xs leading-relaxed">
                    {threat.explanation}
                  </p>

                  {isExpanded && (
                    <div className="mt-2.5 ml-8 p-3 rounded-lg bg-black/40 border border-zinc-800 space-y-2">
                      {threat.disclaimer && (
                        <div className="flex items-start space-x-2 text-amber-300/90 text-[11px]">
                          <InfoIcon className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                          <span>{threat.disclaimer}</span>
                        </div>
                      )}

                      {threat.details && Object.keys(threat.details).length > 0 && (
                        <div className="font-mono text-[11px] text-zinc-400 space-y-1">
                          {Object.entries(threat.details).map(([k, v]) => (
                            <div key={k} className="flex items-center justify-between">
                              <span className="text-zinc-500">{k}:</span>
                              <span className="text-zinc-300">{JSON.stringify(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
