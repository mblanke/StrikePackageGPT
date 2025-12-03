"""
Configuration Validator Module
Validates configurations before save/change with plain-English warnings.
Provides backup/restore functionality and auto-fix suggestions.
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import copy


# Configuration storage (in production, use persistent storage)
config_backups: Dict[str, List[Dict[str, Any]]] = {}
BACKUP_DIR = os.getenv("CONFIG_BACKUP_DIR", "/workspace/config_backups")


def validate_config(
    config_data: Dict[str, Any],
    config_type: str = "general"
) -> Dict[str, Any]:
    """
    Validate configuration data before applying changes.
    
    Args:
        config_data: Configuration dictionary to validate
        config_type: Type of configuration (scan, system, security, network)
        
    Returns:
        Dictionary with validation results
        {
            "valid": bool,
            "warnings": List[str],
            "errors": List[str],
            "suggestions": List[Dict],
            "safe_to_apply": bool
        }
    """
    errors = []
    warnings = []
    suggestions = []
    
    # Type-specific validation
    if config_type == "scan":
        errors, warnings, suggestions = _validate_scan_config(config_data)
    elif config_type == "network":
        errors, warnings, suggestions = _validate_network_config(config_data)
    elif config_type == "security":
        errors, warnings, suggestions = _validate_security_config(config_data)
    else:
        errors, warnings, suggestions = _validate_general_config(config_data)
    
    # Check for common issues across all config types
    common_errors, common_warnings = _check_common_issues(config_data)
    errors.extend(common_errors)
    warnings.extend(common_warnings)
    
    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "suggestions": suggestions,
        "safe_to_apply": len(errors) == 0 and len([w for w in warnings if "critical" in w.lower()]) == 0,
        "config_type": config_type
    }


def _validate_scan_config(config_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[Dict]]:
    """Validate scan configuration."""
    errors = []
    warnings = []
    suggestions = []
    
    # Check timeout
    timeout = config_data.get("timeout", 300)
    if not isinstance(timeout, (int, float)):
        errors.append("Timeout must be a number (seconds)")
    elif timeout < 1:
        errors.append("Timeout must be at least 1 second")
    elif timeout < 10:
        warnings.append("Very short timeout (< 10s) may cause scans to fail prematurely")
    elif timeout > 3600:
        warnings.append("Very long timeout (> 1 hour) may cause scans to hang indefinitely")
    
    # Check target
    target = config_data.get("target", "")
    if not target or not isinstance(target, str):
        errors.append("Target must be specified (IP address, hostname, or network range)")
    elif not _is_valid_target(target):
        warnings.append(f"Target '{target}' may not be valid - ensure it's a valid IP, hostname, or CIDR")
    
    # Check scan intensity
    intensity = config_data.get("intensity", 3)
    if isinstance(intensity, (int, float)):
        if intensity < 1 or intensity > 5:
            warnings.append("Scan intensity should be between 1 (stealth) and 5 (aggressive)")
        if intensity >= 4:
            warnings.append("High intensity scans may trigger IDS/IPS systems")
            suggestions.append({
                "field": "intensity",
                "suggestion": 3,
                "reason": "Balanced intensity for stealth and speed"
            })
    
    # Check port range
    ports = config_data.get("ports", "")
    if ports:
        if not _is_valid_port_spec(str(ports)):
            errors.append(f"Invalid port specification: {ports}")
    
    return errors, warnings, suggestions


def _validate_network_config(config_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[Dict]]:
    """Validate network configuration."""
    errors = []
    warnings = []
    suggestions = []
    
    # Check port
    port = config_data.get("port")
    if port is not None:
        if not isinstance(port, int):
            errors.append("Port must be an integer")
        elif port < 1 or port > 65535:
            errors.append("Port must be between 1 and 65535")
        elif port < 1024:
            warnings.append("Ports below 1024 require elevated privileges")
    
    # Check host/bind address
    host = config_data.get("host", "")
    if host and not _is_valid_ip_or_hostname(host):
        warnings.append(f"Host '{host}' may not be a valid IP address or hostname")
    
    # Check max connections
    max_conn = config_data.get("max_connections")
    if max_conn is not None:
        if not isinstance(max_conn, int) or max_conn < 1:
            errors.append("max_connections must be a positive integer")
        elif max_conn > 1000:
            warnings.append("Very high max_connections (> 1000) may exhaust system resources")
    
    return errors, warnings, suggestions


def _validate_security_config(config_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[Dict]]:
    """Validate security configuration."""
    errors = []
    warnings = []
    suggestions = []
    
    # Check for exposed secrets
    for key, value in config_data.items():
        if any(secret_word in key.lower() for secret_word in ['password', 'secret', 'token', 'key', 'credential']):
            if isinstance(value, str):
                if len(value) < 8:
                    warnings.append(f"SECURITY: {key} appears weak (< 8 characters)")
                if value in ['password', '123456', 'admin', 'default']:
                    errors.append(f"SECURITY: {key} is using a default/weak value")
    
    # Check SSL/TLS settings
    ssl_enabled = config_data.get("ssl_enabled", False)
    if not ssl_enabled:
        warnings.append("SECURITY: SSL/TLS is disabled - data will be transmitted unencrypted")
    
    # Check authentication
    auth_enabled = config_data.get("authentication_enabled", True)
    if not auth_enabled:
        warnings.append("SECURITY: Authentication is disabled - system will be exposed")
    
    return errors, warnings, suggestions


def _validate_general_config(config_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[Dict]]:
    """Validate general configuration."""
    errors = []
    warnings = []
    suggestions = []
    
    # Check for valid JSON structure
    if not isinstance(config_data, dict):
        errors.append("Configuration must be a JSON object")
        return errors, warnings, suggestions
    
    # Check for empty config
    if not config_data:
        warnings.append("Configuration is empty")
    
    return errors, warnings, suggestions


def _check_common_issues(config_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Check for common configuration issues."""
    errors = []
    warnings = []
    
    # Validate that config_data is a dict and not too large
    if not isinstance(config_data, dict):
        errors.append("Configuration must be a dictionary")
        return errors, warnings
    
    if len(config_data) > 1000:
        warnings.append("Configuration has unusually large number of keys (>1000)")
    
    # Check for null/undefined values
    for key, value in config_data.items():
        # Validate key is a string
        if not isinstance(key, str):
            warnings.append(f"Configuration key {key} is not a string")
            continue
        
        if value is None:
            warnings.append(f"Value for '{key}' is null - will use default")
    
    # Check for suspicious paths
    for key, value in config_data.items():
        if isinstance(value, str):
            if value.startswith('/root/') or value.startswith('C:\\Windows\\'):
                warnings.append(f"SECURITY: '{key}' points to a sensitive system path")
    
    return errors, warnings


