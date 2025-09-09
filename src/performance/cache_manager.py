"""
Intelligent caching system for market data and API responses.
"""

import time
import threading
import logging
from typing import Any, Optional, Dict, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import hashlib
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    default_ttl: int = 300  # 5 minutes default TTL
    max_size: int = 1000    # Maximum cache entries
    cleanup_interval: int = 60  # Cleanup every 60 seconds
    enable_persistence: bool = False
    persistence_file: Optional[str] = None
    
    # Specific TTLs for different data types
    options_chain_ttl: int = 60     # 1 minute for options chain
    ltp_ttl: int = 5               # 5 seconds for LTP data
    historical_data_ttl: int = 3600 # 1 hour for historical data
    instrument_search_ttl: int = 86400  # 24 hours for instrument search
    profile_ttl: int = 3600        # 1 hour for profile data


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    ttl: int
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheManager:
    """
    Intelligent cache manager with TTL, LRU eviction, and performance monitoring.
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_bytes': 0,
            'cleanup_runs': 0
        }
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker, 
            daemon=True
        )
        self._cleanup_thread.start()
        
        logger.info(f"Cache manager initialized with max_size={self.config.max_size}, "
                   f"default_ttl={self.config.default_ttl}s")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            if entry.is_expired():
                self._remove_entry(key)
                self._stats['misses'] += 1
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)
            
        Returns:
            True if successfully cached
        """
        if ttl is None:
            ttl = self._get_ttl_for_key(key)
        
        try:
            # Calculate size
            size_bytes = self._calculate_size(value)
            
            with self._lock:
                # Remove existing entry if present
                if key in self._cache:
                    self._remove_entry(key)
                
                # Check if we need to evict entries
                while len(self._cache) >= self.config.max_size:
                    self._evict_lru()
                
                # Create new entry
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=time.time(),
                    ttl=ttl,
                    size_bytes=size_bytes
                )
                
                self._cache[key] = entry
                self._stats['size_bytes'] += size_bytes
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if entry was deleted
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats['size_bytes'] = 0
            logger.info("Cache cleared")
    
    def get_or_set(self, key: str, factory: Callable[[], Any], 
                   ttl: Optional[int] = None) -> Any:
        """
        Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory: Function to generate value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or newly generated value
        """
        # Try to get from cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Generate new value
        try:
            value = factory()
            self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"Factory function failed for key {key}: {e}")
            raise
    
    def _get_ttl_for_key(self, key: str) -> int:
        """Get appropriate TTL based on key pattern."""
        if 'options_chain' in key:
            return self.config.options_chain_ttl
        elif 'ltp' in key:
            return self.config.ltp_ttl
        elif 'historical' in key:
            return self.config.historical_data_ttl
        elif 'search' in key or 'instruments' in key:
            return self.config.instrument_search_ttl
        elif 'profile' in key:
            return self.config.profile_ttl
        else:
            return self.config.default_ttl
    
    def _calculate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes."""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (int, float)):
                return 8
            elif isinstance(value, (list, dict)):
                return len(json.dumps(value, default=str))
            else:
                return len(str(value))
        except Exception:
            return 100  # Default estimate
    
    def _remove_entry(self, key: str):
        """Remove entry and update stats."""
        entry = self._cache.pop(key, None)
        if entry:
            self._stats['size_bytes'] -= entry.size_bytes
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if self._cache:
            key, _ = self._cache.popitem(last=False)  # Remove first (oldest)
            self._stats['evictions'] += 1
            logger.debug(f"Evicted LRU entry: {key}")
    
    def _cleanup_worker(self):
        """Background thread to cleanup expired entries."""
        while True:
            try:
                time.sleep(self.config.cleanup_interval)
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self):
        """Remove expired entries."""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_entry(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            self._stats['cleanup_runs'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'entries': len(self._cache),
                'max_size': self.config.max_size,
                'size_bytes': self._stats['size_bytes'],
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'evictions': self._stats['evictions'],
                'cleanup_runs': self._stats['cleanup_runs']
            }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information."""
        with self._lock:
            entries_info = []
            for key, entry in self._cache.items():
                entries_info.append({
                    'key': key,
                    'size_bytes': entry.size_bytes,
                    'ttl': entry.ttl,
                    'age_seconds': int(time.time() - entry.created_at),
                    'access_count': entry.access_count,
                    'expires_in': max(0, int(entry.ttl - (time.time() - entry.created_at)))
                })
            
            return {
                'config': {
                    'max_size': self.config.max_size,
                    'default_ttl': self.config.default_ttl,
                    'cleanup_interval': self.config.cleanup_interval
                },
                'stats': self.get_stats(),
                'entries': entries_info
            }


class SmartCache:
    """
    Smart cache with automatic key generation and type-specific caching strategies.
    """
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def cache_options_chain(self, underlying: str, expiry: str, 
                          data: Any) -> bool:
        """Cache options chain data."""
        key = f"options_chain:{underlying}:{expiry}"
        return self.cache_manager.set(key, data)
    
    def get_options_chain(self, underlying: str, expiry: str) -> Optional[Any]:
        """Get cached options chain data."""
        key = f"options_chain:{underlying}:{expiry}"
        return self.cache_manager.get(key)
    
    def cache_ltp(self, exchange: str, symbol: str, token: str, 
                  price: float) -> bool:
        """Cache LTP data."""
        key = f"ltp:{exchange}:{symbol}:{token}"
        return self.cache_manager.set(key, price)
    
    def get_ltp(self, exchange: str, symbol: str, token: str) -> Optional[float]:
        """Get cached LTP data."""
        key = f"ltp:{exchange}:{symbol}:{token}"
        return self.cache_manager.get(key)
    
    def cache_historical_data(self, symbol: str, interval: str, 
                            from_date: str, to_date: str, data: Any) -> bool:
        """Cache historical data."""
        key = f"historical:{symbol}:{interval}:{from_date}:{to_date}"
        return self.cache_manager.set(key, data)
    
    def get_historical_data(self, symbol: str, interval: str,
                          from_date: str, to_date: str) -> Optional[Any]:
        """Get cached historical data."""
        key = f"historical:{symbol}:{interval}:{from_date}:{to_date}"
        return self.cache_manager.get(key)
    
    def cache_instrument_search(self, exchange: str, search_term: str, 
                              results: List[Dict]) -> bool:
        """Cache instrument search results."""
        # Create hash of search term for consistent key
        search_hash = hashlib.md5(search_term.encode()).hexdigest()[:8]
        key = f"search:{exchange}:{search_hash}"
        return self.cache_manager.set(key, results)
    
    def get_instrument_search(self, exchange: str, search_term: str) -> Optional[List[Dict]]:
        """Get cached instrument search results."""
        search_hash = hashlib.md5(search_term.encode()).hexdigest()[:8]
        key = f"search:{exchange}:{search_hash}"
        return self.cache_manager.get(key)
    
    def cache_atm_strike(self, underlying: str, expiry: str, 
                        spot_price: float, atm_result: Any) -> bool:
        """Cache ATM strike calculation result."""
        # Round spot price to avoid cache misses due to minor price differences
        rounded_spot = round(spot_price, 2)
        key = f"atm:{underlying}:{expiry}:{rounded_spot}"
        return self.cache_manager.set(key, atm_result)
    
    def get_atm_strike(self, underlying: str, expiry: str, 
                      spot_price: float) -> Optional[Any]:
        """Get cached ATM strike result."""
        rounded_spot = round(spot_price, 2)
        key = f"atm:{underlying}:{expiry}:{rounded_spot}"
        return self.cache_manager.get(key)