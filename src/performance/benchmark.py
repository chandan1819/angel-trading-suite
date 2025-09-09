"""
Performance benchmark script to validate latency requirements.
"""

import time
import logging
import statistics
from typing import Dict, List, Callable, Any
from datetime import datetime
import json

from .performance_monitor import PerformanceMonitor, LatencyRequirement
from .cache_manager import CacheManager, CacheConfig
from .concurrent_processor import ConcurrentProcessor
from ..data.data_manager import DataManager
from ..api.angel_api_client import AngelAPIClient

logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """
    Performance benchmark suite for trading system components.
    """
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.results = {}
        
        # Define latency requirements from design document
        self.requirements = {
            'options_chain_processing': 2000,  # 2 seconds
            'strategy_evaluation': 5000,       # 5 seconds
            'order_placement': 3000,           # 3 seconds
            'position_monitoring': 30000,      # 30 seconds
            'atm_calculation': 1000,           # 1 second
            'api_call': 5000                   # 5 seconds
        }
    
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks."""
        logger.info("Starting performance benchmark suite")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'benchmarks': {},
            'summary': {},
            'violations': []
        }
        
        # Run individual benchmarks
        results['benchmarks']['cache_performance'] = self.benchmark_cache_performance()
        results['benchmarks']['concurrent_processing'] = self.benchmark_concurrent_processing()
        results['benchmarks']['data_processing'] = self.benchmark_data_processing()
        results['benchmarks']['memory_usage'] = self.benchmark_memory_usage()
        
        # Generate summary
        results['summary'] = self._generate_summary(results['benchmarks'])
        results['violations'] = self._check_violations()
        
        logger.info("Performance benchmark suite completed")
        return results
    
    def benchmark_cache_performance(self) -> Dict[str, Any]:
        """Benchmark cache performance."""
        logger.info("Benchmarking cache performance")
        
        cache_manager = CacheManager(CacheConfig(max_size=1000, default_ttl=300))
        
        # Test cache write performance
        write_times = []
        for i in range(1000):
            start_time = time.time()
            cache_manager.set(f"key_{i}", f"value_{i}")
            write_times.append((time.time() - start_time) * 1000)  # Convert to ms
        
        # Test cache read performance
        read_times = []
        for i in range(1000):
            start_time = time.time()
            cache_manager.get(f"key_{i}")
            read_times.append((time.time() - start_time) * 1000)  # Convert to ms
        
        # Test cache hit rate
        hit_count = 0
        for i in range(1000):
            if cache_manager.get(f"key_{i}") is not None:
                hit_count += 1
        
        hit_rate = (hit_count / 1000) * 100
        
        return {
            'write_performance': {
                'avg_time_ms': statistics.mean(write_times),
                'median_time_ms': statistics.median(write_times),
                'p95_time_ms': self._percentile(write_times, 95),
                'max_time_ms': max(write_times)
            },
            'read_performance': {
                'avg_time_ms': statistics.mean(read_times),
                'median_time_ms': statistics.median(read_times),
                'p95_time_ms': self._percentile(read_times, 95),
                'max_time_ms': max(read_times)
            },
            'hit_rate_percent': hit_rate,
            'cache_stats': cache_manager.get_stats()
        }
    
    def benchmark_concurrent_processing(self) -> Dict[str, Any]:
        """Benchmark concurrent processing performance."""
        logger.info("Benchmarking concurrent processing")
        
        processor = ConcurrentProcessor(max_workers=4)
        
        def test_task(task_id: int, duration: float = 0.1):
            """Test task that simulates work."""
            time.sleep(duration)
            return f"Task {task_id} completed"
        
        # Test sequential vs concurrent execution
        num_tasks = 20
        task_duration = 0.05  # 50ms per task
        
        # Sequential execution time (baseline)
        sequential_start = time.time()
        for i in range(num_tasks):
            test_task(i, task_duration)
        sequential_time = time.time() - sequential_start
        
        # Concurrent execution time
        concurrent_start = time.time()
        
        task_ids = []
        for i in range(num_tasks):
            from ..performance.concurrent_processor import ProcessingTask
            task = ProcessingTask(
                task_id=f"benchmark_task_{i}",
                operation=test_task,
                args=(i, task_duration),
                timeout=5.0
            )
            processor.submit_task(task)
            task_ids.append(task.task_id)
        
        # Wait for all tasks to complete
        results = processor.wait_for_results(task_ids, timeout=10.0)
        concurrent_time = time.time() - concurrent_start
        
        # Calculate speedup
        speedup = sequential_time / concurrent_time if concurrent_time > 0 else 0
        
        processor.shutdown(wait=True)
        
        return {
            'sequential_time_s': sequential_time,
            'concurrent_time_s': concurrent_time,
            'speedup_factor': speedup,
            'tasks_completed': len(results),
            'success_rate': len([r for r in results.values() if r.success]) / len(results) * 100,
            'avg_task_time_ms': statistics.mean([r.execution_time * 1000 for r in results.values()])
        }
    
    def benchmark_data_processing(self) -> Dict[str, Any]:
        """Benchmark data processing operations."""
        logger.info("Benchmarking data processing")
        
        # Simulate options chain data
        options_chain_data = self._generate_mock_options_chain(100)  # 100 strikes
        
        # Benchmark options chain processing
        processing_times = []
        for _ in range(10):  # Run 10 iterations
            start_time = time.time()
            self._process_options_chain_mock(options_chain_data)
            processing_times.append((time.time() - start_time) * 1000)  # Convert to ms
        
        # Benchmark ATM calculation
        atm_times = []
        strikes = list(range(44000, 46000, 100))  # 20 strikes
        spot_price = 45000
        
        for _ in range(100):  # Run 100 iterations
            start_time = time.time()
            self._calculate_atm_mock(spot_price, strikes)
            atm_times.append((time.time() - start_time) * 1000)  # Convert to ms
        
        return {
            'options_chain_processing': {
                'avg_time_ms': statistics.mean(processing_times),
                'median_time_ms': statistics.median(processing_times),
                'p95_time_ms': self._percentile(processing_times, 95),
                'max_time_ms': max(processing_times),
                'meets_requirement': max(processing_times) < self.requirements['options_chain_processing']
            },
            'atm_calculation': {
                'avg_time_ms': statistics.mean(atm_times),
                'median_time_ms': statistics.median(atm_times),
                'p95_time_ms': self._percentile(atm_times, 95),
                'max_time_ms': max(atm_times),
                'meets_requirement': max(atm_times) < self.requirements['atm_calculation']
            }
        }
    
    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage patterns."""
        logger.info("Benchmarking memory usage")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test cache memory usage
        cache_manager = CacheManager(CacheConfig(max_size=10000))
        
        # Fill cache with data
        for i in range(5000):
            large_data = "x" * 1000  # 1KB per entry
            cache_manager.set(f"large_key_{i}", large_data)
        
        cache_memory = process.memory_info().rss / 1024 / 1024  # MB
        cache_overhead = cache_memory - baseline_memory
        
        # Test concurrent processor memory
        processor = ConcurrentProcessor(max_workers=8)
        
        processor_memory = process.memory_info().rss / 1024 / 1024  # MB
        processor_overhead = processor_memory - cache_memory
        
        processor.shutdown(wait=True)
        
        return {
            'baseline_memory_mb': baseline_memory,
            'cache_memory_mb': cache_memory,
            'cache_overhead_mb': cache_overhead,
            'processor_memory_mb': processor_memory,
            'processor_overhead_mb': processor_overhead,
            'total_memory_mb': processor_memory
        }
    
    def _generate_mock_options_chain(self, num_strikes: int) -> Dict[str, Any]:
        """Generate mock options chain data for benchmarking."""
        strikes = []
        base_strike = 45000
        
        for i in range(num_strikes):
            strike = base_strike + (i - num_strikes // 2) * 100
            strikes.append({
                'strike': strike,
                'call': {
                    'ltp': max(1, base_strike - strike + 100),
                    'volume': 1000 + i * 10,
                    'oi': 5000 + i * 50,
                    'bid': 0.5,
                    'ask': 1.5
                },
                'put': {
                    'ltp': max(1, strike - base_strike + 100),
                    'volume': 800 + i * 8,
                    'oi': 4000 + i * 40,
                    'bid': 0.5,
                    'ask': 1.5
                }
            })
        
        return {
            'underlying_symbol': 'BANKNIFTY',
            'underlying_price': base_strike,
            'expiry_date': '2024-01-25',
            'strikes': strikes
        }
    
    def _process_options_chain_mock(self, options_chain: Dict[str, Any]) -> Dict[str, Any]:
        """Mock options chain processing for benchmarking."""
        strikes = options_chain['strikes']
        
        # Simulate processing operations
        call_volumes = [s['call']['volume'] for s in strikes]
        put_volumes = [s['put']['volume'] for s in strikes]
        call_oi = [s['call']['oi'] for s in strikes]
        put_oi = [s['put']['oi'] for s in strikes]
        
        return {
            'total_call_volume': sum(call_volumes),
            'total_put_volume': sum(put_volumes),
            'total_call_oi': sum(call_oi),
            'total_put_oi': sum(put_oi),
            'pcr_volume': sum(put_volumes) / max(1, sum(call_volumes)),
            'pcr_oi': sum(put_oi) / max(1, sum(call_oi))
        }
    
    def _calculate_atm_mock(self, spot_price: float, strikes: List[float]) -> float:
        """Mock ATM calculation for benchmarking."""
        min_distance = float('inf')
        atm_strike = strikes[0]
        
        for strike in strikes:
            distance = abs(strike - spot_price)
            if distance < min_distance:
                min_distance = distance
                atm_strike = strike
        
        return atm_strike
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int(percentile / 100 * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _generate_summary(self, benchmarks: Dict[str, Any]) -> Dict[str, Any]:
        """Generate benchmark summary."""
        summary = {
            'total_benchmarks': len(benchmarks),
            'performance_score': 0,
            'recommendations': []
        }
        
        # Calculate performance score based on requirements
        score_components = []
        
        # Cache performance (weight: 20%)
        cache_perf = benchmarks.get('cache_performance', {})
        if cache_perf:
            read_time = cache_perf.get('read_performance', {}).get('avg_time_ms', 0)
            cache_score = max(0, 100 - read_time * 10)  # Penalty for slow reads
            score_components.append(('cache', cache_score, 0.2))
        
        # Concurrent processing (weight: 30%)
        concurrent_perf = benchmarks.get('concurrent_processing', {})
        if concurrent_perf:
            speedup = concurrent_perf.get('speedup_factor', 1)
            concurrent_score = min(100, speedup * 25)  # Reward for good speedup
            score_components.append(('concurrent', concurrent_score, 0.3))
        
        # Data processing (weight: 40%)
        data_perf = benchmarks.get('data_processing', {})
        if data_perf:
            atm_meets_req = data_perf.get('atm_calculation', {}).get('meets_requirement', False)
            chain_meets_req = data_perf.get('options_chain_processing', {}).get('meets_requirement', False)
            data_score = (atm_meets_req + chain_meets_req) * 50  # 50 points each
            score_components.append(('data', data_score, 0.4))
        
        # Memory usage (weight: 10%)
        memory_perf = benchmarks.get('memory_usage', {})
        if memory_perf:
            total_memory = memory_perf.get('total_memory_mb', 0)
            memory_score = max(0, 100 - (total_memory - 100) * 2)  # Penalty for high memory
            score_components.append(('memory', memory_score, 0.1))
        
        # Calculate weighted score
        if score_components:
            weighted_score = sum(score * weight for _, score, weight in score_components)
            summary['performance_score'] = round(weighted_score, 2)
        
        # Generate recommendations
        if cache_perf and cache_perf.get('hit_rate_percent', 0) < 80:
            summary['recommendations'].append("Consider increasing cache TTL or size to improve hit rate")
        
        if concurrent_perf and concurrent_perf.get('speedup_factor', 0) < 2:
            summary['recommendations'].append("Concurrent processing speedup is low, check for bottlenecks")
        
        if memory_perf and memory_perf.get('total_memory_mb', 0) > 500:
            summary['recommendations'].append("High memory usage detected, consider optimization")
        
        return summary
    
    def _check_violations(self) -> List[Dict[str, Any]]:
        """Check for latency requirement violations."""
        violations = []
        
        # Get performance metrics
        metrics = self.performance_monitor.get_all_metrics()
        
        for operation, requirement_ms in self.requirements.items():
            if operation in metrics:
                metric = metrics[operation]
                avg_time_ms = metric.avg_time * 1000
                
                if avg_time_ms > requirement_ms:
                    violations.append({
                        'operation': operation,
                        'avg_time_ms': round(avg_time_ms, 2),
                        'requirement_ms': requirement_ms,
                        'violation_percent': round((avg_time_ms / requirement_ms - 1) * 100, 2)
                    })
        
        return violations
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save benchmark results to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_benchmark_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Benchmark results saved to {filename}")


def run_performance_benchmark():
    """Run performance benchmark and save results."""
    benchmark = PerformanceBenchmark()
    results = benchmark.run_all_benchmarks()
    
    # Print summary
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("="*60)
    
    summary = results.get('summary', {})
    print(f"Performance Score: {summary.get('performance_score', 0):.1f}/100")
    print(f"Total Benchmarks: {summary.get('total_benchmarks', 0)}")
    
    violations = results.get('violations', [])
    if violations:
        print(f"\nLatency Violations: {len(violations)}")
        for violation in violations:
            print(f"  - {violation['operation']}: {violation['avg_time_ms']}ms "
                  f"(requirement: {violation['requirement_ms']}ms)")
    else:
        print("\nNo latency violations detected ✓")
    
    recommendations = summary.get('recommendations', [])
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
    
    # Save results
    benchmark.save_results(results)
    
    return results


if __name__ == "__main__":
    run_performance_benchmark()