// frontend/src/pages/Login.jsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export default function Login(){
  const [identifier,setIdentifier] = useState('') // username or email
  const [password,setPassword]=useState('')
  const { login } = useAuth()
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    try{
      await login(identifier, password)
      navigate('/mailplans')
    }catch(err){
      const msg = err?.response?.data?.detail || JSON.stringify(err?.response?.data) || err.message
      alert('Login failed: ' + msg)
    }
  }

  return (
    <div className="max-w-md mx-auto mt-24 bg-white p-6 rounded shadow">
      <h1 className="text-xl font-semibold mb-4">Sign in</h1>
      <form onSubmit={submit}>
        <label className="text-sm text-gray-600">Username or Email</label>
        <input value={identifier} onChange={e=>setIdentifier(e.target.value)} placeholder="Username or email" className="w-full p-2 border mb-2 rounded" />
        <input value={password} onChange={e=>setPassword(e.target.value)} type="password" placeholder="Password" className="w-full p-2 border mb-4 rounded" />
        <button className="w-full bg-blue-600 text-white p-2 rounded">Sign In</button>
      </form>
    </div>
  )
}
