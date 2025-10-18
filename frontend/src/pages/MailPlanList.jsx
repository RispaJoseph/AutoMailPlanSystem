import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export default function MailPlanList() {
  const [plans, setPlans] = useState([])
  const navigate = useNavigate()
  const { logout } = useAuth()

  useEffect(() => {
    loadPlans()
  }, [])

  const loadPlans = () => {
    api.get('/mailplans/')
      .then(res => {
        if (Array.isArray(res.data)) setPlans(res.data)
        else setPlans(res.data.results || [])
      })
      .catch(err => console.error('Error fetching mail plans', err))
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this mail plan?')) return
    try {
      await api.delete(`/mailplans/${id}/`)
      setPlans(prev => prev.filter(p => p.id !== id))
      alert('Mail plan deleted successfully')
    } catch (err) {
      console.error('Error deleting mail plan', err)
      alert('Failed to delete mail plan')
    }
  }

  function getRecipientFromFlow(plan) {
    try {
      const flow = plan.flow || {}
      const nodes = flow.nodes || []
      for (const node of nodes) {
        const data = node.data || {}
        if (node.type === 'email' || data.recipient_email) {
          return data.recipient_email
        }
      }
    } catch {}
    return plan.recipient_email || ''
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold">Mail Plans</h2>
        <div className="flex gap-3">
          <button onClick={() => navigate('/mailplans/new')} className="bg-green-600 text-white px-3 py-1 rounded">New Plan</button>
          <button onClick={handleLogout} className="bg-red-500 text-white px-3 py-1 rounded">Logout</button>
        </div>
      </div>

      <div className="bg-white rounded shadow">
        <table className="min-w-full">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-2 text-left">Name</th>
              <th className="p-2 text-left">Recipient</th>
              <th className="p-2 text-left">Trigger</th>
              <th className="p-2 text-left">Status</th>
              <th className="p-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {plans.map(p => (
              <tr key={p.id} className="border-t">
                <td className="p-2">{p.name}</td>
                <td className="p-2">{getRecipientFromFlow(p)}</td>
                <td className="p-2">{p.trigger_type}</td>
                <td className="p-2">{p.status}</td>
                <td className="p-2 space-x-3">
                  <button
                    onClick={() => navigate(`/mailplans/${p.id}/edit`)}
                    className="text-blue-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {plans.length === 0 && (
              <tr>
                <td colSpan="5" className="p-4 text-center text-gray-500">
                  No mail plans found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
