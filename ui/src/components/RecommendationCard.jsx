import React from 'react';

const RecommendationCard = ({ recommendation, guidance }) => {
  const getBorderColor = () => {
    if (recommendation === 'ship') return 'var(--accent-green)';
    if (recommendation === 'ramp') return 'var(--accent-yellow)';
    return 'var(--accent-red)';
  };

  const getIcon = () => {
    if (recommendation === 'ship') return '🚀';
    if (recommendation === 'ramp') return '📈';
    return '✋';
  };

  return (
    <div className="result-card">
      <h3>{getIcon()} Rollout Guidance</h3>
      <div className="guidance-box" style={{ borderLeftColor: getBorderColor() }}>
        {guidance}
      </div>
    </div>
  );
};

export default RecommendationCard;

