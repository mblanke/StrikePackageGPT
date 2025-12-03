"""
Explain Module
Provides "Explain this" functionality for configs, logs, errors, and onboarding.
Generates plain-English explanations and suggestions for fixes.
"""

from typing import Dict, Any, Optional, List
import re
import os


def explain_config(config_key: str, config_value: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Explain a configuration setting in plain English.
    
    Args:
        config_key: Configuration key/name
        config_value: Current value of the configuration
        context: Additional context about the configuration
        
    Returns:
        Dictionary with explanation and recommendations
    """
    # Common configuration patterns and their explanations
    config_patterns = {
        r'.*timeout.*': {
            'description': 'Controls how long the system waits before giving up on an operation',
            'example': 'A timeout of 30 seconds means operations will be cancelled after 30s',
            'recommendations': [
                'Increase timeout for slow networks or large scans',
                'Decrease timeout for faster detection of unavailable services',
                'Typical values: 10-300 seconds'
            ]
        },
        r'.*port.*': {
            'description': 'Specifies which network port to use for communication',
            'example': 'Port 8080 is commonly used for web applications',
            'recommendations': [
                'Use standard ports (80/443) for production',
                'Use high ports (8000+) for development',
                'Ensure port is not blocked by firewall'
            ]
        },
        r'.*api[_-]?key.*': {
            'description': 'Authentication key for accessing external services',
            'example': 'API keys should be kept secret and not shared publicly',
            'recommendations': [
                'Store API keys in environment variables',
                'Never commit API keys to version control',
                'Rotate keys regularly for security'
            ]
        },
        r'.*thread.*|.*worker.*': {
            'description': 'Controls parallel processing and concurrency',
            'example': '4 workers means 4 operations can run simultaneously',
            'recommendations': [
                'More workers = faster but more resource usage',
                'Typical range: number of CPU cores or 2x CPU cores',
                'Too many workers can overwhelm the system'
            ]
        },
        r'.*rate[_-]?limit.*': {
            'description': 'Limits the frequency of operations to prevent overload',
            'example': 'Rate limit of 100/minute means max 100 requests per minute',
            'recommendations': [
                'Set based on target system capabilities',
                'Lower for sensitive or production targets',
                'Higher for testing environments'
            ]
        }
    }
    
    # Find matching pattern
    explanation = {
        'description': 'Configuration setting',
        'example': '',
        'recommendations': []
    }
    
    for pattern, details in config_patterns.items():
        if re.search(pattern, config_key, re.IGNORECASE):
            explanation = details
            break
    
    # Value-specific analysis
    value_analysis = _analyze_config_value(config_key, config_value)
    
    return {
        'config_key': config_key,
        'current_value': str(config_value),
        'description': explanation['description'],
        'example': explanation['example'],
        'recommendations': explanation['recommendations'],
        'value_analysis': value_analysis,
        'safe_to_change': _is_safe_to_change(config_key),
        'requires_restart': _requires_restart(config_key)
    }


def explain_error(error_message: str, error_type: Optional[str] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Explain an error message in plain English with suggested fixes.
    
    Args:
        error_message: The error message text
        error_type: Type/category of error (if known)
        context: Additional context about where/when the error occurred
        
    Returns:
        Dictionary with explanation and fix suggestions
    """
    # Common error patterns
    error_patterns = [
        {
            'pattern': r'connection\s+(refused|timed?\s?out|failed|reset)',
            'plain_english': 'Unable to connect to the target',
            'likely_causes': [
                'Target is offline or unreachable',
                'Firewall blocking the connection',
                'Wrong IP address or port',
                'Network connectivity issues'
            ],
            'suggested_fixes': [
                'Verify target IP address is correct',
                'Check if target is online (ping test)',
                'Ensure no firewall is blocking the connection',
                'Try a different port or protocol'
            ]
        },
        {
            'pattern': r'permission\s+denied|access\s+denied|forbidden',
            'plain_english': 'You don\'t have permission to perform this action',
            'likely_causes': [
                'Insufficient user privileges',
                'Authentication failed',
                'Resource is protected',
                'Rate limiting in effect'
            ],
            'suggested_fixes': [
                'Run with appropriate privileges (sudo if needed)',
                'Check authentication credentials',
                'Verify you have permission to access this resource',
                'Wait before retrying (if rate limited)'
            ]
        },
        {
            'pattern': r'not\s+found|does\s+not\s+exist|no\s+such',
            'plain_english': 'The requested resource could not be found',
            'likely_causes': [
                'Resource has been moved or deleted',
                'Incorrect path or name',
                'Typo in the request',
                'Resource not yet created'
            ],
            'suggested_fixes': [
                'Check spelling and capitalization',
                'Verify the resource exists',
                'Check if path or URL is correct',
                'Create the resource if needed'
            ]
        },
        {
            'pattern': r'invalid\s+(argument|parameter|input|syntax)',
            'plain_english': 'The input provided is not valid or in the wrong format',
            'likely_causes': [
                'Wrong data type or format',
                'Missing required parameter',
                'Value out of valid range',
                'Syntax error in command'
            ],
            'suggested_fixes': [
                'Check documentation for correct format',
                'Verify all required parameters are provided',
                'Ensure values are within valid ranges',
                'Check for typos in the command'
            ]
        },
        {
            'pattern': r'timeout|timed\s+out',
            'plain_english': 'The operation took too long and was cancelled',
            'likely_causes': [
                'Network is slow or congested',
                'Target is responding slowly',
                'Timeout setting is too low',
                'Large operation needs more time'
            ],
            'suggested_fixes': [
                'Increase timeout value in settings',
                'Check network connectivity',
                'Try again during off-peak hours',
                'Break operation into smaller parts'
            ]
        },
        {
            'pattern': r'out\s+of\s+memory|memory\s+error',
            'plain_english': 'The system ran out of available memory',
            'likely_causes': [
                'Too many concurrent operations',
                'Processing too much data at once',
                'Memory leak in the application',
                'Insufficient system resources'
            ],
            'suggested_fixes': [
                'Reduce number of concurrent operations',
                'Process data in smaller batches',
                'Restart the application',
                'Add more RAM to the system'
            ]
        }
    ]
    
    # Find matching pattern
    match_result = {
        'plain_english': 'An error occurred',
        'likely_causes': ['Unknown error condition'],
        'suggested_fixes': ['Check logs for more details', 'Try the operation again']
    }
    
    error_lower = error_message.lower()
    for pattern_info in error_patterns:
        if re.search(pattern_info['pattern'], error_lower):
            match_result = {
                'plain_english': pattern_info['plain_english'],
                'likely_causes': pattern_info['likely_causes'],
                'suggested_fixes': pattern_info['suggested_fixes']
            }
            break
    
    return {
        'original_error': error_message,
        'error_type': error_type or 'unknown',
        'plain_english': match_result['plain_english'],
        'likely_causes': match_result['likely_causes'],
        'suggested_fixes': match_result['suggested_fixes'],
        'severity': _assess_error_severity(error_message),
        'context': context or {}
    }


def explain_log_entry(log_entry: str, log_level: Optional[str] = None) -> Dict[str, Any]:
    """
    Explain a log entry in plain English.
    
    Args:
        log_entry: The log message text
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Dictionary with explanation of the log entry
    """
    # Detect log level if not provided
    if not log_level:
        log_level = _detect_log_level(log_entry)
    
    # Extract key information from log
    extracted_info = _extract_log_info(log_entry)
    
    # Determine if action is needed
    action_needed = log_level in ['ERROR', 'CRITICAL', 'WARNING']
    
    explanation = {
        'log_entry': log_entry,
        'log_level': log_level,
        'timestamp': extracted_info.get('timestamp'),
        'component': extracted_info.get('component'),
        'message': extracted_info.get('message', log_entry),
        'action_needed': action_needed,
        'explanation': _generate_log_explanation(log_entry, log_level),
        'next_steps': _suggest_log_next_steps(log_entry, log_level) if action_needed else []
    }
    
    return explanation


def get_wizard_step_help(wizard_type: str, step_number: int) -> Dict[str, Any]:
    """
    Get help text for a specific wizard step.
    
    Args:
        wizard_type: Type of wizard (create_operation, onboard_agent, run_scan, first_time_setup)
        step_number: Current step number (1-indexed)
        
    Returns:
        Dictionary with help information for the step
    """
    wizard_help = {
        'create_operation': {
            1: {
                'title': 'Operation Name and Type',
                'description': 'Give your operation a memorable name and select the type of security assessment',
                'tips': [
                    'Use descriptive names like "Q4 External Assessment" or "Web App Pentest"',
                    'Choose the operation type that matches your goals',
                    'You can change these later in settings'
                ],
                'example': 'Example: "Internal Network Audit - Production"'
            },
            2: {
                'title': 'Define Target Scope',
                'description': 'Specify which systems, networks, or applications to include in the assessment',
                'tips': [
                    'Use CIDR notation for network ranges (e.g., 192.168.1.0/24)',
                    'Add individual hosts or domains as needed',
                    'Clearly define what is in-scope and out-of-scope'
                ],
                'example': 'Example: 192.168.1.0/24, app.example.com'
            },
            3: {
                'title': 'Configure Assessment Tools',
                'description': 'Select which security tools to use and configure their settings',
                'tips': [
                    'Start with reconnaissance tools (nmap, whatweb)',
                    'Add vulnerability scanners based on target type',
                    'Adjust scan intensity based on target sensitivity'
                ],
                'example': 'Example: nmap (aggressive), nikto (web servers only)'
            }
        },
        'run_scan': {
            1: {
                'title': 'Select Scan Tool',
                'description': 'Choose the security tool appropriate for your target',
                'tips': [
                    'nmap: Network scanning and service detection',
                    'nikto: Web server vulnerability scanning',
                    'gobuster: Directory and file discovery',
                    'sqlmap: SQL injection testing'
                ],
                'example': 'For a web server, use nikto or gobuster'
            },
            2: {
                'title': 'Specify Target',
                'description': 'Enter the IP address, hostname, or network range to scan',
                'tips': [
                    'Single host: 192.168.1.100 or example.com',
                    'Network range: 192.168.1.0/24',
                    'Multiple hosts: 192.168.1.1-50'
                ],
                'example': 'Example: 192.168.1.0/24 for entire subnet'
            },
            3: {
                'title': 'Scan Options',
                'description': 'Configure scan parameters and intensity',
                'tips': [
                    'Quick scan: Fast but less thorough',
                    'Full scan: Comprehensive but slower',
                    'Stealth: Slower but harder to detect'
                ],
                'example': 'Use quick scan for initial reconnaissance'
            }
        }
    }
    
    steps = wizard_help.get(wizard_type, {})
    step_help = steps.get(step_number, {
        'title': f'Step {step_number}',
        'description': 'Complete this step to continue',
        'tips': ['Fill in the required information'],
        'example': ''
    })
    
    return {
        'wizard_type': wizard_type,
        'step_number': step_number,
        'total_steps': len(steps),
        **step_help
    }


def suggest_fix(issue_description: str, context: Optional[Dict] = None) -> List[str]:
    """
    Suggest fixes for a described issue.
    
    Args:
        issue_description: Description of the problem
        context: Additional context (error codes, logs, etc.)
        
    Returns:
        List of suggested fix actions
    """
    issue_lower = issue_description.lower()
    fixes = []
    
    # Connectivity issues
    if any(word in issue_lower for word in ['connect', 'network', 'reach', 'timeout']):
        fixes.extend([
            'Verify target is online with ping test',
            'Check firewall rules and network connectivity',
            'Ensure correct IP address and port number',
            'Try increasing timeout value in settings'
        ])
    
    # Permission issues
    if any(word in issue_lower for word in ['permission', 'access', 'denied', 'forbidden']):
        fixes.extend([
            'Run with elevated privileges (sudo)',
            'Check file/directory permissions',
            'Verify authentication credentials',
            'Ensure user has required roles/permissions'
        ])
    
    # Configuration issues
    if any(word in issue_lower for word in ['config', 'setting', 'option']):
        fixes.extend([
            'Review configuration file for errors',
            'Restore default configuration',
            'Check configuration documentation',
            'Validate configuration format (JSON/YAML)'
        ])
    
    # Tool/command issues
    if any(word in issue_lower for word in ['command', 'tool', 'not found', 'install']):
        fixes.extend([
            'Install the required tool or package',
            'Check if tool is in system PATH',
            'Verify tool name spelling',
            'Update tool to latest version'
        ])
    
    # Default suggestions if no specific fix found
    if not fixes:
        fixes = [
            'Check system logs for more details',
            'Restart the affected service',
            'Review recent configuration changes',
            'Consult documentation or support'
        ]
    
    return fixes[:5]  # Return top 5 suggestions


# Helper functions

def _analyze_config_value(key: str, value: Any) -> str:
    """Analyze a configuration value and provide feedback."""
    if isinstance(value, int):
        if 'timeout' in key.lower():
            if value < 10:
                return 'Very low - may cause premature failures'
            elif value > 300:
                return 'Very high - operations may take long to fail'
            else:
                return 'Reasonable value'
        elif 'port' in key.lower():
            if value < 1024:
                return 'System port - requires elevated privileges'
            else:
                return 'User port - no special privileges needed'
    
    return 'Current value seems valid'


def _is_safe_to_change(config_key: str) -> bool:
    """Determine if a config is safe to change without risk."""
    unsafe_keys = ['database', 'credential', 'key', 'secret', 'password']
    return not any(unsafe in config_key.lower() for unsafe in unsafe_keys)


def _requires_restart(config_key: str) -> bool:
    """Determine if changing this config requires a restart."""
    restart_keys = ['port', 'host', 'database', 'worker', 'thread']
    return any(key in config_key.lower() for key in restart_keys)


def _assess_error_severity(error_message: str) -> str:
    """Assess the severity of an error."""
    error_lower = error_message.lower()
    
    if any(word in error_lower for word in ['critical', 'fatal', 'crash', 'panic']):
        return 'critical'
    elif any(word in error_lower for word in ['error', 'fail', 'exception']):
        return 'high'
    elif any(word in error_lower for word in ['warning', 'warn']):
        return 'medium'
    else:
        return 'low'


def _detect_log_level(log_entry: str) -> str:
    """Detect log level from log entry."""
    levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    for level in levels:
        if level in log_entry.upper():
            return level
    return 'INFO'


def _extract_log_info(log_entry: str) -> Dict[str, str]:
    """Extract structured information from a log entry."""
    info = {}
    
    # Try to extract timestamp
    timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'
    timestamp_match = re.search(timestamp_pattern, log_entry)
    if timestamp_match:
        info['timestamp'] = timestamp_match.group()
    
    # Try to extract component/module name
    component_pattern = r'\[(\w+)\]'
    component_match = re.search(component_pattern, log_entry)
    if component_match:
        info['component'] = component_match.group(1)
    
    # Extract the main message
    parts = log_entry.split(':', 1)
    if len(parts) > 1:
        info['message'] = parts[1].strip()
    else:
        info['message'] = log_entry
    
    return info


def _generate_log_explanation(log_entry: str, log_level: str) -> str:
    """Generate a plain English explanation of a log entry."""
    if log_level == 'ERROR':
        return 'An error occurred that may require attention. Check the details to understand what went wrong.'
    elif log_level == 'WARNING':
        return 'A potential issue was detected. It may not be critical but should be reviewed.'
    elif log_level == 'INFO':
        return 'Normal operational message providing status information.'
    elif log_level == 'DEBUG':
        return 'Detailed diagnostic information useful for troubleshooting.'
    else:
        return 'Log entry documenting system activity.'


def _suggest_log_next_steps(log_entry: str, log_level: str) -> List[str]:
    """Suggest next steps based on log entry."""
    steps = []
    
    if log_level in ['ERROR', 'CRITICAL']:
        steps.append('Review the error details and check related logs')
        steps.append('Check if the issue is repeating or isolated')
        steps.append('Consider rolling back recent changes if applicable')
    
    if log_level == 'WARNING':
        steps.append('Monitor for repeated warnings')
        steps.append('Check if this indicates a trend or pattern')
    
    if 'connection' in log_entry.lower():
        steps.append('Verify network connectivity to the target')
    
    if 'timeout' in log_entry.lower():
        steps.append('Consider increasing timeout values')
    
    return steps
