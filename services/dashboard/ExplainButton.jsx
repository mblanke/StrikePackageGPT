/**
 * ExplainButton Component
 * Reusable inline "Explain" button for configs, logs, and errors
 * Shows modal/popover with LLM-powered explanation
 */

import React, { useState } from 'react';

const ExplainButton = ({ 
  type = 'config', // config, log, error, scan_result
  content, 
  context = {},
  size = 'small',
  style = {}
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [error, setError] = useState(null);

  const handleExplain = async () => {
    setIsLoading(true);
    setError(null);
    setShowModal(true);

    try {
      const response = await fetch('/api/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          content,
          context
        })
      });

      if (!response.ok) {
        throw new Error('Failed to get explanation');
      }

      const data = await response.json();
      setExplanation(data);
    } catch (err) {
      console.error('Error getting explanation:', err);
      setError('Failed to load explanation. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setExplanation(null);
    setError(null);
  };

  const buttonSizes = {
    small: { padding: '4px 8px', fontSize: '12px' },
    medium: { padding: '6px 12px', fontSize: '14px' },
    large: { padding: '8px 16px', fontSize: '16px' }
  };

  const buttonStyle = {
    ...buttonSizes[size],
    backgroundColor: '#3498DB',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    transition: 'background-color 0.2s',
    ...style
  };

  const renderExplanation = () => {
    if (error) {
      return (
        <div style={{ color: '#E74C3C', padding: '10px' }}>
          {error}
        </div>
      );
    }

    if (isLoading) {
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <div style={{ fontSize: '24px', marginBottom: '10px' }}>⏳</div>
          <div>Generating explanation...</div>
        </div>
      );
    }

    if (!explanation) {
      return null;
    }

    // Render based on explanation type
    switch (type) {
      case 'config':
        return (
          <div style={{ padding: '15px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '18px' }}>
              {explanation.config_key || 'Configuration'}
            </h3>
            
            <div style={{ marginBottom: '15px' }}>
              <strong>Current Value:</strong> 
              <code style={{ 
                backgroundColor: '#f5f5f5', 
                padding: '2px 6px', 
                borderRadius: '3px',
                marginLeft: '5px'
              }}>
                {explanation.current_value}
              </code>
            </div>

            <div style={{ marginBottom: '15px', lineHeight: '1.6' }}>
              <strong>What it does:</strong>
              <p style={{ margin: '5px 0' }}>{explanation.description}</p>
            </div>

            {explanation.example && (
              <div style={{ marginBottom: '15px', lineHeight: '1.6' }}>
                <strong>Example:</strong>
                <p style={{ margin: '5px 0', fontStyle: 'italic' }}>{explanation.example}</p>
              </div>
            )}

            {explanation.value_analysis && (
              <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#E8F4F8', borderRadius: '4px' }}>
                <strong>Analysis:</strong> {explanation.value_analysis}
              </div>
            )}

            {explanation.recommendations && explanation.recommendations.length > 0 && (
              <div style={{ marginBottom: '15px' }}>
                <strong>Recommendations:</strong>
                <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                  {explanation.recommendations.map((rec, i) => (
                    <li key={i} style={{ margin: '5px 0' }}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ fontSize: '12px', color: '#666', marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #ddd' }}>
              {explanation.requires_restart && (
                <div>⚠️ Changing this setting requires a restart</div>
              )}
              {!explanation.safe_to_change && (
                <div>⚠️ Use caution when changing this setting</div>
              )}
            </div>
          </div>
        );

      case 'error':
        return (
          <div style={{ padding: '15px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '18px', color: '#E74C3C' }}>
              Error Explanation
            </h3>

            <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#fef5e7', borderRadius: '4px', fontSize: '14px' }}>
              <strong>Original Error:</strong>
              <div style={{ marginTop: '5px', fontFamily: 'monospace', fontSize: '12px' }}>
                {explanation.original_error}
              </div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <strong>What went wrong:</strong>
              <p style={{ margin: '5px 0', lineHeight: '1.6' }}>{explanation.plain_english}</p>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <strong>Likely causes:</strong>
              <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                {explanation.likely_causes?.map((cause, i) => (
                  <li key={i} style={{ margin: '5px 0' }}>{cause}</li>
                ))}
              </ul>
            </div>

            <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#E8F8F5', borderRadius: '4px' }}>
              <strong>💡 How to fix it:</strong>
              <ol style={{ margin: '5px 0', paddingLeft: '20px' }}>
                {explanation.suggested_fixes?.map((fix, i) => (
                  <li key={i} style={{ margin: '5px 0' }}>{fix}</li>
                ))}
              </ol>
            </div>

            <div style={{ fontSize: '12px', color: '#666', marginTop: '15px' }}>
              Severity: <span style={{ 
                color: explanation.severity === 'critical' ? '#E74C3C' : 
                       explanation.severity === 'high' ? '#E67E22' : 
                       explanation.severity === 'medium' ? '#F39C12' : '#95A5A6',
                fontWeight: 'bold'
              }}>
                {(explanation.severity || 'unknown').toUpperCase()}
              </span>
            </div>
          </div>
        );

      case 'log':
        return (
          <div style={{ padding: '15px' }}>
            <h3 style={{ margin: '0 0 10px 0', fontSize: '18px' }}>
              Log Entry Explanation
            </h3>

            <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '4px', fontSize: '13px', fontFamily: 'monospace' }}>
              {explanation.log_entry}
            </div>

            <div style={{ marginBottom: '15px' }}>
              <strong>Level:</strong> 
              <span style={{ 
                marginLeft: '5px',
                padding: '2px 8px',
                borderRadius: '3px',
                backgroundColor: explanation.log_level === 'ERROR' ? '#E74C3C' : 
                                 explanation.log_level === 'WARNING' ? '#F39C12' : 
                                 explanation.log_level === 'INFO' ? '#3498DB' : '#95A5A6',
                color: 'white',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {explanation.log_level}
              </span>
            </div>

            {explanation.timestamp && (
              <div style={{ marginBottom: '15px', fontSize: '14px', color: '#666' }}>
                <strong>Time:</strong> {explanation.timestamp}
              </div>
            )}

            <div style={{ marginBottom: '15px', lineHeight: '1.6' }}>
              <strong>What this means:</strong>
              <p style={{ margin: '5px 0' }}>{explanation.explanation}</p>
            </div>

            {explanation.action_needed && explanation.next_steps && explanation.next_steps.length > 0 && (
              <div style={{ padding: '10px', backgroundColor: '#FEF5E7', borderRadius: '4px' }}>
                <strong>⚠️ Action needed:</strong>
                <ul style={{ margin: '5px 0', paddingLeft: '20px' }}>
                  {explanation.next_steps.map((step, i) => (
                    <li key={i} style={{ margin: '5px 0' }}>{step}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );

      default:
        return (
          <div style={{ padding: '15px' }}>
            <div>{explanation.explanation || 'No explanation available.'}</div>
          </div>
        );
    }
  };

  return (
    <>
      <button
        onClick={handleExplain}
        onMouseEnter={(e) => e.target.style.backgroundColor = '#2980B9'}
        onMouseLeave={(e) => e.target.style.backgroundColor = '#3498DB'}
        style={buttonStyle}
        title="Get AI-powered explanation"
      >
        <span>❓</span>
        <span>Explain</span>
      </button>

      {showModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
          onClick={closeModal}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '8px',
              maxWidth: '600px',
              maxHeight: '80vh',
              overflow: 'auto',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
              position: 'relative'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ 
              position: 'sticky', 
              top: 0, 
              backgroundColor: 'white', 
              padding: '15px', 
              borderBottom: '1px solid #ddd',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ margin: 0, fontSize: '20px' }}>Explanation</h2>
              <button
                onClick={closeModal}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                ×
              </button>
            </div>

            {renderExplanation()}
          </div>
        </div>
      )}
    </>
  );
};

export default ExplainButton;
