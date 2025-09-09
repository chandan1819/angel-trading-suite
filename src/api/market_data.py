"""
Market data retrieval methods with caching and real-time monitoring.
"""

import time
import logging
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

from .angel_api_client import AngelAPIClient
from .error_handler import APIError, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with timestamp and data."""
    data: Any
    timestamp: datetime
    ttl_seconds: int = 300  # 5 minutes default
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() - self.timestamp > timedelta(seconds=self.ttl_seconds)


@dataclass
class OptionsChainData:
    """Options chain data structure."""
    underlying_symbol: str
    underlying_price: float
    expiry_date: str
    strikes: List[Dict[str, Any]]
    timestamp: datetime
    atm_strike: Optional[float] = None


@dataclass
class HistoricalDataPoint:
    """Historical data point structure."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class RealTimePriceData:
    """Real-time price data structure."""
    symbol: str
    ltp: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime


class DataCache:
    """Thread-safe data cache with TTL support."""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        with self.lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired():
                return entry.data
            elif entry:
                # Remove expired entry
                del self.cache[key]
            return None
    
    def set(self, key: str, data: Any, ttl_seconds: int = 300):
        """Set cached data with TTL."""
        with self.lock:
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=datetime.now(),
                ttl_seconds=ttl_seconds
            )
    
    def invalidate(self, key: str):
        """Invalidate specific cache entry."""
        with self.lock:
            self.cache.pop(key, None)
    
    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
    
    def cleanup_expired(self):
        """Remove all expired entries."""
        with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self.cache[key]


