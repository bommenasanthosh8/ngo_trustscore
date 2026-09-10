import { useAuth } from '@/auth/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-surface-border bg-surface-card/50 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div className="lg:hidden">
          {/* Mobile menu toggle — wired in Phase 2 */}
          <button className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
        <h2 className="text-sm font-semibold text-slate-300">Dashboard</h2>
      </div>

      <div className="flex items-center gap-4">
        {user && (
          <>
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-medium text-white leading-tight">{user.full_name}</span>
              <span className="text-xs text-slate-400">{user.email}</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-gradient-brand flex items-center justify-center
                            text-white font-semibold text-sm shadow-lg shadow-brand-500/30">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <button
              id="navbar-logout"
              onClick={logout}
              className="text-slate-400 hover:text-red-400 transition-colors p-2 rounded-lg
                         hover:bg-red-900/20"
              title="Sign out"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </>
        )}
      </div>
    </header>
  )
}
