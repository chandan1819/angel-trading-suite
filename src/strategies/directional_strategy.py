"""
Directional Single-Leg Strategy implementation for Bank Nifty Options Trading.

This strategy uses momentum indicators like EMA crossovers and ATR breakouts
to identify directional moves and buys call or put options accordingly.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from ..data.indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class DirectionalStrategy(BaseStrategy):
    """
    Directional Single-Leg Strategy.
    
    Identifies directional momentum using technical indicators and buys
    call options for bullish signals or put options for bearish signals.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Directional Strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("DirectionalStrategy", config)
        
        # EMA parameters
        self.ema_fast_period = config.get('ema_fast_period', 9)
        self.ema_slow_period = config.get('ema_slow_period', 21)
        self.ema_signal_period = config.get('ema_signal_period', 5)  # For signal line
        
        # ATR breakout parameters
        self.atr_period = config.get('atr_period', 14)
        self.atr_multiplier = config.get('atr_multiplier', 2.0)  # ATR breakout threshold
        self.atr_lookback = config.get('atr_lookback', 5)  # Periods to look back for breakout
        
        # Momentum parameters
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.momentum_period = config.get('momentum_period', 10)
        
        # Volume confirmation
        self.volume_confirmation = config.get('volume_confirmation', True)
        self.volume_multiplier = config.get('volume_multiplier', 1.5)  # Above average volume
        self.volume_lookback = config.get('volume_lookback', 20)
        
        # Option selection parameters
        self.strike_selection_method = config.get('strike_selection_method', 'atm')  # 'atm', 'otm', 'itm'
        self.otm_distance_pct = config.get('otm_distance_pct', 1.0)  # % OTM for OTM selection
        self.itm_distance_pct = config.get('itm_distance_pct', 1.0)  # % ITM for ITM selection
        self.delta_target = config.get('delta_target', 0.5)  # Target delta for option selection
        
        # Time and expiry filters
        self.min_dte = config.get('min_dte', 1)
        self.max_dte = config.get('max_dte', 30)
        self.preferred_dte_range = config.get('preferred_dte_range', [7, 14])  # Preferred DTE range
        
        # Signal strength thresholds
        self.min_signal_strength = config.get('min_signal_strength', 0.6)
        self.strong_signal_threshold = config.get('strong_signal_threshold', 0.8)
        
        # Risk management
        self.max_option_price = config.get('max_option_price', 500.0)  # Max premium per option
        self.min_option_price = config.get('min_option_price', 10.0)   # Min premium per option
        
        self.indicator_calculator = IndicatorCalculator()
        
        logger.info(f"Initialized DirectionalStrategy: EMA({self.ema_fast_period},{self.ema_slow_period}), "
                   f"ATR({self.atr_period}x{self.atr_multiplier}), strike_method={self.strike_selection_method}")
    
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions for directional entry.
        
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
                logger.debug("Insufficient market data for directional strategy")
                return None
            
            # Check basic market conditions
            if not self._check_market_conditions(options_chain, current_time):
                return None
            
            # Calculate technical indicators
            tech_indicators = self._calculate_technical_indicators(historical_data, indicators)
            if not tech_indicators:
                return None
            
            # Determine directional bias
            direction, signal_strength = self._determine_direction(tech_indicators, historical_data)
            if not direction or signal_strength < self.min_signal_strength:
                logger.debug(f"No strong directional signal: direction={direction}, strength={signal_strength:.2f}")
                return None
            
            # Select appropriate option
            strike, option_type = self._select_option(options_chain, direction)
            if not strike or not option_type:
                logger.debug("Could not select suitable option")
                return None
            
            # Validate option characteristics
            if not self._validate_option_selection(options_chain, strike, option_type):
                return None
            
            # Calculate position sizing
            quantity = self._calculate_position_sizing(options_chain, strike, option_type)
            if quantity <= 0:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                options_chain, tech_indicators, signal_strength, direction
            )
            
            # Create trading signal
            signal_type = SignalType.BUY  # Always buying options for directional plays
            
            signal = TradingSignal(
                strategy_name=self.name,
                signal_type=signal_type,
                underlying=options_chain.underlying_symbol,
                strikes=[strike],
                option_types=[option_type],
                quantities=[quantity],
                confidence=confidence,
                timestamp=current_time,
                expiry_date=options_chain.expiry_date,
                target_pnl=self.target_profit_per_trade,
                stop_loss=-self.max_loss_per_trade,
                metadata={
                    'direction': direction,
                    'signal_strength': signal_strength,
                    'strike_selection_method': self.strike_selection_method,
                    'atm_strike': options_chain.atm_strike,
                    'underlying_price': options_chain.underlying_price,
                    'option_premium': self._get_option_premium(options_chain, strike, option_type),
                    'delta': self._get_option_delta(options_chain, strike, option_type),
                    'days_to_expiry': self._calculate_days_to_expiry(options_chain.expiry_date),
                    'ema_cross': tech_indicators.get('ema_cross_signal'),
                    'atr_breakout': tech_indicators.get('atr_breakout_signal'),
                    'rsi': tech_indicators.get('rsi'),
                    'volume_confirmation': tech_indicators.get('volume_confirmation', False)
                }
            )
            
            logger.info(f"Generated directional signal: {direction} {option_type.value} at {strike}, "
                       f"confidence={confidence:.2f}, strength={signal_strength:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating directional strategy: {e}")
            return None
    
    def _check_market_conditions(self, options_chain: OptionsChain, current_time: datetime) -> bool:
        """Check basic market conditions for strategy entry."""
        try:
            # Check days to expiry
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if not (self.min_dte <= days_to_expiry <= self.max_dte):
                logger.debug(f"Days to expiry {days_to_expiry} outside range [{self.min_dte}, {self.max_dte}]")
                return False
            
            # Check if within market hours
            if not self.is_market_hours():
                return False
            
            # Avoid entries too close to market close
            if self.is_early_exit_time():
                logger.debug("Too close to market close for new directional entries")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False
    
    def _calculate_technical_indicators(self, historical_data: List[Dict[str, Any]], 
                                      existing_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate technical indicators for directional analysis."""
        try:
            if len(historical_data) < max(self.ema_slow_period, self.atr_period, self.rsi_period) + 5:
                logger.debug("Insufficient historical data for technical indicators")
                return {}
            
            indicators = {}
            
            # Extract price data
            closes = [float(candle.get('close', 0)) for candle in historical_data]
            highs = [float(candle.get('high', 0)) for candle in historical_data]
            lows = [float(candle.get('low', 0)) for candle in historical_data]
            volumes = [float(candle.get('volume', 0)) for candle in historical_data]
            
            # EMA calculations
            ema_fast = self.indicator_calculator.calculate_ema(closes, self.ema_fast_period)
            ema_slow = self.indicator_calculator.calculate_ema(closes, self.ema_slow_period)
            
            if ema_fast and ema_slow:
                indicators['ema_fast'] = ema_fast[-1]
                indicators['ema_slow'] = ema_slow[-1]
                indicators['ema_fast_prev'] = ema_fast[-2] if len(ema_fast) > 1 else ema_fast[-1]
                indicators['ema_slow_prev'] = ema_slow[-2] if len(ema_slow) > 1 else ema_slow[-1]
                
                # EMA cross signal
                current_cross = ema_fast[-1] - ema_slow[-1]
                prev_cross = (ema_fast[-2] if len(ema_fast) > 1 else ema_fast[-1]) - \
                           (ema_slow[-2] if len(ema_slow) > 1 else ema_slow[-1])
                
                if current_cross > 0 and prev_cross <= 0:
                    indicators['ema_cross_signal'] = 'bullish'
                elif current_cross < 0 and prev_cross >= 0:
                    indicators['ema_cross_signal'] = 'bearish'
                else:
                    indicators['ema_cross_signal'] = 'none'
            
            # ATR calculations
            atr_values = self.indicator_calculator.calculate_atr(highs, lows, closes, self.atr_period)
            if atr_values:
                current_atr = atr_values[-1]
                indicators['atr'] = current_atr
                
                # ATR breakout detection
                recent_high = max(highs[-self.atr_lookback:])
                recent_low = min(lows[-self.atr_lookback:])
                current_price = closes[-1]
                
                breakout_threshold = current_atr * self.atr_multiplier
                
                if current_price > recent_high + breakout_threshold:
                    indicators['atr_breakout_signal'] = 'bullish'
                elif current_price < recent_low - breakout_threshold:
                    indicators['atr_breakout_signal'] = 'bearish'
                else:
                    indicators['atr_breakout_signal'] = 'none'
            
            # RSI calculation
            rsi_values = self.indicator_calculator.calculate_rsi(closes, self.rsi_period)
            if rsi_values:
                indicators['rsi'] = rsi_values[-1]
            
            # Momentum calculation
            if len(closes) > self.momentum_period:
                momentum = (closes[-1] / closes[-self.momentum_period - 1] - 1) * 100
                indicators['momentum'] = momentum
            
            # Volume confirmation
            if self.volume_confirmation and volumes:
                avg_volume = sum(volumes[-self.volume_lookback:]) / min(len(volumes), self.volume_lookback)
                current_volume = volumes[-1]
                indicators['volume_confirmation'] = current_volume > (avg_volume * self.volume_multiplier)
                indicators['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return {}
    
    def _determine_direction(self, indicators: Dict[str, Any], 
                           historical_data: List[Dict[str, Any]]) -> tuple:
        """
        Determine directional bias and signal strength.
        
        Returns:
            Tuple of (direction, signal_strength) where direction is 'bullish'/'bearish'/None
        """
        try:
            bullish_signals = 0
            bearish_signals = 0
            signal_weights = []
            
            # EMA cross signal
            ema_cross = indicators.get('ema_cross_signal', 'none')
            if ema_cross == 'bullish':
                bullish_signals += 1
                signal_weights.append(0.3)
            elif ema_cross == 'bearish':
                bearish_signals += 1
                signal_weights.append(0.3)
            
            # EMA trend signal
            ema_fast = indicators.get('ema_fast', 0)
            ema_slow = indicators.get('ema_slow', 0)
            if ema_fast > ema_slow:
                bullish_signals += 1
                signal_weights.append(0.2)
            elif ema_fast < ema_slow:
                bearish_signals += 1
                signal_weights.append(0.2)
            
            # ATR breakout signal
            atr_breakout = indicators.get('atr_breakout_signal', 'none')
            if atr_breakout == 'bullish':
                bullish_signals += 1
                signal_weights.append(0.4)
            elif atr_breakout == 'bearish':
                bearish_signals += 1
                signal_weights.append(0.4)
            
            # RSI momentum (but avoid extreme levels)
            rsi = indicators.get('rsi', 50)
            if 50 < rsi < self.rsi_overbought:  # Bullish momentum but not overbought
                bullish_signals += 1
                signal_weights.append(0.15)
            elif self.rsi_oversold < rsi < 50:  # Bearish momentum but not oversold
                bearish_signals += 1
                signal_weights.append(0.15)
            
            # Price momentum
            momentum = indicators.get('momentum', 0)
            if momentum > 1.0:  # Positive momentum
                bullish_signals += 1
                signal_weights.append(0.2)
            elif momentum < -1.0:  # Negative momentum
                bearish_signals += 1
                signal_weights.append(0.2)
            
            # Volume confirmation (enhances signal strength)
            volume_confirmation = indicators.get('volume_confirmation', False)
            volume_multiplier = 1.2 if volume_confirmation else 1.0
            
            # Determine direction and calculate signal strength
            total_signals = bullish_signals + bearish_signals
            if total_signals == 0:
                return None, 0.0
            
            if bullish_signals > bearish_signals:
                direction = 'bullish'
                signal_strength = (bullish_signals / total_signals) * volume_multiplier
            elif bearish_signals > bullish_signals:
                direction = 'bearish'
                signal_strength = (bearish_signals / total_signals) * volume_multiplier
            else:
                return None, 0.0  # Conflicting signals
            
            # Enhance signal strength based on signal quality
            if signal_weights:
                weighted_strength = sum(signal_weights) / len(signal_weights)
                signal_strength = (signal_strength + weighted_strength) / 2
            
            # Cap signal strength
            signal_strength = min(1.0, signal_strength)
            
            return direction, signal_strength
            
        except Exception as e:
            logger.error(f"Error determining direction: {e}")
            return None, 0.0
    
    def _select_option(self, options_chain: OptionsChain, direction: str) -> tuple:
        """
        Select appropriate option based on direction and strategy parameters.
        
        Returns:
            Tuple of (strike, option_type)
        """
        try:
            if direction == 'bullish':
                option_type = OptionType.CE
            elif direction == 'bearish':
                option_type = OptionType.PE
            else:
                return None, None
            
            atm_strike = options_chain.atm_strike
            underlying_price = options_chain.underlying_price
            
            # Select strike based on method
            if self.strike_selection_method == 'atm':
                target_strike = atm_strike
            elif self.strike_selection_method == 'otm':
                if direction == 'bullish':
                    # OTM call (strike above current price)
                    target_strike = underlying_price * (1 + self.otm_distance_pct / 100)
                else:
                    # OTM put (strike below current price)
                    target_strike = underlying_price * (1 - self.otm_distance_pct / 100)
            elif self.strike_selection_method == 'itm':
                if direction == 'bullish':
                    # ITM call (strike below current price)
                    target_strike = underlying_price * (1 - self.itm_distance_pct / 100)
                else:
                    # ITM put (strike above current price)
                    target_strike = underlying_price * (1 + self.itm_distance_pct / 100)
            else:
                target_strike = atm_strike
            
            # Find closest available strike
            available_strikes = sorted([strike_data['strike'] for strike_data in options_chain.strikes])
            closest_strike = min(available_strikes, key=lambda x: abs(x - target_strike))
            
            return closest_strike, option_type
            
        except Exception as e:
            logger.error(f"Error selecting option: {e}")
            return None, None
    
    def _validate_option_selection(self, options_chain: OptionsChain, 
                                 strike: float, option_type: OptionType) -> bool:
        """Validate the selected option meets criteria."""
        try:
            option_data = self.get_option_by_strike_type(
                options_chain, strike, option_type.value.lower()
            )
            
            if not option_data:
                logger.debug(f"No data for {option_type.value} option at strike {strike}")
                return False
            
            # Check liquidity
            if not self.validate_option_liquidity(option_data):
                logger.debug(f"Liquidity check failed for {option_type.value} option at strike {strike}")
                return False
            
            # Check option price range
            ltp = option_data.get('ltp', 0)
            if not (self.min_option_price <= ltp <= self.max_option_price):
                logger.debug(f"Option price {ltp} outside range [{self.min_option_price}, {self.max_option_price}]")
                return False
            
            # Check delta if available
            delta = option_data.get('delta', 0)
            if delta != 0:  # If delta is available
                abs_delta = abs(delta)
                if abs_delta < 0.1:  # Too far OTM
                    logger.debug(f"Option delta {abs_delta:.2f} too low (too far OTM)")
                    return False
                elif abs_delta > 0.9:  # Too deep ITM
                    logger.debug(f"Option delta {abs_delta:.2f} too high (too deep ITM)")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating option selection: {e}")
            return False
    
    def _calculate_position_sizing(self, options_chain: OptionsChain, 
                                 strike: float, option_type: OptionType) -> int:
        """Calculate position sizing for the option."""
        try:
            # For directional strategies, typically start with 1 lot
            # Could be enhanced with more sophisticated sizing based on:
            # - Option price
            # - Available capital
            # - Risk tolerance
            # - Signal strength
            
            base_quantity = 1
            
            # Adjust based on option price (buy more of cheaper options)
            option_data = self.get_option_by_strike_type(
                options_chain, strike, option_type.value.lower()
            )
            
            if option_data:
                ltp = option_data.get('ltp', 0)
                if ltp > 0:
                    # Simple inverse relationship with price
                    if ltp < 50:
                        base_quantity = 2  # Buy more of cheap options
                    elif ltp > 200:
                        base_quantity = 1  # Standard quantity for expensive options
            
            return base_quantity
            
        except Exception as e:
            logger.error(f"Error calculating position sizing: {e}")
            return 1
    
    def _calculate_confidence_score(self, options_chain: OptionsChain, 
                                  indicators: Dict[str, Any], 
                                  signal_strength: float, direction: str) -> float:
        """Calculate confidence score for the directional signal."""
        try:
            base_confidence = signal_strength
            
            # Enhance confidence based on multiple confirmations
            confirmations = 0
            
            # EMA cross confirmation
            if indicators.get('ema_cross_signal') == direction:
                confirmations += 1
                base_confidence += 0.1
            
            # ATR breakout confirmation
            if indicators.get('atr_breakout_signal') == direction:
                confirmations += 1
                base_confidence += 0.15
            
            # Volume confirmation
            if indicators.get('volume_confirmation', False):
                confirmations += 1
                base_confidence += 0.1
            
            # RSI not at extreme levels
            rsi = indicators.get('rsi', 50)
            if self.rsi_oversold < rsi < self.rsi_overbought:
                base_confidence += 0.05
            
            # Days to expiry in preferred range
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if self.preferred_dte_range[0] <= days_to_expiry <= self.preferred_dte_range[1]:
                base_confidence += 0.05
            
            # Multiple confirmation bonus
            if confirmations >= 3:
                base_confidence += 0.1
            elif confirmations >= 2:
                base_confidence += 0.05
            
            # Apply base strategy confidence calculation
            final_confidence = self.calculate_confidence_score(
                {'options_chain': options_chain}, base_confidence
            )
            
            return max(0.0, min(1.0, final_confidence))
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return signal_strength
    
    def _get_option_premium(self, options_chain: OptionsChain, 
                          strike: float, option_type: OptionType) -> float:
        """Get option premium (LTP)."""
        try:
            option_data = self.get_option_by_strike_type(
                options_chain, strike, option_type.value.lower()
            )
            return option_data.get('ltp', 0.0) if option_data else 0.0
        except Exception as e:
            logger.error(f"Error getting option premium: {e}")
            return 0.0
    
    def _get_option_delta(self, options_chain: OptionsChain, 
                        strike: float, option_type: OptionType) -> float:
        """Get option delta."""
        try:
            option_data = self.get_option_by_strike_type(
                options_chain, strike, option_type.value.lower()
            )
            return option_data.get('delta', 0.0) if option_data else 0.0
        except Exception as e:
            logger.error(f"Error getting option delta: {e}")
            return 0.0
    
    def _calculate_days_to_expiry(self, expiry_date: str) -> int:
        """Calculate days to expiry."""
        try:
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            current_dt = datetime.now().date()
            return (expiry_dt - current_dt).days
        except Exception as e:
            logger.error(f"Error calculating days to expiry: {e}")
            return 0