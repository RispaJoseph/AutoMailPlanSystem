import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import MailPlanList from './pages/MailPlanList'
import MailPlanBuilder from './pages/MailPlanBuilder'
import { AuthProvider, useAuth } from './services/auth'
import ErrorBoundary from './components/ErrorBoundary'

function PrivateRoute({ children }) {
  const { token } = useAuth()
  if (!token) return <Navigate to='/login' />
  return children
}

export default function App(){
  return (
    <AuthProvider>
      <ErrorBoundary>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/login" element={<Login/>} />
            <Route path="/mailplans" element={
              <PrivateRoute><MailPlanList/></PrivateRoute>
            } />
            <Route path="/mailplans/new" element={
              <PrivateRoute><MailPlanBuilder/></PrivateRoute>
            } />
            <Route path="/mailplans/:id/edit" element={
              <PrivateRoute><MailPlanBuilder/></PrivateRoute>
            } />
            <Route path="*" element={<Navigate to='/mailplans'/>} />
          </Routes>
        </div>
      </ErrorBoundary>
    </AuthProvider>
  )
}
