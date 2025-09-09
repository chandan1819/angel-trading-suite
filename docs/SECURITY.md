# Security Documentation

This document outlines security best practices, credential management, and security considerations for the Bank Nifty Options Trading System.

## Table of Contents

1. [Security Overview](#security-overview)
2. [Credential Management](#credential-management)
3. [Configuration Security](#configuration-security)
4. [Network Security](#network-security)
5. [System Security](#system-security)
6. [Data Protection](#data-protection)
7. [Access Control](#access-control)
8. [Monitoring and Auditing](#monitoring-and-auditing)
9. [Incident Response](#incident-response)
10. [Security Checklist](#security-checklist)

## Security Overview

The Bank Nifty Options Trading System handles sensitive financial data and API credentials that require robust security measures. This document provides comprehensive guidelines for securing the system in development, testing, and production environments.

### Security Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimum necessary access rights
3. **Zero Trust**: Verify everything, trust nothing
4. **Data Minimization**: Collect and store only necessary data
5. **Encryption**: Protect data in transit and at rest
6. **Monitoring**: Continuous security monitoring and alerting

### Threat Model

**Primary Threats:**
- Unauthorized access to trading accounts
- API credential theft or misuse
- System compromise leading to financial loss
- Data breaches exposing trading strategies
- Denial of service attacks during trading hours

**Attack Vectors:**
- Credential stuffing and brute force attacks
- Social engineering targeting API credentials
- Malware and system compromise
- Network interception and man-in-the-middle attacks
- Insider threats and privilege abuse

## Credential Management

### Angel Broking API Credentials

The system requires four critical credentials for Angel Broking API access:

1. **API Key**: Unique identifier for your application
2. **Client Code**: Your Angel Broking client identifier
3. **PIN**: Your trading PIN
4. **TOTP Secret**: Time-based One-Time Password secret

### Secure Credential Storage

#### ✅ Recommended Methods

**1. Environment Variables (Preferred)**
```bash
# Set in system environment
export ANGEL_API_KEY="your_api_key_here"
export ANGEL_CLIENT_CODE="your_client_code_here"
export ANGEL_PIN="your_pin_here"
export ANGEL_TOTP_SECRET="your_totp_secret_here"

# For persistent storage, add to ~/.bashrc or /etc/environment
echo 'export ANGEL_API_KEY="your_api_key_here"' >> ~/.bashrc
```

**2. Encrypted Configuration Files**
```bash
# Create encrypted configuration
gpg --symmetric --cipher-algo AES256 credentials.yaml

# Decrypt when needed
gpg --decrypt credentials.yaml.gpg > /tmp/credentials.yaml
```

**3. System Keyring (Linux/macOS)**
```bash
# Store in system keyring
secret-tool store --label="Angel API Key" service angel-api username api_key
secret-tool store --label="Angel Client Code" service angel-api username client_code

# Retrieve from keyring
API_KEY=$(secret-tool lookup service angel-api username api_key)
```

**4. HashiCorp Vault (Enterprise)**
```bash
# Store in Vault
vault kv put secret/angel-api api_key="your_key" client_code="your_code"

# Retrieve from Vault
vault kv get -field=api_key secret/angel-api
```

#### ❌ Methods to Avoid

**Never store credentials in:**
- Configuration files in plain text
- Source code or version control
- Log files or console output
- Shared directories or cloud storage
- Email or messaging systems
- Screenshots or documentation

### Credential Rotation

**Regular Rotation Schedule:**
- API Keys: Every 90 days
- TOTP Secrets: Every 180 days
- Trading PINs: Every 60 days (or as required by broker)

**Rotation Procedure:**
1. Generate new credentials in Angel Broking portal
2. Test new credentials in paper trading mode
3. Update production environment variables
4. Verify system functionality
5. Revoke old credentials
6. Document rotation in security log

### Credential Validation

```python
# Example credential validation
import os
import re

def validate_credentials():
    """Validate API credentials format and presence"""
    
    # Check presence
    required_vars = ['ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SECRET']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(f"Missing credentials: {missing}")
    
    # Validate format
    api_key = os.getenv('ANGEL_API_KEY')
    if not api_key or len(api_key) < 10:
        raise ValueError("Invalid API key format")
    
    client_code = os.getenv('ANGEL_CLIENT_CODE')
    if not client_code or not re.match(r'^[A-Z0-9]+$', client_code):
        raise ValueError("Invalid client code format")
    
    pin = os.getenv('ANGEL_PIN')
    if not pin or not re.match(r'^\d{4,6}$', pin):
        raise ValueError("Invalid PIN format")
    
    totp_secret = os.getenv('ANGEL_TOTP_SECRET')
    if not totp_secret or len(totp_secret) < 16:
        raise ValueError("Invalid TOTP secret format")
    
    return True
```

## Configuration Security

### Secure Configuration Practices

**1. Configuration File Permissions**
```bash
# Set restrictive permissions
chmod 600 config/trading_config.yaml
chmod 700 config/

# Verify permissions
ls -la config/
# Should show: -rw------- for config files
```

**2. Environment Variable Substitution**
```yaml
# Use environment variables in configuration
api:
  credentials:
    api_key: ${ANGEL_API_KEY}
    client_code: ${ANGEL_CLIENT_CODE}
    pin: ${ANGEL_PIN}
    totp_secret: ${ANGEL_TOTP_SECRET}

# Never hardcode credentials
api:
  credentials:
    api_key: "hardcoded_key_here"  # ❌ NEVER DO THIS
```

**3. Configuration Validation**
```python
def sanitize_config_for_logging(config_dict):
    """Remove sensitive data from config before logging"""
    sensitive_keys = ['api_key', 'client_code', 'pin', 'totp_secret', 'password']
    
    def sanitize_recursive(obj):
        if isinstance(obj, dict):
            return {
                key: '***REDACTED***' if any(sensitive in key.lower() for sensitive in sensitive_keys)
                else sanitize_recursive(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [sanitize_recursive(item) for item in obj]
        else:
            return obj
    
    return sanitize_recursive(config_dict)
```

### Configuration Backup Security

```bash
# Encrypt configuration backups
tar -czf - config/ | gpg --symmetric --cipher-algo AES256 > config_backup_$(date +%Y%m%d).tar.gz.gpg

# Secure backup storage
chmod 600 config_backup_*.tar.gz.gpg
mv config_backup_*.tar.gz.gpg /secure/backup/location/
```

## Network Security

### API Communication Security

**1. HTTPS Enforcement**
```python
# Always use HTTPS for API calls
API_BASE_URL = "https://apiconnect.angelbroking.com"  # ✅ Secure
# Never use HTTP
API_BASE_URL = "http://apiconnect.angelbroking.com"   # ❌ Insecure
```

**2. Certificate Validation**
```python
import requests

# Enable certificate verification (default)
response = requests.get(url, verify=True)  # ✅ Secure

# Never disable certificate verification
response = requests.get(url, verify=False)  # ❌ Insecure
```

**3. Request Timeout Configuration**
```python
# Set reasonable timeouts to prevent hanging connections
requests.get(url, timeout=(5, 30))  # (connect_timeout, read_timeout)
```

### Firewall Configuration

**Outbound Rules (Allow):**
```bash
# HTTPS for API calls
sudo ufw allow out 443/tcp

# DNS resolution
sudo ufw allow out 53/udp

# NTP synchronization
sudo ufw allow out 123/udp
```

**Inbound Rules (Deny by Default):**
```bash
# SSH access (if needed)
sudo ufw allow ssh

# Deny all other inbound traffic
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

### Proxy Configuration (if required)

```yaml
# Secure proxy configuration
api:
  proxy:
    https_proxy: "https://proxy.company.com:8080"
    verify_ssl: true
    proxy_auth:
      username: ${PROXY_USERNAME}
      password: ${PROXY_PASSWORD}
```

## System Security

### Operating System Hardening

**1. User Account Security**
```bash
# Create dedicated trading user
sudo useradd -r -s /bin/false -d /opt/banknifty-trading trading

# Set ownership
sudo chown -R trading:trading /opt/banknifty-trading

# Run system as trading user
sudo -u trading python3 main.py trade --mode live
```

**2. File System Permissions**
```bash
# Application files
chmod 755 /opt/banknifty-trading
chmod 644 /opt/banknifty-trading/src/**/*.py
chmod 755 /opt/banknifty-trading/main.py

# Configuration files
chmod 600 /opt/banknifty-trading/config/*.yaml

# Log directories
chmod 755 /opt/banknifty-trading/logs
chmod 644 /opt/banknifty-trading/logs/*.log

# Temporary files
chmod 700 /tmp/trading_*
```

**3. System Updates**
```bash
# Regular security updates
sudo apt update && sudo apt upgrade -y

# Automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### Python Environment Security

**1. Virtual Environment Isolation**
```bash
# Create isolated environment
python3 -m venv /opt/banknifty-trading/venv

# Activate and install packages
source /opt/banknifty-trading/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify package integrity
pip check
```

**2. Dependency Security**
```bash
# Check for known vulnerabilities
pip install safety
safety check

# Audit packages
pip-audit

# Pin package versions
pip freeze > requirements.lock
```

### Process Security

**1. Process Isolation**
```bash
# Run with limited privileges
sudo -u trading python3 main.py trade --mode live

# Use systemd for process management
sudo systemctl enable banknifty-trading
sudo systemctl start banknifty-trading
```

**2. Resource Limits**
```bash
# Set resource limits in systemd service
[Service]
LimitNOFILE=1024
LimitNPROC=100
MemoryLimit=1G
CPUQuota=50%
```

## Data Protection

### Sensitive Data Handling

**1. Data Classification**
- **Critical**: API credentials, trading PINs
- **Sensitive**: Trading strategies, P&L data, position information
- **Internal**: Configuration settings, log files
- **Public**: Documentation, general system information

**2. Data Encryption**

**At Rest:**
```bash
# Encrypt sensitive files
gpg --symmetric --cipher-algo AES256 sensitive_data.json

# Use encrypted file systems
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 encrypted_storage
```

**In Transit:**
```python
# All API communications use HTTPS/TLS
import ssl
import requests

# Verify TLS version
context = ssl.create_default_context()
print(f"TLS Version: {context.protocol}")
```

### Log Security

**1. Secure Logging Practices**
```python
import logging
import re

class SecureFormatter(logging.Formatter):
    """Custom formatter that redacts sensitive information"""
    
    SENSITIVE_PATTERNS = [
        r'api_key["\s]*[:=]["\s]*([^"\s,}]+)',
        r'pin["\s]*[:=]["\s]*([^"\s,}]+)',
        r'password["\s]*[:=]["\s]*([^"\s,}]+)',
        r'token["\s]*[:=]["\s]*([^"\s,}]+)',
    ]
    
    def format(self, record):
        message = super().format(record)
        
        # Redact sensitive information
        for pattern in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, r'\1***REDACTED***', message, flags=re.IGNORECASE)
        
        return message

# Configure secure logging
handler = logging.FileHandler('secure.log')
handler.setFormatter(SecureFormatter())
logger.addHandler(handler)
```

**2. Log File Security**
```bash
# Secure log file permissions
chmod 640 logs/*.log
chown trading:adm logs/*.log

# Log rotation with compression
logrotate -f /etc/logrotate.d/banknifty-trading
```

### Data Retention

**1. Retention Policies**
```yaml
# Configuration for data retention
data_retention:
  trade_logs: 7_years      # Regulatory requirement
  system_logs: 1_year      # Operational requirement
  debug_logs: 30_days      # Development requirement
  temp_files: 24_hours     # Cleanup requirement
```

**2. Secure Data Deletion**
```bash
# Secure file deletion
shred -vfz -n 3 sensitive_file.txt

# Secure directory cleanup
find /tmp -name "trading_*" -mtime +1 -exec shred -vfz {} \;
```

## Access Control

### User Access Management

**1. Role-Based Access Control**

**Roles:**
- **Administrator**: Full system access, configuration changes
- **Operator**: Start/stop trading, monitor system
- **Analyst**: Read-only access to logs and reports
- **Auditor**: Read-only access for compliance

**2. SSH Key Management**
```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "trading-system-access"

# Configure authorized keys
echo "ssh-ed25519 AAAAC3... user@host" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Disable password authentication
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### Service Account Security

**1. Dedicated Service Account**
```bash
# Create service account
sudo useradd -r -s /bin/false -d /opt/banknifty-trading trading-service

# Configure sudo access (if needed)
echo "trading-service ALL=(ALL) NOPASSWD: /bin/systemctl restart banknifty-trading" | sudo tee /etc/sudoers.d/trading-service
```

**2. API Key Management**
```bash
# Store API keys in secure location
sudo mkdir -p /etc/banknifty-trading/secrets
sudo chmod 700 /etc/banknifty-trading/secrets
sudo chown trading-service:trading-service /etc/banknifty-trading/secrets
```

## Monitoring and Auditing

### Security Monitoring

**1. System Monitoring**
```bash
# Monitor failed login attempts
sudo tail -f /var/log/auth.log | grep "Failed password"

# Monitor file access
sudo auditctl -w /opt/banknifty-trading/config -p rwxa -k config_access
sudo ausearch -k config_access
```

**2. Application Monitoring**
```python
import logging
import functools

def audit_log(action):
    """Decorator for auditing sensitive actions"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger('audit')
            logger.info(f"Action: {action}, User: {os.getenv('USER')}, Time: {datetime.now()}")
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Action: {action}, Status: SUCCESS")
                return result
            except Exception as e:
                logger.error(f"Action: {action}, Status: FAILED, Error: {str(e)}")
                raise
        
        return wrapper
    return decorator

@audit_log("place_order")
def place_order(order_details):
    # Order placement logic
    pass
```

### Security Alerts

**1. Automated Alerting**
```python
def security_alert(message, severity="HIGH"):
    """Send security alert"""
    alert_data = {
        "timestamp": datetime.now().isoformat(),
        "severity": severity,
        "message": message,
        "system": "banknifty-trading",
        "host": socket.gethostname()
    }
    
    # Send to monitoring system
    send_webhook_alert(alert_data)
    
    # Log security event
    security_logger.critical(f"SECURITY_ALERT: {message}")

# Example usage
if failed_login_attempts > 5:
    security_alert("Multiple failed login attempts detected")
```

**2. Intrusion Detection**
```bash
# Install and configure fail2ban
sudo apt install fail2ban

# Configure jail for SSH
sudo tee /etc/fail2ban/jail.local << EOF
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOF

sudo systemctl restart fail2ban
```

## Incident Response

### Security Incident Classification

**1. Severity Levels**
- **Critical**: Unauthorized access to trading accounts, credential compromise
- **High**: System compromise, data breach, service disruption during trading hours
- **Medium**: Failed authentication attempts, configuration changes
- **Low**: Policy violations, minor security events

**2. Response Procedures**

**Immediate Response (0-15 minutes):**
1. Activate emergency stop if trading is active
2. Isolate affected systems from network
3. Preserve evidence and logs
4. Notify incident response team

**Short-term Response (15 minutes - 4 hours):**
1. Assess scope and impact
2. Contain the incident
3. Begin forensic analysis
4. Implement temporary fixes

**Long-term Response (4+ hours):**
1. Complete forensic investigation
2. Implement permanent fixes
3. Update security controls
4. Document lessons learned

### Emergency Procedures

**1. Credential Compromise**
```bash
# Immediate actions
echo "SECURITY INCIDENT - CREDENTIAL COMPROMISE" > emergency_stop.txt

# Revoke compromised credentials
# (Manual process through Angel Broking portal)

# Generate new credentials
# Update environment variables
export ANGEL_API_KEY="new_api_key"
export ANGEL_CLIENT_CODE="new_client_code"

# Test new credentials
python3 main.py trade --mode paper --once

# Resume trading with new credentials
rm emergency_stop.txt
python3 main.py trade --mode live --continuous
```

**2. System Compromise**
```bash
# Immediate isolation
sudo iptables -A OUTPUT -j DROP
sudo systemctl stop banknifty-trading

# Preserve evidence
sudo dd if=/dev/sda of=/forensics/system_image.dd bs=4M
sudo tar -czf /forensics/logs_$(date +%Y%m%d_%H%M%S).tar.gz /opt/banknifty-trading/logs/

# Incident documentation
echo "Incident ID: INC-$(date +%Y%m%d-%H%M%S)" > /forensics/incident_report.txt
echo "Discovery Time: $(date)" >> /forensics/incident_report.txt
echo "Discovered By: $(whoami)" >> /forensics/incident_report.txt
```

## Security Checklist

### Pre-Deployment Security Checklist

#### Credentials and Authentication
- [ ] API credentials stored in environment variables
- [ ] No hardcoded credentials in configuration files
- [ ] Credential format validation implemented
- [ ] TOTP secret properly configured
- [ ] Credential rotation schedule established

#### System Security
- [ ] Dedicated user account created for trading system
- [ ] File permissions set correctly (600 for configs, 755 for directories)
- [ ] System packages updated to latest versions
- [ ] Firewall configured with minimal required rules
- [ ] SSH key authentication enabled, password auth disabled

#### Application Security
- [ ] Virtual environment configured and isolated
- [ ] Dependencies checked for known vulnerabilities
- [ ] Secure logging implemented (no sensitive data in logs)
- [ ] Input validation implemented for all user inputs
- [ ] Error handling doesn't expose sensitive information

#### Network Security
- [ ] HTTPS enforced for all API communications
- [ ] Certificate validation enabled
- [ ] Proxy configuration secured (if applicable)
- [ ] Network timeouts configured appropriately
- [ ] Rate limiting implemented

#### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] Secure data transmission (TLS/HTTPS)
- [ ] Log files protected with appropriate permissions
- [ ] Data retention policies implemented
- [ ] Secure deletion procedures for temporary files

### Ongoing Security Checklist

#### Daily
- [ ] Review security logs for anomalies
- [ ] Check system resource usage
- [ ] Verify emergency stop procedures work
- [ ] Monitor failed authentication attempts

#### Weekly
- [ ] Review and rotate temporary credentials
- [ ] Check for system updates
- [ ] Analyze security monitoring alerts
- [ ] Test backup and recovery procedures

#### Monthly
- [ ] Rotate API credentials
- [ ] Conduct security vulnerability scan
- [ ] Review and update firewall rules
- [ ] Update incident response procedures
- [ ] Security awareness training

#### Quarterly
- [ ] Comprehensive security audit
- [ ] Penetration testing (if applicable)
- [ ] Review and update security policies
- [ ] Disaster recovery testing
- [ ] Third-party security assessment

### Security Compliance

#### Regulatory Requirements
- Maintain audit trails for all trading activities
- Implement appropriate data retention policies
- Ensure secure handling of financial data
- Comply with broker security requirements

#### Industry Standards
- Follow OWASP security guidelines
- Implement defense-in-depth strategies
- Use encryption for sensitive data
- Regular security assessments and updates

This security documentation provides a comprehensive framework for securing the Bank Nifty Options Trading System. Regular review and updates of these security measures are essential to maintain a strong security posture.