"""
Short Straddle/Strangle Strategy implementation for Bank Nifty Options Trading.

This strategy sells ATM or near-ATM call and put options to profit from low volatility
and time decay, with IV rank and liquidity checks for optimal entry conditions.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, time

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from ..data.indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class StraddleStrategy(BaseStrategy):
    """
    Short Straddle/Strangle Strategy.
    
    Sells ATM call and put options (straddle) or slightly OTM options (strangle)
    when IV rank is high and market conditions favor low volatility.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Straddle Strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("StraddleStrategy", config)
        
        # Strategy-specific parameters
        self.min_iv_rank = config.get('min_iv_rank', 70.0)  # Minimum IV rank for entry
        self.max_iv_rank = config.get('max_iv_rank', 95.0)  # Maximum IV rank (too high = risky)
        self.min_iv_percentile = config.get('min_iv_percentile', 60.0)  # Alternative to IV rank
        self.strategy_type = config.get('strategy_type', 'straddle')  # 'straddle' or 'strangle'
        
        # Strangle-specific parameters
        self.strangle_otm_distance = config.get('strangle_otm_distance', 100.0)  # Points OTM
        self.strangle_otm_percentage = config.get('strangle_otm_percentage', 2.0)  # % OTM
        
        # Time-based parameters
        self.min_dte = config.get('min_dte', 0)  # Minimum days to expiry
        self.max_dte = config.get('max_dte', 7)  # Maximum days to expiry (weekly options)
        self.early_exit_minutes = config.get('early_exit_minutes', 60)  # Minutes before close
        self.no_entry_minutes = config.get('no_entry_minutes', 90)  # No entry X minutes before close
        
        # Risk and position sizing
        self.max_loss_multiplier = config.get('max_loss_multiplier', 2.0)  # Max loss as multiple of premium
        self.profit_target_percentage = config.get('profit_target_percentage', 50.0)  # % of premium
        self.delta_neutral_threshold = config.get('delta_neutral_threshold', 0.1)  # Max net delta
        
        # Market condition filters
        self.min_underlying_price = config.get('min_underlying_price', 40000.0)  # Min BANKNIFTY price
        self.max_underlying_price = config.get('max_underlying_price', 60000.0)  # Max BANKNIFTY price
        self.trend_filter_enabled = config.get('trend_filter_enabled', True)
        self.trend_lookback_periods = config.get('trend_lookback_periods', 20)
        
        # Liquidity requirements (stricter for short options)
        self.min_volume = config.get('min_volume', 500)  # Higher volume requirement
        self.min_open_interest = config.get('min_open_interest', 1000)  # Higher OI requirement
        self.max_bid_ask_spread_pct = config.get('max_bid_ask_spread_pct', 3.0)  # Tighter spread
        
        self.indicator_calculator = IndicatorCalculator()
        
        logger.info(f"Initialized StraddleStrategy: type={self.strategy_type}, "
                   f"IV_rank_range=[{self.min_iv_rank}, {self.max_iv_rank}]")
    
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions for straddle/strangle entry.
        
        Args:
            market_data: Market data dictionary containing:
                - options_chain: OptionsChain object
                - historical_data: Historical price data
                - indicators: Technical indicators
                - current_time: Current timestamp
                
        Returns:
            TradingSignal if conditions are met, None otherwise
        """
        try:
            # Extract market data
            options_chain = market_data.get('options_chain')
            historical_data = market_data.get('historical_data', [])
            indicators = market_data.get('indicators', {})
            current_time = market_data.get('current_time', datetime.now())
            
            if not options_chain:
                logger.debug("No options chain data available")
                return None
            
            # Check basic market conditions
            if not self._check_market_conditions(options_chain, current_time):
                return None
            
            # Check volatility conditions
            iv_metrics = self._calculate_iv_metrics(options_chain, historical_data)
            if not self._check_volatility_conditions(iv_metrics):
                return None
            
            # Check trend conditions
            if self.trend_filter_enabled:
                trend_metrics = self._calculate_trend_metrics(historical_data, indicators)
                if not self._check_trend_conditions(trend_metrics):
                    return None
            
            # Select strikes based on strategy type
            if self.strategy_type == 'straddle':
                strikes, option_types = self._select_straddle_strikes(options_chain)
            else:  # strangle
                strikes, option_types = self._select_strangle_strikes(options_chain)
            
            if not strikes:
                logger.debug("No suitable strikes found")
                return None
            
            # Validate option liquidity
            if not self._validate_option_liquidity(options_chain, strikes, option_types):
                return None
            
            # Calculate position sizing and risk metrics
            quantities = self._calculate_position_sizing(options_chain, strikes, option_types)
            if not quantities:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                options_chain, iv_metrics, trend_metrics if self.trend_filter_enabled else {}
            )
            
            # Create trading signal
            signal = TradingSignal(
                strategy_name=self.name,
                signal_type=SignalType.STRADDLE if self.strategy_type == 'straddle' else SignalType.STRANGLE,
                underlying=options_chain.underlying_symbol,
                strikes=strikes,
                option_types=option_types,
                quantities=quantities,
                confidence=confidence,
                timestamp=current_time,
                expiry_date=options_chain.expiry_date,
                target_pnl=self.target_profit_per_trade,
                stop_loss=-self.max_loss_per_trade,
                metadata={
                    'strategy_type': self.strategy_type,
                    'iv_rank': iv_metrics.get('iv_rank', 0),
                    'iv_percentile': iv_metrics.get('iv_percentile', 0),
                    'atm_strike': options_chain.atm_strike,
                    'underlying_price': options_chain.underlying_price,
                    'premium_collected': self._estimate_premium_collected(options_chain, strikes, option_types),
                    'max_loss_estimate': self._estimate_max_loss(options_chain, strikes, option_types),
                    'delta_neutral': self._check_delta_neutral(options_chain, strikes, option_types),
                    'days_to_expiry': self._calculate_days_to_expiry(options_chain.expiry_date)
                }
            )
            
            logger.info(f"Generated {self.strategy_type} signal: strikes={strikes}, "
                       f"confidence={confidence:.2f}, IV_rank={iv_metrics.get('iv_rank', 0):.1f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating straddle strategy: {e}")
            return None
    
    def _check_market_conditions(self, options_chain: OptionsChain, current_time: datetime) -> bool:
        """Check basic market conditions for strategy entry."""
        try:
            # Check underlying price range
            if not (self.min_underlying_price <= options_chain.underlying_price <= self.max_underlying_price):
                logger.debug(f"Underlying price {options_chain.underlying_price} outside range "
                           f"[{self.min_underlying_price}, {self.max_underlying_price}]")
                return False
            
            # Check time to expiry
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if not (self.min_dte <= days_to_expiry <= self.max_dte):
                logger.debug(f"Days to expiry {days_to_expiry} outside range [{self.min_dte}, {self.max_dte}]")
                return False
            
            # Check time until market close (no entry too close to close)
            current_time_only = current_time.time()
            no_entry_time = time(15, 30 - self.no_entry_minutes // 60, 
                               30 - (self.no_entry_minutes % 60))
            
            if current_time_only >= no_entry_time:
                logger.debug(f"Too close to market close for new entries: {current_time_only}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False
    
    def _calculate_iv_metrics(self, options_chain: OptionsChain, 
                            historical_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate implied volatility metrics."""
        try:
            iv_metrics = {}
            
            # Get ATM options IV
            atm_call_iv = 0.0
            atm_put_iv = 0.0
            
            for strike_data in options_chain.strikes:
                if strike_data['strike'] == options_chain.atm_strike:
                    call_data = strike_data.get('call', {})
                    put_data = strike_data.get('put', {})
                    
                    atm_call_iv = call_data.get('iv', 0.0)
                    atm_put_iv = put_data.get('iv', 0.0)
                    break
            
            # Average ATM IV
            atm_iv = (atm_call_iv + atm_put_iv) / 2 if (atm_call_iv > 0 and atm_put_iv > 0) else 0.0
            iv_metrics['atm_iv'] = atm_iv
            
            # Calculate IV rank and percentile if historical data available
            if historical_data and len(historical_data) >= 252:  # At least 1 year of data
                # Calculate historical volatility for IV rank comparison
                historical_vols = []
                for i in range(len(historical_data) - 20):  # 20-day rolling HV
                    period_data = historical_data[i:i+20]
                    hv = self.indicator_calculator.calculate_historical_volatility(period_data, 20)
                    if hv > 0:
                        historical_vols.append(hv * 100)  # Convert to percentage
                
                if historical_vols:
                    # IV rank: where current IV stands relative to 1-year range
                    min_hv = min(historical_vols)
                    max_hv = max(historical_vols)
                    if max_hv > min_hv:
                        iv_rank = ((atm_iv - min_hv) / (max_hv - min_hv)) * 100
                        iv_metrics['iv_rank'] = max(0, min(100, iv_rank))
                    
                    # IV percentile: percentage of days IV was below current level
                    below_current = sum(1 for hv in historical_vols if hv < atm_iv)
                    iv_percentile = (below_current / len(historical_vols)) * 100
                    iv_metrics['iv_percentile'] = iv_percentile
            
            # If no historical data, use simplified IV assessment
            if 'iv_rank' not in iv_metrics:
                # Rough IV assessment based on absolute levels
                if atm_iv > 25:
                    iv_metrics['iv_rank'] = 80.0  # High IV
                elif atm_iv > 20:
                    iv_metrics['iv_rank'] = 60.0  # Medium-high IV
                elif atm_iv > 15:
                    iv_metrics['iv_rank'] = 40.0  # Medium IV
                else:
                    iv_metrics['iv_rank'] = 20.0  # Low IV
                
                iv_metrics['iv_percentile'] = iv_metrics['iv_rank']
            
            return iv_metrics
            
        except Exception as e:
            logger.error(f"Error calculating IV metrics: {e}")
            return {'atm_iv': 0.0, 'iv_rank': 0.0, 'iv_percentile': 0.0}
    
    def _check_volatility_conditions(self, iv_metrics: Dict[str, float]) -> bool:
        """Check if volatility conditions favor short options strategy."""
        try:
            iv_rank = iv_metrics.get('iv_rank', 0.0)
            iv_percentile = iv_metrics.get('iv_percentile', 0.0)
            
            # Check IV rank
            if not (self.min_iv_rank <= iv_rank <= self.max_iv_rank):
                logger.debug(f"IV rank {iv_rank:.1f} outside range [{self.min_iv_rank}, {self.max_iv_rank}]")
                return False
            
            # Check IV percentile as alternative/additional filter
            if iv_percentile < self.min_iv_percentile:
                logger.debug(f"IV percentile {iv_percentile:.1f} below minimum {self.min_iv_percentile}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking volatility conditions: {e}")
            return False
    
    def _calculate_trend_metrics(self, historical_data: List[Dict[str, Any]], 
                               indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate trend metrics for market condition assessment."""
        try:
            trend_metrics = {}
            
            if not historical_data or len(historical_data) < self.trend_lookback_periods:
                return trend_metrics
            
            # Get recent price data
            recent_data = historical_data[-self.trend_lookback_periods:]
            prices = [float(candle.get('close', 0)) for candle in recent_data]
            
            if not prices:
                return trend_metrics
            
            # Calculate trend strength using linear regression slope
            x_values = list(range(len(prices)))
            n = len(prices)
            
            sum_x = sum(x_values)
            sum_y = sum(prices)
            sum_xy = sum(x * y for x, y in zip(x_values, prices))
            sum_x2 = sum(x * x for x in x_values)
            
            # Linear regression slope
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            trend_metrics['slope'] = slope
            
            # Trend strength (normalized)
            price_range = max(prices) - min(prices)
            if price_range > 0:
                trend_strength = abs(slope * n) / price_range
                trend_metrics['trend_strength'] = trend_strength
            else:
                trend_metrics['trend_strength'] = 0.0
            
            # Moving average trend
            if len(prices) >= 10:
                sma_short = sum(prices[-5:]) / 5  # 5-period SMA
                sma_long = sum(prices[-10:]) / 10  # 10-period SMA
                trend_metrics['ma_trend'] = 1 if sma_short > sma_long else -1
            
            # Volatility trend (for mean reversion assessment)
            if len(historical_data) >= 20:
                recent_volatility = self.indicator_calculator.calculate_historical_volatility(
                    historical_data[-20:], 20
                )
                longer_volatility = self.indicator_calculator.calculate_historical_volatility(
                    historical_data[-40:-20] if len(historical_data) >= 40 else historical_data[-20:], 20
                )
                
                if longer_volatility > 0:
                    vol_ratio = recent_volatility / longer_volatility
                    trend_metrics['volatility_ratio'] = vol_ratio
            
            return trend_metrics
            
        except Exception as e:
            logger.error(f"Error calculating trend metrics: {e}")
            return {}
    
    def _check_trend_conditions(self, trend_metrics: Dict[str, Any]) -> bool:
        """Check if trend conditions favor short straddle/strangle."""
        try:
            # For short straddle/strangle, we prefer:
            # 1. Low trend strength (sideways market)
            # 2. Mean-reverting conditions
            # 3. Decreasing volatility
            
            trend_strength = trend_metrics.get('trend_strength', 0.0)
            volatility_ratio = trend_metrics.get('volatility_ratio', 1.0)
            
            # Prefer low trend strength (sideways market)
            max_trend_strength = 0.02  # 2% trend strength threshold
            if trend_strength > max_trend_strength:
                logger.debug(f"Trend strength {trend_strength:.3f} too high for short options")
                return False
            
            # Prefer decreasing volatility (vol ratio < 1)
            max_vol_ratio = 1.2  # Allow some increase but not too much
            if volatility_ratio > max_vol_ratio:
                logger.debug(f"Volatility increasing too much: ratio {volatility_ratio:.2f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking trend conditions: {e}")
            return False
    
    def _select_straddle_strikes(self, options_chain: OptionsChain) -> tuple:
        """Select strikes for straddle strategy (ATM call and put)."""
        try:
            atm_strike = options_chain.atm_strike
            
            # For straddle, use same strike for both call and put
            strikes = [atm_strike, atm_strike]
            option_types = [OptionType.CE, OptionType.PE]
            
            return strikes, option_types
            
        except Exception as e:
            logger.error(f"Error selecting straddle strikes: {e}")
            return [], []
    
    def _select_strangle_strikes(self, options_chain: OptionsChain) -> tuple:
        """Select strikes for strangle strategy (OTM call and put)."""
        try:
            atm_strike = options_chain.atm_strike
            underlying_price = options_chain.underlying_price
            
            # Calculate OTM distances
            if self.strangle_otm_percentage > 0:
                # Percentage-based OTM
                otm_distance = underlying_price * (self.strangle_otm_percentage / 100)
            else:
                # Fixed points OTM
                otm_distance = self.strangle_otm_distance
            
            # Find suitable OTM strikes
            call_strike = None
            put_strike = None
            
            available_strikes = sorted([strike_data['strike'] for strike_data in options_chain.strikes])
            
            # Find OTM call strike (above current price)
            target_call_strike = underlying_price + otm_distance
            for strike in available_strikes:
                if strike >= target_call_strike:
                    call_strike = strike
                    break
            
            # Find OTM put strike (below current price)
            target_put_strike = underlying_price - otm_distance
            for strike in reversed(available_strikes):
                if strike <= target_put_strike:
                    put_strike = strike
                    break
            
            if call_strike and put_strike:
                strikes = [call_strike, put_strike]
                option_types = [OptionType.CE, OptionType.PE]
                return strikes, option_types
            else:
                logger.debug("Could not find suitable OTM strikes for strangle")
                return [], []
                
        except Exception as e:
            logger.error(f"Error selecting strangle strikes: {e}")
            return [], []
    
    def _validate_option_liquidity(self, options_chain: OptionsChain, 
                                 strikes: List[float], option_types: List[OptionType]) -> bool:
        """Validate liquidity for selected options."""
        try:
            for strike, option_type in zip(strikes, option_types):
                option_data = self.get_option_by_strike_type(
                    options_chain, strike, option_type.value.lower()
                )
                
                if not option_data:
                    logger.debug(f"No data for {option_type.value} option at strike {strike}")
                    return False
                
                # Use stricter liquidity requirements for short options
                if not self.validate_option_liquidity(option_data):
                    logger.debug(f"Liquidity check failed for {option_type.value} option at strike {strike}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating option liquidity: {e}")
            return False
    
    def _calculate_position_sizing(self, options_chain: OptionsChain, 
                                 strikes: List[float], option_types: List[OptionType]) -> List[int]:
        """Calculate position sizing for the strategy."""
        try:
            # For straddle/strangle, typically equal quantities
            base_quantity = 1  # Start with 1 lot
            
            # Could implement more sophisticated sizing based on:
            # - Available margin
            # - Risk tolerance
            # - Option prices
            # - Greeks
            
            quantities = [base_quantity] * len(strikes)
            
            return quantities
            
        except Exception as e:
            logger.error(f"Error calculating position sizing: {e}")
            return []
    
    def _calculate_confidence_score(self, options_chain: OptionsChain, 
                                  iv_metrics: Dict[str, float], 
                                  trend_metrics: Dict[str, Any]) -> float:
        """Calculate confidence score for the strategy."""
        try:
            base_confidence = 0.5
            
            # IV rank contribution (higher IV rank = higher confidence for short options)
            iv_rank = iv_metrics.get('iv_rank', 0.0)
            if iv_rank >= 80:
                base_confidence += 0.3
            elif iv_rank >= 70:
                base_confidence += 0.2
            elif iv_rank >= 60:
                base_confidence += 0.1
            
            # Trend strength contribution (lower trend strength = higher confidence)
            trend_strength = trend_metrics.get('trend_strength', 0.0)
            if trend_strength <= 0.01:
                base_confidence += 0.15
            elif trend_strength <= 0.02:
                base_confidence += 0.1
            
            # Volatility regime contribution
            vol_ratio = trend_metrics.get('volatility_ratio', 1.0)
            if vol_ratio < 1.0:  # Decreasing volatility
                base_confidence += 0.1
            elif vol_ratio > 1.3:  # Increasing volatility
                base_confidence -= 0.1
            
            # Time to expiry contribution
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if days_to_expiry <= 2:  # Very short term
                base_confidence += 0.1
            elif days_to_expiry >= 5:  # Longer term
                base_confidence -= 0.05
            
            # Apply base strategy confidence calculation
            final_confidence = self.calculate_confidence_score(
                {'options_chain': options_chain}, base_confidence
            )
            
            return max(0.0, min(1.0, final_confidence))
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.5
    
    def _calculate_days_to_expiry(self, expiry_date: str) -> int:
        """Calculate days to expiry."""
        try:
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            current_dt = datetime.now().date()
            return (expiry_dt - current_dt).days
        except Exception as e:
            logger.error(f"Error calculating days to expiry: {e}")
            return 0
    
    def _estimate_premium_collected(self, options_chain: OptionsChain, 
                                  strikes: List[float], option_types: List[OptionType]) -> float:
        """Estimate premium collected from short options."""
        try:
            total_premium = 0.0
            
            for strike, option_type in zip(strikes, option_types):
                option_data = self.get_option_by_strike_type(
                    options_chain, strike, option_type.value.lower()
                )
                
                if option_data:
                    # Use bid price for short options (what we receive)
                    bid_price = option_data.get('bid', 0.0)
                    total_premium += bid_price
            
            return total_premium
            
        except Exception as e:
            logger.error(f"Error estimating premium collected: {e}")
            return 0.0
    
    def _estimate_max_loss(self, options_chain: OptionsChain, 
                         strikes: List[float], option_types: List[OptionType]) -> float:
        """Estimate maximum potential loss."""
        try:
            premium_collected = self._estimate_premium_collected(options_chain, strikes, option_types)
            
            # For short straddle/strangle, max loss is theoretically unlimited
            # Use a practical estimate based on premium collected and multiplier
            estimated_max_loss = premium_collected * self.max_loss_multiplier
            
            return estimated_max_loss
            
        except Exception as e:
            logger.error(f"Error estimating max loss: {e}")
            return self.max_loss_per_trade
    
    def _check_delta_neutral(self, options_chain: OptionsChain, 
                           strikes: List[float], option_types: List[OptionType]) -> bool:
        """Check if the position is approximately delta neutral."""
        try:
            total_delta = 0.0
            
            for strike, option_type in zip(strikes, option_types):
                option_data = self.get_option_by_strike_type(
                    options_chain, strike, option_type.value.lower()
                )
                
                if option_data:
                    delta = option_data.get('delta', 0.0)
                    # For short options, delta is negative
                    total_delta -= delta
            
            # Check if net delta is within threshold
            return abs(total_delta) <= self.delta_neutral_threshold
            
        except Exception as e:
            logger.error(f"Error checking delta neutral: {e}")
            return False