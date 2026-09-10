import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/auth/AuthContext'
import ProtectedRoute from '@/auth/ProtectedRoute'
import PublicLayout from '@/components/layout/PublicLayout'
import LandingPage from '@/pages/LandingPage'
import NGOSearchPage from '@/pages/NGOSearchPage'
import NGOProfilePage from '@/pages/NGOProfilePage'
import PublicProjectsPage from '@/pages/PublicProjectsPage'
import PublicProjectDetailPage from '@/pages/PublicProjectDetailPage'
import PublicMapPage from '@/pages/PublicMapPage'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import Projects from '@/pages/Projects'
import NGOProjectDetailPage from '@/pages/NGOProjectDetailPage'
import EvidenceHub from '@/pages/EvidenceHub'
import AuditorAdminDashboard from '@/pages/AuditorAdminDashboard'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Transparency Experience routes */}
          <Route element={<PublicLayout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/public/ngos" element={<NGOSearchPage />} />
            <Route path="/public/ngos/:id" element={<NGOProfilePage />} />
            <Route path="/public/projects" element={<PublicProjectsPage />} />
            <Route path="/public/projects/:id" element={<PublicProjectDetailPage />} />
            <Route path="/public/map" element={<PublicMapPage />} />
          </Route>

          {/* Auth routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Unauthorized page */}
          <Route
            path="/unauthorized"
            element={
              <div className="min-h-screen bg-surface flex items-center justify-center text-white">
                <div className="text-center">
                  <h1 className="text-4xl font-bold text-red-400 mb-2">403</h1>
                  <p className="text-slate-400">You do not have permission to access this page.</p>
                </div>
              </div>
            }
          />

          {/* Protected routes (any authenticated role) */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/projects/:id" element={<NGOProjectDetailPage />} />
            <Route path="/evidence" element={<EvidenceHub />} />
          </Route>

          {/* Auditor + Admin routes */}
          <Route element={<ProtectedRoute allowedRoles={['AUDITOR', 'ADMIN']} />}>
            <Route path="/audit" element={<AuditorAdminDashboard />} />
          </Route>

          {/* Admin-only routes */}
          <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
            <Route path="/admin" element={<AuditorAdminDashboard />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

