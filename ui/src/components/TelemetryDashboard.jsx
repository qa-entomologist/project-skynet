import React from 'react';

const TelemetryDashboard = ({ telemetry, onRefresh }) => {
  if (!telemetry) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📊</div>
        <h3>Loading Telemetry…</h3>
        <p>Agent telemetry data will appear here after running assessments.</p>
      </div>
    );
  }

  const { total_runs, total_dd_queries, summary, runs } = telemetry;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700 }}>🤖 Agent Observability</h2>
        <button
          onClick={onRefresh}
          style={{
            padding: '8px 16px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            fontSize: 13,
            fontFamily: 'inherit',
          }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Top-level metrics */}
      <div className="telemetry-grid">
        <div className="telemetry-stat">
          <div className="telemetry-stat-value">{total_runs}</div>
          <div className="telemetry-stat-label">Total Runs</div>
        </div>
        <div className="telemetry-stat">
          <div className="telemetry-stat-value">{total_dd_queries}</div>
          <div className="telemetry-stat-label">DD Queries</div>
        </div>
        <div className="telemetry-stat">
          <div className="telemetry-stat-value">{summary?.avg_latency_ms || 0}ms</div>
          <div className="telemetry-stat-label">Avg Latency</div>
        </div>
        <div className="telemetry-stat">
          <div className="telemetry-stat-value">{summary?.avg_risk_score || 0}</div>
          <div className="telemetry-stat-label">Avg Risk Score</div>
        </div>
      </div>

      {/* Recommendation distribution */}
      <div className="telemetry-chart" style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
          📊 Recommendation Distribution
        </h3>
        <div className="rec-distribution">
          <div className="rec-dist-item">
            <div className="rec-dist-count" style={{ color: 'var(--accent-green)' }}>
              {summary?.recommendation_distribution?.ship || 0}
            </div>
            <div className="rec-dist-label" style={{ color: 'var(--accent-green)' }}>Ship</div>
          </div>
          <div className="rec-dist-item">
            <div className="rec-dist-count" style={{ color: 'var(--accent-yellow)' }}>
              {summary?.recommendation_distribution?.ramp || 0}
            </div>
            <div className="rec-dist-label" style={{ color: 'var(--accent-yellow)' }}>Ramp</div>
          </div>
          <div className="rec-dist-item">
            <div className="rec-dist-count" style={{ color: 'var(--accent-red)' }}>
              {summary?.recommendation_distribution?.hold || 0}
            </div>
            <div className="rec-dist-label" style={{ color: 'var(--accent-red)' }}>Hold</div>
          </div>
        </div>
      </div>

      {/* Recent runs detail */}
      {runs && runs.length > 0 && (
        <div className="result-card">
          <h3>🕐 Recent Agent Runs</h3>
          <div className="runs-table-container">
            <table className="runs-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Latency</th>
                  <th>DD Queries</th>
                  <th>Signatures</th>
                  <th>Risk Score</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--accent-purple)' }}>
                      {run.run_id}
                    </td>
                    <td>{run.latency_ms}ms</td>
                    <td>{run.dd_query_count}</td>
                    <td>{run.signatures_matched}</td>
                    <td>
                      <span style={{
                        fontWeight: 700,
                        color: run.risk_score <= 30 ? 'var(--accent-green)' :
                               run.risk_score <= 60 ? 'var(--accent-yellow)' :
                               'var(--accent-red)'
                      }}>
                        {run.risk_score}
                      </span>
                    </td>
                    <td>
                      <span className={`recommendation-badge ${run.recommendation}`} style={{ fontSize: 11, padding: '3px 10px' }}>
                        {run.recommendation?.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default TelemetryDashboard;

