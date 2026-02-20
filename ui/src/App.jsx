import React, { useState, useEffect, useCallback } from 'react';
import './styles/App.css';
import RiskScoreGauge from './components/RiskScoreGauge';
import RecommendationCard from './components/RecommendationCard';
import RunHistory from './components/RunHistory';
import TelemetryDashboard from './components/TelemetryDashboard';

const API_BASE = '/api';

function App() {
  const [activeTab, setActiveTab] = useState('assess');
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);
  const [telemetry, setTelemetry] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    feature_name: '',
    service: '',
    platform: '',
    time_window_days: 30,
    tags: '',
    post_deploy_minutes: 60,
  });

  // Fetch services on mount
  useEffect(() => {
    fetch(`${API_BASE}/services`)
      .then(r => r.json())
      .then(data => setServices(data.services || []))
      .catch(() => {});
  }, []);

  const fetchRuns = useCallback(() => {
    fetch(`${API_BASE}/runs`)
      .then(r => r.json())
      .then(data => setRuns(data.runs || []))
      .catch(() => {});
  }, []);

  const fetchTelemetry = useCallback(() => {
    fetch(`${API_BASE}/telemetry`)
      .then(r => r.json())
      .then(data => setTelemetry(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (activeTab === 'history') fetchRuns();
    if (activeTab === 'telemetry') fetchTelemetry();
  }, [activeTab, fetchRuns, fetchTelemetry]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        ...formData,
        tags: formData.tags ? formData.tags.split(',').map(t => t.trim()) : null,
        platform: formData.platform || null,
      };

      const response = await fetch(`${API_BASE}/assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Assessment failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const getCheckIcon = (check) => {
    if (check.startsWith('CRITICAL')) return { cls: 'critical', icon: '!' };
    if (check.startsWith('WARNING')) return { cls: 'warning', icon: '⚠' };
    if (check.startsWith('WATCH')) return { cls: 'watch', icon: '👁' };
    return { cls: 'standard', icon: '✓' };
  };

  const getSimClass = (sim) => {
    if (sim >= 0.5) return 'high';
    if (sim >= 0.25) return 'medium';
    return 'low';
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <span className="header-logo">🛡️</span>
          <h1>Release Revert Risk Advisor</h1>
          <span className="header-badge">AI AGENT</span>
        </div>
      </header>

      <main className="main">
        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'assess' ? 'active' : ''}`}
            onClick={() => setActiveTab('assess')}
          >
            🔍 Assess Risk
          </button>
          <button
            className={`tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            📋 Run History
          </button>
          <button
            className={`tab ${activeTab === 'telemetry' ? 'active' : ''}`}
            onClick={() => setActiveTab('telemetry')}
          >
            📊 Agent Telemetry
          </button>
        </div>

        {/* ── Assess Tab ── */}
        {activeTab === 'assess' && (
          <div className="assess-section">
            {/* Form */}
            <form className="form-card" onSubmit={handleSubmit}>
              <h2>🚀 New Assessment</h2>

              <div className="form-group">
                <label>Feature / Experiment Name</label>
                <input
                  type="text"
                  value={formData.feature_name}
                  onChange={e => handleInputChange('feature_name', e.target.value)}
                  placeholder="e.g. playback-buffer-v2"
                  required
                />
              </div>

              <div className="form-group">
                <label>Service</label>
                <select
                  value={formData.service}
                  onChange={e => handleInputChange('service', e.target.value)}
                  required
                >
                  <option value="">Select a service…</option>
                  {services.map(s => (
                    <option key={s.name} value={s.name}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Platform</label>
                <select
                  value={formData.platform}
                  onChange={e => handleInputChange('platform', e.target.value)}
                >
                  <option value="">All platforms</option>
                  <option value="ios">iOS</option>
                  <option value="android">Android</option>
                  <option value="web">Web</option>
                </select>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>History Window (days)</label>
                  <input
                    type="number"
                    value={formData.time_window_days}
                    onChange={e => handleInputChange('time_window_days', parseInt(e.target.value) || 30)}
                    min="1"
                    max="365"
                  />
                </div>
                <div className="form-group">
                  <label>Post-deploy (min)</label>
                  <input
                    type="number"
                    value={formData.post_deploy_minutes}
                    onChange={e => handleInputChange('post_deploy_minutes', parseInt(e.target.value) || 60)}
                    min="1"
                    max="1440"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Tags (comma-separated)</label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={e => handleInputChange('tags', e.target.value)}
                  placeholder="e.g. playback, ios, latency"
                />
              </div>

              <button
                type="submit"
                className={`btn-assess ${loading ? 'loading' : ''}`}
                disabled={loading || !formData.feature_name || !formData.service}
              >
                {loading ? 'Analyzing…' : 'Run Risk Assessment'}
              </button>
            </form>

            {/* Results */}
            <div className="results-panel">
              {error && <div className="error-banner">⚠️ {error}</div>}

              {!result && !loading && (
                <div className="empty-state">
                  <div className="empty-state-icon">🔍</div>
                  <h3>Ready to Assess</h3>
                  <p>
                    Enter a feature name and service to analyze release risk
                    based on historical revert patterns and current SLI health.
                  </p>
                </div>
              )}

              {result && (
                <>
                  {/* Risk Score */}
                  <div className="result-card risk-score-card">
                    <RiskScoreGauge
                      score={result.risk_score}
                      recommendation={result.recommendation}
                    />
                    <div className="agent-metrics">
                      <span className="agent-metric">
                        ⏱️ Latency: <span>{result.agent_metrics?.latency_ms}ms</span>
                      </span>
                      <span className="agent-metric">
                        🔎 DD Queries: <span>{result.agent_metrics?.dd_query_count}</span>
                      </span>
                      <span className="agent-metric">
                        🧬 Signatures: <span>{result.agent_metrics?.signatures_matched}</span>
                      </span>
                    </div>
                  </div>

                  {/* Scoring Breakdown */}
                  <div className="result-card">
                    <h3>📈 Score Breakdown</h3>
                    <div className="scoring-bars">
                      <div className="score-bar">
                        <span className="score-bar-label">Similarity</span>
                        <div className="score-bar-track">
                          <div
                            className="score-bar-fill"
                            style={{
                              width: `${(result.scoring_breakdown.similarity / 50) * 100}%`,
                              background: 'var(--accent-purple)',
                            }}
                          />
                        </div>
                        <span className="score-bar-value">{result.scoring_breakdown.similarity}/50</span>
                      </div>
                      <div className="score-bar">
                        <span className="score-bar-label">Volatility</span>
                        <div className="score-bar-track">
                          <div
                            className="score-bar-fill"
                            style={{
                              width: `${(result.scoring_breakdown.volatility / 30) * 100}%`,
                              background: 'var(--accent-yellow)',
                            }}
                          />
                        </div>
                        <span className="score-bar-value">{result.scoring_breakdown.volatility}/30</span>
                      </div>
                      <div className="score-bar">
                        <span className="score-bar-label">Anomaly</span>
                        <div className="score-bar-track">
                          <div
                            className="score-bar-fill"
                            style={{
                              width: `${(result.scoring_breakdown.anomaly / 20) * 100}%`,
                              background: 'var(--accent-red)',
                            }}
                          />
                        </div>
                        <span className="score-bar-value">{result.scoring_breakdown.anomaly}/20</span>
                      </div>
                    </div>
                  </div>

                  {/* Risk Drivers */}
                  {result.risk_drivers?.length > 0 && (
                    <div className="result-card">
                      <h3>⚡ Top Risk Drivers</h3>
                      <ul className="risk-drivers-list">
                        {result.risk_drivers.map((driver, i) => (
                          <li key={i} className="risk-driver-item">{driver}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Matched Patterns */}
                  {result.matched_patterns?.length > 0 && (
                    <div className="result-card">
                      <h3>🔄 Similar Past Incidents</h3>
                      <div className="patterns-grid">
                        {result.matched_patterns.map((p, i) => (
                          <div key={i} className="pattern-card">
                            <div className="pattern-header">
                              <span className="pattern-id">{p.revert_id}</span>
                              <span className={`pattern-similarity ${getSimClass(p.similarity)}`}>
                                {(p.similarity * 100).toFixed(0)}% match
                              </span>
                            </div>
                            <div className="pattern-feature">{p.feature}</div>
                            <div className="pattern-desc">{p.description}</div>
                            <div className="pattern-meta">
                              <span className="pattern-tag">📅 {p.date?.slice(0, 10)}</span>
                              <span className="pattern-tag">🖥️ {p.platform}</span>
                              <span className="pattern-tag">⚠️ {p.severity}</span>
                              <span className="pattern-tag">📈 {p.max_spike_ratio}x spike</span>
                              {p.impacted_slis?.map(sli => (
                                <span key={sli} className="pattern-tag">{sli}</span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Monitoring Checks */}
                  <div className="result-card">
                    <h3>🔔 Recommended Monitoring</h3>
                    <div className="checks-list">
                      {result.monitoring_checks?.map((check, i) => {
                        const { cls, icon } = getCheckIcon(check);
                        return (
                          <div key={i} className="check-item">
                            <span className={`check-icon ${cls}`}>{icon}</span>
                            <span>{check}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Rollback Thresholds */}
                  {result.rollback_thresholds?.length > 0 && (
                    <div className="result-card">
                      <h3>🚧 Rollback Thresholds</h3>
                      <div className="runs-table-container">
                        <table className="thresholds-table">
                          <thead>
                            <tr>
                              <th>SLI</th>
                              <th>Baseline</th>
                              <th>Current</th>
                              <th>Warn At</th>
                              <th>Rollback At</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.rollback_thresholds.map((t, i) => (
                              <tr key={i}>
                                <td style={{ fontWeight: 600 }}>{t.sli}</td>
                                <td>{t.baseline_avg}</td>
                                <td>{t.current_value}</td>
                                <td>{t.warn_threshold}</td>
                                <td>{t.rollback_threshold}</td>
                                <td>
                                  <span className={`status-badge ${t.status.toLowerCase()}`}>
                                    {t.status}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Rollout Guidance */}
                  <RecommendationCard
                    recommendation={result.recommendation}
                    guidance={result.rollout_guidance}
                  />

                  {/* Evidence Trail */}
                  <div className="result-card">
                    <h3>🧾 Evidence Trail</h3>
                    <div className="evidence-list">
                      {result.evidence?.map((ev, i) => (
                        <div key={i} className="evidence-item">{ev}</div>
                      ))}
                    </div>
                  </div>

                  {/* Summary */}
                  <div className="result-card">
                    <h3>📝 Full Summary</h3>
                    <div className="summary-content">{result.summary}</div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── History Tab ── */}
        {activeTab === 'history' && (
          <RunHistory runs={runs} onRefresh={fetchRuns} />
        )}

        {/* ── Telemetry Tab ── */}
        {activeTab === 'telemetry' && (
          <TelemetryDashboard telemetry={telemetry} onRefresh={fetchTelemetry} />
        )}
      </main>
    </div>
  );
}

export default App;

