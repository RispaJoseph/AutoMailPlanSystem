// frontend/src/components/ErrorBoundary.jsx
import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ error, info })
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const { error, info } = this.state
    return (
      <div style={{ padding: 24 }}>
        <h2 style={{ color: '#b91c1c' }}>Something went wrong</h2>

        <div style={{ marginTop: 12, whiteSpace: 'pre-wrap', background: '#f8f8f8', padding: 12, borderRadius: 6 }}>
          <strong>Error:</strong>
          <div>{String(error && error.toString())}</div>
        </div>

        {info?.componentStack && (
          <details style={{ marginTop: 12, background: '#fff', padding: 8 }}>
            <summary style={{ cursor: 'pointer' }}>Component stack</summary>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{info.componentStack}</pre>
          </details>
        )}

        <p style={{ marginTop: 12 }}>Open the browser console for the full stack trace.</p>
      </div>
    )
  }
}
