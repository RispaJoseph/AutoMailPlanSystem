import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export default function Header() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex justify-between items-center bg-gray-800 text-white p-4">
      <h1 className="font-bold text-lg">Auto Mail Plan</h1>
      <button onClick={handleLogout} className="bg-red-500 hover:bg-red-600 px-3 py-1 rounded">
        Logout
      </button>
    </div>
  )
}
