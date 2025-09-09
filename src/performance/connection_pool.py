"""
Connection pool manager for optimized API connections.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from queue import Queue, Empty, Full
from contextlib import contextmanager
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for connection pool."""
    pool_size: int = 10
    max_retries: int = 3
    backoff_factor: float = 0.3
    timeout: int = 10
    keep_alive: bool = True
    pool_block: bool = True
    pool_maxsize: int = 10


class PooledConnection:
    """Individual pooled connection wrapper."""
    
    def __init__(self, connection_id: str, session: requests.Session):
        self.connection_id = connection_id
        self.session = session
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.use_count = 0
        self.is_healthy = True
        self.lock = threading.Lock()
    
    def use(self):
        """Mark connection as used."""
        with self.lock:
            self.last_used = datetime.now()
            self.use_count += 1
    
    def is_expired(self, max_age_minutes: int = 30) -> bool:
        """Check if connection is expired."""
        age = datetime.now() - self.created_at
        return age > timedelta(minutes=max_age_minutes)
    
    def is_idle(self, max_idle_minutes: int = 5) -> bool:
        """Check if connection has been idle too long."""
        idle_time = datetime.now() - self.last_used
        return idle_time > timedelta(minutes=max_idle_minutes)
    
    def health_check(self) -> bool:
        """Perform basic health check on connection."""
        try:
            # Simple health check - could be enhanced with actual API ping
            return self.session is not None and self.is_healthy
        except Exception as e:
            logger.warning(f"Connection {self.connection_id} health check failed: {e}")
            self.is_healthy = False
            return False
    
    def close(self):
        """Close the connection."""
        try:
            if self.session:
                self.session.close()
            self.is_healthy = False
        except Exception as e:
            logger.warning(f"Error closing connection {self.connection_id}: {e}")


