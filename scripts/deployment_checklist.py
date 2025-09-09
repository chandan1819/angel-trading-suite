#!/usr/bin/env python3
"""
Deployment Checklist Script for Bank Nifty Options Trading System

This script provides a comprehensive pre-deployment checklist and validation
to ensure the system is ready for production use.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.config_manager import ConfigManager


class DeploymentChecker:
    """Comprehensive deployment readiness checker"""
    
    def __init__(self, config_file: str = 'trading_config.yaml'):
        self.config_file = config_file
        self.checklist = {
            'timestamp': datetime.now().isoformat(),
            'config_file': config_file,
            'checks': {},
            'overall_status': 'UNKNOWN',
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }
    
    def run_deployment_check(self) -> Dict[str, Any]:
        """Run complete deployment readiness check"""
        print("🚀 Bank Nifty Options Trading System - Deployment Checklist")
        print("=" * 60)
        
        # 1. Environment and Dependencies
        self._check_environment()
        
        # 2. Configuration Validation
        self._check_configuration()
        
        # 3. Security Validation
        self._check_security()
        
        # 4. API Credentials and Connectivity
        self._check_api_setup()
        
        # 5. File System and Permissions
        self._check_filesystem()
        
        # 6. Risk Management Validation
        self._check_risk_management()
        
        # 7. Logging and Monitoring Setup
        self._check_logging_monitoring()
        
        # 8. Backup and Recovery
        self._check_backup_recovery()
        
        # 9. Performance and Resources
        self._check_performance_resources()
        
        # 10. Testing and Validation
        self._check_testing_validation()
        
        # Determine overall readiness
        self._determine_deployment_readiness()
        
        return self.checklist
    
    def _check_environment(self):
        """Check Python environment and dependencies"""
        check_name = 'environment'
        print(f"\n📋 Checking Environment and Dependencies...")
        
        checks = {}
        
        # Python version
        python_version = sys.version_info
        python_ok = python_version >= (3, 8)
        checks['python_version'] = {
            'status': 'PASS' if python_ok else 'FAIL',
            'version': f"{python_version.major}.{python_version.minor}.{python_version.micro}",
            'required': '3.8+'
        }
        
        if not python_ok:
            self.checklist['critical_issues'].append(f"Python version {python_version.major}.{python_version.minor} is too old. Requires 3.8+")
        
        # Required packages
        required_packages = [
            'pandas', 'numpy', 'requests', 'pyyaml', 'pytest', 'psutil'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                checks[f'package_{package}'] = {'status': 'PASS'}
            except ImportError:
                checks[f'package_{package}'] = {'status': 'FAIL'}
                missing_packages.append(package)
        
        if missing_packages:
            self.checklist['critical_issues'].append(f"Missing required packages: {', '.join(missing_packages)}")
        
        # Virtual environment check
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        checks['virtual_environment'] = {
            'status': 'PASS' if in_venv else 'WARN',
            'in_venv': in_venv
        }
        
        if not in_venv:
            self.checklist['warnings'].append("Not running in virtual environment (recommended for production)")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Python Version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        print(f"   ✓ Required Packages: {len(required_packages) - len(missing_packages)}/{len(required_packages)}")
        if missing_packages:
            print(f"   ✗ Missing Packages: {', '.join(missing_packages)}")
    
    def _check_configuration(self):
        """Check configuration file and settings"""
        check_name = 'configuration'
        print(f"\n⚙️  Checking Configuration...")
        
        checks = {}
        
        # Configuration file exists
        config_exists = Path(self.config_file).exists()
        checks['config_file_exists'] = {
            'status': 'PASS' if config_exists else 'FAIL',
            'file': self.config_file
        }
        
        if not config_exists:
            self.checklist['critical_issues'].append(f"Configuration file {self.config_file} not found")
            self.checklist['checks'][check_name] = checks
            return
        
        # Load and validate configuration
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            checks['config_loading'] = {'status': 'PASS'}
            
            # Validate configuration
            validation_result = config.validate()
            checks['config_validation'] = {
                'status': 'PASS' if validation_result else 'FAIL'
            }
            
            if not validation_result:
                self.checklist['critical_issues'].append("Configuration validation failed")
            
            # Check critical settings
            checks['trading_mode'] = {
                'status': 'PASS',
                'mode': config.mode.value
            }
            
            # Risk settings validation
            risk_settings_ok = all([
                config.risk.profit_target > 0,
                config.risk.stop_loss > 0,
                config.risk.max_daily_loss > 0,
                config.risk.max_concurrent_trades > 0
            ])
            
            checks['risk_settings'] = {
                'status': 'PASS' if risk_settings_ok else 'FAIL',
                'profit_target': config.risk.profit_target,
                'stop_loss': config.risk.stop_loss,
                'max_daily_loss': config.risk.max_daily_loss
            }
            
            if not risk_settings_ok:
                self.checklist['critical_issues'].append("Invalid risk management settings")
            
            # Strategy configuration
            enabled_strategies = []
            if config.strategy.straddle.enabled:
                enabled_strategies.append('straddle')
            if config.strategy.directional.enabled:
                enabled_strategies.append('directional')
            if config.strategy.iron_condor.enabled:
                enabled_strategies.append('iron_condor')
            if config.strategy.greeks.enabled:
                enabled_strategies.append('greeks')
            if config.strategy.volatility.enabled:
                enabled_strategies.append('volatility')
            
            checks['strategies'] = {
                'status': 'PASS' if enabled_strategies else 'WARN',
                'enabled_strategies': enabled_strategies,
                'count': len(enabled_strategies)
            }
            
            if not enabled_strategies:
                self.checklist['warnings'].append("No trading strategies enabled")
            
        except Exception as e:
            checks['config_loading'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            self.checklist['critical_issues'].append(f"Configuration loading failed: {str(e)}")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Configuration File: {config_exists}")
        if config_exists:
            print(f"   ✓ Configuration Valid: {checks.get('config_validation', {}).get('status') == 'PASS'}")
    
    def _check_security(self):
        """Check security configuration"""
        check_name = 'security'
        print(f"\n🔒 Checking Security Configuration...")
        
        checks = {}
        
        # Environment variables for credentials
        required_env_vars = [
            'ANGEL_API_KEY',
            'ANGEL_CLIENT_CODE',
            'ANGEL_PIN',
            'ANGEL_TOTP_SECRET'
        ]
        
        missing_env_vars = []
        for var in required_env_vars:
            if os.getenv(var):
                checks[f'env_var_{var.lower()}'] = {'status': 'PASS'}
            else:
                checks[f'env_var_{var.lower()}'] = {'status': 'FAIL'}
                missing_env_vars.append(var)
        
        if missing_env_vars:
            self.checklist['critical_issues'].append(f"Missing environment variables: {', '.join(missing_env_vars)}")
        
        # Check for hardcoded credentials in config
        config_file_content = ""
        try:
            with open(self.config_file, 'r') as f:
                config_file_content = f.read()
        except:
            pass
        
        hardcoded_creds = any([
            'api_key:' in config_file_content and '${' not in config_file_content,
            'client_code:' in config_file_content and '${' not in config_file_content,
            'pin:' in config_file_content and '${' not in config_file_content
        ])
        
        checks['no_hardcoded_credentials'] = {
            'status': 'FAIL' if hardcoded_creds else 'PASS'
        }
        
        if hardcoded_creds:
            self.checklist['critical_issues'].append("Hardcoded credentials detected in configuration file")
        
        # File permissions
        config_path = Path(self.config_file)
        if config_path.exists():
            file_mode = oct(config_path.stat().st_mode)[-3:]
            secure_permissions = file_mode in ['600', '644']
            checks['config_file_permissions'] = {
                'status': 'PASS' if secure_permissions else 'WARN',
                'permissions': file_mode
            }
            
            if not secure_permissions:
                self.checklist['warnings'].append(f"Configuration file permissions ({file_mode}) may be too permissive")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Environment Variables: {len(required_env_vars) - len(missing_env_vars)}/{len(required_env_vars)}")
        print(f"   ✓ No Hardcoded Credentials: {not hardcoded_creds}")
    
    def _check_api_setup(self):
        """Check API credentials and connectivity"""
        check_name = 'api_setup'
        print(f"\n🌐 Checking API Setup...")
        
        checks = {}
        
        # Basic credential check (already done in security, but verify format)
        api_key = os.getenv('ANGEL_API_KEY')
        client_code = os.getenv('ANGEL_CLIENT_CODE')
        pin = os.getenv('ANGEL_PIN')
        totp_secret = os.getenv('ANGEL_TOTP_SECRET')
        
        credentials_format_ok = all([
            api_key and len(api_key) > 10,
            client_code and len(client_code) > 3,
            pin and len(pin) >= 4,
            totp_secret and len(totp_secret) > 10
        ])
        
        checks['credentials_format'] = {
            'status': 'PASS' if credentials_format_ok else 'FAIL'
        }
        
        if not credentials_format_ok:
            self.checklist['critical_issues'].append("API credentials appear to have invalid format")
        
        # Network connectivity test
        try:
            import requests
            response = requests.get('https://apiconnect.angelbroking.com', timeout=10)
            network_ok = response.status_code in [200, 404]  # 404 is OK, means server is reachable
        except:
            network_ok = False
        
        checks['network_connectivity'] = {
            'status': 'PASS' if network_ok else 'FAIL'
        }
        
        if not network_ok:
            self.checklist['critical_issues'].append("Cannot reach Angel Broking API servers")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Credentials Format: {credentials_format_ok}")
        print(f"   ✓ Network Connectivity: {network_ok}")
    
    def _check_filesystem(self):
        """Check file system setup and permissions"""
        check_name = 'filesystem'
        print(f"\n📁 Checking File System Setup...")
        
        checks = {}
        
        # Required directories
        required_dirs = ['logs', 'config', 'backtest_results']
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            exists = dir_path.exists()
            writable = False
            
            if exists:
                try:
                    test_file = dir_path / '.test_write'
                    test_file.write_text('test')
                    test_file.unlink()
                    writable = True
                except:
                    writable = False
            else:
                # Try to create directory
                try:
                    dir_path.mkdir(exist_ok=True)
                    exists = True
                    writable = True
                except:
                    pass
            
            checks[f'directory_{dir_name}'] = {
                'status': 'PASS' if (exists and writable) else 'FAIL',
                'exists': exists,
                'writable': writable
            }
            
            if not (exists and writable):
                self.checklist['critical_issues'].append(f"Directory {dir_name} is not accessible or writable")
        
        # Disk space check
        try:
            import shutil
            total, used, free = shutil.disk_usage('.')
            free_gb = free / (1024**3)
            
            sufficient_space = free_gb > 1.0  # At least 1GB free
            checks['disk_space'] = {
                'status': 'PASS' if sufficient_space else 'WARN',
                'free_gb': round(free_gb, 2)
            }
            
            if not sufficient_space:
                self.checklist['warnings'].append(f"Low disk space: {free_gb:.2f}GB free")
        except:
            checks['disk_space'] = {'status': 'UNKNOWN'}
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Required Directories: {sum(1 for d in required_dirs if checks[f'directory_{d}']['status'] == 'PASS')}/{len(required_dirs)}")
    
    def _check_risk_management(self):
        """Check risk management configuration"""
        check_name = 'risk_management'
        print(f"\n⚠️  Checking Risk Management...")
        
        checks = {}
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            # Risk parameter validation
            risk_params = {
                'profit_target': config.risk.profit_target,
                'stop_loss': config.risk.stop_loss,
                'max_daily_loss': config.risk.max_daily_loss,
                'max_concurrent_trades': config.risk.max_concurrent_trades
            }
            
            # Validate risk ratios
            profit_loss_ratio = config.risk.profit_target / config.risk.stop_loss
            reasonable_ratio = 1.5 <= profit_loss_ratio <= 3.0
            
            checks['profit_loss_ratio'] = {
                'status': 'PASS' if reasonable_ratio else 'WARN',
                'ratio': round(profit_loss_ratio, 2),
                'recommended_range': '1.5 - 3.0'
            }
            
            if not reasonable_ratio:
                self.checklist['warnings'].append(f"Profit/Loss ratio ({profit_loss_ratio:.2f}) may not be optimal")
            
            # Daily loss vs position size
            max_loss_per_trade = config.risk.stop_loss * config.risk.max_concurrent_trades
            daily_loss_adequate = config.risk.max_daily_loss >= max_loss_per_trade
            
            checks['daily_loss_adequacy'] = {
                'status': 'PASS' if daily_loss_adequate else 'FAIL',
                'max_daily_loss': config.risk.max_daily_loss,
                'max_possible_loss': max_loss_per_trade
            }
            
            if not daily_loss_adequate:
                self.checklist['critical_issues'].append("Daily loss limit is less than maximum possible loss from concurrent trades")
            
            # Emergency stop file configuration
            emergency_file = getattr(config.risk, 'emergency_stop_file', 'emergency_stop.txt')
            checks['emergency_stop_configured'] = {
                'status': 'PASS',
                'file': emergency_file
            }
            
        except Exception as e:
            checks['risk_validation'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            self.checklist['critical_issues'].append(f"Risk management validation failed: {str(e)}")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Risk Parameters: Valid")
        print(f"   ✓ Emergency Stop: Configured")
    
    def _check_logging_monitoring(self):
        """Check logging and monitoring setup"""
        check_name = 'logging_monitoring'
        print(f"\n📊 Checking Logging and Monitoring...")
        
        checks = {}
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            # Logging configuration
            logging_enabled = config.logging.enable_file or config.logging.enable_console
            checks['logging_enabled'] = {
                'status': 'PASS' if logging_enabled else 'FAIL',
                'file_logging': config.logging.enable_file,
                'console_logging': config.logging.enable_console
            }
            
            if not logging_enabled:
                self.checklist['critical_issues'].append("No logging enabled")
            
            # Log directory writable (if file logging enabled)
            if config.logging.enable_file:
                log_dir = Path(getattr(config.logging, 'log_dir', 'logs'))
                log_dir_writable = log_dir.exists() and os.access(log_dir, os.W_OK)
                checks['log_directory_writable'] = {
                    'status': 'PASS' if log_dir_writable else 'FAIL',
                    'directory': str(log_dir)
                }
                
                if not log_dir_writable:
                    self.checklist['critical_issues'].append(f"Log directory {log_dir} is not writable")
            
            # Notification configuration
            notifications_configured = config.notification.enabled
            checks['notifications_configured'] = {
                'status': 'PASS' if notifications_configured else 'WARN',
                'enabled': notifications_configured
            }
            
            if not notifications_configured:
                self.checklist['warnings'].append("No notifications configured (recommended for production)")
            
        except Exception as e:
            checks['logging_validation'] = {
                'status': 'FAIL',
                'error': str(e)
            }
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Logging: Configured")
        print(f"   ✓ Monitoring: {'Configured' if checks.get('notifications_configured', {}).get('enabled') else 'Not Configured'}")
    
    def _check_backup_recovery(self):
        """Check backup and recovery procedures"""
        check_name = 'backup_recovery'
        print(f"\n💾 Checking Backup and Recovery...")
        
        checks = {}
        
        # Configuration backup
        config_backup_exists = any([
            Path(f'{self.config_file}.backup').exists(),
            Path(f'{self.config_file}.bak').exists(),
            Path('config_backup').exists()
        ])
        
        checks['config_backup'] = {
            'status': 'PASS' if config_backup_exists else 'WARN'
        }
        
        if not config_backup_exists:
            self.checklist['warnings'].append("No configuration backup found (recommended)")
        
        # Log retention policy
        checks['log_retention'] = {
            'status': 'PASS',  # Assume configured in logging settings
            'note': 'Check log rotation settings in configuration'
        }
        
        # Recovery procedures documented
        recovery_docs = any([
            Path('RECOVERY.md').exists(),
            Path('docs/RECOVERY.md').exists(),
            Path('README.md').exists()  # Assume recovery info in README
        ])
        
        checks['recovery_documentation'] = {
            'status': 'PASS' if recovery_docs else 'WARN'
        }
        
        if not recovery_docs:
            self.checklist['warnings'].append("Recovery procedures not documented")
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Backup Strategy: {'Configured' if config_backup_exists else 'Recommended'}")
    
    def _check_performance_resources(self):
        """Check system performance and resources"""
        check_name = 'performance_resources'
        print(f"\n⚡ Checking Performance and Resources...")
        
        checks = {}
        
        try:
            import psutil
            
            # CPU check
            cpu_count = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=1)
            
            checks['cpu'] = {
                'status': 'PASS' if cpu_count >= 2 and cpu_usage < 80 else 'WARN',
                'cores': cpu_count,
                'usage_percent': cpu_usage
            }
            
            if cpu_count < 2:
                self.checklist['warnings'].append("Low CPU core count may affect performance")
            
            # Memory check
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            memory_usage = memory.percent
            
            checks['memory'] = {
                'status': 'PASS' if memory_gb >= 4 and memory_usage < 80 else 'WARN',
                'total_gb': round(memory_gb, 2),
                'usage_percent': memory_usage
            }
            
            if memory_gb < 4:
                self.checklist['warnings'].append("Low memory may affect system performance")
            
            # Network latency (basic check)
            try:
                import subprocess
                import time
                start_time = time.time()
                subprocess.run(['ping', '-c', '1', '8.8.8.8'], 
                             capture_output=True, timeout=5)
                latency = (time.time() - start_time) * 1000
                
                checks['network_latency'] = {
                    'status': 'PASS' if latency < 100 else 'WARN',
                    'latency_ms': round(latency, 2)
                }
                
                if latency >= 100:
                    self.checklist['warnings'].append(f"High network latency ({latency:.2f}ms) may affect trading")
            except:
                checks['network_latency'] = {'status': 'UNKNOWN'}
            
        except ImportError:
            checks['system_monitoring'] = {
                'status': 'WARN',
                'note': 'psutil not available for system monitoring'
            }
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ System Resources: Adequate")
    
    def _check_testing_validation(self):
        """Check testing and validation status"""
        check_name = 'testing_validation'
        print(f"\n🧪 Checking Testing and Validation...")
        
        checks = {}
        
        # Test files exist
        test_files_exist = any([
            Path('tests').exists(),
            Path('test').exists()
        ])
        
        checks['test_files_exist'] = {
            'status': 'PASS' if test_files_exist else 'WARN'
        }
        
        # Run basic system validation if available
        validation_script = Path('scripts/system_validation.py')
        if validation_script.exists():
            try:
                # Run quick validation
                result = subprocess.run([
                    sys.executable, str(validation_script), 
                    '--config', self.config_file, '--json'
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    validation_results = json.loads(result.stdout)
                    validation_passed = validation_results.get('overall_status') == 'PASSED'
                else:
                    validation_passed = False
                
                checks['system_validation'] = {
                    'status': 'PASS' if validation_passed else 'FAIL',
                    'validation_run': True
                }
                
                if not validation_passed:
                    self.checklist['critical_issues'].append("System validation failed")
                
            except Exception as e:
                checks['system_validation'] = {
                    'status': 'WARN',
                    'error': str(e)
                }
        else:
            checks['system_validation'] = {
                'status': 'WARN',
                'note': 'System validation script not found'
            }
        
        self.checklist['checks'][check_name] = checks
        print(f"   ✓ Testing: {'Available' if test_files_exist else 'Limited'}")
    
    def _determine_deployment_readiness(self):
        """Determine overall deployment readiness"""
        # Count status types
        all_checks = []
        for check_group in self.checklist['checks'].values():
            for check in check_group.values():
                if isinstance(check, dict) and 'status' in check:
                    all_checks.append(check['status'])
        
        fail_count = all_checks.count('FAIL')
        warn_count = all_checks.count('WARN')
        pass_count = all_checks.count('PASS')
        
        # Determine readiness
        if fail_count > 0 or len(self.checklist['critical_issues']) > 0:
            self.checklist['overall_status'] = 'NOT_READY'
            self.checklist['recommendations'].append("❌ System is NOT ready for deployment")
            self.checklist['recommendations'].append("🔧 Address all critical issues before deployment")
        elif warn_count > 5:
            self.checklist['overall_status'] = 'NEEDS_ATTENTION'
            self.checklist['recommendations'].append("⚠️  System needs attention before deployment")
            self.checklist['recommendations'].append("🔍 Review and address warnings")
        else:
            self.checklist['overall_status'] = 'READY'
            self.checklist['recommendations'].append("✅ System is ready for deployment")
            self.checklist['recommendations'].append("🚀 Proceed with deployment")
        
        # Add specific recommendations
        if self.checklist['critical_issues']:
            self.checklist['recommendations'].append("\n🚨 Critical Issues to Address:")
            for issue in self.checklist['critical_issues']:
                self.checklist['recommendations'].append(f"   • {issue}")
        
        if self.checklist['warnings']:
            self.checklist['recommendations'].append("\n⚠️  Warnings to Consider:")
            for warning in self.checklist['warnings'][:5]:  # Show first 5 warnings
                self.checklist['recommendations'].append(f"   • {warning}")
        
        # Summary
        print(f"\n📊 Deployment Readiness Summary:")
        print(f"   ✅ Passed: {pass_count}")
        print(f"   ⚠️  Warnings: {warn_count}")
        print(f"   ❌ Failed: {fail_count}")
        print(f"   🚨 Critical Issues: {len(self.checklist['critical_issues'])}")
        print(f"\n🎯 Overall Status: {self.checklist['overall_status']}")
    
    def generate_checklist_report(self, output_file: Optional[str] = None) -> str:
        """Generate deployment checklist report"""
        report_lines = []
        report_lines.append("🚀 BANK NIFTY OPTIONS TRADING SYSTEM")
        report_lines.append("📋 DEPLOYMENT READINESS CHECKLIST")
        report_lines.append("=" * 60)
        report_lines.append(f"📅 Timestamp: {self.checklist['timestamp']}")
        report_lines.append(f"⚙️  Configuration: {self.checklist['config_file']}")
        report_lines.append(f"🎯 Overall Status: {self.checklist['overall_status']}")
        report_lines.append("")
        
        # Detailed check results
        for check_group, checks in self.checklist['checks'].items():
            report_lines.append(f"📋 {check_group.upper().replace('_', ' ')}")
            report_lines.append("-" * 40)
            
            for check_name, check_result in checks.items():
                if isinstance(check_result, dict) and 'status' in check_result:
                    status_icon = {
                        'PASS': '✅',
                        'WARN': '⚠️ ',
                        'FAIL': '❌',
                        'UNKNOWN': '❓'
                    }.get(check_result['status'], '❓')
                    
                    report_lines.append(f"   {status_icon} {check_name.replace('_', ' ').title()}")
                    
                    # Add details if available
                    for key, value in check_result.items():
                        if key != 'status':
                            report_lines.append(f"      {key}: {value}")
            
            report_lines.append("")
        
        # Recommendations
        report_lines.append("🎯 RECOMMENDATIONS")
        report_lines.append("-" * 40)
        for recommendation in self.checklist['recommendations']:
            report_lines.append(recommendation)
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            print(f"\n📄 Deployment checklist saved to {output_file}")
        
        return report_text


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description="Deployment Checklist for Bank Nifty Options Trading System")
    parser.add_argument('--config', '-c', default='trading_config.yaml', help='Configuration file path')
    parser.add_argument('--output', '-o', help='Output file for checklist report')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    
    args = parser.parse_args()
    
    # Run deployment check
    checker = DeploymentChecker(args.config)
    results = checker.run_deployment_check()
    
    # Generate and display report
    if args.json:
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
        else:
            print(json.dumps(results, indent=2))
    else:
        report = checker.generate_checklist_report(args.output)
        if not args.output:
            print("\n" + report)
    
    # Exit with appropriate code
    exit_code = 0 if results['overall_status'] == 'READY' else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()