class MarketDataManager:
    """
    Market data manager with caching, real-time monitoring,
    and comprehensive options chain processing.
    """
    
    def __init__(self, api_client: AngelAPIClient):
        self.api_client = api_client
        self.cache = DataCache()
        
        # Real-time monitoring
        self.price_monitors: Dict[str, Dict] = {}
        self.monitor_lock = threading.Lock()
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Cache TTL settings (in seconds)
        self.cache_ttl = {
            'options_chain': 60,      # 1 minute
            'historical_data': 3600,  # 1 hour
            'ltp': 5,                 # 5 seconds
            'instruments': 86400      # 24 hours
        }
    
    def get_options_chain(self, underlying_symbol: str = "BANKNIFTY", 
                         expiry_date: Optional[str] = None,
                         use_cache: bool = True) -> Optional[OptionsChainData]:
        """
        Get options chain data for the specified underlying and expiry.
        
        Args:
            underlying_symbol: Underlying symbol (default: BANKNIFTY)
            expiry_date: Specific expiry date (YYYY-MM-DD format), None for current month
            use_cache: Whether to use cached data
            
        Returns:
            OptionsChainData object or None if failed
        """
        cache_key = f"options_chain_{underlying_symbol}_{expiry_date or 'current'}"
        
        # Try cache first
        if use_cache:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.debug(f"Using cached options chain for {underlying_symbol}")
                return cached_data
        
        try:
            # Get current expiry if not specified
            if not expiry_date:
                expiry_date = self._get_current_month_expiry(underlying_symbol)
                if not expiry_date:
                    logger.error(f"Could not determine current expiry for {underlying_symbol}")
                    return None
            
            # Search for options instruments
            options_instruments = self._search_options_instruments(underlying_symbol, expiry_date)
            if not options_instruments:
                logger.error(f"No options instruments found for {underlying_symbol} expiry {expiry_date}")
                return None
            
            # Get underlying price
            underlying_price = self._get_underlying_price(underlying_symbol)
            if not underlying_price:
                logger.error(f"Could not get underlying price for {underlying_symbol}")
                return None
            
            # Process options chain
            strikes_data = self._process_options_chain(options_instruments, underlying_price)
            
            # Create options chain data
            options_chain = OptionsChainData(
                underlying_symbol=underlying_symbol,
                underlying_price=underlying_price,
                expiry_date=expiry_date,
                strikes=strikes_data,
                timestamp=datetime.now(),
                atm_strike=self._find_atm_strike(strikes_data, underlying_price)
            )
            
            # Cache the result
            self.cache.set(cache_key, options_chain, self.cache_ttl['options_chain'])
            
            logger.info(f"Retrieved options chain for {underlying_symbol} expiry {expiry_date} "
                       f"with {len(strikes_data)} strikes, ATM: {options_chain.atm_strike}")
            
            return options_chain
            
        except Exception as e:
            logger.error(f"Failed to get options chain for {underlying_symbol}: {e}")
            return None
    
    def _get_current_month_expiry(self, underlying_symbol: str) -> Optional[str]:
        """
        Determine the current month expiry date for the underlying.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            Expiry date string (YYYY-MM-DD) or None
        """
        try:
            # Search for any options of the underlying to find expiry dates
            search_results = self.api_client.search_instruments("NFO", underlying_symbol)
            
            if not search_results:
                return None
            
            # Extract expiry dates from trading symbols
            expiry_dates = set()
            for instrument in search_results:
                symbol = instrument.get('tradingsymbol', '')
                if 'CE' in symbol or 'PE' in symbol:
                    # Extract expiry from symbol (format: BANKNIFTY01JAN25CE50000)
                    expiry_part = self._extract_expiry_from_symbol(symbol)
                    if expiry_part:
                        expiry_dates.add(expiry_part)
            
            if not expiry_dates:
                return None
            
            # Find the nearest expiry (current month)
            current_date = datetime.now().date()
            nearest_expiry = None
            min_days_diff = float('inf')
            
            for expiry_str in expiry_dates:
                try:
                    expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                    if expiry_date >= current_date:
                        days_diff = (expiry_date - current_date).days
                        if days_diff < min_days_diff:
                            min_days_diff = days_diff
                            nearest_expiry = expiry_str
                except ValueError:
                    continue
            
            return nearest_expiry
            
        except Exception as e:
            logger.error(f"Failed to determine current expiry for {underlying_symbol}: {e}")
            return None
    
    def _extract_expiry_from_symbol(self, symbol: str) -> Optional[str]:
        """
        Extract expiry date from trading symbol.
        
        Args:
            symbol: Trading symbol (e.g., BANKNIFTY01JAN25CE50000)
            
        Returns:
            Expiry date string (YYYY-MM-DD) or None
        """
        try:
            import re
            
            # Pattern to match expiry in symbol (e.g., 01JAN25)
            pattern = r'(\d{2})([A-Z]{3})(\d{2})'
            match = re.search(pattern, symbol)
            
            if match:
                day, month_abbr, year = match.groups()
                
                # Convert month abbreviation to number
                month_map = {
                    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                    'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                    'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
                }
                
                month = month_map.get(month_abbr)
                if not month:
                    return None
                
                # Convert 2-digit year to 4-digit
                year_int = int(year)
                if year_int < 50:
                    full_year = 2000 + year_int
                else:
                    full_year = 1900 + year_int
                
                return f"{full_year}-{month}-{day}"
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract expiry from symbol {symbol}: {e}")
            return None
    
    def _search_options_instruments(self, underlying_symbol: str, 
                                  expiry_date: str) -> List[Dict[str, Any]]:
        """
        Search for options instruments for the given underlying and expiry.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date string
            
        Returns:
            List of options instruments
        """
        try:
            # Search for options instruments
            search_results = self.api_client.search_instruments("NFO", underlying_symbol)
            
            if not search_results:
                return []
            
            # Filter by expiry date
            options_instruments = []
            target_expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            
            for instrument in search_results:
                symbol = instrument.get('tradingsymbol', '')
                if 'CE' in symbol or 'PE' in symbol:
                    instrument_expiry = self._extract_expiry_from_symbol(symbol)
                    if instrument_expiry:
                        instrument_expiry_date = datetime.strptime(instrument_expiry, '%Y-%m-%d').date()
                        if instrument_expiry_date == target_expiry:
                            options_instruments.append(instrument)
            
            return options_instruments
            
        except Exception as e:
            logger.error(f"Failed to search options instruments: {e}")
            return []
    
    def _get_underlying_price(self, underlying_symbol: str) -> Optional[float]:
        """
        Get current price of the underlying.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            Current price or None
        """
        try:
            # For BANKNIFTY, we need to get the index price
            if underlying_symbol == "BANKNIFTY":
                # Search for BANKNIFTY index
                search_results = self.api_client.search_instruments("NSE", "NIFTY BANK")
                
                if search_results:
                    instrument = search_results[0]
                    ltp = self.api_client.get_ltp(
                        instrument['exchange'],
                        instrument['tradingsymbol'],
                        instrument['symboltoken']
                    )
                    return ltp
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get underlying price for {underlying_symbol}: {e}")
            return None
    
    def _process_options_chain(self, options_instruments: List[Dict[str, Any]], 
                             underlying_price: float) -> List[Dict[str, Any]]:
        """
        Process options instruments into structured chain data.
        
        Args:
            options_instruments: List of options instruments
            underlying_price: Current underlying price
            
        Returns:
            List of strike data dictionaries
        """
        strikes_data = defaultdict(lambda: {'strike': 0, 'call': None, 'put': None})
        
        try:
            # Group options by strike price
            for instrument in options_instruments:
                symbol = instrument.get('tradingsymbol', '')
                strike_price = self._extract_strike_from_symbol(symbol)
                
                if strike_price:
                    option_type = 'call' if 'CE' in symbol else 'put'
                    
                    # Get current LTP for the option
                    ltp = self.api_client.get_ltp(
                        instrument['exchange'],
                        instrument['tradingsymbol'],
                        instrument['symboltoken']
                    )
                    
                    option_data = {
                        'symbol': symbol,
                        'token': instrument['symboltoken'],
                        'ltp': ltp or 0.0,
                        'exchange': instrument['exchange']
                    }
                    
                    strikes_data[strike_price]['strike'] = strike_price
                    strikes_data[strike_price][option_type] = option_data
            
            # Convert to list and sort by strike
            result = []
            for strike_price in sorted(strikes_data.keys()):
                strike_data = strikes_data[strike_price]
                if strike_data['call'] or strike_data['put']:  # At least one option available
                    result.append(strike_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process options chain: {e}")
            return []
    
    def _extract_strike_from_symbol(self, symbol: str) -> Optional[float]:
        """
        Extract strike price from trading symbol.
        
        Args:
            symbol: Trading symbol (e.g., BANKNIFTY01JAN25CE50000)
            
        Returns:
            Strike price or None
        """
        try:
            import re
            
            # Pattern to match strike at the end (e.g., CE50000 or PE45000)
            pattern = r'(CE|PE)(\d+)$'
            match = re.search(pattern, symbol)
            
            if match:
                strike_str = match.group(2)
                return float(strike_str)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract strike from symbol {symbol}: {e}")
            return None
    
    def _find_atm_strike(self, strikes_data: List[Dict[str, Any]], 
                        underlying_price: float) -> Optional[float]:
        """
        Find the At-The-Money strike price.
        
        Args:
            strikes_data: List of strike data
            underlying_price: Current underlying price
            
        Returns:
            ATM strike price or None
        """
        if not strikes_data:
            return None
        
        try:
            # Find the strike closest to underlying price
            min_diff = float('inf')
            atm_strike = None
            
            for strike_data in strikes_data:
                strike = strike_data['strike']
                diff = abs(strike - underlying_price)
                
                if diff < min_diff:
                    min_diff = diff
                    atm_strike = strike
                elif diff == min_diff and strike < underlying_price:
                    # Tie-breaker: choose lower strike if exactly between two strikes
                    atm_strike = strike
            
            return atm_strike
            
        except Exception as e:
            logger.error(f"Failed to find ATM strike: {e}")
            return None
    
    def get_historical_data(self, symbol: str, token: str, exchange: str,
                          interval: str = "ONE_DAY", from_date: str = None,
                          to_date: str = None, use_cache: bool = True) -> List[HistoricalDataPoint]:
        """
        Get historical data with caching.
        
        Args:
            symbol: Trading symbol
            token: Instrument token
            exchange: Exchange name
            interval: Data interval (ONE_MINUTE, FIVE_MINUTE, ONE_DAY, etc.)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            use_cache: Whether to use cached data
            
        Returns:
            List of historical data points
        """
        # Set default dates if not provided
        if not to_date:
            to_date = datetime.now().strftime('%Y-%m-%d')
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        cache_key = f"historical_{symbol}_{interval}_{from_date}_{to_date}"
        
        # Try cache first
        if use_cache:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.debug(f"Using cached historical data for {symbol}")
                return cached_data
        
        try:
            params = {
                'exchange': exchange,
                'symboltoken': token,
                'interval': interval,
                'fromdate': from_date + ' 09:15',
                'todate': to_date + ' 15:30'
            }
            
            raw_data = self.api_client.get_historical_data(params)
            
            # Convert to structured data
            historical_data = []
            for data_point in raw_data:
                if len(data_point) >= 6:  # [timestamp, open, high, low, close, volume]
                    historical_data.append(HistoricalDataPoint(
                        timestamp=datetime.fromisoformat(data_point[0]),
                        open=float(data_point[1]),
                        high=float(data_point[2]),
                        low=float(data_point[3]),
                        close=float(data_point[4]),
                        volume=int(data_point[5])
                    ))
            
            # Cache the result
            self.cache.set(cache_key, historical_data, self.cache_ttl['historical_data'])
            
            logger.info(f"Retrieved {len(historical_data)} historical data points for {symbol}")
            return historical_data
            
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
            return []
    
    def start_real_time_monitoring(self, symbols: List[Dict[str, str]], 
                                 callback: Callable[[RealTimePriceData], None],
                                 interval_seconds: int = 5):
        """
        Start real-time price monitoring for specified symbols.
        
        Args:
            symbols: List of symbol dictionaries with 'exchange', 'symbol', 'token'
            callback: Callback function to handle price updates
            interval_seconds: Monitoring interval in seconds
        """
        with self.monitor_lock:
            if self.monitoring_active:
                logger.warning("Real-time monitoring already active")
                return
            
            self.price_monitors = {
                f"{s['exchange']}:{s['symbol']}": s for s in symbols
            }
            self.monitoring_active = True
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_prices,
                args=(callback, interval_seconds),
                daemon=True
            )
            self.monitor_thread.start()
            
            logger.info(f"Started real-time monitoring for {len(symbols)} symbols")
    
    def stop_real_time_monitoring(self):
        """Stop real-time price monitoring."""
        with self.monitor_lock:
            if not self.monitoring_active:
                return
            
            self.monitoring_active = False
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            self.price_monitors.clear()
            logger.info("Stopped real-time monitoring")
    
    def _monitor_prices(self, callback: Callable[[RealTimePriceData], None], 
                       interval_seconds: int):
        """
        Internal method to monitor prices in a separate thread.
        
        Args:
            callback: Callback function for price updates
            interval_seconds: Monitoring interval
        """
        while self.monitoring_active:
            try:
                # Get current prices for all monitored symbols
                for symbol_key, symbol_info in self.price_monitors.items():
                    if not self.monitoring_active:
                        break
                    
                    try:
                        ltp = self.api_client.get_ltp(
                            symbol_info['exchange'],
                            symbol_info['symbol'],
                            symbol_info['token']
                        )
                        
                        if ltp is not None:
                            price_data = RealTimePriceData(
                                symbol=symbol_info['symbol'],
                                ltp=ltp,
                                bid=0.0,  # Would need market data API for bid/ask
                                ask=0.0,
                                volume=0,
                                timestamp=datetime.now()
                            )
                            
                            callback(price_data)
                    
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol_key}: {e}")
                
                # Wait for next interval
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def get_cached_data_info(self) -> Dict[str, Any]:
        """Get information about cached data."""
        with self.cache.lock:
            cache_info = {
                'total_entries': len(self.cache.cache),
                'entries': {}
            }
            
            for key, entry in self.cache.cache.items():
                cache_info['entries'][key] = {
                    'timestamp': entry.timestamp.isoformat(),
                    'ttl_seconds': entry.ttl_seconds,
                    'expired': entry.is_expired(),
                    'data_type': type(entry.data).__name__
                }
            
            return cache_info
    
    def cleanup_cache(self):
        """Clean up expired cache entries."""
        self.cache.cleanup_expired()
        logger.info("Cache cleanup completed")
    
    def invalidate_cache(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match cache keys (None to clear all)
        """
        if pattern is None:
            self.cache.clear()
            logger.info("All cache entries invalidated")
        else:
            with self.cache.lock:
                keys_to_remove = [
                    key for key in self.cache.cache.keys()
                    if pattern in key
                ]
                for key in keys_to_remove:
                    self.cache.invalidate(key)
                logger.info(f"Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")