def backup_config(config_name: str, config_data: Dict[str, Any], description: str = "") -> Dict[str, Any]:
    """
    Create a backup of current configuration.
    
    Args:
        config_name: Name/ID of the configuration
        config_data: Configuration data to backup
        description: Optional description of the backup
        
    Returns:
        Dictionary with backup information
    """
    timestamp = datetime.utcnow().isoformat()
    backup_id = f"{config_name}_{timestamp}"
    
    backup = {
        "backup_id": backup_id,
        "config_name": config_name,
        "timestamp": timestamp,
        "description": description or "Automatic backup",
        "config_data": copy.deepcopy(config_data),
        "size_bytes": len(json.dumps(config_data))
    }
    
    # Store in memory
    if config_name not in config_backups:
        config_backups[config_name] = []
    config_backups[config_name].append(backup)
    
    # Keep only last 10 backups per config
    if len(config_backups[config_name]) > 10:
        config_backups[config_name] = config_backups[config_name][-10:]
    
    # Also save to disk if backup directory exists
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_file = os.path.join(BACKUP_DIR, f"{backup_id}.json")
        with open(backup_file, 'w') as f:
            json.dump(backup, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save backup to disk: {e}")
    
    return {
        "success": True,
        "backup_id": backup_id,
        "timestamp": timestamp,
        "message": f"Configuration backed up successfully"
    }


def restore_config(backup_id: str) -> Dict[str, Any]:
    """
    Restore configuration from a backup.
    
    Args:
        backup_id: ID of the backup to restore
        
    Returns:
        Dictionary with restored configuration and metadata
    """
    # Search in memory backups
    for config_name, backups in config_backups.items():
        for backup in backups:
            if backup["backup_id"] == backup_id:
                return {
                    "success": True,
                    "backup_id": backup_id,
                    "config_name": config_name,
                    "config_data": copy.deepcopy(backup["config_data"]),
                    "timestamp": backup["timestamp"],
                    "description": backup["description"],
                    "message": "Configuration restored successfully"
                }
    
    # Try loading from disk
    try:
        backup_file = os.path.join(BACKUP_DIR, f"{backup_id}.json")
        if os.path.exists(backup_file):
            with open(backup_file, 'r') as f:
                backup = json.load(f)
            return {
                "success": True,
                "backup_id": backup_id,
                "config_name": backup["config_name"],
                "config_data": backup["config_data"],
                "timestamp": backup["timestamp"],
                "description": backup.get("description", ""),
                "message": "Configuration restored from disk backup"
            }
    except Exception as e:
        pass
    
    return {
        "success": False,
        "backup_id": backup_id,
        "error": "Backup not found",
        "message": f"No backup found with ID: {backup_id}"
    }


def suggest_autofix(validation_result: Dict[str, Any], config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Suggest automatic fixes for configuration issues.
    
    Args:
        validation_result: Result from validate_config()
        config_data: Original configuration data
        
    Returns:
        Dictionary with auto-fix suggestions
    """
    if validation_result.get("valid") and not validation_result.get("warnings"):
        return {
            "has_fixes": False,
            "message": "Configuration is valid, no fixes needed"
        }
    
    fixed_config = copy.deepcopy(config_data)
    fixes_applied = []
    
    # Apply suggestions from validation
    for suggestion in validation_result.get("suggestions", []):
        field = suggestion.get("field")
        suggested_value = suggestion.get("suggestion")
        reason = suggestion.get("reason")
        
        if field in fixed_config:
            old_value = fixed_config[field]
            fixed_config[field] = suggested_value
            fixes_applied.append({
                "field": field,
                "old_value": old_value,
                "new_value": suggested_value,
                "reason": reason
            })
    
    # Apply common fixes based on errors
    for error in validation_result.get("errors", []):
        if "timeout must be" in error.lower():
            if "timeout" in fixed_config:
                fixed_config["timeout"] = 300  # Default safe timeout
                fixes_applied.append({
                    "field": "timeout",
                    "old_value": config_data.get("timeout"),
                    "new_value": 300,
                    "reason": "Reset to safe default value"
                })
        
        if "port must be" in error.lower():
            if "port" in fixed_config:
                fixed_config["port"] = 8080  # Default safe port
                fixes_applied.append({
                    "field": "port",
                    "old_value": config_data.get("port"),
                    "new_value": 8080,
                    "reason": "Reset to safe default port"
                })
    
    return {
        "has_fixes": len(fixes_applied) > 0,
        "fixes_applied": fixes_applied,
        "fixed_config": fixed_config,
        "message": f"Applied {len(fixes_applied)} automatic fixes"
    }


def list_backups(config_name: Optional[str] = None) -> Dict[str, Any]:
    """
    List available configuration backups.
    
    Args:
        config_name: Optional config name to filter by
        
    Returns:
        Dictionary with list of backups
    """
    all_backups = []
    
    # Get from memory
    if config_name:
        backups = config_backups.get(config_name, [])
        for backup in backups:
            all_backups.append({
                "backup_id": backup["backup_id"],
                "config_name": backup["config_name"],
                "timestamp": backup["timestamp"],
                "description": backup["description"],
                "size_bytes": backup["size_bytes"]
            })
    else:
        for cfg_name, backups in config_backups.items():
            for backup in backups:
                all_backups.append({
                    "backup_id": backup["backup_id"],
                    "config_name": backup["config_name"],
                    "timestamp": backup["timestamp"],
                    "description": backup["description"],
                    "size_bytes": backup["size_bytes"]
                })
    
    # Also check disk backups
    try:
        if os.path.exists(BACKUP_DIR):
            for filename in os.listdir(BACKUP_DIR):
                if filename.endswith('.json'):
                    backup_id = filename[:-5]  # Remove .json
                    # Check if already in list (avoid duplicates)
                    if not any(b["backup_id"] == backup_id for b in all_backups):
                        try:
                            filepath = os.path.join(BACKUP_DIR, filename)
                            with open(filepath, 'r') as f:
                                backup = json.load(f)
                            if not config_name or backup["config_name"] == config_name:
                                all_backups.append({
                                    "backup_id": backup["backup_id"],
                                    "config_name": backup["config_name"],
                                    "timestamp": backup["timestamp"],
                                    "description": backup.get("description", ""),
                                    "size_bytes": os.path.getsize(filepath)
                                })
                        except:
                            pass
    except Exception as e:
        print(f"Warning: Could not read disk backups: {e}")
    
    # Sort by timestamp (newest first)
    all_backups.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "backups": all_backups,
        "count": len(all_backups),
        "config_name": config_name
    }


# Validation helper functions

def _is_valid_target(target: str) -> bool:
    """Check if target is a valid IP, hostname, or CIDR."""
    import re
    
    # IP address
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, target):
        parts = target.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    # CIDR notation
    if '/' in target:
        cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
        if re.match(cidr_pattern, target):
            ip_part = target.split('/')[0]
            return _is_valid_target(ip_part)
    
    # IP range
    if '-' in target:
        range_pattern = r'^(\d{1,3}\.){3}\d{1,3}-\d{1,3}$'
        if re.match(range_pattern, target):
            return True
    
    # Hostname/domain
    hostname_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$'
    if re.match(hostname_pattern, target):
        return True
    
    return False


def _is_valid_port_spec(ports: str) -> bool:
    """Check if port specification is valid."""
    import re
    
    # Single port
    if ports.isdigit():
        port_num = int(ports)
        return 1 <= port_num <= 65535
    
    # Port range
    if '-' in ports:
        range_pattern = r'^\d+-\d+$'
        if re.match(range_pattern, ports):
            start, end = map(int, ports.split('-'))
            return 1 <= start <= end <= 65535
    
    # Comma-separated ports
    if ',' in ports:
        port_list = ports.split(',')
        return all(_is_valid_port_spec(p.strip()) for p in port_list)
    
    return False


def _is_valid_ip_or_hostname(host: str) -> bool:
    """Check if host is a valid IP address or hostname."""
    import re
    
    # IP address
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, host):
        parts = host.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    # Hostname
    hostname_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$'
    return bool(re.match(hostname_pattern, host))
