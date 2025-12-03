/**
 * NetworkMap Component
 * Interactive network graph visualization using Cytoscape.js
 * Displays discovered hosts from nmap scans with OS/device icons
 */

import React, { useState, useEffect, useRef } from 'react';

const NetworkMap = ({ scanId, onNodeClick }) => {
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterText, setFilterText] = useState('');
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (scanId) {
      fetchHostData(scanId);
    }
  }, [scanId]);

  useEffect(() => {
    if (hosts.length > 0 && containerRef.current) {
      initializeNetwork();
    }
  }, [hosts]);

  const fetchHostData = async (scanId) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/nmap/hosts?scan_id=${scanId}`);
      const data = await response.json();
      setHosts(data.hosts || []);
    } catch (error) {
      console.error('Error fetching host data:', error);
    } finally {
      setLoading(false);
    }
  };

  const initializeNetwork = () => {
    // NOTE: This component is a template for network visualization.
    // To use it, you must:
    // 1. Install cytoscape: npm install cytoscape
    // 2. Uncomment the code below and add the import at the top
    // 3. Build your React application with a bundler (webpack, vite, etc.)
    //
    // For a simpler integration without React build system, see INTEGRATION_EXAMPLE.md
    
    // Example initialization (requires actual cytoscape import)
    /*
    import cytoscape from 'cytoscape';
    
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildGraphElements(hosts),
      style: getNetworkStyle(),
      layout: {
        name: 'cose',
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0
      }
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const hostData = node.data();
      if (onNodeClick) {
        onNodeClick(hostData);
      }
    });

    cyRef.current = cy;
    */
  };

  const buildGraphElements = (hosts) => {
    const elements = [];
    
    // Add nodes for each host
    hosts.forEach((host, index) => {
      elements.push({
        group: 'nodes',
        data: {
          id: `host-${index}`,
          label: host.hostname || host.ip,
          ...host,
          icon: getIconForHost(host)
        },
        classes: getNodeClass(host)
      });
    });

    // Add edges (connections) - could be inferred from network topology
    // For now, connect hosts in same subnet
    const subnets = groupBySubnet(hosts);
    Object.values(subnets).forEach(subnetHosts => {
      if (subnetHosts.length > 1) {
        for (let i = 0; i < subnetHosts.length - 1; i++) {
          elements.push({
            group: 'edges',
            data: {
              id: `edge-${subnetHosts[i].ip}-${subnetHosts[i + 1].ip}`,
              source: `host-${hosts.indexOf(subnetHosts[i])}`,
              target: `host-${hosts.indexOf(subnetHosts[i + 1])}`
            }
          });
        }
      }
    });

    return elements;
  };

  const getIconForHost = (host) => {
    const osType = (host.os_type || '').toLowerCase();
    const deviceType = (host.device_type || '').toLowerCase();

    if (deviceType.includes('server')) return '/static/server.svg';
    if (deviceType.includes('network') || deviceType.includes('router') || deviceType.includes('switch')) {
      return '/static/network.svg';
    }
    if (deviceType.includes('workstation')) return '/static/workstation.svg';
    
    if (osType.includes('windows')) return '/static/windows.svg';
    if (osType.includes('linux') || osType.includes('unix')) return '/static/linux.svg';
    if (osType.includes('mac') || osType.includes('darwin')) return '/static/mac.svg';
    
    return '/static/unknown.svg';
  };

  const getNodeClass = (host) => {
    const deviceType = (host.device_type || '').toLowerCase();
    if (deviceType.includes('server')) return 'node-server';
    if (deviceType.includes('network')) return 'node-network';
    if (deviceType.includes('workstation')) return 'node-workstation';
    return 'node-unknown';
  };

  const groupBySubnet = (hosts) => {
    const subnets = {};
    hosts.forEach(host => {
      const subnet = host.ip.split('.').slice(0, 3).join('.');
      if (!subnets[subnet]) {
        subnets[subnet] = [];
      }
      subnets[subnet].push(host);
    });
    return subnets;
  };

  const getNetworkStyle = () => {
    return [
      {
        selector: 'node',
        style: {
          'background-color': '#4A90E2',
          'label': 'data(label)',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'font-size': '12px',
          'color': '#333',
          'text-margin-y': 5,
          'width': 50,
          'height': 50,
          'background-image': 'data(icon)',
          'background-fit': 'contain'
        }
      },
      {
        selector: '.node-server',
        style: {
          'background-color': '#4A90E2'
        }
      },
      {
        selector: '.node-network',
        style: {
          'background-color': '#16A085'
        }
      },
      {
        selector: '.node-workstation',
        style: {
          'background-color': '#5DADE2'
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#95A5A6',
          'curve-style': 'bezier'
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 3,
          'border-color': '#E74C3C'
        }
      }
    ];
  };

  const exportToPNG = () => {
    if (cyRef.current) {
      const png = cyRef.current.png({ scale: 2, full: true });
      const link = document.createElement('a');
      link.href = png;
      link.download = `network-map-${Date.now()}.png`;
      link.click();
    }
  };

  const exportToCSV = () => {
    const csvContent = [
      ['IP', 'Hostname', 'OS Type', 'Device Type', 'MAC', 'Vendor', 'Open Ports'].join(','),
      ...hosts.map(host => [
        host.ip,
        host.hostname || '',
        host.os_type || '',
        host.device_type || '',
        host.mac || '',
        host.vendor || '',
        (host.ports || []).map(p => p.port).join(';')
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `network-hosts-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const filteredHosts = hosts.filter(host => {
    if (!filterText) return true;
    const searchLower = filterText.toLowerCase();
    return (
      host.ip.includes(searchLower) ||
      (host.hostname || '').toLowerCase().includes(searchLower) ||
      (host.os_type || '').toLowerCase().includes(searchLower) ||
      (host.device_type || '').toLowerCase().includes(searchLower)
    );
  });

  return (
    <div className="network-map-container" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="network-map-toolbar" style={{ padding: '10px', borderBottom: '1px solid #ddd', display: 'flex', gap: '10px', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Filter hosts (IP, hostname, OS, device type)..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
        />
        <button onClick={exportToPNG} style={{ padding: '8px 16px', cursor: 'pointer', borderRadius: '4px' }}>
          Export PNG
        </button>
        <button onClick={exportToCSV} style={{ padding: '8px 16px', cursor: 'pointer', borderRadius: '4px' }}>
          Export CSV
        </button>
        <span style={{ color: '#666' }}>
          {filteredHosts.length} host{filteredHosts.length !== 1 ? 's' : ''}
        </span>
      </div>
      
      <div 
        ref={containerRef}
        className="network-map-canvas"
        style={{ 
          flex: 1, 
          backgroundColor: '#f5f5f5',
          position: 'relative'
        }}
      >
        {loading && (
          <div style={{ 
            position: 'absolute', 
            top: '50%', 
            left: '50%', 
            transform: 'translate(-50%, -50%)',
            textAlign: 'center'
          }}>
            <div>Loading network map...</div>
          </div>
        )}
        {!loading && hosts.length === 0 && (
          <div style={{ 
            position: 'absolute', 
            top: '50%', 
            left: '50%', 
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            color: '#666'
          }}>
            <div>No hosts discovered yet</div>
            <div style={{ fontSize: '14px', marginTop: '10px' }}>Run a network scan to populate the map</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NetworkMap;
