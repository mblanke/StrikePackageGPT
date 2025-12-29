import React from 'react';
import { createRoot } from 'react-dom/client';
import VoiceControls from './VoiceControls';
import NetworkMap from './NetworkMap';
import GuidedWizard from './GuidedWizard';

// Export components for external mounting
window.GooseStrikeComponents = {
  VoiceControls,
  NetworkMap,
  GuidedWizard,
  mount: {
    voiceControls: (containerId, props = {}) => {
      const container = document.getElementById(containerId);
      if (container) {
        const root = createRoot(container);
        root.render(<VoiceControls {...props} />);
        return root;
      }
    },
    networkMap: (containerId, props = {}) => {
      const container = document.getElementById(containerId);
      if (container) {
        const root = createRoot(container);
        root.render(<NetworkMap {...props} />);
        return root;
      }
    },
    guidedWizard: (containerId, props = {}) => {
      const container = document.getElementById(containerId);
      if (container) {
        const root = createRoot(container);
        root.render(<GuidedWizard {...props} />);
        return root;
      }
    },
  },
};

export { VoiceControls, NetworkMap, GuidedWizard };
