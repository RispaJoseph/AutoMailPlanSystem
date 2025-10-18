// frontend/src/pages/MailPlanBuilder.jsx
import React, { useCallback, useEffect, useState } from 'react'
import ReactFlow, {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Controls,
  Background,
} from 'reactflow'
import 'reactflow/dist/style.css'
import api from '../services/api'
import { useParams, useNavigate } from 'react-router-dom'
import NodeEditor from '../components/NodeEditor'

export default function MailPlanBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()

  // Plan name state (used when saving)
  const [planName, setPlanName] = useState('')

  // Seed with a Start node
  const [nodes, setNodes] = useState([
    { id: 'start', position: { x: 300, y: 200 }, data: { label: 'Start' }, type: 'start' },
  ])
  const [edges, setEdges] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)

  // Defensive loader: uses data.flow if present, otherwise build a simple flow from top-level fields
  useEffect(() => {
    if (!id) return;

    api.get(`/mailplans/${id}/`)
      .then(res => {
        const data = res.data || {}

        // Try to find a flow field under common keys
        let flow = null
        if (data.flow && (data.flow.nodes || data.flow.edges)) flow = data.flow
        else if (data.flow_json && (data.flow_json.nodes || data.flow_json.edges)) flow = data.flow_json
        else if (data.nodes || data.edges) flow = { nodes: data.nodes || [], edges: data.edges || [] }

        if (flow) {
          setNodes(Array.isArray(flow.nodes) ? flow.nodes : [])
          setEdges(Array.isArray(flow.edges) ? flow.edges : [])
          setPlanName(data.name || '')
          return
        }

        // No flow present — construct a minimal Trigger -> Email flow from top-level fields
        const triggerType = data.trigger_type || 'button_click'
        const emailNodeId = `email-${Date.now()}`
        const triggerNodeId = `trigger-${Date.now()}`

        const constructedNodes = [
          { id: triggerNodeId, type: 'trigger', position: { x: 100, y: 120 }, data: { label: 'Trigger', trigger_type: triggerType } },
          {
            id: emailNodeId,
            type: 'email',
            position: { x: 420, y: 120 },
            data: {
              label: data.name || 'Email',
              subject: data.subject || '',
              body: data.content || '',
              recipient_email: data.recipient_email || '',
              template_vars: data.template_vars || {}
            }
          }
        ]

        const constructedEdges = [{ id: `e-${triggerNodeId}-${emailNodeId}`, source: triggerNodeId, target: emailNodeId }]

        setNodes(constructedNodes)
        setEdges(constructedEdges)
        setPlanName(data.name || '')
        console.warn('MailPlan had no flow; building UI nodes from top-level fields', data.id)
      })
      .catch(err => {
        console.error('Failed to load mailplan', err)
      })
  }, [id])

  const onNodesChange = useCallback((changes) => setNodes(ns => applyNodeChanges(changes, ns)), [])
  const onEdgesChange = useCallback((changes) => setEdges(es => applyEdgeChanges(changes, es)), [])
  const onConnect = useCallback((params) => setEdges(es => addEdge(params, es)), [])

  // toolbar actions: add trigger/email/delay nodes
  const addNode = (type) => {
    const nextId = `${type}-${Date.now()}`
    const baseData = { label: type === 'email' ? 'Email' : type === 'trigger' ? 'Trigger' : 'Delay' }

    // default data per node type
    let data = { ...baseData }
    if (type === 'trigger') {
      data = { ...data, trigger_type: 'button_click' } // default - can be changed in NodeEditor
    } else if (type === 'email') {
      data = { ...data, subject: '', body: '', recipient_email: '', template_vars: {} }
    } else if (type === 'delay') {
      // default delay of 1 hour
      data = { ...data, duration: 1, unit: 'hours' } // unit: 'minutes'|'hours'|'days'
    }

    const newNode = {
      id: nextId,
      type,
      position: { x: 100 + Math.random() * 400, y: 100 + Math.random() * 300 },
      data
    }
    setNodes((nds) => nds.concat(newNode))
  }


  // select node
  const onNodeClick = (evt, node) => {
    setSelectedNode(node)
  }

  // update node data helper
  const updateNodeData = (nodeId, key, value) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== nodeId) return n
        const newData = { ...(n.data || {}) }
        if (key === '__save__') {
          // no-op; we persist later on Save button
        } else {
          // support nested fields
          newData[key] = value
        }
        return { ...n, data: newData }
      })
    )
    // reflect selectedNode changes in the panel immediately
    setSelectedNode((prev) => (prev && prev.id === nodeId ? { ...prev, data: { ...prev.data, [key]: value } } : prev))
  }

  // delete node
  const removeSelectedNode = () => {
    if (!selectedNode) return
    setNodes((nds) => nds.filter(n => n.id !== selectedNode.id))
    setEdges((eds) => eds.filter(e => e.source !== selectedNode.id && e.target !== selectedNode.id))
    setSelectedNode(null)
  }

  // helper to derive recipient from nodes (same logic as list)
  const getRecipientFromNodes = (nodesList) => {
    try {
      const nodesArr = nodesList || []
      for (const n of nodesArr) {
        if (!n) continue
        const data = n.data || {}
        if (n.type === 'email' || data.recipient_email || data.recipient) {
          const email = data.recipient_email || data.recipient
          if (email) return email
        }
      }
    } catch (err) {
      // ignore
    }
    return null
  }

  const savePlan = async () => {
    try {
      // find first email node to fill subject/content/recipient defaults
      const emailNode = nodes.find(n => (n.type === 'email') || (n.data && (n.data.subject || n.data.body || n.data.recipient_email)))
      const triggerNode = nodes.find(n => (n.type === 'trigger') || (n.data && n.data.trigger_type))

      // derive recipient from nodes robustly
      const derivedRecipient = getRecipientFromNodes(nodes) || (emailNode?.data?.recipient_email) || (emailNode?.data?.recipient) || 'test@example.com'

      const payload = {
        name: planName || (emailNode?.data?.label || 'Untitled'),
        // top-level required fields the backend expects
        subject: emailNode?.data?.subject || 'No Subject',
        content: emailNode?.data?.body || emailNode?.data?.content || 'No content',
        trigger_type: triggerNode?.data?.trigger_type || 'button_click',
        // ensure top-level recipient_email is always the derived email from nodes
        recipient_email: derivedRecipient,
        // include the full visual flow for persistence
        flow: {
          nodes: nodes || [],
          edges: edges || []
        },
        // keep template_vars top-level too (optional)
        template_vars: emailNode?.data?.template_vars || {}
      }

      if (id) {
        // use PATCH so partial updates are safer (backend may accept PUT too)
        await api.patch(`/mailplans/${id}/`, payload)
      } else {
        await api.post('/mailplans/', payload)
      }
      alert('Saved')
      navigate('/mailplans')
    } catch (err) {
      console.error('Save failed', err?.response?.data || err.message)
      alert('Save failed: ' + JSON.stringify(err?.response?.data || err?.message))
    }
  }

  return (
    <div className="h-[86vh] flex flex-col">
      <div className="p-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <input
            value={planName}
            onChange={(e) => setPlanName(e.target.value)}
            placeholder="Plan name (optional)"
            className="p-2 border rounded"
          />
          <button onClick={() => addNode('trigger')} className="bg-yellow-400 px-3 py-1 rounded">Add Trigger</button>
          <button onClick={() => addNode('email')} className="bg-green-500 px-3 py-1 rounded text-white">Add Email</button>
          <button onClick={() => addNode('delay')} className="bg-indigo-500 px-3 py-1 rounded text-white">Add Delay</button>
          <button onClick={removeSelectedNode} className="bg-red-500 px-3 py-1 rounded text-white">Delete Node</button>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => navigate('/mailplans')}
            className="bg-gray-300 px-3 py-1 rounded hover:bg-gray-400"
          >
            Back
          </button>

          <button
            onClick={() => {
              setNodes([{ id: 'start', position: { x: 300, y: 200 }, data: { label: 'Start' }, type: 'start' }]);
              setEdges([]);
            }}
            className="px-3 py-1 border rounded"
          >
            Reset
          </button>

          <button
            onClick={savePlan}
            className="bg-blue-600 px-3 py-1 rounded text-white hover:bg-blue-700"
          >
            Save
          </button>
        </div>

      </div>

      <div className="flex flex-1">
        <div className="flex-1 bg-gray-50 p-4">
          <div className="bg-white rounded shadow h-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              fitView
              style={{ width: '100%', height: '100%' }}
            >
              <Controls />
              <Background gap={16} />
            </ReactFlow>
          </div>
        </div>

        <div className="w-96 border-l">
          <NodeEditor
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onChange={(field, value) => {
              if (!selectedNode) return
              updateNodeData(selectedNode.id, field, value)
            }}
          />
        </div>
      </div>
    </div>
  )
}
