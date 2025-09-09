"""
DataManager class for market data operations including ATM strike identification,
options chain processing, and expiry detection with performance optimizations.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
import re

from ..api.angel_api_client import AngelAPIClient
from ..api.market_data import MarketDataManager, OptionsChainData
from ..models.trading_models import OptionsChain, Strike, Option, OptionType
from ..config.config_manager import ConfigManager
from .indicators import IndicatorCalculator, HistoricalDataPoint
from ..performance.cache_manager import CacheManager, SmartCache, CacheConfig
from ..performance.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


@dataclass
class ContractMetadata:
    """Contract metadata including lot size and strike spacing"""
    lot_size: int
    strike_spacing: float
    tick_size: float
    underlying_symbol: str
    expiry_date: str


@dataclass
class ATMStrikeResult:
    """Result of ATM strike calculation"""
    atm_strike: float
    distance_from_spot: float
    tie_breaker_used: bool
    available_strikes: List[float]
    spot_price: float


class DataManager:
    """
    DataManager class for market data operations including:
    - ATM strike identification with configurable tie-breaker
    - Options chain processing and validation
    - Current month expiry detection
    - Contract metadata retrieval
    """
    
    def __init__(self, api_client: AngelAPIClient, config_manager: Optional[ConfigManager] = None,
                 cache_manager: Optional[CacheManager] = None, 
                 performance_monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize DataManager with performance optimizations.
        
        Args:
            api_client: Angel API client instance
            config_manager: Configuration manager (optional)
            cache_manager: Cache manager for performance optimization (optional)
            performance_monitor: Performance monitor (optional)
        """
        self.api_client = api_client
        self.config_manager = config_manager
        self.market_data_manager = MarketDataManager(api_client)
        self.indicator_calculator = IndicatorCalculator()
        
        # Performance components
        self.cache_manager = cache_manager or CacheManager(CacheConfig())
        self.smart_cache = SmartCache(self.cache_manager)
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        
        # Default configuration
        self.default_config = {
            'atm_tie_breaker': 'lower',  # 'lower', 'higher', 'nearest'
            'strike_range_multiplier': 0.1,  # 10% range around spot for ATM calculation
            'cache_ttl_seconds': 300,  # 5 minutes cache TTL
            'max_strike_distance': 0.05,  # 5% max distance for ATM consideration
            'default_lot_size': 25,  # Default BANKNIFTY lot size
            'default_strike_spacing': 100.0,  # Default strike spacing
            'enable_caching': True,  # Enable intelligent caching
            'cache_atm_results': True,  # Cache ATM calculation results
        }
        
        # Load configuration if available
        if self.config_manager:
            data_config = self.config_manager.get_section('data_manager', {})
            self.config = {**self.default_config, **data_config}
        else:
            self.config = self.default_config
    
    def get_atm_strike(self, underlying_symbol: str = "BANKNIFTY", 
                      expiry_date: Optional[str] = None,
                      spot_price: Optional[float] = None) -> Optional[ATMStrikeResult]:
        """
        Calculate ATM strike price with configurable tie-breaker and caching.
        
        Args:
            underlying_symbol: Underlying symbol (default: BANKNIFTY)
            expiry_date: Specific expiry date, None for current month
            spot_price: Override spot price (for testing/backtesting)
            
        Returns:
            ATMStrikeResult object or None if calculation fails
        """
        with self.performance_monitor.measure('atm_calculation'):
            try:
                # Get current expiry if not provided
                if not expiry_date:
                    expiry_date = self.get_current_expiry(underlying_symbol)
                    if not expiry_date:
                        logger.error(f"Could not determine expiry for {underlying_symbol}")
                        return None
                
                # Check cache first if enabled
                if self.config.get('cache_atm_results', True) and spot_price is not None:
                    cached_result = self.smart_cache.get_atm_strike(
                        underlying_symbol, expiry_date, spot_price
                    )
                    if cached_result:
                        logger.debug(f"ATM strike retrieved from cache: {cached_result.atm_strike}")
                        return cached_result
                
                # Get options chain data
                options_chain = self.market_data_manager.get_options_chain(
                    underlying_symbol, expiry_date
                )
                
                if not options_chain:
                    logger.error(f"Could not retrieve options chain for {underlying_symbol}")
                    return None
                
                # Use provided spot price or get from options chain
                current_spot = spot_price if spot_price is not None else options_chain.underlying_price
                
                if current_spot <= 0:
                    logger.error(f"Invalid spot price: {current_spot}")
                    return None
                
                # Extract available strikes
                available_strikes = [strike_data['strike'] for strike_data in options_chain.strikes]
                
                if not available_strikes:
                    logger.error("No strikes available in options chain")
                    return None
                
                # Sort strikes
                available_strikes.sort()
                
                # Find ATM strike using configured algorithm
                atm_result = self._calculate_atm_strike(current_spot, available_strikes)
                
                # Cache the result if enabled
                if (atm_result and self.config.get('cache_atm_results', True) and 
                    spot_price is not None):
                    self.smart_cache.cache_atm_strike(
                        underlying_symbol, expiry_date, spot_price, atm_result
                    )
                
                if atm_result:
                    logger.info(f"ATM strike calculated: {atm_result.atm_strike} "
                               f"(spot: {current_spot}, distance: {atm_result.distance_from_spot:.2f}, "
                               f"tie_breaker: {atm_result.tie_breaker_used})")
                
                return atm_result
                
            except Exception as e:
                logger.error(f"Failed to calculate ATM strike for {underlying_symbol}: {e}")
                return None
    
    def _calculate_atm_strike(self, spot_price: float, 
                            available_strikes: List[float]) -> Optional[ATMStrikeResult]:
        """
        Internal method to calculate ATM strike with tie-breaker logic.
        
        Args:
            spot_price: Current spot price
            available_strikes: List of available strike prices (sorted)
            
        Returns:
            ATMStrikeResult or None
        """
        if not available_strikes:
            return None
        
        try:
            # Find the closest strike(s)
            min_distance = float('inf')
            closest_strikes = []
            
            for strike in available_strikes:
                distance = abs(strike - spot_price)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_strikes = [strike]
                elif distance == min_distance:
                    closest_strikes.append(strike)
            
            # Check if distance is within acceptable range
            max_distance_allowed = spot_price * self.config['max_strike_distance']
            if min_distance > max_distance_allowed:
                logger.warning(f"Closest strike distance {min_distance:.2f} exceeds "
                             f"maximum allowed {max_distance_allowed:.2f}")
            
            # Apply tie-breaker if multiple strikes have same distance
            tie_breaker_used = len(closest_strikes) > 1
            atm_strike = self._apply_tie_breaker(spot_price, closest_strikes)
            
            return ATMStrikeResult(
                atm_strike=atm_strike,
                distance_from_spot=min_distance,
                tie_breaker_used=tie_breaker_used,
                available_strikes=available_strikes,
                spot_price=spot_price
            )
            
        except Exception as e:
            logger.error(f"Error in ATM strike calculation: {e}")
            return None
    
    def _apply_tie_breaker(self, spot_price: float, closest_strikes: List[float]) -> float:
        """
        Apply tie-breaker logic when multiple strikes are equidistant from spot.
        
        Args:
            spot_price: Current spot price
            closest_strikes: List of equidistant strikes
            
        Returns:
            Selected ATM strike
        """
        if len(closest_strikes) == 1:
            return closest_strikes[0]
        
        tie_breaker = self.config['atm_tie_breaker']
        
        if tie_breaker == 'lower':
            # Choose the lower strike
            return min(closest_strikes)
        elif tie_breaker == 'higher':
            # Choose the higher strike
            return max(closest_strikes)
        elif tie_breaker == 'nearest':
            # Choose the strike closest to spot (should be same distance, so pick first)
            return closest_strikes[0]
        else:
            logger.warning(f"Unknown tie-breaker method: {tie_breaker}, using 'lower'")
            return min(closest_strikes)
    
    def get_current_expiry(self, underlying_symbol: str = "BANKNIFTY") -> Optional[str]:
        """
        Detect current month expiry date automatically with caching.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            Expiry date string (YYYY-MM-DD) or None
        """
        with self.performance_monitor.measure('expiry_detection'):
            try:
                # Check cache first
                cache_key = f"current_expiry:{underlying_symbol}"
                if self.config.get('enable_caching', True):
                    cached_expiry = self.cache_manager.get(cache_key)
                    if cached_expiry:
                        logger.debug(f"Current expiry retrieved from cache: {cached_expiry}")
                        return cached_expiry
                
                # Use market data manager's expiry detection
                expiry_date = self.market_data_manager._get_current_month_expiry(underlying_symbol)
                
                if expiry_date:
                    # Validate the expiry date
                    if self._validate_expiry_date(expiry_date):
                        # Cache the result (TTL: 1 hour since expiry doesn't change often)
                        if self.config.get('enable_caching', True):
                            self.cache_manager.set(cache_key, expiry_date, ttl=3600)
                        
                        logger.info(f"Current month expiry detected: {expiry_date}")
                        return expiry_date
                    else:
                        logger.error(f"Invalid expiry date detected: {expiry_date}")
                        return None
                
                # Fallback: try alternative expiry detection methods
                fallback_expiry = self._fallback_expiry_detection(underlying_symbol)
                
                # Cache fallback result with shorter TTL
                if fallback_expiry and self.config.get('enable_caching', True):
                    self.cache_manager.set(cache_key, fallback_expiry, ttl=1800)  # 30 minutes
                
                return fallback_expiry
                
            except Exception as e:
                logger.error(f"Failed to detect current expiry for {underlying_symbol}: {e}")
                return None
    
    def _validate_expiry_date(self, expiry_date: str) -> bool:
        """
        Validate expiry date accuracy.
        
        Args:
            expiry_date: Expiry date string (YYYY-MM-DD)
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse the date
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            current_date = datetime.now().date()
            
            # Check if expiry is in the future
            if expiry_dt <= current_date:
                logger.warning(f"Expiry date {expiry_date} is not in the future")
                return False
            
            # Check if expiry is within reasonable range (next 60 days)
            days_to_expiry = (expiry_dt - current_date).days
            if days_to_expiry > 60:
                logger.warning(f"Expiry date {expiry_date} is too far in future ({days_to_expiry} days)")
                return False
            
            # Check if it's a Thursday (typical options expiry day)
            if expiry_dt.weekday() != 3:  # Thursday = 3
                logger.warning(f"Expiry date {expiry_date} is not a Thursday")
                # Don't return False as some expiries might be on different days
            
            return True
            
        except ValueError as e:
            logger.error(f"Invalid expiry date format {expiry_date}: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for data operations."""
        return {
            'cache_stats': self.cache_manager.get_stats(),
            'performance_metrics': self.performance_monitor.get_summary(),
            'config': {
                'caching_enabled': self.config.get('enable_caching', True),
                'cache_atm_results': self.config.get('cache_atm_results', True),
                'cache_ttl': self.config.get('cache_ttl_seconds', 300)
            }
        }
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache_manager.clear()
        logger.info("Data manager cache cleared")
    
    def get_options_chain_cached(self, underlying_symbol: str = "BANKNIFTY",
                                expiry_date: Optional[str] = None) -> Optional[OptionsChainData]:
        """
        Get options chain with intelligent caching.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date (None for current month)
            
        Returns:
            Options chain data or None
        """
        with self.performance_monitor.measure('options_chain_processing'):
            try:
                # Get current expiry if not provided
                if not expiry_date:
                    expiry_date = self.get_current_expiry(underlying_symbol)
                    if not expiry_date:
                        return None
                
                # Check cache first
                if self.config.get('enable_caching', True):
                    cached_chain = self.smart_cache.get_options_chain(underlying_symbol, expiry_date)
                    if cached_chain:
                        logger.debug(f"Options chain retrieved from cache: {underlying_symbol}:{expiry_date}")
                        return cached_chain
                
                # Fetch from API
                options_chain = self.market_data_manager.get_options_chain(
                    underlying_symbol, expiry_date
                )
                
                # Cache the result
                if options_chain and self.config.get('enable_caching', True):
                    self.smart_cache.cache_options_chain(underlying_symbol, expiry_date, options_chain)
                
                return options_chain
                
            except Exception as e:
                logger.error(f"Failed to get options chain for {underlying_symbol}:{expiry_date}: {e}")
                return None
    
    def process_options_chain_efficiently(self, options_chain: OptionsChainData) -> Dict[str, Any]:
        """
        Efficiently process options chain data for analysis.
        
        Args:
            options_chain: Options chain data
            
        Returns:
            Processed options data with key metrics
        """
        with self.performance_monitor.measure('options_chain_processing'):
            try:
                if not options_chain or not options_chain.strikes:
                    return {}
                
                # Pre-allocate lists for efficiency
                call_volumes = []
                put_volumes = []
                call_oi = []
                put_oi = []
                strikes = []
                
                # Single pass through strikes for efficiency
                for strike_data in options_chain.strikes:
                    strike = strike_data['strike']
                    strikes.append(strike)
                    
                    # Call data
                    call_data = strike_data.get('call', {})
                    call_volumes.append(call_data.get('volume', 0))
                    call_oi.append(call_data.get('oi', 0))
                    
                    # Put data
                    put_data = strike_data.get('put', {})
                    put_volumes.append(put_data.get('volume', 0))
                    put_oi.append(put_data.get('oi', 0))
                
                # Calculate aggregated metrics efficiently
                total_call_volume = sum(call_volumes)
                total_put_volume = sum(put_volumes)
                total_call_oi = sum(call_oi)
                total_put_oi = sum(put_oi)
                
                # Find max volume and OI strikes
                max_call_vol_idx = call_volumes.index(max(call_volumes)) if call_volumes else 0
                max_put_vol_idx = put_volumes.index(max(put_volumes)) if put_volumes else 0
                max_call_oi_idx = call_oi.index(max(call_oi)) if call_oi else 0
                max_put_oi_idx = put_oi.index(max(put_oi)) if put_oi else 0
                
                return {
                    'total_strikes': len(strikes),
                    'strike_range': (min(strikes), max(strikes)) if strikes else (0, 0),
                    'total_call_volume': total_call_volume,
                    'total_put_volume': total_put_volume,
                    'total_call_oi': total_call_oi,
                    'total_put_oi': total_put_oi,
                    'pcr_volume': total_put_volume / max(1, total_call_volume),
                    'pcr_oi': total_put_oi / max(1, total_call_oi),
                    'max_call_volume_strike': strikes[max_call_vol_idx] if strikes else 0,
                    'max_put_volume_strike': strikes[max_put_vol_idx] if strikes else 0,
                    'max_call_oi_strike': strikes[max_call_oi_idx] if strikes else 0,
                    'max_put_oi_strike': strikes[max_put_oi_idx] if strikes else 0,
                    'underlying_price': options_chain.underlying_price,
                    'expiry_date': options_chain.expiry_date
                }
                
            except Exception as e:
                logger.error(f"Error processing options chain efficiently: {e}")
                return {}
    
    def _fallback_expiry_detection(self, underlying_symbol: str) -> Optional[str]:
        """
        Fallback mechanism for expiry detection with multiple strategies.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            Expiry date string or None
        """
        try:
            logger.info(f"Starting fallback expiry detection for {underlying_symbol}")
            
            # Method 1: Calculate next Thursday (most common expiry day)
            expiry_candidate = self._get_next_thursday()
            if self._test_expiry_candidate(underlying_symbol, expiry_candidate):
                logger.info(f"Fallback expiry detection (next Thursday): {expiry_candidate}")
                return expiry_candidate
            
            # Method 2: Try next week's Thursday
            next_week_thursday = datetime.strptime(expiry_candidate, '%Y-%m-%d').date() + timedelta(days=7)
            expiry_candidate = next_week_thursday.strftime('%Y-%m-%d')
            if self._test_expiry_candidate(underlying_symbol, expiry_candidate):
                logger.info(f"Fallback expiry detection (next week Thursday): {expiry_candidate}")
                return expiry_candidate
            
            # Method 3: Try last Thursday of current month
            expiry_candidate = self._get_last_thursday_of_month()
            if expiry_candidate and self._test_expiry_candidate(underlying_symbol, expiry_candidate):
                logger.info(f"Fallback expiry detection (last Thursday): {expiry_candidate}")
                return expiry_candidate
            
            # Method 4: Try last Thursday of next month
            expiry_candidate = self._get_last_thursday_of_next_month()
            if expiry_candidate and self._test_expiry_candidate(underlying_symbol, expiry_candidate):
                logger.info(f"Fallback expiry detection (next month): {expiry_candidate}")
                return expiry_candidate
            
            # Method 5: Search through known expiry patterns
            expiry_candidate = self._search_known_expiry_patterns(underlying_symbol)
            if expiry_candidate:
                logger.info(f"Fallback expiry detection (pattern search): {expiry_candidate}")
                return expiry_candidate
            
            logger.error("All fallback expiry detection methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Fallback expiry detection failed: {e}")
            return None
    
    def _get_next_thursday(self) -> str:
        """Get the next Thursday date."""
        current_date = datetime.now().date()
        days_ahead = 3 - current_date.weekday()  # Thursday = 3
        
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_thursday = current_date + timedelta(days=days_ahead)
        return next_thursday.strftime('%Y-%m-%d')
    
    def _get_last_thursday_of_month(self, target_month: Optional[int] = None, 
                                   target_year: Optional[int] = None) -> Optional[str]:
        """
        Get the last Thursday of the specified month.
        
        Args:
            target_month: Target month (None for current month)
            target_year: Target year (None for current year)
            
        Returns:
            Date string or None
        """
        try:
            current_date = datetime.now().date()
            month = target_month or current_date.month
            year = target_year or current_date.year
            
            # Find the last day of the month
            if month == 12:
                last_day = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)
            
            # Find the last Thursday
            days_back = (last_day.weekday() - 3) % 7
            last_thursday = last_day - timedelta(days=days_back)
            
            # Only return if it's in the future
            if last_thursday > current_date:
                return last_thursday.strftime('%Y-%m-%d')
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating last Thursday of month: {e}")
            return None
    
    def _get_last_thursday_of_next_month(self) -> Optional[str]:
        """Get the last Thursday of next month."""
        current_date = datetime.now().date()
        next_month = current_date.month + 1 if current_date.month < 12 else 1
        next_year = current_date.year if current_date.month < 12 else current_date.year + 1
        
        return self._get_last_thursday_of_month(next_month, next_year)
    
    def _test_expiry_candidate(self, underlying_symbol: str, expiry_date: str) -> bool:
        """
        Test if an expiry date candidate has valid options data.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date to test
            
        Returns:
            True if valid options data exists
        """
        try:
            # Validate date format and future date
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            if expiry_dt <= datetime.now().date():
                return False
            
            # Try to get options chain for this date
            options_chain = self.market_data_manager.get_options_chain(
                underlying_symbol, expiry_date
            )
            
            # Check if we have valid options data
            if options_chain and options_chain.strikes:
                # Additional validation: check if we have reasonable number of strikes
                if len(options_chain.strikes) >= 5:  # Minimum reasonable strikes
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Expiry candidate {expiry_date} test failed: {e}")
            return False
    
    def _search_known_expiry_patterns(self, underlying_symbol: str) -> Optional[str]:
        """
        Search for expiry dates using known patterns for Indian options.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            Expiry date string or None
        """
        try:
            # For Indian options, expiries are typically on last Thursday of month
            # Try current month and next few months
            current_date = datetime.now().date()
            
            for month_offset in range(0, 4):  # Check current + next 3 months
                target_month = current_date.month + month_offset
                target_year = current_date.year
                
                # Handle year rollover
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                
                expiry_candidate = self._get_last_thursday_of_month(target_month, target_year)
                
                if expiry_candidate and self._test_expiry_candidate(underlying_symbol, expiry_candidate):
                    return expiry_candidate
            
            return None
            
        except Exception as e:
            logger.error(f"Error in known expiry pattern search: {e}")
            return None
    
    def get_all_available_expiries(self, underlying_symbol: str = "BANKNIFTY") -> List[str]:
        """
        Get all available expiry dates for the underlying.
        
        Args:
            underlying_symbol: Underlying symbol
            
        Returns:
            List of expiry date strings sorted by date
        """
        try:
            # Search for instruments to find all expiry dates
            search_results = self.api_client.search_instruments("NFO", underlying_symbol)
            
            if not search_results:
                logger.warning(f"No instruments found for {underlying_symbol}")
                return []
            
            # Extract expiry dates from trading symbols
            expiry_dates = set()
            for instrument in search_results:
                symbol = instrument.get('tradingsymbol', '')
                if 'CE' in symbol or 'PE' in symbol:
                    expiry_part = self.market_data_manager._extract_expiry_from_symbol(symbol)
                    if expiry_part:
                        # Validate the expiry date
                        try:
                            expiry_dt = datetime.strptime(expiry_part, '%Y-%m-%d').date()
                            if expiry_dt > datetime.now().date():  # Only future expiries
                                expiry_dates.add(expiry_part)
                        except ValueError:
                            continue
            
            # Sort expiry dates
            sorted_expiries = sorted(list(expiry_dates))
            
            logger.info(f"Found {len(sorted_expiries)} available expiries for {underlying_symbol}")
            return sorted_expiries
            
        except Exception as e:
            logger.error(f"Failed to get available expiries for {underlying_symbol}: {e}")
            return []
    
    def get_nearest_expiry(self, underlying_symbol: str = "BANKNIFTY", 
                          min_days_to_expiry: int = 0) -> Optional[str]:
        """
        Get the nearest expiry date with minimum days to expiry.
        
        Args:
            underlying_symbol: Underlying symbol
            min_days_to_expiry: Minimum days to expiry (default: 0)
            
        Returns:
            Nearest expiry date string or None
        """
        try:
            available_expiries = self.get_all_available_expiries(underlying_symbol)
            
            if not available_expiries:
                return None
            
            current_date = datetime.now().date()
            
            for expiry_str in available_expiries:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                days_to_expiry = (expiry_date - current_date).days
                
                if days_to_expiry >= min_days_to_expiry:
                    logger.info(f"Nearest expiry: {expiry_str} ({days_to_expiry} days)")
                    return expiry_str
            
            logger.warning(f"No expiry found with minimum {min_days_to_expiry} days")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get nearest expiry: {e}")
            return None
    
    def get_contract_metadata(self, underlying_symbol: str = "BANKNIFTY",
                            expiry_date: Optional[str] = None) -> Optional[ContractMetadata]:
        """
        Retrieve contract metadata including lot size and strike spacing.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date (None for current month)
            
        Returns:
            ContractMetadata object or None
        """
        try:
            # Get current expiry if not provided
            if not expiry_date:
                expiry_date = self.get_current_expiry(underlying_symbol)
                if not expiry_date:
                    logger.error(f"Could not determine expiry for {underlying_symbol}")
                    return None
            
            # Get options chain to analyze contract specifications
            options_chain = self.market_data_manager.get_options_chain(
                underlying_symbol, expiry_date
            )
            
            if not options_chain or not options_chain.strikes:
                logger.error(f"No options data available for metadata extraction")
                return None
            
            # Extract lot size from first available option
            lot_size = self._extract_lot_size(options_chain)
            
            # Calculate strike spacing
            strike_spacing = self._calculate_strike_spacing(options_chain.strikes)
            
            # Default tick size (would need to be retrieved from exchange specs)
            tick_size = 0.05  # Default for BANKNIFTY options
            
            metadata = ContractMetadata(
                lot_size=lot_size,
                strike_spacing=strike_spacing,
                tick_size=tick_size,
                underlying_symbol=underlying_symbol,
                expiry_date=expiry_date
            )
            
            logger.info(f"Contract metadata: lot_size={lot_size}, "
                       f"strike_spacing={strike_spacing}, expiry={expiry_date}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get contract metadata: {e}")
            return None
    
    def _extract_lot_size(self, options_chain: OptionsChainData) -> int:
        """
        Extract lot size from options chain data.
        
        Args:
            options_chain: Options chain data
            
        Returns:
            Lot size (default if not found)
        """
        try:
            # For BANKNIFTY, lot size is typically 25
            # This could be enhanced to query from API if available
            if options_chain.underlying_symbol == "BANKNIFTY":
                return 25
            
            # Default fallback
            return self.config['default_lot_size']
            
        except Exception as e:
            logger.error(f"Error extracting lot size: {e}")
            return self.config['default_lot_size']
    
    def _calculate_strike_spacing(self, strikes_data: List[Dict[str, Any]]) -> float:
        """
        Calculate strike spacing from available strikes.
        
        Args:
            strikes_data: List of strike data from options chain
            
        Returns:
            Strike spacing
        """
        try:
            if len(strikes_data) < 2:
                return self.config['default_strike_spacing']
            
            # Get sorted strike prices
            strikes = sorted([strike_data['strike'] for strike_data in strikes_data])
            
            # Calculate differences between consecutive strikes
            spacings = []
            for i in range(1, len(strikes)):
                spacing = strikes[i] - strikes[i-1]
                if spacing > 0:
                    spacings.append(spacing)
            
            if not spacings:
                return self.config['default_strike_spacing']
            
            # Find the most common spacing (mode)
            from collections import Counter
            spacing_counts = Counter(spacings)
            most_common_spacing = spacing_counts.most_common(1)[0][0]
            
            return most_common_spacing
            
        except Exception as e:
            logger.error(f"Error calculating strike spacing: {e}")
            return self.config['default_strike_spacing']
    
    def validate_options_chain(self, options_chain: OptionsChainData) -> Tuple[bool, List[str]]:
        """
        Validate options chain data for completeness and accuracy.
        
        Args:
            options_chain: Options chain data to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            # Basic data validation
            if not options_chain.underlying_symbol:
                issues.append("Missing underlying symbol")
            
            if options_chain.underlying_price <= 0:
                issues.append(f"Invalid underlying price: {options_chain.underlying_price}")
            
            if not options_chain.expiry_date:
                issues.append("Missing expiry date")
            
            if not options_chain.strikes:
                issues.append("No strikes available")
                return False, issues
            
            # Validate expiry date format and value
            try:
                expiry_dt = datetime.strptime(options_chain.expiry_date, '%Y-%m-%d').date()
                if expiry_dt <= datetime.now().date():
                    issues.append(f"Expiry date {options_chain.expiry_date} is in the past")
            except ValueError:
                issues.append(f"Invalid expiry date format: {options_chain.expiry_date}")
            
            # Validate strikes data
            valid_strikes = 0
            for i, strike_data in enumerate(options_chain.strikes):
                strike_issues = self._validate_strike_data(strike_data, i)
                if strike_issues:
                    issues.extend(strike_issues)
                else:
                    valid_strikes += 1
            
            if valid_strikes == 0:
                issues.append("No valid strikes found")
            elif valid_strikes < len(options_chain.strikes) * 0.5:
                issues.append(f"Only {valid_strikes}/{len(options_chain.strikes)} strikes are valid")
            
            # Validate ATM strike
            if options_chain.atm_strike:
                atm_found = any(
                    strike_data['strike'] == options_chain.atm_strike 
                    for strike_data in options_chain.strikes
                )
                if not atm_found:
                    issues.append(f"ATM strike {options_chain.atm_strike} not found in strikes list")
            
            # Check for reasonable strike range around spot price
            strikes = [strike_data['strike'] for strike_data in options_chain.strikes]
            min_strike = min(strikes)
            max_strike = max(strikes)
            spot = options_chain.underlying_price
            
            if spot < min_strike or spot > max_strike:
                issues.append(f"Spot price {spot} is outside strike range [{min_strike}, {max_strike}]")
            
            is_valid = len(issues) == 0
            
            if is_valid:
                logger.info(f"Options chain validation passed for {options_chain.underlying_symbol}")
            else:
                logger.warning(f"Options chain validation failed with {len(issues)} issues")
            
            return is_valid, issues
            
        except Exception as e:
            logger.error(f"Error during options chain validation: {e}")
            issues.append(f"Validation error: {str(e)}")
            return False, issues
    
    def _validate_strike_data(self, strike_data: Dict[str, Any], index: int) -> List[str]:
        """
        Validate individual strike data.
        
        Args:
            strike_data: Strike data dictionary
            index: Strike index for error reporting
            
        Returns:
            List of validation issues
        """
        issues = []
        
        try:
            # Check strike price
            strike = strike_data.get('strike', 0)
            if strike <= 0:
                issues.append(f"Strike {index}: Invalid strike price {strike}")
            
            # Check call option data
            call_data = strike_data.get('call')
            if call_data:
                call_issues = self._validate_option_data(call_data, f"Strike {index} Call")
                issues.extend(call_issues)
            
            # Check put option data
            put_data = strike_data.get('put')
            if put_data:
                put_issues = self._validate_option_data(put_data, f"Strike {index} Put")
                issues.extend(put_issues)
            
            # At least one option should be present
            if not call_data and not put_data:
                issues.append(f"Strike {index}: No call or put option data available")
            
        except Exception as e:
            issues.append(f"Strike {index}: Validation error - {str(e)}")
        
        return issues
    
    def _validate_option_data(self, option_data: Dict[str, Any], context: str) -> List[str]:
        """
        Validate individual option data.
        
        Args:
            option_data: Option data dictionary
            context: Context string for error reporting
            
        Returns:
            List of validation issues
        """
        issues = []
        
        try:
            # Check required fields
            required_fields = ['symbol', 'token', 'ltp']
            for field in required_fields:
                if field not in option_data:
                    issues.append(f"{context}: Missing {field}")
                elif not option_data[field]:
                    issues.append(f"{context}: Empty {field}")
            
            # Check LTP value
            ltp = option_data.get('ltp', 0)
            if ltp < 0:
                issues.append(f"{context}: Negative LTP {ltp}")
            elif ltp == 0:
                issues.append(f"{context}: Zero LTP (may indicate no trading)")
            
        except Exception as e:
            issues.append(f"{context}: Validation error - {str(e)}")
        
        return issues
    
    def get_options_chain_summary(self, underlying_symbol: str = "BANKNIFTY",
                                expiry_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a summary of the options chain for analysis.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date (None for current month)
            
        Returns:
            Summary dictionary or None
        """
        try:
            options_chain = self.market_data_manager.get_options_chain(
                underlying_symbol, expiry_date
            )
            
            if not options_chain:
                return None
            
            # Calculate ATM strike
            atm_result = self.get_atm_strike(underlying_symbol, expiry_date)
            
            # Get contract metadata
            metadata = self.get_contract_metadata(underlying_symbol, expiry_date)
            
            # Calculate summary statistics
            strikes = [strike_data['strike'] for strike_data in options_chain.strikes]
            
            summary = {
                'underlying_symbol': options_chain.underlying_symbol,
                'underlying_price': options_chain.underlying_price,
                'expiry_date': options_chain.expiry_date,
                'timestamp': options_chain.timestamp.isoformat(),
                'total_strikes': len(strikes),
                'strike_range': {
                    'min': min(strikes) if strikes else 0,
                    'max': max(strikes) if strikes else 0
                },
                'atm_info': {
                    'atm_strike': atm_result.atm_strike if atm_result else None,
                    'distance_from_spot': atm_result.distance_from_spot if atm_result else None,
                    'tie_breaker_used': atm_result.tie_breaker_used if atm_result else None
                },
                'contract_metadata': {
                    'lot_size': metadata.lot_size if metadata else None,
                    'strike_spacing': metadata.strike_spacing if metadata else None,
                    'tick_size': metadata.tick_size if metadata else None
                },
                'validation': {}
            }
            
            # Add validation results
            is_valid, issues = self.validate_options_chain(options_chain)
            summary['validation'] = {
                'is_valid': is_valid,
                'issues': issues
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate options chain summary: {e}")
            return None
    
    def get_historical_data_with_indicators(self, symbol: str, token: str, exchange: str,
                                          interval: str = "ONE_DAY", days_back: int = 30,
                                          indicators: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Get historical data with calculated indicators.
        
        Args:
            symbol: Trading symbol
            token: Instrument token
            exchange: Exchange name
            interval: Data interval
            days_back: Number of days to fetch
            indicators: List of indicators to calculate
            
        Returns:
            Dictionary with historical data and indicators
        """
        try:
            # Calculate date range
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Get historical data from market data manager
            raw_data = self.market_data_manager.get_historical_data(
                symbol, token, exchange, interval, start_date, end_date
            )
            
            if not raw_data:
                logger.error(f"No historical data retrieved for {symbol}")
                return None
            
            # Convert to HistoricalDataPoint format
            historical_data = []
            for data_point in raw_data:
                historical_data.append(HistoricalDataPoint(
                    timestamp=data_point.timestamp,
                    open=data_point.open,
                    high=data_point.high,
                    low=data_point.low,
                    close=data_point.close,
                    volume=data_point.volume
                ))
            
            # Validate data quality
            quality_report = self.indicator_calculator.validate_data_quality(historical_data)
            
            if not quality_report['valid']:
                logger.warning(f"Data quality issues for {symbol}: {quality_report['issues']}")
            
            # Calculate indicators
            if indicators is None:
                indicators = ['sma_short', 'sma_long', 'ema_short', 'ema_long', 'atr']
            
            indicator_results = self.indicator_calculator.calculate_multiple_indicators(
                historical_data, indicators
            )
            
            # Generate summary
            summary = self.indicator_calculator.get_indicator_summary(historical_data)
            
            result = {
                'symbol': symbol,
                'exchange': exchange,
                'interval': interval,
                'data_points': len(historical_data),
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'raw_data': [
                    {
                        'timestamp': point.timestamp.isoformat(),
                        'open': point.open,
                        'high': point.high,
                        'low': point.low,
                        'close': point.close,
                        'volume': point.volume
                    }
                    for point in historical_data
                ],
                'indicators': {
                    name: {
                        'values': result.values,
                        'timestamps': [ts.isoformat() for ts in result.timestamps],
                        'parameters': result.parameters
                    }
                    for name, result in indicator_results.items()
                },
                'summary': summary,
                'data_quality': quality_report
            }
            
            logger.info(f"Retrieved historical data with {len(indicators)} indicators for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get historical data with indicators for {symbol}: {e}")
            return None
    
    def analyze_option_liquidity(self, options_chain: OptionsChainData, 
                               min_volume: int = 100, 
                               max_spread_pct: float = 5.0) -> Dict[str, Any]:
        """
        Analyze option liquidity based on volume and bid-ask spreads.
        
        Args:
            options_chain: Options chain data
            min_volume: Minimum volume threshold
            max_spread_pct: Maximum acceptable spread percentage
            
        Returns:
            Liquidity analysis results
        """
        try:
            if not options_chain or not options_chain.strikes:
                return {'error': 'No options chain data provided'}
            
            liquid_strikes = []
            illiquid_strikes = []
            spread_data = []
            volume_data = []
            
            for strike_data in options_chain.strikes:
                strike_price = strike_data['strike']
                strike_analysis = {
                    'strike': strike_price,
                    'call_liquid': False,
                    'put_liquid': False,
                    'call_spread_pct': None,
                    'put_spread_pct': None,
                    'call_volume': 0,
                    'put_volume': 0
                }
                
                # Analyze call option
                call_data = strike_data.get('call')
                if call_data:
                    call_ltp = call_data.get('ltp', 0)
                    # For real implementation, would need bid/ask from API
                    # Using estimated spread for now
                    estimated_spread = max(0.05, call_ltp * 0.02)  # 2% or minimum 0.05
                    spread_pct = (estimated_spread / call_ltp * 100) if call_ltp > 0 else 100
                    
                    strike_analysis['call_spread_pct'] = spread_pct
                    strike_analysis['call_volume'] = 0  # Would need from API
                    
                    if spread_pct <= max_spread_pct:
                        strike_analysis['call_liquid'] = True
                
                # Analyze put option
                put_data = strike_data.get('put')
                if put_data:
                    put_ltp = put_data.get('ltp', 0)
                    estimated_spread = max(0.05, put_ltp * 0.02)
                    spread_pct = (estimated_spread / put_ltp * 100) if put_ltp > 0 else 100
                    
                    strike_analysis['put_spread_pct'] = spread_pct
                    strike_analysis['put_volume'] = 0  # Would need from API
                    
                    if spread_pct <= max_spread_pct:
                        strike_analysis['put_liquid'] = True
                
                # Categorize strike
                if strike_analysis['call_liquid'] or strike_analysis['put_liquid']:
                    liquid_strikes.append(strike_analysis)
                else:
                    illiquid_strikes.append(strike_analysis)
                
                # Collect data for analysis
                if strike_analysis['call_spread_pct'] is not None:
                    spread_data.append(strike_analysis['call_spread_pct'])
                if strike_analysis['put_spread_pct'] is not None:
                    spread_data.append(strike_analysis['put_spread_pct'])
            
            # Calculate summary statistics
            total_strikes = len(options_chain.strikes)
            liquid_count = len(liquid_strikes)
            liquidity_ratio = liquid_count / total_strikes if total_strikes > 0 else 0
            
            avg_spread_pct = sum(spread_data) / len(spread_data) if spread_data else 0
            
            analysis = {
                'total_strikes': total_strikes,
                'liquid_strikes': liquid_count,
                'illiquid_strikes': len(illiquid_strikes),
                'liquidity_ratio': liquidity_ratio,
                'average_spread_pct': avg_spread_pct,
                'criteria': {
                    'min_volume': min_volume,
                    'max_spread_pct': max_spread_pct
                },
                'liquid_strikes_detail': liquid_strikes,
                'illiquid_strikes_detail': illiquid_strikes,
                'liquidity_score': min(100, max(0, (1 - avg_spread_pct / max_spread_pct) * 100))
            }
            
            logger.info(f"Liquidity analysis: {liquid_count}/{total_strikes} strikes liquid "
                       f"(ratio: {liquidity_ratio:.2f}, avg spread: {avg_spread_pct:.2f}%)")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze option liquidity: {e}")
            return {'error': f'Analysis failed: {str(e)}'}
    
    def get_trading_signals(self, underlying_symbol: str = "BANKNIFTY",
                          expiry_date: Optional[str] = None,
                          lookback_days: int = 20) -> Dict[str, Any]:
        """
        Generate trading signals based on technical indicators and options data.
        
        Args:
            underlying_symbol: Underlying symbol
            expiry_date: Expiry date (None for current month)
            lookback_days: Days of historical data to analyze
            
        Returns:
            Trading signals and analysis
        """
        try:
            # Get options chain
            options_chain = self.market_data_manager.get_options_chain(
                underlying_symbol, expiry_date
            )
            
            if not options_chain:
                return {'error': 'Could not retrieve options chain'}
            
            # Get ATM strike
            atm_result = self.get_atm_strike(underlying_symbol, expiry_date)
            
            if not atm_result:
                return {'error': 'Could not calculate ATM strike'}
            
            # For underlying analysis, we would need the underlying instrument details
            # This is a simplified version focusing on options chain analysis
            
            signals = {
                'timestamp': datetime.now().isoformat(),
                'underlying_symbol': underlying_symbol,
                'underlying_price': options_chain.underlying_price,
                'expiry_date': options_chain.expiry_date,
                'atm_strike': atm_result.atm_strike,
                'signals': {},
                'analysis': {}
            }
            
            # ATM-based signals
            distance_pct = (atm_result.distance_from_spot / options_chain.underlying_price) * 100
            
            if distance_pct < 0.5:  # Very close to ATM
                signals['signals']['atm_proximity'] = 'very_close'
            elif distance_pct < 1.0:
                signals['signals']['atm_proximity'] = 'close'
            else:
                signals['signals']['atm_proximity'] = 'far'
            
            # Liquidity analysis
            liquidity_analysis = self.analyze_option_liquidity(options_chain)
            signals['analysis']['liquidity'] = liquidity_analysis
            
            # Options chain structure analysis
            strikes = [strike_data['strike'] for strike_data in options_chain.strikes]
            strike_range = max(strikes) - min(strikes)
            strike_coverage_pct = (strike_range / options_chain.underlying_price) * 100
            
            signals['analysis']['strike_coverage'] = {
                'range': strike_range,
                'coverage_pct': strike_coverage_pct,
                'total_strikes': len(strikes)
            }
            
            # Generate basic trading signals
            if liquidity_analysis.get('liquidity_ratio', 0) > 0.5:
                signals['signals']['liquidity_signal'] = 'good'
            elif liquidity_analysis.get('liquidity_ratio', 0) > 0.3:
                signals['signals']['liquidity_signal'] = 'moderate'
            else:
                signals['signals']['liquidity_signal'] = 'poor'
            
            # Time to expiry analysis
            if expiry_date:
                try:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                    days_to_expiry = (expiry_dt - datetime.now().date()).days
                    
                    if days_to_expiry <= 1:
                        signals['signals']['time_decay'] = 'high'
                    elif days_to_expiry <= 7:
                        signals['signals']['time_decay'] = 'moderate'
                    else:
                        signals['signals']['time_decay'] = 'low'
                    
                    signals['analysis']['days_to_expiry'] = days_to_expiry
                except ValueError:
                    pass
            
            logger.info(f"Generated trading signals for {underlying_symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Failed to generate trading signals: {e}")
            return {'error': f'Signal generation failed: {str(e)}'}
    
    def cleanup_cache(self):
        """Clean up cached data in market data manager"""
        try:
            self.market_data_manager.cleanup_cache()
            logger.info("DataManager cache cleanup completed")
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached data"""
        try:
            return self.market_data_manager.get_cached_data_info()
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {}