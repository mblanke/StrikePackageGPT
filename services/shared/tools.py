"""
Security tool definitions and command builders.
"""
from typing import Dict, List, Optional, Any


SECURITY_TOOLS = {
    # ============== Reconnaissance ==============
    "nmap": {
        "name": "nmap",
        "description": "Network scanner and security auditing tool",
        "category": "reconnaissance",
        "templates": {
            "quick": "nmap -T4 -F {target}",
            "full": "nmap -sV -sC -O -p- {target}",
            "stealth": "nmap -sS -T2 -f {target}",
            "udp": "nmap -sU --top-ports 100 {target}",
            "vuln": "nmap --script vuln {target}",
            "version": "nmap -sV -p {ports} {target}",
            "os": "nmap -O --osscan-guess {target}",
        },
        "default_template": "quick",
        "output_parser": "nmap"
    },
    
    "masscan": {
        "name": "masscan",
        "description": "Fast TCP port scanner",
        "category": "reconnaissance",
        "templates": {
            "quick": "masscan {target} --ports 0-1000 --rate 1000",
            "full": "masscan {target} --ports 0-65535 --rate 10000",
            "top100": "masscan {target} --top-ports 100 --rate 1000",
        },
        "default_template": "quick",
    },
    
    "amass": {
        "name": "amass",
        "description": "Subdomain enumeration tool",
        "category": "reconnaissance",
        "templates": {
            "passive": "amass enum -passive -d {target}",
            "active": "amass enum -active -d {target}",
            "intel": "amass intel -d {target}",
        },
        "default_template": "passive",
    },
    
    "theharvester": {
        "name": "theHarvester",
        "description": "OSINT tool for gathering emails, names, subdomains",
        "category": "reconnaissance",
        "templates": {
            "all": "theHarvester -d {target} -b all",
            "google": "theHarvester -d {target} -b google",
            "linkedin": "theHarvester -d {target} -b linkedin",
        },
        "default_template": "all",
    },
    
    "whatweb": {
        "name": "whatweb",
        "description": "Web technology fingerprinting",
        "category": "reconnaissance",
        "templates": {
            "default": "whatweb {target}",
            "aggressive": "whatweb -a 3 {target}",
            "verbose": "whatweb -v {target}",
        },
        "default_template": "default",
    },
    
    "dnsrecon": {
        "name": "dnsrecon",
        "description": "DNS enumeration tool",
        "category": "reconnaissance",
        "templates": {
            "standard": "dnsrecon -d {target}",
            "zone": "dnsrecon -d {target} -t axfr",
            "brute": "dnsrecon -d {target} -t brt",
        },
        "default_template": "standard",
    },
    
    # ============== Vulnerability Scanning ==============
    "nikto": {
        "name": "nikto",
        "description": "Web server vulnerability scanner",
        "category": "vulnerability_scanning",
        "templates": {
            "default": "nikto -h {target}",
            "ssl": "nikto -h {target} -ssl",
            "tuning": "nikto -h {target} -Tuning x",
            "full": "nikto -h {target} -C all",
        },
        "default_template": "default",
        "output_parser": "nikto"
    },
    
    "sqlmap": {
        "name": "sqlmap",
        "description": "SQL injection detection and exploitation",
        "category": "vulnerability_scanning",
        "templates": {
            "test": "sqlmap -u '{target}' --batch",
            "dbs": "sqlmap -u '{target}' --batch --dbs",
            "tables": "sqlmap -u '{target}' --batch -D {database} --tables",
            "dump": "sqlmap -u '{target}' --batch -D {database} -T {table} --dump",
            "forms": "sqlmap -u '{target}' --batch --forms",
        },
        "default_template": "test",
        "output_parser": "sqlmap"
    },
    
    "wpscan": {
        "name": "wpscan",
        "description": "WordPress vulnerability scanner",
        "category": "vulnerability_scanning",
        "templates": {
            "default": "wpscan --url {target}",
            "enumerate": "wpscan --url {target} -e vp,vt,u",
            "aggressive": "wpscan --url {target} -e ap,at,u --plugins-detection aggressive",
        },
        "default_template": "default",
    },
    
    # ============== Web Testing ==============
    "gobuster": {
        "name": "gobuster",
        "description": "Directory/file brute-forcing",
        "category": "web_testing",
        "templates": {
            "dir": "gobuster dir -u {target} -w /usr/share/wordlists/dirb/common.txt",
            "big": "gobuster dir -u {target} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
            "dns": "gobuster dns -d {target} -w /usr/share/wordlists/dns/subdomains-top1million-5000.txt",
            "vhost": "gobuster vhost -u {target} -w /usr/share/wordlists/dns/subdomains-top1million-5000.txt",
        },
        "default_template": "dir",
        "output_parser": "gobuster"
    },
    
    "ffuf": {
        "name": "ffuf",
        "description": "Fast web fuzzer",
        "category": "web_testing",
        "templates": {
            "dir": "ffuf -u {target}/FUZZ -w /usr/share/wordlists/dirb/common.txt",
            "vhost": "ffuf -u {target} -H 'Host: FUZZ.{domain}' -w /usr/share/wordlists/dns/subdomains-top1million-5000.txt",
            "param": "ffuf -u '{target}?FUZZ=test' -w /usr/share/wordlists/dirb/common.txt",
        },
        "default_template": "dir",
    },
    
    "dirb": {
        "name": "dirb",
        "description": "Web content scanner",
        "category": "web_testing",
        "templates": {
            "default": "dirb {target}",
            "small": "dirb {target} /usr/share/wordlists/dirb/small.txt",
            "big": "dirb {target} /usr/share/wordlists/dirb/big.txt",
        },
        "default_template": "default",
    },
    
    # ============== Exploitation ==============
    "searchsploit": {
        "name": "searchsploit",
        "description": "Exploit database search tool",
        "category": "exploitation",
        "templates": {
            "search": "searchsploit {query}",
            "exact": "searchsploit -e {query}",
            "json": "searchsploit -j {query}",
            "path": "searchsploit -p {exploit_id}",
        },
        "default_template": "search",
    },
    
    "hydra": {
        "name": "hydra",
        "description": "Network login cracker",
        "category": "password_attacks",
        "templates": {
            "ssh": "hydra -l {user} -P /usr/share/wordlists/rockyou.txt {target} ssh",
            "ftp": "hydra -l {user} -P /usr/share/wordlists/rockyou.txt {target} ftp",
            "http_post": "hydra -l {user} -P /usr/share/wordlists/rockyou.txt {target} http-post-form '{form}'",
            "smb": "hydra -l {user} -P /usr/share/wordlists/rockyou.txt {target} smb",
        },
        "default_template": "ssh",
        "output_parser": "hydra"
    },
    
    # ============== Network Tools ==============
    "netcat": {
        "name": "nc",
        "description": "Network utility for TCP/UDP connections",
        "category": "network",
        "templates": {
            "listen": "nc -lvnp {port}",
            "connect": "nc -v {target} {port}",
            "scan": "nc -zv {target} {port_range}",
        },
        "default_template": "scan",
    },
    
    "curl": {
        "name": "curl",
        "description": "HTTP client",
        "category": "web_testing",
        "templates": {
            "get": "curl -v {target}",
            "headers": "curl -I {target}",
            "post": "curl -X POST -d '{data}' {target}",
            "follow": "curl -L -v {target}",
        },
        "default_template": "get",
    },
}


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Get tool definition by name."""
    return SECURITY_TOOLS.get(name.lower())


def get_tools_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all tools in a category."""
    return [tool for tool in SECURITY_TOOLS.values() if tool.get("category") == category]


def build_command(tool_name: str, template_name: str = None, **kwargs) -> Optional[str]:
    """Build a command from a tool template."""
    tool = get_tool(tool_name)
    if not tool:
        return None
    
    template_name = template_name or tool.get("default_template")
    template = tool.get("templates", {}).get(template_name)
    
    if not template:
        return None
    
    try:
        return template.format(**kwargs)
    except KeyError as e:
        return None


def list_all_tools() -> Dict[str, List[Dict[str, str]]]:
    """List all available tools grouped by category."""
    result = {}
    for tool in SECURITY_TOOLS.values():
        category = tool.get("category", "other")
        if category not in result:
            result[category] = []
        result[category].append({
            "name": tool["name"],
            "description": tool["description"],
            "templates": list(tool.get("templates", {}).keys())
        })
    return result
