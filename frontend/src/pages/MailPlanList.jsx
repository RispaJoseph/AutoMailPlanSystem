import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export default function MailPlanList() {
  const [plans, setPlans] = useState([])
  const [loadingIds, setLoadingIds] = useState([]) // track which plans are being triggered
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

  const handleTrigger = async (planId) => {
    if (loadingIds.includes(planId)) return
    setLoadingIds(prev => [...prev, planId])
    try {
      const res = await api.post(`/mailplans/${planId}/trigger/`, { confirm: true })
      const message = res?.data?.message || 'Triggered'
      alert(message)

      // Map response to a UI status
      setPlans(prev => prev.map(p => {
        if (p.id === planId) {
          let newStatus = p.status
          if (res.status === 200) {
            newStatus = 'sent'
          } else if (res.status === 202) {
            const msg = (res.data?.message || '').toLowerCase()
            if (msg.includes('flow enqueued') || msg.includes('honor') || msg.includes('scheduled')) {
              newStatus = 'scheduled'
            } else if (msg.includes('mail send enqueued') || msg.includes('mail send')) {
              newStatus = 'sent'
            } else {
              newStatus = 'scheduled'
            }
          }
          return { ...p, status: newStatus }
        }
        return p
      }))
    } catch (err) {
      console.error('Trigger failed', err)
      const errMsg = err?.response?.data?.error || 'Failed to trigger mail plan'
      alert(errMsg)
    } finally {
      setLoadingIds(prev => prev.filter(id => id !== planId))
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold">Mail Plans</h2>
        <div className="flex gap-3">
          <button
            onClick={() => navigate('/mailplans/new')}
            className="bg-green-600 text-white px-3 py-1 rounded"
          >
            New Plan
          </button>
          <button
            onClick={handleLogout}
            className="bg-red-500 text-white px-3 py-1 rounded"
          >
            Logout
          </button>
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
                  
                  {/* Edit button */}
                  <button
                    onClick={() => navigate(`/mailplans/${p.id}/edit`)}
                    className="text-blue-600 hover:underline"
                  >
                    Edit
                  </button>

                  {/* Delete button */}
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="text-red-600 hover:underline"
                  >
                    Delete
                  </button>

                  {/* Send Now button (after Edit & Delete) */}
                  {p.trigger_type === 'button_click' && p.status === 'active' && (
                    <button
                      onClick={() => handleTrigger(p.id)}
                      disabled={loadingIds.includes(p.id)}
                      className={`px-2 py-1 rounded ${loadingIds.includes(p.id)
                        ? 'bg-gray-300 text-gray-700'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                    >
                      {loadingIds.includes(p.id) ? 'Sending...' : 'Send Now'}
                    </button>
                  )}
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
