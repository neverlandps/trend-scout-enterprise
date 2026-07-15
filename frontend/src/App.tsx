import { BrowserRouter, Routes, Route } from 'react-router-dom'
import * as React from 'react'
import { Layout } from './components/Layout'

const { Suspense } = React

const SourcesPage = React.lazy(() => import('./pages/SourcesPage').then(m => ({ default: m.SourcesPage })))
const ScansPage = React.lazy(() => import('./pages/ScansPage').then(m => ({ default: m.ScansPage })))
const ReportsPage = React.lazy(() => import('./pages/ReportsPage').then(m => ({ default: m.ReportsPage })))
const SettingsPage = React.lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const LoginPage = React.lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const TeamPage = React.lazy(() => import('./pages/TeamPage').then(m => ({ default: m.TeamPage })))
const TrendsPage = React.lazy(() => import('./pages/TrendsPage').then(m => ({ default: m.TrendsPage })))

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div>Loading...</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<SourcesPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="scans" element={<ScansPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="trends" element={<TrendsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="team" element={<TeamPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
