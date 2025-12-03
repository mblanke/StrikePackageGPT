"""
Nmap Parser Module
Parses Nmap XML or JSON output to extract host information including:
- IP addresses, hostnames
- Operating system detection
- Device type classification (workstation/server/appliance)
- MAC vendor information
- Open ports and services
"""

import xml.etree.ElementTree as ET
import json
from typing import Dict, List, Any, Optional
import re


def parse_nmap_xml(xml_content: str) -> List[Dict[str, Any]]:
    """
    Parse Nmap XML output and extract host information.
    
    Args:
        xml_content: Raw XML string from nmap -oX output
        
    Returns:
        List of host dictionaries with parsed information
    """
    hosts = []
    
    try:
        # Clean up XML content - remove any non-XML content before the declaration
        xml_start = xml_content.find('<?xml')
        if xml_start == -1:
            xml_start = xml_content.find('<nmaprun')
        if xml_start > 0:
            xml_content = xml_content[xml_start:]
        
        root = ET.fromstring(xml_content)
        
        for host_elem in root.findall('.//host'):
            # Check if host is up
            status = host_elem.find('status')
            if status is None or status.get('state') != 'up':
                continue
            
            host = _parse_host_element(host_elem)
            if host.get('ip'):
                hosts.append(host)
                
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        # Return empty list on parse error
        return []
    
    return hosts


def parse_nmap_json(json_content: str) -> List[Dict[str, Any]]:
    """
    Parse Nmap JSON output and extract host information.
    
    Args:
        json_content: JSON string from nmap with JSON output
        
    Returns:
        List of host dictionaries with parsed information
    """
    hosts = []
    
    try:
        data = json.loads(json_content)
        
        # Handle different JSON structures
        if isinstance(data, list):
            scan_results = data
        elif isinstance(data, dict):
            # Try common JSON nmap output structures
            scan_results = data.get('hosts', data.get('scan', []))
        else:
            return []
        
        for host_data in scan_results:
            host = _parse_host_json(host_data)
            if host.get('ip'):
                hosts.append(host)
                
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return []
    
    return hosts


def _parse_host_element(host_elem: ET.Element) -> Dict[str, Any]:
    """
    Parse an individual host XML element.
    
    Args:
        host_elem: XML Element representing a single host
        
    Returns:
        Dictionary with host information
    """
    host = {
        'ip': '',
        'hostname': '',
        'mac': '',
        'vendor': '',
        'os_type': '',
        'os_details': '',
        'device_type': '',
        'ports': [],
        'os_accuracy': 0
    }
    
    # Extract IP address
    addr = host_elem.find("address[@addrtype='ipv4']")
    if addr is not None:
        host['ip'] = addr.get('addr', '')
    
    # Extract MAC address and vendor
    mac = host_elem.find("address[@addrtype='mac']")
    if mac is not None:
        host['mac'] = mac.get('addr', '')
        host['vendor'] = mac.get('vendor', '')
    
    # Extract hostname
    hostname_elem = host_elem.find(".//hostname")
    if hostname_elem is not None:
        host['hostname'] = hostname_elem.get('name', '')
    
    # Extract OS information
    osmatch = host_elem.find(".//osmatch")
    if osmatch is not None:
        os_name = osmatch.get('name', '')
        host['os_details'] = os_name
        host['os_type'] = detect_os_type(os_name)
        try:
            host['os_accuracy'] = int(osmatch.get('accuracy', 0))
        except (ValueError, TypeError):
            host['os_accuracy'] = 0
    else:
        # Try osclass as fallback
        osclass = host_elem.find(".//osclass")
        if osclass is not None:
            osfamily = osclass.get('osfamily', '')
            osgen = osclass.get('osgen', '')
            host['os_type'] = detect_os_type(osfamily)
            host['os_details'] = f"{osfamily} {osgen}".strip()
            try:
                host['os_accuracy'] = int(osclass.get('accuracy', 0))
            except (ValueError, TypeError):
                host['os_accuracy'] = 0
    
    # Extract ports
    for port_elem in host_elem.findall(".//port"):
        port_info = {
            'port': int(port_elem.get('portid', 0)),
            'protocol': port_elem.get('protocol', 'tcp'),
            'state': '',
            'service': '',
            'product': '',
            'version': ''
        }
        
        state_elem = port_elem.find('state')
        if state_elem is not None:
            port_info['state'] = state_elem.get('state', '')
        
        service_elem = port_elem.find('service')
        if service_elem is not None:
            port_info['service'] = service_elem.get('name', '')
            port_info['product'] = service_elem.get('product', '')
            port_info['version'] = service_elem.get('version', '')
            
            # Use service info to help detect OS if not already detected
            if not host['os_type']:
                product = service_elem.get('product', '').lower()
                if 'microsoft' in product or 'windows' in product:
                    host['os_type'] = 'Windows'
                elif 'apache' in product or 'nginx' in product or 'linux' in product:
                    host['os_type'] = 'Linux'
        
        if port_info['state'] == 'open':
            host['ports'].append(port_info)
    
    # Infer OS from ports if still unknown
    if not host['os_type'] and host['ports']:
        host['os_type'] = _infer_os_from_ports(host['ports'])
    
    # Classify device type
    host['device_type'] = classify_device_type(host)
    
    return host


