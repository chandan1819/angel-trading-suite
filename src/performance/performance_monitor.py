"""
Performance monitoring system for critical trading operations.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""
    operation_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    median_time: float = 0.0
    p95_time: float = 0.0
    p99_time: float = 0.0
    error_count: int = 0
    success_rate: float = 100.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update_stats(self, execution_time: float, success: bool = True):
        """Update metrics with new execution data."""
        self.total_calls += 1
        
        if success:
            self.total_time += execution_time
            self.min_time = min(self.min_time, execution_time)
            self.max_time = max(self.max_time, execution_time)
            self.avg_time = self.total_time / (self.total_calls - self.error_count)
        else:
            self.error_count += 1
        
        self.success_rate = ((self.total_calls - self.error_count) / self.total_calls) * 100
        self.last_updated = datetime.now()


@dataclass
class LatencyRequirement:
    """Latency requirement for an operation."""
    operation_name: str
    max_latency_ms: float
    warning_threshold_ms: float
    alert_threshold_ms: float
    
    def check_violation(self, latency_ms: float) -> Optional[str]:
        """Check if latency violates requirements."""
        if latency_ms > self.max_latency_ms:
            return "CRITICAL"
        elif latency_ms > self.alert_threshold_ms:
            return "ALERT"
        elif latency_ms > self.warning_threshold_ms:
            return "WARNING"
        return None


class PerformanceMonitor:
    """
    Performance monitoring system for critical trading operations.
    """
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._metrics: Dict[str, PerformanceMetrics] = {}
        self._samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self._lock = threading.RLock()
        
        # Latency requirements for critical operations
        self._requirements = {
            'options_chain_processing': LatencyRequirement(
                'options_chain_processing', 2000, 1500, 1800
            ),
            'strategy_evaluation': LatencyRequirement(
                'strategy_evaluation', 5000, 3000, 4000
            ),
            'order_placement': LatencyRequirement(
                'order_placement', 3000, 2000, 2500
            ),
            'position_monitoring': LatencyRequirement(
                'position_monitoring', 30000, 20000, 25000
            ),
            'atm_calculation': LatencyRequirement(
                'atm_calculation', 1000, 500, 750
            ),
            'api_call': LatencyRequirement(
                'api_call', 5000, 3000, 4000
            )
        }
        
        # Performance alerts
        self._alert_callbacks: List[Callable] = []
        
        logger.info(f"Performance monitor initialized with {len(self._requirements)} requirements")
    
    @contextmanager
    def measure(self, operation_name: str):
        """
        Context manager to measure operation performance.
        
        Args:
            operation_name: Name of the operation being measured
        """
        start_time = time.time()
        success = True
        
        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            self.record_execution(operation_name, execution_time, success)
    
    def record_execution(self, operation_name: str, execution_time: float, 
                        success: bool = True):
        """
        Record execution time for an operation.
        
        Args:
            operation_name: Name of the operation
            execution_time: Execution time in seconds
            success: Whether the operation was successful
        """
        with self._lock:
            # Initialize metrics if not exists
            if operation_name not in self._metrics:
                self._metrics[operation_name] = PerformanceMetrics(operation_name)
            
            # Update metrics
            metrics = self._metrics[operation_name]
            metrics.update_stats(execution_time, success)
            
            # Store sample for percentile calculations
            if success:
                self._samples[operation_name].append(execution_time)
                self._update_percentiles(operation_name)
            
            # Check latency requirements
            latency_ms = execution_time * 1000
            self._check_latency_requirements(operation_name, latency_ms)
    
    def _update_percentiles(self, operation_name: str):
        """Update percentile calculations for an operation."""
        samples = list(self._samples[operation_name])
        if len(samples) < 2:
            return
        
        metrics = self._metrics[operation_name]
        sorted_samples = sorted(samples)
        
        metrics.median_time = statistics.median(sorted_samples)
        
        if len(sorted_samples) >= 20:  # Need sufficient samples for percentiles
            p95_idx = int(0.95 * len(sorted_samples))
            p99_idx = int(0.99 * len(sorted_samples))
            
            metrics.p95_time = sorted_samples[p95_idx]
            metrics.p99_time = sorted_samples[p99_idx]
    
    def _check_latency_requirements(self, operation_name: str, latency_ms: float):
        """Check if operation meets latency requirements."""
        requirement = self._requirements.get(operation_name)
        if not requirement:
            return
        
        violation = requirement.check_violation(latency_ms)
        if violation:
            alert_data = {
                'operation': operation_name,
                'latency_ms': latency_ms,
                'requirement_ms': requirement.max_latency_ms,
                'violation_level': violation,
                'timestamp': datetime.now()
            }
            
            logger.warning(f"Latency violation: {operation_name} took {latency_ms:.2f}ms "
                          f"(requirement: {requirement.max_latency_ms}ms, level: {violation})")
            
            # Trigger alerts
            for callback in self._alert_callbacks:
                try:
                    callback(alert_data)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")
    
    def get_metrics(self, operation_name: str) -> Optional[PerformanceMetrics]:
        """Get metrics for a specific operation."""
        with self._lock:
            return self._metrics.get(operation_name)
    
    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get metrics for all operations."""
        with self._lock:
            return dict(self._metrics)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        with self._lock:
            summary = {
                'total_operations': len(self._metrics),
                'operations': {},
                'violations': []
            }
            
            for name, metrics in self._metrics.items():
                op_summary = {
                    'total_calls': metrics.total_calls,
                    'avg_time_ms': round(metrics.avg_time * 1000, 2),
                    'p95_time_ms': round(metrics.p95_time * 1000, 2),
                    'success_rate': round(metrics.success_rate, 2),
                    'error_count': metrics.error_count
                }
                
                # Check current performance against requirements
                requirement = self._requirements.get(name)
                if requirement and metrics.avg_time > 0:
                    avg_latency_ms = metrics.avg_time * 1000
                    violation = requirement.check_violation(avg_latency_ms)
                    if violation:
                        summary['violations'].append({
                            'operation': name,
                            'avg_latency_ms': avg_latency_ms,
                            'requirement_ms': requirement.max_latency_ms,
                            'violation_level': violation
                        })
                
                summary['operations'][name] = op_summary
            
            return summary
    
    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for performance alerts."""
        self._alert_callbacks.append(callback)
    
    def reset_metrics(self, operation_name: Optional[str] = None):
        """Reset metrics for specific operation or all operations."""
        with self._lock:
            if operation_name:
                if operation_name in self._metrics:
                    del self._metrics[operation_name]
                if operation_name in self._samples:
                    self._samples[operation_name].clear()
            else:
                self._metrics.clear()
                self._samples.clear()
    
    def set_requirement(self, operation_name: str, requirement: LatencyRequirement):
        """Set or update latency requirement for an operation."""
        self._requirements[operation_name] = requirement
        logger.info(f"Updated requirement for {operation_name}: {requirement.max_latency_ms}ms")
    
    def get_slow_operations(self, threshold_ms: float = 1000) -> List[Dict[str, Any]]:
        """Get operations that are slower than threshold."""
        slow_ops = []
        
        with self._lock:
            for name, metrics in self._metrics.items():
                if metrics.avg_time * 1000 > threshold_ms:
                    slow_ops.append({
                        'operation': name,
                        'avg_time_ms': round(metrics.avg_time * 1000, 2),
                        'p95_time_ms': round(metrics.p95_time * 1000, 2),
                        'total_calls': metrics.total_calls,
                        'success_rate': round(metrics.success_rate, 2)
                    })
        
        return sorted(slow_ops, key=lambda x: x['avg_time_ms'], reverse=True)
    
    def get_error_prone_operations(self, min_error_rate: float = 5.0) -> List[Dict[str, Any]]:
        """Get operations with high error rates."""
        error_prone = []
        
        with self._lock:
            for name, metrics in self._metrics.items():
                error_rate = 100 - metrics.success_rate
                if error_rate >= min_error_rate and metrics.total_calls >= 10:
                    error_prone.append({
                        'operation': name,
                        'error_rate': round(error_rate, 2),
                        'error_count': metrics.error_count,
                        'total_calls': metrics.total_calls,
                        'avg_time_ms': round(metrics.avg_time * 1000, 2)
                    })
        
        return sorted(error_prone, key=lambda x: x['error_rate'], reverse=True)


class OperationTimer:
    """Simple timer for measuring individual operations."""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
    
    def start(self):
        """Start timing."""
        self.start_time = time.time()
    
    def stop(self, success: bool = True):
        """Stop timing and record result."""
        if self.start_time is None:
            logger.warning(f"Timer for {self.operation_name} was not started")
            return
        
        execution_time = time.time() - self.start_time
        self.monitor.record_execution(self.operation_name, execution_time, success)
        self.start_time = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        self.stop(success)