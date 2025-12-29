import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';

const NetworkMap = ({ hosts = [], onHostSelect = () => {} }) => {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || hosts.length === 0) return;

    // Build Cytoscape elements from hosts
    const elements = [];

    hosts.forEach((host) => {
      elements.push({
        data: {
          id: host.ip,
          label: host.hostname || host.ip,
          type: host.device_type || 'unknown',
          os: host.os || 'unknown',
          ports: host.ports || [],
        },
        classes: host.device_type || 'unknown',
      });

      // Add edges for network relationships (simple example: connect all to a central gateway)
      if (host.ip !== '192.168.1.1') {
        elements.push({
          data: {
            id: `edge-${host.ip}`,
            source: '192.168.1.1',
            target: host.ip,
          },
        });
      }
    });

    // Initialize Cytoscape
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#dc2626',
            label: 'data(label)',
            color: '#e5e5e5',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '10px',
            width: 40,
            height: 40,
          },
        },
        {
          selector: 'node.router',
          style: {
            'background-color': '#3b82f6',
            shape: 'diamond',
          },
        },
        {
          selector: 'node.server',
          style: {
            'background-color': '#22c55e',
            shape: 'rectangle',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#3a3a3a',
            'target-arrow-color': '#3a3a3a',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        nodeDimensionsIncludeLabels: true,
      },
    });

    // Handle node clicks
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      onHostSelect(node.data());
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [hosts, onHostSelect]);

  return (
    <div
      ref={containerRef}
      className="network-map-container w-full h-full min-h-[500px] rounded border border-sp-grey-mid"
    />
  );
};

export default NetworkMap;
