# Performance Optimization and Monitoring

This module provides comprehensive performance optimization and monitoring capabilities for the Bank Nifty options trading system.

## Components

### 1. Cache Manager (`cache_manager.py`)

Intelligent caching system with TTL, LRU eviction, and performance monitoring.

**Features:**
- Configurable TTL (Time To Live) for different data types
- LRU (Least Recently Used) eviction policy
- Automatic cleanup of expired entries
- Performance statistics and hit rate monitoring
- Smart cache with type-specific caching strategies

**Usage:**
```python
from src.performance.cache_manager import CacheManager, CacheConfig, SmartCache

# Initialize cache
config = CacheConfig(max_size=1000, default_ttl=300)
cache_manager = CacheManager(config)
smart_cache = SmartCache(cache_manager)

# Cache options chain data
smart_cache.cache_options_chain("BANKNIFTY", "2024-01-25", options_data)

# Retrieve cached data
cached_data = smart_cache.get_options_chain("BANKNIFTY", "2024-01-25")
```

**Configuration Options:**
- `default_ttl`: Default time to live in seconds (300)
- `max_size`: Maximum cache entries (1000)
- `options_chain_ttl`: TTL for options chain data (60s)
- `ltp_ttl`: TTL for LTP data (5s)
- `historical_data_ttl`: TTL for historical data (3600s)

### 2. Performance Monitor (`performance_monitor.py`)

Real-time performance monitoring with latency requirements validation.

**Features:**
- Context manager for easy performance measurement
- Latency requirement checking with alerts
- Percentile calculations (P95, P99)
- Performance violation detection
- Configurable alert callbacks

**Usage:**
```python
from src.performance.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor()

# Measure operation performance
with monitor.measure('atm_calculation'):
    result = calculate_atm_strike(spot_price, strikes)

# Get performance metrics
metrics = monitor.get_metrics('atm_calculation')
print(f"Average time: {metrics.avg_time * 1000:.2f}ms")
```

**Latency Requirements:**
- Options chain processing: < 2000ms
- Strategy evaluation: < 5000ms
- Order placement: < 3000ms
- Position monitoring: < 30000ms
- ATM calculation: < 1000ms

### 3. Connection Pool Manager (`connection_pool.py`)

Optimized HTTP connection pooling for API requests.

**Features:**
- Connection pooling with health monitoring
- Automatic connection recycling
- Retry strategies with exponential backoff
- Connection statistics and monitoring
- Thread-safe connection management

**Usage:**
```python
from src.performance.connection_pool import ConnectionPoolManager, ConnectionConfig

config = ConnectionConfig(pool_size=10, timeout=10)
pool_manager = ConnectionPoolManager(config)

# Use pooled connection
with pool_manager.get_connection() as conn:
    response = conn.session.get(url)
```

### 4. Concurrent Processor (`concurrent_processor.py`)

Concurrent processing system for multiple strategies and operations.

**Features:**
- Thread pool execution for CPU-bound tasks
- Priority-based task scheduling
- Timeout handling and error recovery
- Concurrent strategy evaluation
- Performance statistics and monitoring

**Usage:**
```python
from src.performance.concurrent_processor import ConcurrentProcessor, StrategyEvaluationManager

processor = ConcurrentProcessor(max_workers=4)
manager = StrategyEvaluationManager(processor)

# Evaluate strategies concurrently
strategies = {
    'strategy1': strategy1_func,
    'strategy2': strategy2_func,
    'strategy3': strategy3_func
}

results = manager.evaluate_strategies_concurrent(strategies, market_data)
```

## Integration with Trading System

### Data Manager Integration

The `DataManager` class has been enhanced with performance optimizations:

```python
from src.data.data_manager import DataManager
from src.performance.cache_manager import CacheManager
from src.performance.performance_monitor import PerformanceMonitor

# Initialize with performance components
cache_manager = CacheManager()
performance_monitor = PerformanceMonitor()

data_manager = DataManager(
    api_client=api_client,
    cache_manager=cache_manager,
    performance_monitor=performance_monitor
)

# Get performance statistics
stats = data_manager.get_performance_stats()
```

### API Client Integration

The `AngelAPIClient` has been enhanced with caching and connection pooling:

```python
from src.api.angel_api_client import AngelAPIClient
from src.performance.cache_manager import CacheManager
from src.performance.performance_monitor import PerformanceMonitor

# Initialize with performance components
cache_manager = CacheManager()
performance_monitor = PerformanceMonitor()

api_client = AngelAPIClient(
    credentials=credentials,
    performance_monitor=performance_monitor,
    cache_manager=cache_manager
)

# Get performance statistics
stats = api_client.get_performance_stats()
```

