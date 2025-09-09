#!/usr/bin/env python3
"""
Performance Testing Script for Bank Nifty Options Trading System

This script conducts comprehensive performance testing including:
- System initialization performance
- Trading cycle execution time
- Memory usage monitoring
- API response time testing
- Concurrent operation testing
"""

import sys
import os
import time
import json
import threading
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import argparse
import psutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.config_manager import ConfigManager
from trading.trading_manager import TradingManager


class PerformanceTester:
    """Comprehensive performance testing suite"""
    
    def __init__(self, config_file: str = 'trading_config.yaml'):
        self.config_file = config_file
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'config_file': config_file,
            'system_info': self._get_system_info(),
            'tests': {},
            'summary': {}
        }
        
        # Performance thresholds
        self.thresholds = {
            'initialization_time': 30.0,  # seconds
            'trading_cycle_time': 10.0,   # seconds
            'memory_usage_mb': 500.0,     # MB
            'api_response_time': 5.0,     # seconds
            'cpu_usage_percent': 80.0     # percent
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'platform': sys.platform
            }
        except:
            return {'error': 'Could not retrieve system info'}
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        print("⚡ Bank Nifty Options Trading System - Performance Testing")
        print("=" * 60)
        
        # 1. Initialization Performance Test
        self._test_initialization_performance()
        
        # 2. Trading Cycle Performance Test
        self._test_trading_cycle_performance()
        
        # 3. Memory Usage Test
        self._test_memory_usage()
        
        # 4. API Performance Test
        self._test_api_performance()
        
        # 5. Concurrent Operations Test
        self._test_concurrent_operations()
        
        # 6. Stress Test
        self._test_system_stress()
        
        # 7. Resource Monitoring Test
        self._test_resource_monitoring()
        
        # Generate summary
        self._generate_performance_summary()
        
        return self.results
    
    def _test_initialization_performance(self):
        """Test system initialization performance"""
        test_name = 'initialization_performance'
        print(f"\n🚀 Testing Initialization Performance...")
        
        try:
            # Load configuration
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            # Test multiple initialization cycles
            init_times = []
            
            for i in range(5):
                start_time = time.time()
                
                # Initialize trading manager
                trading_manager = TradingManager(config, 'paper')
                success = trading_manager.initialize()
                
                end_time = time.time()
                init_time = end_time - start_time
                
                if success:
                    init_times.append(init_time)
                
                # Cleanup
                try:
                    trading_manager.cleanup()
                except:
                    pass
                
                print(f"   Initialization {i+1}: {init_time:.2f}s")
            
            if init_times:
                avg_init_time = statistics.mean(init_times)
                min_init_time = min(init_times)
                max_init_time = max(init_times)
                
                performance_ok = avg_init_time <= self.thresholds['initialization_time']
                
                self.results['tests'][test_name] = {
                    'status': 'PASS' if performance_ok else 'FAIL',
                    'average_time': round(avg_init_time, 2),
                    'min_time': round(min_init_time, 2),
                    'max_time': round(max_init_time, 2),
                    'threshold': self.thresholds['initialization_time'],
                    'samples': len(init_times)
                }
                
                print(f"   Average: {avg_init_time:.2f}s (Threshold: {self.thresholds['initialization_time']}s)")
            else:
                self.results['tests'][test_name] = {
                    'status': 'FAIL',
                    'error': 'No successful initializations'
                }
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_trading_cycle_performance(self):
        """Test trading cycle execution performance"""
        test_name = 'trading_cycle_performance'
        print(f"\n🔄 Testing Trading Cycle Performance...")
        
        try:
            # Initialize system
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            trading_manager = TradingManager(config, 'paper')
            
            if not trading_manager.initialize():
                self.results['tests'][test_name] = {
                    'status': 'ERROR',
                    'error': 'Failed to initialize trading manager'
                }
                return
            
            # Test multiple trading cycles
            cycle_times = []
            
            for i in range(10):
                start_time = time.time()
                
                try:
                    result = trading_manager.process_trading_cycle()
                    end_time = time.time()
                    cycle_time = end_time - start_time
                    
                    if result is not None:
                        cycle_times.append(cycle_time)
                    
                    print(f"   Cycle {i+1}: {cycle_time:.2f}s")
                
                except Exception as e:
                    print(f"   Cycle {i+1}: ERROR - {e}")
            
            # Cleanup
            trading_manager.cleanup()
            
            if cycle_times:
                avg_cycle_time = statistics.mean(cycle_times)
                min_cycle_time = min(cycle_times)
                max_cycle_time = max(cycle_times)
                
                performance_ok = avg_cycle_time <= self.thresholds['trading_cycle_time']
                
                self.results['tests'][test_name] = {
                    'status': 'PASS' if performance_ok else 'FAIL',
                    'average_time': round(avg_cycle_time, 2),
                    'min_time': round(min_cycle_time, 2),
                    'max_time': round(max_cycle_time, 2),
                    'threshold': self.thresholds['trading_cycle_time'],
                    'samples': len(cycle_times)
                }
                
                print(f"   Average: {avg_cycle_time:.2f}s (Threshold: {self.thresholds['trading_cycle_time']}s)")
            else:
                self.results['tests'][test_name] = {
                    'status': 'FAIL',
                    'error': 'No successful trading cycles'
                }
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_memory_usage(self):
        """Test memory usage during operations"""
        test_name = 'memory_usage'
        print(f"\n💾 Testing Memory Usage...")
        
        try:
            process = psutil.Process()
            
            # Baseline memory
            baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            # Initialize system and monitor memory
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            trading_manager = TradingManager(config, 'paper')
            
            init_memory = process.memory_info().rss / (1024 * 1024)
            
            if trading_manager.initialize():
                post_init_memory = process.memory_info().rss / (1024 * 1024)
                
                # Run multiple cycles and monitor memory
                memory_samples = []
                
                for i in range(20):
                    try:
                        trading_manager.process_trading_cycle()
                        current_memory = process.memory_info().rss / (1024 * 1024)
                        memory_samples.append(current_memory)
                    except:
                        pass
                
                # Cleanup
                trading_manager.cleanup()
                final_memory = process.memory_info().rss / (1024 * 1024)
                
                if memory_samples:
                    max_memory = max(memory_samples)
                    avg_memory = statistics.mean(memory_samples)
                    memory_increase = max_memory - baseline_memory
                    
                    memory_ok = memory_increase <= self.thresholds['memory_usage_mb']
                    
                    self.results['tests'][test_name] = {
                        'status': 'PASS' if memory_ok else 'FAIL',
                        'baseline_mb': round(baseline_memory, 2),
                        'max_usage_mb': round(max_memory, 2),
                        'avg_usage_mb': round(avg_memory, 2),
                        'memory_increase_mb': round(memory_increase, 2),
                        'threshold_mb': self.thresholds['memory_usage_mb']
                    }
                    
                    print(f"   Baseline: {baseline_memory:.2f}MB")
                    print(f"   Maximum: {max_memory:.2f}MB")
                    print(f"   Increase: {memory_increase:.2f}MB (Threshold: {self.thresholds['memory_usage_mb']}MB)")
                else:
                    self.results['tests'][test_name] = {
                        'status': 'FAIL',
                        'error': 'No memory samples collected'
                    }
            else:
                self.results['tests'][test_name] = {
                    'status': 'ERROR',
                    'error': 'Failed to initialize system for memory test'
                }
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_api_performance(self):
        """Test API performance and response times"""
        test_name = 'api_performance'
        print(f"\n🌐 Testing API Performance...")
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            from api.angel_api_client import AngelAPIClient
            
            api_client = AngelAPIClient(config.api)
            
            if api_client.initialize():
                # Test API response times
                api_times = []
                
                for i in range(5):
                    start_time = time.time()
                    
                    try:
                        # Test basic API call
                        result = api_client.search_instruments("NSE", "BANKNIFTY")
                        end_time = time.time()
                        api_time = end_time - start_time
                        
                        if result is not None:
                            api_times.append(api_time)
                        
                        print(f"   API Call {i+1}: {api_time:.2f}s")
                    
                    except Exception as e:
                        print(f"   API Call {i+1}: ERROR - {e}")
                
                if api_times:
                    avg_api_time = statistics.mean(api_times)
                    max_api_time = max(api_times)
                    
                    api_performance_ok = avg_api_time <= self.thresholds['api_response_time']
                    
                    self.results['tests'][test_name] = {
                        'status': 'PASS' if api_performance_ok else 'FAIL',
                        'average_time': round(avg_api_time, 2),
                        'max_time': round(max_api_time, 2),
                        'threshold': self.thresholds['api_response_time'],
                        'samples': len(api_times)
                    }
                    
                    print(f"   Average: {avg_api_time:.2f}s (Threshold: {self.thresholds['api_response_time']}s)")
                else:
                    self.results['tests'][test_name] = {
                        'status': 'FAIL',
                        'error': 'No successful API calls'
                    }
            else:
                self.results['tests'][test_name] = {
                    'status': 'ERROR',
                    'error': 'Failed to initialize API client'
                }
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_concurrent_operations(self):
        """Test concurrent operations performance"""
        test_name = 'concurrent_operations'
        print(f"\n🔀 Testing Concurrent Operations...")
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            
            # Test concurrent trading managers
            results = []
            threads = []
            
            def run_trading_cycle(manager_id):
                try:
                    trading_manager = TradingManager(config, 'paper')
                    if trading_manager.initialize():
                        start_time = time.time()
                        trading_manager.process_trading_cycle()
                        end_time = time.time()
                        
                        results.append({
                            'manager_id': manager_id,
                            'success': True,
                            'time': end_time - start_time
                        })
                        
                        trading_manager.cleanup()
                    else:
                        results.append({
                            'manager_id': manager_id,
                            'success': False,
                            'error': 'Initialization failed'
                        })
                except Exception as e:
                    results.append({
                        'manager_id': manager_id,
                        'success': False,
                        'error': str(e)
                    })
            
            # Start concurrent threads
            num_threads = 3
            start_time = time.time()
            
            for i in range(num_threads):
                thread = threading.Thread(target=run_trading_cycle, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=60)  # 60 second timeout
            
            end_time = time.time()
            total_time = end_time - start_time
            
            successful_results = [r for r in results if r['success']]
            
            if successful_results:
                avg_concurrent_time = statistics.mean([r['time'] for r in successful_results])
                
                concurrent_performance_ok = len(successful_results) >= num_threads * 0.8  # 80% success rate
                
                self.results['tests'][test_name] = {
                    'status': 'PASS' if concurrent_performance_ok else 'FAIL',
                    'total_time': round(total_time, 2),
                    'avg_operation_time': round(avg_concurrent_time, 2),
                    'successful_operations': len(successful_results),
                    'total_operations': num_threads,
                    'success_rate': round(len(successful_results) / num_threads, 2)
                }
                
                print(f"   Successful: {len(successful_results)}/{num_threads}")
                print(f"   Total Time: {total_time:.2f}s")
                print(f"   Avg Operation: {avg_concurrent_time:.2f}s")
            else:
                self.results['tests'][test_name] = {
                    'status': 'FAIL',
                    'error': 'No successful concurrent operations'
                }
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_system_stress(self):
        """Test system under stress conditions"""
        test_name = 'system_stress'
        print(f"\n🔥 Testing System Stress...")
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(self.config_file)
            trading_manager = TradingManager(config, 'paper')
            
            if not trading_manager.initialize():
                self.results['tests'][test_name] = {
                    'status': 'ERROR',
                    'error': 'Failed to initialize for stress test'
                }
                return
            
            # Monitor system resources during stress test
            process = psutil.Process()
            
            start_memory = process.memory_info().rss / (1024 * 1024)
            start_cpu = process.cpu_percent()
            
            # Run intensive operations
            operations_completed = 0
            errors = 0
            
            start_time = time.time()
            
            for i in range(50):  # 50 intensive cycles
                try:
                    trading_manager.process_trading_cycle()
                    operations_completed += 1
                except Exception as e:
                    errors += 1
                
                # Brief pause to allow CPU measurement
                time.sleep(0.1)
            
            end_time = time.time()
            
            end_memory = process.memory_info().rss / (1024 * 1024)
            end_cpu = process.cpu_percent()
            
            total_time = end_time - start_time
            memory_increase = end_memory - start_memory
            
            # Cleanup
            trading_manager.cleanup()
            
            # Evaluate stress test results
            success_rate = operations_completed / 50
            memory_ok = memory_increase < self.thresholds['memory_usage_mb']
            
            stress_test_ok = success_rate >= 0.8 and memory_ok
            
            self.results['tests'][test_name] = {
                'status': 'PASS' if stress_test_ok else 'FAIL',
                'operations_completed': operations_completed,
                'total_operations': 50,
                'success_rate': round(success_rate, 2),
                'errors': errors,
                'total_time': round(total_time, 2),
                'memory_increase_mb': round(memory_increase, 2),
                'avg_cpu_percent': round((start_cpu + end_cpu) / 2, 2)
            }
            
            print(f"   Operations: {operations_completed}/50")
            print(f"   Success Rate: {success_rate:.2%}")
            print(f"   Memory Increase: {memory_increase:.2f}MB")
            print(f"   Total Time: {total_time:.2f}s")
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _test_resource_monitoring(self):
        """Test resource monitoring capabilities"""
        test_name = 'resource_monitoring'
        print(f"\n📊 Testing Resource Monitoring...")
        
        try:
            # Test system resource monitoring
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('.')
            
            # Network test (if available)
            network_ok = True
            try:
                import requests
                start_time = time.time()
                response = requests.get('https://httpbin.org/delay/1', timeout=10)
                network_latency = (time.time() - start_time) * 1000
            except:
                network_ok = False
                network_latency = None
            
            resource_health = {
                'cpu_ok': cpu_usage < self.thresholds['cpu_usage_percent'],
                'memory_ok': memory_info.percent < 90,
                'disk_ok': disk_info.free > 1024**3,  # 1GB free
                'network_ok': network_ok
            }
            
            overall_health = all(resource_health.values())
            
            self.results['tests'][test_name] = {
                'status': 'PASS' if overall_health else 'WARN',
                'cpu_usage_percent': round(cpu_usage, 2),
                'memory_usage_percent': round(memory_info.percent, 2),
                'disk_free_gb': round(disk_info.free / (1024**3), 2),
                'network_latency_ms': round(network_latency, 2) if network_latency else None,
                'resource_health': resource_health
            }
            
            print(f"   CPU Usage: {cpu_usage:.1f}%")
            print(f"   Memory Usage: {memory_info.percent:.1f}%")
            print(f"   Disk Free: {disk_info.free / (1024**3):.2f}GB")
            if network_latency:
                print(f"   Network Latency: {network_latency:.2f}ms")
        
        except Exception as e:
            self.results['tests'][test_name] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def _generate_performance_summary(self):
        """Generate performance test summary"""
        test_statuses = []
        for test_result in self.results['tests'].values():
            test_statuses.append(test_result.get('status', 'UNKNOWN'))
        
        pass_count = test_statuses.count('PASS')
        fail_count = test_statuses.count('FAIL')
        warn_count = test_statuses.count('WARN')
        error_count = test_statuses.count('ERROR')
        
        # Overall performance rating
        if error_count > 0 or fail_count > 2:
            overall_rating = 'POOR'
        elif fail_count > 0 or warn_count > 2:
            overall_rating = 'FAIR'
        elif warn_count > 0:
            overall_rating = 'GOOD'
        else:
            overall_rating = 'EXCELLENT'
        
        self.results['summary'] = {
            'overall_rating': overall_rating,
            'tests_passed': pass_count,
            'tests_failed': fail_count,
            'tests_warned': warn_count,
            'tests_errored': error_count,
            'total_tests': len(test_statuses)
        }
        
        print(f"\n📊 Performance Test Summary:")
        print(f"   ✅ Passed: {pass_count}")
        print(f"   ❌ Failed: {fail_count}")
        print(f"   ⚠️  Warnings: {warn_count}")
        print(f"   🚨 Errors: {error_count}")
        print(f"   🎯 Overall Rating: {overall_rating}")
    
    def generate_performance_report(self, output_file: Optional[str] = None) -> str:
        """Generate performance test report"""
        report_lines = []
        report_lines.append("⚡ BANK NIFTY OPTIONS TRADING SYSTEM")
        report_lines.append("📊 PERFORMANCE TEST REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"📅 Timestamp: {self.results['timestamp']}")
        report_lines.append(f"⚙️  Configuration: {self.results['config_file']}")
        report_lines.append("")
        
        # System Information
        report_lines.append("💻 SYSTEM INFORMATION")
        report_lines.append("-" * 30)
        for key, value in self.results['system_info'].items():
            report_lines.append(f"   {key}: {value}")
        report_lines.append("")
        
        # Test Results
        report_lines.append("🧪 TEST RESULTS")
        report_lines.append("-" * 30)
        
        for test_name, test_result in self.results['tests'].items():
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌',
                'WARN': '⚠️ ',
                'ERROR': '🚨'
            }.get(test_result['status'], '❓')
            
            report_lines.append(f"{status_icon} {test_name.upper().replace('_', ' ')}")
            
            for key, value in test_result.items():
                if key != 'status':
                    report_lines.append(f"   {key}: {value}")
            
            report_lines.append("")
        
        # Summary
        summary = self.results['summary']
        report_lines.append("📊 SUMMARY")
        report_lines.append("-" * 30)
        report_lines.append(f"🎯 Overall Rating: {summary['overall_rating']}")
        report_lines.append(f"✅ Tests Passed: {summary['tests_passed']}")
        report_lines.append(f"❌ Tests Failed: {summary['tests_failed']}")
        report_lines.append(f"⚠️  Warnings: {summary['tests_warned']}")
        report_lines.append(f"🚨 Errors: {summary['tests_errored']}")
        report_lines.append("")
        
        # Recommendations
        report_lines.append("💡 RECOMMENDATIONS")
        report_lines.append("-" * 30)
        
        if summary['overall_rating'] == 'EXCELLENT':
            report_lines.append("🎉 System performance is excellent!")
            report_lines.append("✅ Ready for production deployment")
        elif summary['overall_rating'] == 'GOOD':
            report_lines.append("👍 System performance is good")
            report_lines.append("⚠️  Monitor warnings and optimize if needed")
        elif summary['overall_rating'] == 'FAIR':
            report_lines.append("⚠️  System performance needs improvement")
            report_lines.append("🔧 Address failed tests before production")
        else:
            report_lines.append("🚨 System performance is poor")
            report_lines.append("❌ Not recommended for production")
            report_lines.append("🔧 Significant optimization required")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            print(f"\n📄 Performance report saved to {output_file}")
        
        return report_text


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description="Performance Testing for Bank Nifty Options Trading System")
    parser.add_argument('--config', '-c', default='trading_config.yaml', help='Configuration file path')
    parser.add_argument('--output', '-o', help='Output file for performance report')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    
    args = parser.parse_args()
    
    # Run performance tests
    tester = PerformanceTester(args.config)
    results = tester.run_performance_tests()
    
    # Generate and display report
    if args.json:
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
        else:
            print(json.dumps(results, indent=2))
    else:
        report = tester.generate_performance_report(args.output)
        if not args.output:
            print("\n" + report)
    
    # Exit with appropriate code based on performance
    overall_rating = results['summary']['overall_rating']
    exit_code = 0 if overall_rating in ['EXCELLENT', 'GOOD'] else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()