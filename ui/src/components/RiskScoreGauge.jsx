import React from 'react';

const RiskScoreGauge = ({ score, recommendation }) => {
  const radius = 80;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const offset = circumference - progress;

  const getColor = () => {
    if (score <= 30) return 'var(--risk-low)';
    if (score <= 60) return 'var(--risk-medium)';
    return 'var(--risk-high)';
  };

  const getEmoji = () => {
    if (recommendation === 'ship') return '🟢';
    if (recommendation === 'ramp') return '🟡';
    return '🔴';
  };

  return (
    <div>
      <div className="risk-gauge">
        <svg viewBox="0 0 200 200">
          <circle
            className="risk-gauge-bg"
            cx="100"
            cy="100"
            r={radius}
          />
          <circle
            className="risk-gauge-fill"
            cx="100"
            cy="100"
            r={radius}
            stroke={getColor()}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="risk-gauge-text">
          <div className="risk-score-number" style={{ color: getColor() }}>
            {score}
          </div>
          <div className="risk-score-label">out of 100</div>
        </div>
      </div>
      <div className={`recommendation-badge ${recommendation}`}>
        {getEmoji()} {recommendation?.toUpperCase()}
      </div>
    </div>
  );
};

export default RiskScoreGauge;

