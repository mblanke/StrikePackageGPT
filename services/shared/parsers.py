"""
Output parsers for security tool results.
Converts raw tool output into structured data.
"""
import re
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from datetime import datetime


class BaseParser:
    """Base class for tool output parsers."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        raise NotImplementedError


class NmapParser(BaseParser):
    """Parser for nmap output."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        """Parse nmap text output."""
        results = {
            "hosts": [],
            "scan_info": {},
            "raw": output
        }
        
        current_host = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Parse scan info
            if line.startswith('Nmap scan report for'):
                if current_host:
                    results["hosts"].append(current_host)
                
                # Extract hostname and IP
                match = re.search(r'for (\S+)(?: \((\d+\.\d+\.\d+\.\d+)\))?', line)
                if match:
                    current_host = {
                        "hostname": match.group(1),
                        "ip": match.group(2) or match.group(1),
                        "ports": [],
                        "os": None,
                        "status": "up"
                    }
            
            # Parse port info
            elif current_host and re.match(r'^\d+/(tcp|udp)', line):
                parts = line.split()
                if len(parts) >= 3:
                    port_proto = parts[0].split('/')
                    current_host["ports"].append({
                        "port": int(port_proto[0]),
                        "protocol": port_proto[1],
                        "state": parts[1],
                        "service": parts[2] if len(parts) > 2 else "unknown",
                        "version": ' '.join(parts[3:]) if len(parts) > 3 else None
                    })
            
            # Parse OS detection
            elif current_host and 'OS details:' in line:
                current_host["os"] = line.replace('OS details:', '').strip()
            
            # Parse timing info
            elif 'scanned in' in line.lower():
                match = re.search(r'scanned in ([\d.]+) seconds', line)
                if match:
                    results["scan_info"]["duration_seconds"] = float(match.group(1))
        
        if current_host:
            results["hosts"].append(current_host)
        
        return results
    
    def parse_xml(self, xml_output: str) -> Dict[str, Any]:
        """Parse nmap XML output for more detailed results."""
        try:
            root = ET.fromstring(xml_output)
            results = {
                "hosts": [],
                "scan_info": {
                    "scanner": root.get("scanner"),
                    "args": root.get("args"),
                    "start_time": root.get("start"),
                }
            }
            
            for host in root.findall('.//host'):
                host_info = {
                    "ip": None,
                    "hostname": None,
                    "status": host.find('status').get('state') if host.find('status') is not None else "unknown",
                    "ports": [],
                    "os": []
                }
                
                # Get addresses
                for addr in host.findall('.//address'):
                    if addr.get('addrtype') == 'ipv4':
                        host_info["ip"] = addr.get('addr')
                
                # Get hostnames
                hostname_elem = host.find('.//hostname')
                if hostname_elem is not None:
                    host_info["hostname"] = hostname_elem.get('name')
                
                # Get ports
                for port in host.findall('.//port'):
                    port_info = {
                        "port": int(port.get('portid')),
                        "protocol": port.get('protocol'),
                        "state": port.find('state').get('state') if port.find('state') is not None else "unknown",
                    }
                    
                    service = port.find('service')
                    if service is not None:
                        port_info["service"] = service.get('name')
                        port_info["product"] = service.get('product')
                        port_info["version"] = service.get('version')
                    
                    host_info["ports"].append(port_info)
                
                results["hosts"].append(host_info)
            
            return results
        except ET.ParseError:
            return {"error": "Failed to parse XML", "raw": xml_output}


class NiktoParser(BaseParser):
    """Parser for nikto output."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        results = {
            "target": None,
            "findings": [],
            "server_info": {},
            "raw": output
        }
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Target info
            if '+ Target IP:' in line:
                results["target"] = line.split(':')[-1].strip()
            elif '+ Target Hostname:' in line:
                results["server_info"]["hostname"] = line.split(':')[-1].strip()
            elif '+ Target Port:' in line:
                results["server_info"]["port"] = line.split(':')[-1].strip()
            elif '+ Server:' in line:
                results["server_info"]["server"] = line.split(':', 1)[-1].strip()
            
            # Findings (lines starting with +)
            elif line.startswith('+') and ':' in line:
                # Skip info lines
                if any(skip in line for skip in ['Target IP', 'Target Hostname', 'Target Port', 'Server:', 'Start Time', 'End Time']):
                    continue
                
                finding = {
                    "raw": line[1:].strip(),
                    "severity": "info"
                }
                
                # Determine severity based on content
                if any(word in line.lower() for word in ['vulnerable', 'vulnerability', 'exploit']):
                    finding["severity"] = "high"
                elif any(word in line.lower() for word in ['outdated', 'deprecated', 'insecure']):
                    finding["severity"] = "medium"
                elif any(word in line.lower() for word in ['disclosed', 'information', 'header']):
                    finding["severity"] = "low"
                
                # Extract OSVDB if present
                osvdb_match = re.search(r'OSVDB-(\d+)', line)
                if osvdb_match:
                    finding["osvdb"] = osvdb_match.group(1)
                
                results["findings"].append(finding)
        
        return results