def _parse_host_json(host_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse host data from JSON format.
    
    Args:
        host_data: Dictionary containing host information
        
    Returns:
        Standardized host dictionary
    """
    host = {
        'ip': host_data.get('ip', host_data.get('address', '')),
        'hostname': host_data.get('hostname', host_data.get('name', '')),
        'mac': host_data.get('mac', ''),
        'vendor': host_data.get('vendor', ''),
        'os_type': '',
        'os_details': '',
        'device_type': '',
        'ports': [],
        'os_accuracy': 0
    }
    
    # Extract OS information
    os_info = host_data.get('os', host_data.get('osmatch', {}))
    if isinstance(os_info, dict):
        host['os_details'] = os_info.get('name', os_info.get('details', ''))
        host['os_accuracy'] = int(os_info.get('accuracy', 0))
    elif isinstance(os_info, str):
        host['os_details'] = os_info
    
    host['os_type'] = detect_os_type(host['os_details'])
    
    # Extract ports
    ports_data = host_data.get('ports', host_data.get('tcp', {}))
    if isinstance(ports_data, list):
        host['ports'] = ports_data
    elif isinstance(ports_data, dict):
        for port_num, port_info in ports_data.items():
            if isinstance(port_info, dict):
                host['ports'].append({
                    'port': int(port_num),
                    'protocol': 'tcp',
                    'state': port_info.get('state', ''),
                    'service': port_info.get('service', port_info.get('name', '')),
                    'product': port_info.get('product', ''),
                    'version': port_info.get('version', '')
                })
    
    # Infer OS from ports if unknown
    if not host['os_type'] and host['ports']:
        host['os_type'] = _infer_os_from_ports(host['ports'])
    
    # Classify device type
    host['device_type'] = classify_device_type(host)
    
    return host


def detect_os_type(os_string: str) -> str:
    """
    Detect OS type from an OS description string.
    
    Args:
        os_string: OS description from nmap
        
    Returns:
        Standardized OS type string
    """
    if not os_string:
        return 'Unknown'
    
    os_lower = os_string.lower()
    
    # Windows detection
    if any(keyword in os_lower for keyword in ['windows', 'microsoft', 'win7', 'win10', 'win11', 'server 20']):
        return 'Windows'
    
    # Linux detection
    elif any(keyword in os_lower for keyword in ['linux', 'ubuntu', 'debian', 'centos', 'red hat', 'rhel', 'fedora', 'arch', 'gentoo', 'suse']):
        return 'Linux'
    
    # macOS detection
    elif any(keyword in os_lower for keyword in ['mac os', 'darwin', 'apple', 'macos']):
        return 'macOS'
    
    # Unix variants
    elif any(keyword in os_lower for keyword in ['freebsd', 'openbsd', 'netbsd', 'unix', 'solaris', 'aix']):
        return 'Unix'
    
    # Network devices
    elif any(keyword in os_lower for keyword in ['cisco', 'ios']):
        return 'Cisco'
    elif 'juniper' in os_lower or 'junos' in os_lower:
        return 'Juniper'
    elif 'fortinet' in os_lower or 'fortigate' in os_lower:
        return 'Fortinet'
    elif 'palo alto' in os_lower or 'panos' in os_lower:
        return 'Palo Alto'
    elif any(keyword in os_lower for keyword in ['switch', 'router', 'firewall', 'gateway']):
        return 'Network Device'
    
    # Virtualization
    elif 'vmware' in os_lower or 'esxi' in os_lower:
        return 'VMware'
    elif 'hyper-v' in os_lower:
        return 'Hyper-V'
    
    # Mobile
    elif 'android' in os_lower:
        return 'Android'
    elif 'ios' in os_lower and 'apple' in os_lower:
        return 'iOS'
    
    # Printers and IoT
    elif any(keyword in os_lower for keyword in ['printer', 'hp jetdirect', 'canon', 'epson', 'xerox']):
        return 'Printer'
    elif 'iot' in os_lower or 'embedded' in os_lower:
        return 'IoT Device'
    
    return 'Unknown'


def classify_device_type(host: Dict[str, Any]) -> str:
    """
    Classify the device type based on OS, ports, and services.
    
    Args:
        host: Host dictionary with OS and port information
        
    Returns:
        Device type classification (workstation, server, network, appliance, etc.)
    """
    os_type = host.get('os_type', '').lower()
    os_details = host.get('os_details', '').lower()
    ports = host.get('ports', [])
    vendor = host.get('vendor', '').lower()
    
    port_numbers = {p['port'] for p in ports}
    services = {p.get('service', '').lower() for p in ports}
    
    # Network infrastructure
    if os_type in ['cisco', 'juniper', 'fortinet', 'palo alto', 'network device']:
        if 'switch' in os_details or 'catalyst' in os_details:
            return 'Network Switch'
        elif 'router' in os_details or 'ios' in os_details:
            return 'Router'
        elif 'firewall' in os_details or 'fortigate' in os_details:
            return 'Firewall'
        else:
            return 'Network Device'
    
    # Check for SNMP (common on network devices)
    if 161 in port_numbers or 162 in port_numbers:
        return 'Network Device'
    
    # Printers
    if os_type == 'printer' or 9100 in port_numbers or 631 in port_numbers:
        return 'Printer'
    
    # IoT devices
    if os_type == 'iot device':
        return 'IoT Device'
    
    # Servers - check for common server ports and services
    server_indicators = {
        # Web servers
        80, 443, 8080, 8443,
        # Database servers
        3306, 5432, 1433, 27017, 6379,
        # Mail servers
        25, 587, 465, 110, 995, 143, 993,
        # File servers
        21, 22, 139, 445, 2049,
        # Directory services
        389, 636, 88, 464,
        # Application servers
        8000, 8001, 8888, 9000, 3000, 5000,
        # Virtualization
        902, 443
    }
    
    server_services = {
        'http', 'https', 'apache', 'nginx', 'iis',
        'mysql', 'postgresql', 'mssql', 'mongodb', 'redis',
        'smtp', 'pop3', 'imap',
        'ftp', 'ssh', 'smb', 'nfs',
        'ldap', 'ldaps', 'kerberos',
        'vmware'
    }
    
    # Check if it's explicitly a server OS
    if 'server' in os_details:
        return 'Server'
    
    # Check for server ports/services
    if port_numbers & server_indicators or services & server_services:
        # More than 3 server ports suggests a server
        if len(port_numbers & server_indicators) >= 3:
            return 'Server'
        # Specific database or web server services
        if any(svc in services for svc in ['mysql', 'postgresql', 'mongodb', 'apache', 'nginx', 'iis']):
            return 'Server'
    
    # Virtualization hosts
    if os_type in ['vmware', 'hyper-v'] or 'esxi' in os_details:
        return 'Virtualization Host'
    
    # Workstations
    if os_type in ['windows', 'macos', 'linux']:
        # Windows/macOS are typically workstations unless server indicators
        if os_type in ['windows', 'macos']:
            if 3389 in port_numbers:  # RDP
                # Could be either, but default to workstation
                return 'Workstation'
            return 'Workstation'
        # Linux could be either
        elif os_type == 'linux':
            # Desktop Linux if few ports open
            if len(port_numbers) <= 3:
                return 'Workstation'
            else:
                return 'Server'
    
    # Mobile devices
    if os_type in ['android', 'ios']:
        return 'Mobile Device'
    
    # Default classification
    if len(port_numbers) >= 5:
        return 'Server'
    elif len(port_numbers) >= 1:
        return 'Workstation'
    
    return 'Unknown'


def _infer_os_from_ports(ports: List[Dict[str, Any]]) -> str:
    """
    Infer OS type from open ports and services.
    
    Args:
        ports: List of port dictionaries
        
    Returns:
        Inferred OS type
    """
    port_numbers = {p['port'] for p in ports}
    services = [p.get('service', '').lower() for p in ports]
    products = [p.get('product', '').lower() for p in ports]
    
    # Windows indicators
    windows_ports = {135, 139, 445, 3389, 5985, 5986}
    if windows_ports & port_numbers:
        return 'Windows'
    
    if any('microsoft' in p or 'windows' in p for p in products):
        return 'Windows'
    
    # Linux indicators (SSH is common)
    if 22 in port_numbers and 'ssh' in services:
        # Could be Linux or Unix
        return 'Linux'
    
    # Network device indicators
    if 161 in port_numbers or 162 in port_numbers:  # SNMP
        return 'Network Device'
    if 23 in port_numbers:  # Telnet (often network devices)
        return 'Network Device'
    
    # Printer indicators
    if 9100 in port_numbers or 631 in port_numbers:
        return 'Printer'
    
    return 'Unknown'


def get_os_icon_name(host: Dict[str, Any]) -> str:
    """
    Get the appropriate icon name for a host based on OS and device type.
    
    Args:
        host: Host dictionary
        
    Returns:
        Icon filename (without extension)
    """
    os_type = host.get('os_type', '').lower()
    device_type = host.get('device_type', '').lower()
    
    # Device type takes precedence for specialized devices
    if 'server' in device_type:
        return 'server'
    elif 'network' in device_type or 'router' in device_type or 'switch' in device_type or 'firewall' in device_type:
        return 'network'
    elif 'printer' in device_type:
        return 'printer'
    elif 'workstation' in device_type:
        return 'workstation'
    
    # Fall back to OS type
    if 'windows' in os_type:
        return 'windows'
    elif 'linux' in os_type or 'unix' in os_type:
        return 'linux'
    elif 'mac' in os_type:
        return 'mac'
    elif any(net in os_type for net in ['cisco', 'juniper', 'fortinet', 'network']):
        return 'network'
    
    return 'unknown'