class ConnectionPoolManager:
    """
    Connection pool manager for optimized API connections with health monitoring.
    """
    
    def __init__(self, config: ConnectionConfig = None):
        self.config = config or ConnectionConfig()
        self._pool: Queue[PooledConnection] = Queue(maxsize=self.config.pool_size)
        self._active_connections: Dict[str, PooledConnection] = {}
        self._lock = threading.RLock()
        self._connection_counter = 0
        
        # Statistics
        self._stats = {
            'created': 0,
            'destroyed': 0,
            'borrowed': 0,
            'returned': 0,
            'health_checks': 0,
            'health_failures': 0
        }
        
        # Initialize pool
        self._initialize_pool()
        
        # Start maintenance thread
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_worker,
            daemon=True
        )
        self._maintenance_thread.start()
        
        logger.info(f"Connection pool initialized with {self.config.pool_size} connections")
    
    def _initialize_pool(self):
        """Initialize the connection pool."""
        for _ in range(self.config.pool_size):
            connection = self._create_connection()
            if connection:
                try:
                    self._pool.put_nowait(connection)
                except Full:
                    connection.close()
                    break
    
    def _create_connection(self) -> Optional[PooledConnection]:
        """Create a new pooled connection."""
        try:
            with self._lock:
                self._connection_counter += 1
                connection_id = f"conn_{self._connection_counter}"
            
            # Create session with optimized settings
            session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=self.config.max_retries,
                backoff_factor=self.config.backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
            )
            
            # Configure adapter with connection pooling
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=self.config.pool_maxsize,
                pool_maxsize=self.config.pool_maxsize,
                pool_block=self.config.pool_block
            )
            
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Set default timeout
            session.timeout = self.config.timeout
            
            # Configure keep-alive
            if self.config.keep_alive:
                session.headers.update({'Connection': 'keep-alive'})
            
            connection = PooledConnection(connection_id, session)
            
            with self._lock:
                self._stats['created'] += 1
            
            logger.debug(f"Created connection: {connection_id}")
            return connection
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """
        Get a connection from the pool.
        
        Args:
            timeout: Timeout for getting connection from pool
            
        Yields:
            PooledConnection: Connection from pool
        """
        connection = None
        try:
            # Get connection from pool
            connection = self._borrow_connection(timeout)
            if not connection:
                raise RuntimeError("Could not get connection from pool")
            
            yield connection
            
        finally:
            # Return connection to pool
            if connection:
                self._return_connection(connection)
    
    def _borrow_connection(self, timeout: float) -> Optional[PooledConnection]:
        """Borrow a connection from the pool."""
        try:
            # Try to get from pool
            connection = self._pool.get(timeout=timeout)
            
            # Health check
            if not connection.health_check():
                logger.warning(f"Unhealthy connection {connection.connection_id}, creating new one")
                connection.close()
                connection = self._create_connection()
                if not connection:
                    return None
            
            # Mark as active
            with self._lock:
                self._active_connections[connection.connection_id] = connection
                self._stats['borrowed'] += 1
            
            connection.use()
            return connection
            
        except Empty:
            logger.warning("Connection pool exhausted, creating temporary connection")
            # Create temporary connection if pool is exhausted
            return self._create_connection()
        except Exception as e:
            logger.error(f"Error borrowing connection: {e}")
            return None
    
    def _return_connection(self, connection: PooledConnection):
        """Return a connection to the pool."""
        try:
            with self._lock:
                # Remove from active connections
                self._active_connections.pop(connection.connection_id, None)
                self._stats['returned'] += 1
            
            # Check if connection is still healthy and not expired
            if (connection.health_check() and 
                not connection.is_expired() and 
                not connection.is_idle()):
                
                try:
                    self._pool.put_nowait(connection)
                    return
                except Full:
                    # Pool is full, close the connection
                    pass
            
            # Close unhealthy/expired connection
            connection.close()
            with self._lock:
                self._stats['destroyed'] += 1
            
        except Exception as e:
            logger.error(f"Error returning connection {connection.connection_id}: {e}")
            connection.close()
    
    def _maintenance_worker(self):
        """Background maintenance worker."""
        while True:
            try:
                time.sleep(60)  # Run maintenance every minute
                self._perform_maintenance()
            except Exception as e:
                logger.error(f"Connection pool maintenance error: {e}")
    
    def _perform_maintenance(self):
        """Perform pool maintenance tasks."""
        with self._lock:
            # Health check active connections
            unhealthy_connections = []
            for conn_id, connection in self._active_connections.items():
                self._stats['health_checks'] += 1
                if not connection.health_check():
                    unhealthy_connections.append(conn_id)
                    self._stats['health_failures'] += 1
            
            # Remove unhealthy active connections
            for conn_id in unhealthy_connections:
                connection = self._active_connections.pop(conn_id, None)
                if connection:
                    connection.close()
                    self._stats['destroyed'] += 1
                    logger.warning(f"Removed unhealthy active connection: {conn_id}")
        
        # Clean up pool connections
        temp_connections = []
        while True:
            try:
                connection = self._pool.get_nowait()
                
                # Check if connection should be kept
                if (connection.health_check() and 
                    not connection.is_expired() and 
                    not connection.is_idle()):
                    temp_connections.append(connection)
                else:
                    connection.close()
                    with self._lock:
                        self._stats['destroyed'] += 1
                    logger.debug(f"Cleaned up connection: {connection.connection_id}")
                    
            except Empty:
                break
        
        # Return good connections to pool
        for connection in temp_connections:
            try:
                self._pool.put_nowait(connection)
            except Full:
                connection.close()
                with self._lock:
                    self._stats['destroyed'] += 1
        
        # Ensure minimum pool size
        current_size = self._pool.qsize()
        if current_size < self.config.pool_size // 2:
            needed = self.config.pool_size - current_size
            for _ in range(needed):
                connection = self._create_connection()
                if connection:
                    try:
                        self._pool.put_nowait(connection)
                    except Full:
                        connection.close()
                        break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            return {
                'pool_size': self._pool.qsize(),
                'active_connections': len(self._active_connections),
                'max_pool_size': self.config.pool_size,
                'stats': dict(self._stats),
                'health_rate': (
                    (self._stats['health_checks'] - self._stats['health_failures']) / 
                    max(1, self._stats['health_checks']) * 100
                ) if self._stats['health_checks'] > 0 else 100
            }
    
    def get_pool_info(self) -> Dict[str, Any]:
        """Get detailed pool information."""
        with self._lock:
            active_info = []
            for conn_id, connection in self._active_connections.items():
                active_info.append({
                    'connection_id': conn_id,
                    'created_at': connection.created_at.isoformat(),
                    'last_used': connection.last_used.isoformat(),
                    'use_count': connection.use_count,
                    'is_healthy': connection.is_healthy
                })
            
            return {
                'config': {
                    'pool_size': self.config.pool_size,
                    'timeout': self.config.timeout,
                    'max_retries': self.config.max_retries
                },
                'stats': self.get_stats(),
                'active_connections': active_info
            }
    
    def close_all(self):
        """Close all connections and shutdown pool."""
        logger.info("Shutting down connection pool")
        
        with self._lock:
            # Close active connections
            for connection in self._active_connections.values():
                connection.close()
            self._active_connections.clear()
            
            # Close pooled connections
            while True:
                try:
                    connection = self._pool.get_nowait()
                    connection.close()
                except Empty:
                    break
        
        logger.info("Connection pool shutdown complete")


class OptimizedHTTPClient:
    """HTTP client with connection pooling and performance optimizations."""
    
    def __init__(self, pool_manager: ConnectionPoolManager):
        self.pool_manager = pool_manager
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request using pooled connection."""
        with self.pool_manager.get_connection() as connection:
            return connection.session.request(method, url, **kwargs)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Make POST request."""
        return self.request('POST', url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Make PUT request."""
        return self.request('PUT', url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Make DELETE request."""
        return self.request('DELETE', url, **kwargs)