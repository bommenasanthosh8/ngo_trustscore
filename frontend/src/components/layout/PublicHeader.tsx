import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'

export default function PublicHeader() {
  const { user } = useAuth()
  const location = useLocation()

  function isActive(path: string) {
    return location.pathname === path
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-surface-border/60 bg-surface/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-brand flex items-center justify-center text-white font-bold text-sm shadow-md shadow-brand-500/30">
            🛡️
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold text-white text-base tracking-tight leading-tight">
              Evidence<span className="text-brand-400">NGO</span>
            </span>
            <span className="text-[10px] text-slate-400 font-mono leading-none">
              Trust Engine
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center gap-1 text-xs font-medium">
          <Link
            to="/"
            className={`px-3.5 py-2 rounded-lg transition-colors ${
              isActive('/')
                ? 'bg-brand-950/70 text-brand-300 border border-brand-800/40'
                : 'text-slate-300 hover:text-white hover:bg-surface-card'
            }`}
          >
            How It Works
          </Link>
          <Link
            to="/public/ngos"
            className={`px-3.5 py-2 rounded-lg transition-colors ${
              isActive('/public/ngos')
                ? 'bg-brand-950/70 text-brand-300 border border-brand-800/40'
                : 'text-slate-300 hover:text-white hover:bg-surface-card'
            }`}
          >
            Explore NGOs
          </Link>
          <Link
            to="/public/projects"
            className={`px-3.5 py-2 rounded-lg transition-colors ${
              isActive('/public/projects')
                ? 'bg-brand-950/70 text-brand-300 border border-brand-800/40'
                : 'text-slate-300 hover:text-white hover:bg-surface-card'
            }`}
          >
            Verified Projects
          </Link>
          <Link
            to="/public/map"
            className={`px-3.5 py-2 rounded-lg transition-colors ${
              isActive('/public/map')
                ? 'bg-brand-950/70 text-brand-300 border border-brand-800/40'
                : 'text-slate-300 hover:text-white hover:bg-surface-card'
            }`}
          >
            Transparency Map
          </Link>
        </nav>

        {/* User / CTA buttons */}
        <div className="flex items-center gap-3">
          {user ? (
            <Link
              to="/dashboard"
              className="btn-primary text-xs px-4 py-2 flex items-center gap-1.5"
            >
              <span>👤</span> Dashboard ({user.role})
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="text-xs text-slate-300 hover:text-white px-3 py-1.5 transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="btn-primary text-xs px-4 py-2"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
