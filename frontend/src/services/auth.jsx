// frontend/src/services/auth.jsx
import React, { createContext, useContext, useState } from 'react'
import api from './api'

const AuthContext = createContext()

export function AuthProvider({ children }){
  const [token, setToken] = useState(localStorage.getItem('access_token') || null)

  const login = async (emailOrUsername, password) => {
    // Try common shapes: first 'email', then 'username'
    const attempts = [
      { email: emailOrUsername, password },
      { username: emailOrUsername, password },
    ];

    let lastError = null;
    for (const payload of attempts) {
      try {
        const res = await api.post('/token/', payload)
        // Save tokens and update state
        if (res?.data?.access) {
          localStorage.setItem('access_token', res.data.access)
          if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh)
          setToken(res.data.access)
          return res.data
        } else {
          // Unexpected shape — treat as error
          lastError = new Error('Token response missing access token')
        }
      } catch (err) {
        lastError = err
        const status = err?.response?.status
        const data = err?.response?.data
        // If server says invalid credentials, stop early and throw
        if (status === 401 || (data && data.detail)) throw err
        // otherwise continue trying next payload shape
      }
    }
    throw lastError || new Error('Login failed')
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