## Performance Benchmarking

### Running Benchmarks

```python
from src.performance.benchmark import run_performance_benchmark

# Run comprehensive benchmark suite
results = run_performance_benchmark()
```

### Benchmark Results

The benchmark validates:
- Cache read/write performance
- Concurrent processing speedup
- Data processing latency
- Memory usage patterns
- Latency requirement compliance

**Sample Results:**
```
Performance Score: 98.9/100
Total Benchmarks: 4
No latency violations detected ✓
```

## Configuration

### Cache Configuration

```yaml
data_manager:
  enable_caching: true
  cache_atm_results: true
  cache_ttl_seconds: 300
  
cache_config:
  max_size: 1000
  default_ttl: 300
  options_chain_ttl: 60
  ltp_ttl: 5
  historical_data_ttl: 3600
```

### Performance Monitoring Configuration

```yaml
performance_monitor:
  max_samples: 1000
  enable_alerts: true
  
latency_requirements:
  atm_calculation: 1000      # 1 second
  options_chain_processing: 2000  # 2 seconds
  strategy_evaluation: 5000  # 5 seconds
```

### Connection Pool Configuration

```yaml
connection_pool:
  pool_size: 10
  max_retries: 3
  timeout: 10
  backoff_factor: 0.3
```

## Monitoring and Alerts

### Performance Alerts

The system can trigger alerts when performance thresholds are exceeded:

```python
def performance_alert_handler(alert_data):
    print(f"Performance alert: {alert_data['operation']} "
          f"took {alert_data['latency_ms']}ms")

monitor.add_alert_callback(performance_alert_handler)
```

### Statistics and Metrics

Get comprehensive performance statistics:

```python
# Cache statistics
cache_stats = cache_manager.get_stats()
print(f"Cache hit rate: {cache_stats['hit_rate_percent']}%")

# Performance metrics
perf_summary = monitor.get_summary()
print(f"Slow operations: {len(perf_summary['violations'])}")

# Connection pool statistics
pool_stats = pool_manager.get_stats()
print(f"Active connections: {pool_stats['active_connections']}")
```

## Testing

Run performance optimization tests:

```bash
python3 -m pytest tests/test_performance_optimization.py -v
```

Run performance benchmark:

```bash
python3 -c "from src.performance.benchmark import run_performance_benchmark; run_performance_benchmark()"
```

## Performance Optimization Guidelines

### 1. Caching Strategy

- Cache frequently accessed data (options chains, LTP data)
- Use appropriate TTL values based on data volatility
- Monitor cache hit rates and adjust cache size accordingly
- Clear cache periodically to prevent memory bloat

### 2. Concurrent Processing

- Use concurrent processing for independent operations
- Evaluate multiple strategies concurrently
- Set appropriate timeouts for tasks
- Monitor task success rates and execution times

### 3. Connection Management

- Use connection pooling for API requests
- Monitor connection health and recycle as needed
- Implement retry strategies with exponential backoff
- Respect API rate limits

### 4. Memory Management

- Monitor memory usage patterns
- Clear old results and cache entries
- Use appropriate data structures for large datasets
- Implement memory-efficient algorithms

### 5. Latency Optimization

- Measure and monitor critical operation latencies
- Set performance requirements and alerts
- Optimize algorithms for time complexity
- Use efficient data processing techniques

## Troubleshooting

### Common Issues

1. **High Cache Miss Rate**
   - Increase cache size or TTL values
   - Check if data access patterns match cache strategy
   - Monitor cache eviction patterns

2. **Slow Concurrent Processing**
   - Check for thread contention or blocking operations
   - Adjust worker pool size based on workload
   - Monitor task queue size and processing times

3. **Connection Pool Exhaustion**
   - Increase pool size or reduce connection timeout
   - Check for connection leaks or long-running operations
   - Monitor connection health and recycling

4. **Memory Usage Growth**
   - Enable periodic cache cleanup
   - Clear old performance metrics and results
   - Monitor memory usage patterns and optimize data structures

### Performance Tuning

1. **Profile Critical Operations**
   ```python
   with monitor.measure('critical_operation'):
       result = perform_critical_operation()
   ```

2. **Monitor Resource Usage**
   ```python
   stats = {
       'cache': cache_manager.get_stats(),
       'performance': monitor.get_summary(),
       'connections': pool_manager.get_stats()
   }
   ```

3. **Optimize Based on Metrics**
   - Adjust cache sizes based on hit rates
   - Tune worker pool sizes based on throughput
   - Optimize algorithms based on latency measurements