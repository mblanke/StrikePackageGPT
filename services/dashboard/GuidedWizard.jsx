/**
 * GuidedWizard Component
 * Multi-step wizard for onboarding flows
 * Types: create_operation, onboard_agent, run_scan, first_time_setup
 */

import React, { useState, useEffect } from 'react';

const GuidedWizard = ({ 
  wizardType = 'first_time_setup',
  onComplete,
  onCancel,
  initialData = {}
}) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState(initialData);
  const [stepHelp, setStepHelp] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const wizardConfigs = {
    create_operation: {
      title: 'Create New Operation',
      steps: [
        {
          number: 1,
          title: 'Operation Name and Type',
          fields: [
            { name: 'operation_name', label: 'Operation Name', type: 'text', required: true, placeholder: 'Q4 Security Assessment' },
            { name: 'operation_type', label: 'Operation Type', type: 'select', required: true, options: [
              { value: 'external', label: 'External Penetration Test' },
              { value: 'internal', label: 'Internal Network Assessment' },
              { value: 'webapp', label: 'Web Application Test' },
              { value: 'wireless', label: 'Wireless Security Assessment' }
            ]}
          ]
        },
        {
          number: 2,
          title: 'Define Target Scope',
          fields: [
            { name: 'target_range', label: 'Target Network Range', type: 'text', required: true, placeholder: '192.168.1.0/24' },
            { name: 'excluded_hosts', label: 'Excluded Hosts (comma-separated)', type: 'text', placeholder: '192.168.1.1, 192.168.1.254' },
            { name: 'domains', label: 'Target Domains', type: 'textarea', placeholder: 'example.com\napp.example.com' }
          ]
        },
        {
          number: 3,
          title: 'Configure Assessment Tools',
          fields: [
            { name: 'scan_intensity', label: 'Scan Intensity', type: 'select', required: true, options: [
              { value: '1', label: 'Stealth (Slowest, least detectable)' },
              { value: '3', label: 'Balanced (Recommended)' },
              { value: '5', label: 'Aggressive (Fastest, easily detected)' }
            ]},
            { name: 'tools', label: 'Tools to Use', type: 'multiselect', options: [
              { value: 'nmap', label: 'Nmap (Network Scanning)' },
              { value: 'nikto', label: 'Nikto (Web Server Scanning)' },
              { value: 'gobuster', label: 'Gobuster (Directory Enumeration)' },
              { value: 'sqlmap', label: 'SQLMap (SQL Injection Testing)' }
            ]}
          ]
        }
      ]
    },
    run_scan: {
      title: 'Run Security Scan',
      steps: [
        {
          number: 1,
          title: 'Select Scan Tool',
          fields: [
            { name: 'tool', label: 'Security Tool', type: 'select', required: true, options: [
              { value: 'nmap', label: 'Nmap - Network Scanner' },
              { value: 'nikto', label: 'Nikto - Web Server Scanner' },
              { value: 'gobuster', label: 'Gobuster - Directory/File Discovery' },
              { value: 'sqlmap', label: 'SQLMap - SQL Injection' },
              { value: 'whatweb', label: 'WhatWeb - Technology Detection' }
            ]}
          ]
        },
        {
          number: 2,
          title: 'Specify Target',
          fields: [
            { name: 'target', label: 'Target', type: 'text', required: true, placeholder: '192.168.1.0/24 or example.com' },
            { name: 'ports', label: 'Ports (optional)', type: 'text', placeholder: '80,443,8080 or 1-1000' }
          ]
        },
        {
          number: 3,
          title: 'Scan Options',
          fields: [
            { name: 'scan_type', label: 'Scan Type', type: 'select', required: true, options: [
              { value: 'quick', label: 'Quick Scan (Fast, common ports)' },
              { value: 'full', label: 'Full Scan (Comprehensive, slower)' },
              { value: 'stealth', label: 'Stealth Scan (Slow, harder to detect)' },
              { value: 'vuln', label: 'Vulnerability Scan (Checks for known vulns)' }
            ]},
            { name: 'timeout', label: 'Timeout (seconds)', type: 'number', placeholder: '300' }
          ]
        }
      ]
    },
    first_time_setup: {
      title: 'Welcome to StrikePackageGPT',
      steps: [
        {
          number: 1,
          title: 'Welcome',
          fields: [
            { name: 'user_name', label: 'Your Name', type: 'text', placeholder: 'John Doe' },
            { name: 'skill_level', label: 'Security Testing Experience', type: 'select', required: true, options: [
              { value: 'beginner', label: 'Beginner - Learning the basics' },
              { value: 'intermediate', label: 'Intermediate - Some experience' },
              { value: 'advanced', label: 'Advanced - Professional pentester' }
            ]}
          ]
        },
        {
          number: 2,
          title: 'Configure LLM Provider',
          fields: [
            { name: 'llm_provider', label: 'LLM Provider', type: 'select', required: true, options: [
              { value: 'ollama', label: 'Ollama (Local, Free)' },
              { value: 'openai', label: 'OpenAI (Cloud, Requires API Key)' },
              { value: 'anthropic', label: 'Anthropic Claude (Cloud, Requires API Key)' }
            ]},
            { name: 'api_key', label: 'API Key (if using cloud provider)', type: 'password', placeholder: 'sk-...' }
          ]
        },
        {
          number: 3,
          title: 'Review and Finish',
          fields: []
        }
      ]
    }
  };

  const config = wizardConfigs[wizardType] || wizardConfigs.first_time_setup;
  const totalSteps = config.steps.length;
  const currentStepConfig = config.steps[currentStep - 1];

  useEffect(() => {
    fetchStepHelp();
  }, [currentStep]);

  const fetchStepHelp = async () => {
    try {
      const response = await fetch(`/api/wizard/help?type=${wizardType}&step=${currentStep}`);
      if (response.ok) {
        const data = await response.json();
        setStepHelp(data);
      }
    } catch (err) {
      console.error('Failed to fetch step help:', err);
    }
  };

  const handleFieldChange = (fieldName, value) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));
  };

  const validateCurrentStep = () => {
    const requiredFields = currentStepConfig.fields.filter(f => f.required);
    for (const field of requiredFields) {
      if (!formData[field.name]) {
        setError(`${field.label} is required`);
        return false;
      }
    }
    setError(null);
    return true;
  };

  const handleNext = () => {
    if (!validateCurrentStep()) return;
    
    if (currentStep < totalSteps) {
      setCurrentStep(prev => prev + 1);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
      setError(null);
    }
  };

  const handleComplete = async () => {
    if (!validateCurrentStep()) return;

    setLoading(true);
    try {
      if (onComplete) {
        await onComplete(formData);
      }
    } catch (err) {
      setError('Failed to complete wizard: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderField = (field) => {
    const commonStyle = {
      width: '100%',
      padding: '10px',
      border: '1px solid #ddd',
      borderRadius: '4px',
      fontSize: '14px'
    };

    switch (field.type) {
      case 'text':
      case 'password':
      case 'number':
        return (
          <input
            type={field.type}
            value={formData[field.name] || ''}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            style={commonStyle}
          />
        );

      case 'textarea':
        return (
          <textarea
            value={formData[field.name] || ''}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            rows={4}
            style={{ ...commonStyle, resize: 'vertical' }}
          />
        );

      case 'select':
        return (
          <select
            value={formData[field.name] || ''}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            style={commonStyle}
          >
            <option value="">Select...</option>
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        );

      case 'multiselect':
        const selectedValues = formData[field.name] || [];
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {field.options?.map(opt => (
              <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedValues.includes(opt.value)}
                  onChange={(e) => {
                    const newValues = e.target.checked
                      ? [...selectedValues, opt.value]
                      : selectedValues.filter(v => v !== opt.value);
                    handleFieldChange(field.name, newValues);
                  }}
                />
                <span>{opt.label}</span>
              </label>
            ))}
          </div>
        );

      default:
        return null;
    }
  };

  return (
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
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          width: '90%',
          maxWidth: '700px',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
        }}
      >
        {/* Header */}
        <div style={{ 
          padding: '20px', 
          borderBottom: '2px solid #3498DB',
          backgroundColor: '#f8f9fa'
        }}>
          <h2 style={{ margin: '0 0 10px 0', color: '#2C3E50' }}>{config.title}</h2>
          
          {/* Progress indicator */}
          <div style={{ display: 'flex', gap: '5px', marginTop: '15px' }}>
            {config.steps.map((step, index) => (
              <div
                key={index}
                style={{
                  flex: 1,
                  height: '4px',
                  backgroundColor: index + 1 <= currentStep ? '#3498DB' : '#ddd',
                  borderRadius: '2px',
                  transition: 'background-color 0.3s'
                }}
              />
            ))}
          </div>
          <div style={{ marginTop: '8px', fontSize: '14px', color: '#666' }}>
            Step {currentStep} of {totalSteps}
          </div>
        </div>

        {/* Step content */}
        <div style={{ padding: '30px' }}>
          <h3 style={{ margin: '0 0 20px 0', color: '#34495E' }}>
            {currentStepConfig.title}
          </h3>

          {/* Help section */}
          {stepHelp && (
            <div style={{ 
              padding: '15px', 
              backgroundColor: '#E8F4F8', 
              borderRadius: '6px', 
              marginBottom: '20px',
              borderLeft: '4px solid #3498DB'
            }}>
              {stepHelp.description && (
                <p style={{ margin: '0 0 10px 0' }}>{stepHelp.description}</p>
              )}
              {stepHelp.tips && stepHelp.tips.length > 0 && (
                <div>
                  <strong style={{ fontSize: '14px' }}>💡 Tips:</strong>
                  <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px', fontSize: '14px' }}>
                    {stepHelp.tips.map((tip, i) => (
                      <li key={i} style={{ margin: '5px 0' }}>{tip}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Form fields */}
          {currentStepConfig.fields.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {currentStepConfig.fields.map(field => (
                <div key={field.name}>
                  <label style={{ 
                    display: 'block', 
                    marginBottom: '8px', 
                    fontWeight: '500',
                    color: '#2C3E50'
                  }}>
                    {field.label}
                    {field.required && <span style={{ color: '#E74C3C' }}> *</span>}
                  </label>
                  {renderField(field)}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
              <h4>Review Your Settings</h4>
              <div style={{ 
                marginTop: '20px', 
                textAlign: 'left', 
                backgroundColor: '#f8f9fa', 
                padding: '15px', 
                borderRadius: '4px',
                maxHeight: '300px',
                overflow: 'auto'
              }}>
                {Object.entries(formData).map(([key, value]) => (
                  <div key={key} style={{ marginBottom: '10px' }}>
                    <strong>{key}:</strong> {Array.isArray(value) ? value.join(', ') : value}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div style={{ 
              marginTop: '20px', 
              padding: '12px', 
              backgroundColor: '#FCE4E4', 
              color: '#E74C3C', 
              borderRadius: '4px',
              fontSize: '14px'
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ 
          padding: '20px', 
          borderTop: '1px solid #ddd',
          display: 'flex',
          justifyContent: 'space-between',
          backgroundColor: '#f8f9fa'
        }}>
          <button
            onClick={onCancel}
            style={{
              padding: '10px 20px',
              border: '1px solid #95A5A6',
              backgroundColor: 'white',
              color: '#666',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Cancel
          </button>

          <div style={{ display: 'flex', gap: '10px' }}>
            {currentStep > 1 && (
              <button
                onClick={handleBack}
                style={{
                  padding: '10px 20px',
                  border: '1px solid #3498DB',
                  backgroundColor: 'white',
                  color: '#3498DB',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Back
              </button>
            )}

            <button
              onClick={handleNext}
              disabled={loading}
              style={{
                padding: '10px 20px',
                border: 'none',
                backgroundColor: loading ? '#95A5A6' : '#3498DB',
                color: 'white',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              {loading ? 'Processing...' : currentStep === totalSteps ? 'Finish' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GuidedWizard;
