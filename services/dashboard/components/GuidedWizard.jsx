import React, { useState } from 'react';

const WIZARD_TYPES = {
  first_time_setup: {
    title: 'Welcome to GooseStrike',
    steps: [
      { id: 'intro', title: 'Introduction', icon: '👋' },
      { id: 'phases', title: 'Methodology', icon: '📋' },
      { id: 'tools', title: 'Security Tools', icon: '🛠️' },
      { id: 'start', title: 'Get Started', icon: '🚀' },
    ],
  },
  run_scan: {
    title: 'Run Security Scan',
    steps: [
      { id: 'target', title: 'Target Selection', icon: '🎯' },
      { id: 'scan-type', title: 'Scan Type', icon: '🔍' },
      { id: 'options', title: 'Options', icon: '⚙️' },
      { id: 'execute', title: 'Execute', icon: '▶️' },
    ],
  },
  create_operation: {
    title: 'Create Security Operation',
    steps: [
      { id: 'details', title: 'Operation Details', icon: '📝' },
      { id: 'scope', title: 'Target Scope', icon: '🎯' },
      { id: 'methodology', title: 'Methodology', icon: '📋' },
      { id: 'review', title: 'Review', icon: '✅' },
    ],
  },
};

const GuidedWizard = ({ type = 'first_time_setup', onComplete = () => {}, onCancel = () => {} }) => {
  const wizard = WIZARD_TYPES[type] || WIZARD_TYPES.first_time_setup;
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState({});

  const handleNext = () => {
    if (currentStep < wizard.steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      onComplete(formData);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleInputChange = (key, value) => {
    setFormData({ ...formData, [key]: value });
  };

  const progress = ((currentStep + 1) / wizard.steps.length) * 100;

  return (
    <div className="guided-wizard fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-sp-dark rounded-lg border border-sp-grey-mid w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-sp-grey-mid">
          <h2 className="text-2xl font-bold text-sp-white">{wizard.title}</h2>
          <div className="mt-4 flex gap-2">
            {wizard.steps.map((step, idx) => (
              <div
                key={step.id}
                className={`wizard-step flex-1 p-2 rounded text-center border transition ${
                  idx === currentStep
                    ? 'border-sp-red bg-sp-red bg-opacity-10'
                    : idx < currentStep
                    ? 'border-green-500 bg-green-500 bg-opacity-10'
                    : 'border-sp-grey-mid'
                }`}
              >
                <div className="text-xl">{step.icon}</div>
                <div className="text-xs text-sp-white-muted mt-1">{step.title}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 h-1 bg-sp-grey-mid rounded overflow-hidden">
            <div
              className="wizard-progress h-full bg-sp-red transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="text-sp-white">
            {/* Render step content based on wizard type and current step */}
            {type === 'first_time_setup' && currentStep === 0 && (
              <div>
                <h3 className="text-xl font-bold mb-4">Welcome to GooseStrike! 🍁</h3>
                <p className="text-sp-white-muted mb-4">
                  GooseStrike is an AI-powered penetration testing platform that follows industry-standard
                  methodologies to help you identify security vulnerabilities.
                </p>
                <ul className="list-disc list-inside text-sp-white-muted space-y-2">
                  <li>AI-assisted security analysis with local or cloud LLMs</li>
                  <li>600+ integrated Kali Linux security tools</li>
                  <li>Voice control for hands-free operation</li>
                  <li>Interactive network visualization</li>
                  <li>Comprehensive reporting and documentation</li>
                </ul>
              </div>
            )}
            {type === 'run_scan' && currentStep === 0 && (
              <div>
                <h3 className="text-xl font-bold mb-4">Select Target</h3>
                <label className="block mb-2 text-sm text-sp-white-muted">Target IP or hostname</label>
                <input
                  type="text"
                  className="w-full bg-sp-grey border border-sp-grey-mid rounded px-3 py-2 text-sp-white"
                  placeholder="192.168.1.100 or example.com"
                  value={formData.target || ''}
                  onChange={(e) => handleInputChange('target', e.target.value)}
                />
              </div>
            )}
            {/* Add more step content as needed */}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-sp-grey-mid flex justify-between">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-sp-grey hover:bg-sp-grey-light rounded text-sp-white transition"
          >
            Cancel
          </button>
          <div className="flex gap-2">
            {currentStep > 0 && (
              <button
                onClick={handleBack}
                className="px-4 py-2 bg-sp-grey hover:bg-sp-grey-light rounded text-sp-white transition"
              >
                ← Back
              </button>
            )}
            <button
              onClick={handleNext}
              className="px-4 py-2 bg-sp-red hover:bg-sp-red-dark rounded text-sp-white transition"
            >
              {currentStep === wizard.steps.length - 1 ? 'Complete' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GuidedWizard;
