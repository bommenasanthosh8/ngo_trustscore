import { Outlet } from 'react-router-dom'
import PublicHeader from './PublicHeader'

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <PublicHeader />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-surface-border/40 py-8 bg-surface/80 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p>© 2026 EvidenceNGO Trust Engine. Tamper-evident, multi-engine public charity verification.</p>
          <p className="mt-1 text-[11px] text-slate-600 font-mono">
            Indicator: Evidence-based transparency/verification indicator.
          </p>
        </div>
      </footer>
    </div>
  )
}
