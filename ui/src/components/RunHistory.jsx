import React from 'react';

const RunHistory = ({ runs, onRefresh }) => {
  const getRiskClass = (score) => {
    if (score <= 30) return 'low';
    if (score <= 60) return 'medium';
    return 'high';
  };

  const getRecEmoji = (rec) => {
    if (rec === 'ship') return '🟢';
    if (rec === 'ramp') return '🟡';
    return '🔴';
  };

  if (!runs || runs.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <h3>No Runs Yet</h3>
        <p>Run your first risk assessment to see history here.</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700 }}>Assessment History</h2>
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
      <div className="result-card">
        <div className="runs-table-container">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Feature</th>
                <th>Service</th>
                <th>Risk Score</th>
                <th>Recommendation</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--accent-purple)' }}>
                    {run.run_id}
                  </td>
                  <td style={{ fontWeight: 600 }}>{run.feature_name}</td>
                  <td>{run.service}</td>
                  <td>
                    <span className={`run-risk-score ${getRiskClass(run.risk_score)}`}>
                      {run.risk_score}
                    </span>
                  </td>
                  <td>
                    <span className={`recommendation-badge ${run.recommendation}`} style={{ fontSize: 12, padding: '4px 12px' }}>
                      {getRecEmoji(run.recommendation)} {run.recommendation?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    {run.timestamp ? new Date(run.timestamp).toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default RunHistory;