class SQLMapParser(BaseParser):
    """Parser for sqlmap output."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        results = {
            "target": None,
            "parameters": [],
            "injections": [],
            "databases": [],
            "raw": output
        }
        
        in_parameter_section = False
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Target URL
            if 'target URL' in line.lower():
                match = re.search(r"'([^']+)'", line)
                if match:
                    results["target"] = match.group(1)
            
            # Injectable parameters
            if 'Parameter:' in line:
                param_match = re.search(r"Parameter: (\S+)", line)
                if param_match:
                    results["parameters"].append({
                        "name": param_match.group(1),
                        "injectable": True
                    })
            
            # Injection type
            if 'Type:' in line and 'injection' in line.lower():
                results["injections"].append(line.replace('Type:', '').strip())
            
            # Databases found
            if line.startswith('[*]') and 'available databases' not in line.lower():
                db_name = line[3:].strip()
                if db_name:
                    results["databases"].append(db_name)
        
        return results


class GobusterParser(BaseParser):
    """Parser for gobuster output."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        results = {
            "findings": [],
            "directories": [],
            "files": [],
            "raw": output
        }
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Parse found paths
            # Format: /path (Status: 200) [Size: 1234]
            match = re.search(r'^(/\S*)\s+\(Status:\s*(\d+)\)(?:\s+\[Size:\s*(\d+)\])?', line)
            if match:
                finding = {
                    "path": match.group(1),
                    "status": int(match.group(2)),
                    "size": int(match.group(3)) if match.group(3) else None
                }
                
                results["findings"].append(finding)
                
                if finding["path"].endswith('/'):
                    results["directories"].append(finding["path"])
                else:
                    results["files"].append(finding["path"])
        
        return results


class HydraParser(BaseParser):
    """Parser for hydra output."""
    
    def parse(self, output: str) -> Dict[str, Any]:
        results = {
            "credentials": [],
            "target": None,
            "service": None,
            "raw": output
        }
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Parse found credentials
            # Format: [port][service] host: x   login: y   password: z
            cred_match = re.search(r'\[(\d+)\]\[(\w+)\]\s+host:\s+(\S+)\s+login:\s+(\S+)\s+password:\s+(\S+)', line)
            if cred_match:
                results["credentials"].append({
                    "port": int(cred_match.group(1)),
                    "service": cred_match.group(2),
                    "host": cred_match.group(3),
                    "username": cred_match.group(4),
                    "password": cred_match.group(5)
                })
                results["target"] = cred_match.group(3)
                results["service"] = cred_match.group(2)
        
        return results


# Registry of parsers
PARSERS = {
    "nmap": NmapParser(),
    "nikto": NiktoParser(),
    "sqlmap": SQLMapParser(),
    "gobuster": GobusterParser(),
    "hydra": HydraParser(),
}


def parse_tool_output(tool: str, output: str) -> Dict[str, Any]:
    """Parse output from a security tool."""
    parser = PARSERS.get(tool.lower())
    if parser:
        try:
            return parser.parse(output)
        except Exception as e:
            return {"error": str(e), "raw": output}
    return {"raw": output}
