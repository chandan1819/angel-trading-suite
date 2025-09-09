"""
Volatility Breakout Strategy implementation for Bank Nifty Options Trading.

This strategy uses IV percentile/rank to identify volatility regimes and either
buys volatility (low IV) or sells volatility (high IV) with volatility breakout
detection for optimal entry timing.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from ..data.indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class VolatilityStrategy(BaseStrategy):
    """
    Volatility Breakout Strategy.
    
    Identifies volatility regimes and trades accordingly:
    - Buy volatility (long straddles/strangles) when IV is low
    - Sell volatility (short straddles/strangles) when IV is high
    - Uses volatility breakout detection for timing
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Volatility Strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("VolatilityStrategy", config)
        
        # IV regime parameters
        self.low_iv_threshold = config.get('low_iv_threshold', 30.0)  # IV percentile for low vol
        self.high_iv_threshold = config.get('high_iv_threshold', 70.0)  # IV percentile for high vol
        self.iv_rank_lookback = config.get('iv_rank_lookback', 252)  # Days for IV rank calculation
        
        # Volatility breakout parameters
        self.vol_breakout_threshold = config.get('vol_breakout_threshold', 1.5)  # Multiplier for breakout
        self.vol_lookback_periods = config.get('vol_lookback_periods', 20)  # Periods for vol calculation
        self.breakout_confirmation_periods = config.get('breakout_confirmation_periods', 2)
        
        # Strategy modes
        self.strategy_mode = config.get('strategy_mode', 'adaptive')  # 'buy_vol', 'sell_vol', 'adaptive'
        self.volatility_play_type = config.get('volatility_play_type', 'straddle')  # 'straddle', 'strangle', 'single_leg'
        
        # Straddle/Strangle parameters
        self.strangle_otm_distance_pct = config.get('strangle_otm_distance_pct', 2.0)  # % OTM for strangle
        self.max_strikes_spread = config.get('max_strikes_spread', 500.0)  # Max spread between strikes
        
        # Volatility regime detection
        self.vol_regime_method = config.get('vol_regime_method', 'iv_percentile')  # 'iv_rank', 'iv_percentile', 'hv_comparison'
        self.hv_iv_ratio_threshold = config.get('hv_iv_ratio_threshold', 0.8)  # HV/IV ratio for regime detection
        
        # Risk and timing parameters
        self.min_dte = config.get('min_dte', 7)
        self.max_dte = config.get('max_dte', 45)
        self.preferred_dte_range = config.get('preferred_dte_range', [14, 30])
        self.vol_expansion_min_pct = config.get('vol_expansion_min_pct', 20.0)  # Min vol expansion %
        
        # Position sizing and risk
        self.max_vol_exposure = config.get('max_vol_exposure', 100.0)  # Max vega exposure
        self.vol_position_sizing_method = config.get('vol_position_sizing_method', 'fixed')  # 'fixed', 'vol_adjusted'
        
        # Market condition filters
        self.avoid_earnings_days = config.get('avoid_earnings_days', 3)  # Days around earnings to avoid
        self.min_underlying_price_change = config.get('min_underlying_price_change', 0.5)  # Min % change for breakout
        
        self.indicator_calculator = IndicatorCalculator()
        
        logger.info(f"Initialized VolatilityStrategy: mode={self.strategy_mode}, "
                   f"play_type={self.volatility_play_type}, "
                   f"IV_thresholds=[{self.low_iv_threshold}, {self.high_iv_threshold}]")
    
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions for volatility strategy entry.
        
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
            
            if not options_chain or not historical_data:
                logger.debug("Insufficient market data for volatility strategy")
                return None
            
            # Check basic market conditions
            if not self._check_market_conditions(options_chain, current_time):
                return None
            
            # Analyze volatility regime
            vol_analysis = self._analyze_volatility_regime(options_chain, historical_data)
            if not vol_analysis:
                return None
            
            # Detect volatility breakout
            breakout_analysis = self._detect_volatility_breakout(historical_data, vol_analysis)
            if not breakout_analysis['breakout_detected']:
                logger.debug("No volatility breakout detected")
                return None
            
            # Determine strategy direction based on volatility regime
            strategy_direction = self._determine_strategy_direction(vol_analysis, breakout_analysis)
            if not strategy_direction:
                return None
            
            # Select appropriate strikes and option types
            option_selection = self._select_volatility_play_options(
                options_chain, strategy_direction, vol_analysis
            )
            if not option_selection:
                return None
            
            # Validate option selection
            if not self._validate_volatility_play(options_chain, option_selection, vol_analysis):
                return None
            
            # Calculate position sizing
            quantities = self._calculate_vol_position_sizing(
                options_chain, option_selection, vol_analysis
            )
            if not quantities:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                options_chain, vol_analysis, breakout_analysis, strategy_direction
            )
            
            # Create trading signal
            signal_type = self._get_signal_type(strategy_direction)
            
            signal = TradingSignal(
                strategy_name=self.name,
                signal_type=signal_type,
                underlying=options_chain.underlying_symbol,
                strikes=option_selection['strikes'],
                option_types=option_selection['option_types'],
                quantities=quantities,
                confidence=confidence,
                timestamp=current_time,
                expiry_date=options_chain.expiry_date,
                target_pnl=self.target_profit_per_trade,
                stop_loss=-self.max_loss_per_trade,
                metadata={
                    'strategy_direction': strategy_direction,
                    'volatility_analysis': vol_analysis,
                    'breakout_analysis': breakout_analysis,
                    'play_type': self.volatility_play_type,
                    'iv_percentile': vol_analysis.get('iv_percentile', 0),
                    'iv_rank': vol_analysis.get('iv_rank', 0),
                    'vol_regime': vol_analysis.get('regime', 'unknown'),
                    'atm_strike': options_chain.atm_strike,
                    'underlying_price': options_chain.underlying_price,
                    'days_to_expiry': self._calculate_days_to_expiry(options_chain.expiry_date),
                    'expected_vol_move': breakout_analysis.get('expected_move', 0),
                    'total_vega_exposure': option_selection.get('total_vega', 0)
                }
            )
            
            logger.info(f"Generated volatility signal: {strategy_direction} {self.volatility_play_type}, "
                       f"IV_percentile={vol_analysis.get('iv_percentile', 0):.1f}, "
                       f"confidence={confidence:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating volatility strategy: {e}")
            return None
    
    def _check_market_conditions(self, options_chain: OptionsChain, current_time: datetime) -> bool:
        """Check basic market conditions for volatility strategy."""
        try:
            # Check days to expiry
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if not (self.min_dte <= days_to_expiry <= self.max_dte):
                logger.debug(f"Days to expiry {days_to_expiry} outside range [{self.min_dte}, {self.max_dte}]")
                return False
            
            # Check market hours
            if not self.is_market_hours():
                return False
            
            # Avoid entries too close to market close for volatility plays
            if self.is_early_exit_time():
                logger.debug("Too close to market close for volatility plays")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False
    
    def _analyze_volatility_regime(self, options_chain: OptionsChain, 
                                 historical_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze current volatility regime."""
        try:
            vol_analysis = {}
            
            # Get current implied volatility
            atm_iv = self._get_atm_implied_volatility(options_chain)
            vol_analysis['current_iv'] = atm_iv
            
            if atm_iv <= 0:
                logger.debug("No valid implied volatility data")
                return None
            
            # Calculate historical volatility
            if len(historical_data) >= self.vol_lookback_periods:
                recent_hv = self.indicator_calculator.calculate_historical_volatility(
                    historical_data[-self.vol_lookback_periods:], self.vol_lookback_periods
                ) * 100  # Convert to percentage
                vol_analysis['recent_hv'] = recent_hv
                
                # HV/IV ratio
                if atm_iv > 0:
                    vol_analysis['hv_iv_ratio'] = recent_hv / atm_iv
            
            # Calculate IV percentile/rank
            if len(historical_data) >= self.iv_rank_lookback:
                iv_metrics = self._calculate_iv_percentile_rank(historical_data, atm_iv)
                vol_analysis.update(iv_metrics)
            else:
                # Fallback estimation
                vol_analysis['iv_percentile'] = self._estimate_iv_percentile(atm_iv)
                vol_analysis['iv_rank'] = vol_analysis['iv_percentile']
            
            # Determine volatility regime
            vol_analysis['regime'] = self._classify_volatility_regime(vol_analysis)
            
            # Calculate volatility trend
            if len(historical_data) >= 40:
                vol_trend = self._calculate_volatility_trend(historical_data)
                vol_analysis['vol_trend'] = vol_trend
            
            return vol_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing volatility regime: {e}")
            return None
    
    def _get_atm_implied_volatility(self, options_chain: OptionsChain) -> float:
        """Get ATM implied volatility."""
        try:
            atm_strike = options_chain.atm_strike
            
            for strike_data in options_chain.strikes:
                if strike_data['strike'] == atm_strike:
                    call_data = strike_data.get('call', {})
                    put_data = strike_data.get('put', {})
                    
                    call_iv = call_data.get('iv', 0)
                    put_iv = put_data.get('iv', 0)
                    
                    # Average call and put IV
                    if call_iv > 0 and put_iv > 0:
                        return (call_iv + put_iv) / 2
                    elif call_iv > 0:
                        return call_iv
                    elif put_iv > 0:
                        return put_iv
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting ATM IV: {e}")
            return 0.0
    
    def _calculate_iv_percentile_rank(self, historical_data: List[Dict[str, Any]], 
                                    current_iv: float) -> Dict[str, float]:
        """Calculate IV percentile and rank from historical data."""
        try:
            # Calculate historical volatilities for comparison
            historical_vols = []
            
            for i in range(len(historical_data) - self.vol_lookback_periods):
                period_data = historical_data[i:i + self.vol_lookback_periods]
                hv = self.indicator_calculator.calculate_historical_volatility(
                    period_data, self.vol_lookback_periods
                ) * 100
                
                if hv > 0:
                    historical_vols.append(hv)
            
            if not historical_vols:
                return {'iv_percentile': 50.0, 'iv_rank': 50.0}
            
            # Calculate IV rank (where current IV stands in range)
            min_vol = min(historical_vols)
            max_vol = max(historical_vols)
            
            if max_vol > min_vol:
                iv_rank = ((current_iv - min_vol) / (max_vol - min_vol)) * 100
            else:
                iv_rank = 50.0
            
            # Calculate IV percentile (percentage of days below current IV)
            below_current = sum(1 for vol in historical_vols if vol < current_iv)
            iv_percentile = (below_current / len(historical_vols)) * 100
            
            return {
                'iv_percentile': max(0, min(100, iv_percentile)),
                'iv_rank': max(0, min(100, iv_rank)),
                'iv_min': min_vol,
                'iv_max': max_vol
            }
            
        except Exception as e:
            logger.error(f"Error calculating IV percentile/rank: {e}")
            return {'iv_percentile': 50.0, 'iv_rank': 50.0}
    
    def _estimate_iv_percentile(self, current_iv: float) -> float:
        """Estimate IV percentile based on absolute IV levels."""
        try:
            # Rough estimation based on typical BANKNIFTY IV levels
            if current_iv > 30:
                return 85.0  # High IV
            elif current_iv > 25:
                return 70.0  # Above average IV
            elif current_iv > 20:
                return 55.0  # Average IV
            elif current_iv > 15:
                return 35.0  # Below average IV
            else:
                return 15.0  # Low IV
                
        except Exception as e:
            logger.error(f"Error estimating IV percentile: {e}")
            return 50.0
    
    def _classify_volatility_regime(self, vol_analysis: Dict[str, Any]) -> str:
        """Classify current volatility regime."""
        try:
            iv_percentile = vol_analysis.get('iv_percentile', 50)
            hv_iv_ratio = vol_analysis.get('hv_iv_ratio', 1.0)
            
            # Primary classification based on IV percentile
            if iv_percentile <= self.low_iv_threshold:
                regime = 'low_vol'
            elif iv_percentile >= self.high_iv_threshold:
                regime = 'high_vol'
            else:
                regime = 'normal_vol'
            
            # Adjust based on HV/IV ratio if available
            if hv_iv_ratio:
                if hv_iv_ratio < self.hv_iv_ratio_threshold and regime != 'high_vol':
                    regime = 'low_vol'  # HV much lower than IV
                elif hv_iv_ratio > 1.2 and regime != 'low_vol':
                    regime = 'high_vol'  # HV higher than IV
            
            return regime
            
        except Exception as e:
            logger.error(f"Error classifying volatility regime: {e}")
            return 'normal_vol'
    
    def _calculate_volatility_trend(self, historical_data: List[Dict[str, Any]]) -> str:
        """Calculate volatility trend direction."""
        try:
            # Calculate short and long term volatility
            short_term_data = historical_data[-10:]
            long_term_data = historical_data[-20:]
            
            short_vol = self.indicator_calculator.calculate_historical_volatility(short_term_data, 10)
            long_vol = self.indicator_calculator.calculate_historical_volatility(long_term_data, 20)
            
            if short_vol > 0 and long_vol > 0:
                vol_ratio = short_vol / long_vol
                
                if vol_ratio > 1.1:
                    return 'increasing'
                elif vol_ratio < 0.9:
                    return 'decreasing'
                else:
                    return 'stable'
            
            return 'stable'
            
        except Exception as e:
            logger.error(f"Error calculating volatility trend: {e}")
            return 'stable'
    
    def _detect_volatility_breakout(self, historical_data: List[Dict[str, Any]], 
                                  vol_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Detect volatility breakout conditions."""
        try:
            breakout_analysis = {'breakout_detected': False}
            
            if len(historical_data) < self.vol_lookback_periods + 5:
                return breakout_analysis
            
            # Calculate recent price movements
            recent_data = historical_data[-self.breakout_confirmation_periods:]
            prices = [float(candle.get('close', 0)) for candle in recent_data]
            
            if len(prices) < 2:
                return breakout_analysis
            
            # Calculate recent price change
            price_change_pct = abs((prices[-1] - prices[0]) / prices[0]) * 100
            
            # Check if price change exceeds minimum threshold
            if price_change_pct < self.min_underlying_price_change:
                return breakout_analysis
            
            # Calculate average volatility over lookback period
            lookback_data = historical_data[-self.vol_lookback_periods:]
            avg_vol = self.indicator_calculator.calculate_historical_volatility(
                lookback_data, self.vol_lookback_periods
            ) * 100
            
            # Calculate recent volatility
            recent_vol = self.indicator_calculator.calculate_historical_volatility(
                recent_data, len(recent_data)
            ) * 100
            
            if avg_vol > 0 and recent_vol > 0:
                vol_expansion_ratio = recent_vol / avg_vol
                
                # Check for volatility expansion
                if vol_expansion_ratio >= self.vol_breakout_threshold:
                    breakout_analysis['breakout_detected'] = True
                    breakout_analysis['vol_expansion_ratio'] = vol_expansion_ratio
                    breakout_analysis['price_change_pct'] = price_change_pct
                    breakout_analysis['breakout_type'] = 'expansion'
                    
                    # Estimate expected move
                    current_iv = vol_analysis.get('current_iv', 0)
                    if current_iv > 0:
                        # Rough expected move calculation
                        days_to_expiry = 1  # Assume short-term move
                        expected_move = (current_iv / 100) * prices[-1] * (days_to_expiry / 365) ** 0.5
                        breakout_analysis['expected_move'] = expected_move
            
            return breakout_analysis
            
        except Exception as e:
            logger.error(f"Error detecting volatility breakout: {e}")
            return {'breakout_detected': False}
    
    def _determine_strategy_direction(self, vol_analysis: Dict[str, Any], 
                                    breakout_analysis: Dict[str, Any]) -> Optional[str]:
        """Determine strategy direction based on volatility analysis."""
        try:
            regime = vol_analysis.get('regime', 'normal_vol')
            iv_percentile = vol_analysis.get('iv_percentile', 50)
            
            if self.strategy_mode == 'adaptive':
                # Adaptive mode: buy low vol, sell high vol
                if regime == 'low_vol' or iv_percentile <= self.low_iv_threshold:
                    return 'buy_volatility'
                elif regime == 'high_vol' or iv_percentile >= self.high_iv_threshold:
                    return 'sell_volatility'
                else:
                    # In normal vol regime, prefer buying on breakouts
                    if breakout_analysis.get('vol_expansion_ratio', 1.0) > 1.3:
                        return 'buy_volatility'
                    else:
                        return None
            
            elif self.strategy_mode == 'buy_vol':
                # Always buy volatility mode
                if regime in ['low_vol', 'normal_vol']:
                    return 'buy_volatility'
                else:
                    return None
            
            elif self.strategy_mode == 'sell_vol':
                # Always sell volatility mode
                if regime in ['high_vol', 'normal_vol']:
                    return 'sell_volatility'
                else:
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining strategy direction: {e}")
            return None
    
    def _select_volatility_play_options(self, options_chain: OptionsChain, 
                                      strategy_direction: str, 
                                      vol_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select options for volatility play."""
        try:
            atm_strike = options_chain.atm_strike
            underlying_price = options_chain.underlying_price
            
            if self.volatility_play_type == 'straddle':
                # ATM straddle
                strikes = [atm_strike, atm_strike]
                option_types = [OptionType.CE, OptionType.PE]
                
            elif self.volatility_play_type == 'strangle':
                # OTM strangle
                otm_distance = underlying_price * (self.strangle_otm_distance_pct / 100)
                
                # Find OTM strikes
                available_strikes = sorted([s['strike'] for s in options_chain.strikes])
                
                call_strike = min(available_strikes, 
                                key=lambda x: abs(x - (underlying_price + otm_distance)) 
                                if x > underlying_price else float('inf'))
                
                put_strike = min(available_strikes,
                               key=lambda x: abs(x - (underlying_price - otm_distance))
                               if x < underlying_price else float('inf'))
                
                strikes = [call_strike, put_strike]
                option_types = [OptionType.CE, OptionType.PE]
                
            elif self.volatility_play_type == 'single_leg':
                # Single leg based on expected direction
                # For volatility plays, prefer ATM options
                strikes = [atm_strike]
                
                # Choose option type based on any directional bias
                # For pure vol plays, default to calls
                option_types = [OptionType.CE]
                
            else:
                return None
            
            # Calculate total vega exposure
            total_vega = 0
            for strike, option_type in zip(strikes, option_types):
                option_data = self.get_option_by_strike_type(
                    options_chain, strike, option_type.value.lower()
                )
                if option_data:
                    vega = option_data.get('vega', 0)
                    if strategy_direction == 'buy_volatility':
                        total_vega += vega  # Long vega
                    else:
                        total_vega -= vega  # Short vega
            
            return {
                'strikes': strikes,
                'option_types': option_types,
                'total_vega': total_vega,
                'strategy_direction': strategy_direction
            }
            
        except Exception as e:
            logger.error(f"Error selecting volatility play options: {e}")
            return None
    
    def _validate_volatility_play(self, options_chain: OptionsChain, 
                                option_selection: Dict[str, Any], 
                                vol_analysis: Dict[str, Any]) -> bool:
        """Validate volatility play selection."""
        try:
            strikes = option_selection['strikes']
            option_types = option_selection['option_types']
            total_vega = abs(option_selection['total_vega'])
            
            # Check vega exposure limits
            if total_vega > self.max_vol_exposure:
                logger.debug(f"Total vega exposure {total_vega:.1f} exceeds maximum {self.max_vol_exposure}")
                return False
            
            # Validate all options liquidity
            for strike, option_type in zip(strikes, option_types):
                option_data = self.get_option_by_strike_type(
                    options_chain, strike, option_type.value.lower()
                )
                
                if not option_data:
                    logger.debug(f"No data for {option_type.value} option at strike {strike}")
                    return False
                
                if not self.validate_option_liquidity(option_data):
                    logger.debug(f"Liquidity check failed for {option_type.value} option at strike {strike}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating volatility play: {e}")
            return False
    
    def _calculate_vol_position_sizing(self, options_chain: OptionsChain, 
                                     option_selection: Dict[str, Any], 
                                     vol_analysis: Dict[str, Any]) -> Optional[List[int]]:
        """Calculate position sizing for volatility play."""
        try:
            strikes = option_selection['strikes']
            option_types = option_selection['option_types']
            total_vega = abs(option_selection['total_vega'])
            
            if self.vol_position_sizing_method == 'fixed':
                # Fixed quantity for all legs
                base_quantity = 1
                quantities = [base_quantity] * len(strikes)
                
            elif self.vol_position_sizing_method == 'vol_adjusted':
                # Adjust based on volatility levels
                iv_percentile = vol_analysis.get('iv_percentile', 50)
                
                if iv_percentile <= 30:  # Low vol - can take larger positions
                    base_quantity = 2
                elif iv_percentile >= 70:  # High vol - smaller positions
                    base_quantity = 1
                else:
                    base_quantity = 1
                
                quantities = [base_quantity] * len(strikes)
            
            else:
                quantities = [1] * len(strikes)
            
            # Adjust for vega exposure limits
            if total_vega > 0:
                max_quantity_by_vega = int(self.max_vol_exposure / total_vega)
                quantities = [min(q, max_quantity_by_vega) for q in quantities]
            
            # Ensure minimum quantity
            quantities = [max(1, q) for q in quantities]
            
            return quantities
            
        except Exception as e:
            logger.error(f"Error calculating vol position sizing: {e}")
            return None
    
    def _get_signal_type(self, strategy_direction: str) -> SignalType:
        """Get appropriate signal type based on strategy direction."""
        if strategy_direction == 'buy_volatility':
            if self.volatility_play_type == 'straddle':
                return SignalType.STRADDLE
            elif self.volatility_play_type == 'strangle':
                return SignalType.STRANGLE
            else:
                return SignalType.BUY
        else:  # sell_volatility
            if self.volatility_play_type == 'straddle':
                return SignalType.STRADDLE
            elif self.volatility_play_type == 'strangle':
                return SignalType.STRANGLE
            else:
                return SignalType.SELL
    
    def _calculate_confidence_score(self, options_chain: OptionsChain, 
                                  vol_analysis: Dict[str, Any], 
                                  breakout_analysis: Dict[str, Any], 
                                  strategy_direction: str) -> float:
        """Calculate confidence score for volatility strategy."""
        try:
            base_confidence = 0.5
            
            # Volatility regime contribution
            iv_percentile = vol_analysis.get('iv_percentile', 50)
            regime = vol_analysis.get('regime', 'normal_vol')
            
            if strategy_direction == 'buy_volatility':
                # Higher confidence for buying low vol
                if iv_percentile <= 20:
                    base_confidence += 0.25
                elif iv_percentile <= 30:
                    base_confidence += 0.2
                elif iv_percentile <= 40:
                    base_confidence += 0.1
            else:  # sell_volatility
                # Higher confidence for selling high vol
                if iv_percentile >= 80:
                    base_confidence += 0.25
                elif iv_percentile >= 70:
                    base_confidence += 0.2
                elif iv_percentile >= 60:
                    base_confidence += 0.1
            
            # Breakout strength contribution
            vol_expansion_ratio = breakout_analysis.get('vol_expansion_ratio', 1.0)
            if vol_expansion_ratio >= 2.0:
                base_confidence += 0.2
            elif vol_expansion_ratio >= 1.5:
                base_confidence += 0.15
            elif vol_expansion_ratio >= 1.2:
                base_confidence += 0.1
            
            # HV/IV ratio contribution
            hv_iv_ratio = vol_analysis.get('hv_iv_ratio', 1.0)
            if strategy_direction == 'buy_volatility' and hv_iv_ratio < 0.8:
                base_confidence += 0.1  # HV much lower than IV
            elif strategy_direction == 'sell_volatility' and hv_iv_ratio > 1.2:
                base_confidence += 0.1  # HV higher than IV
            
            # Volatility trend contribution
            vol_trend = vol_analysis.get('vol_trend', 'stable')
            if strategy_direction == 'buy_volatility' and vol_trend == 'increasing':
                base_confidence += 0.1
            elif strategy_direction == 'sell_volatility' and vol_trend == 'decreasing':
                base_confidence += 0.1
            
            # Days to expiry contribution
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if self.preferred_dte_range[0] <= days_to_expiry <= self.preferred_dte_range[1]:
                base_confidence += 0.1
            
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