"""
Greeks-based Momentum Strategy implementation for Bank Nifty Options Trading.

This strategy uses option Greeks (delta, theta, vega, gamma) to select options
based on desired Greek sensitivity and momentum conditions, with bid-ask spread
and volume filters for optimal execution.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from ..data.indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class GreeksStrategy(BaseStrategy):
    """
    Greeks-based Momentum Strategy.
    
    Selects options based on desired Greek characteristics:
    - High delta for directional momentum plays
    - High gamma for acceleration plays
    - Theta considerations for time decay
    - Vega considerations for volatility plays
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Greeks Strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("GreeksStrategy", config)
        
        # Greek target parameters
        self.target_delta_range = config.get('target_delta_range', [0.4, 0.7])  # Preferred delta range
        self.min_gamma = config.get('min_gamma', 0.001)  # Minimum gamma for acceleration
        self.max_theta_decay = config.get('max_theta_decay', -5.0)  # Max acceptable theta decay
        self.max_vega_exposure = config.get('max_vega_exposure', 50.0)  # Max vega per position
        
        # Strategy modes
        self.strategy_mode = config.get('strategy_mode', 'momentum')  # 'momentum', 'gamma_scalp', 'theta_play'
        self.direction_bias = config.get('direction_bias', 'auto')  # 'bullish', 'bearish', 'auto'
        
        # Momentum parameters
        self.momentum_lookback = config.get('momentum_lookback', 5)  # Periods for momentum calculation
        self.momentum_threshold = config.get('momentum_threshold', 1.0)  # % momentum threshold
        self.trend_confirmation_periods = config.get('trend_confirmation_periods', 3)
        
        # Gamma scalping parameters
        self.gamma_scalp_min_gamma = config.get('gamma_scalp_min_gamma', 0.005)
        self.gamma_scalp_max_delta = config.get('gamma_scalp_max_delta', 0.6)
        self.gamma_scalp_target_dte = config.get('gamma_scalp_target_dte', [1, 7])
        
        # Theta play parameters
        self.theta_play_min_theta = config.get('theta_play_min_theta', -10.0)
        self.theta_play_max_delta = config.get('theta_play_max_delta', 0.3)
        self.theta_play_target_dte = config.get('theta_play_target_dte', [1, 3])
        
        # Option selection parameters
        self.strike_selection_method = config.get('strike_selection_method', 'delta_target')  # 'delta_target', 'gamma_max', 'theta_optimal'
        self.allow_itm_options = config.get('allow_itm_options', True)
        self.allow_deep_otm = config.get('allow_deep_otm', False)
        self.max_strikes_to_evaluate = config.get('max_strikes_to_evaluate', 10)
        
        # Risk and time parameters
        self.min_dte = config.get('min_dte', 1)
        self.max_dte = config.get('max_dte', 30)
        self.max_option_price = config.get('max_option_price', 1000.0)
        self.min_option_price = config.get('min_option_price', 5.0)
        
        # Enhanced liquidity requirements for Greeks-based trading
        self.min_volume = config.get('min_volume', 300)
        self.min_open_interest = config.get('min_open_interest', 500)
        self.max_bid_ask_spread_pct = config.get('max_bid_ask_spread_pct', 3.0)
        self.min_bid_ask_ratio = config.get('min_bid_ask_ratio', 0.8)  # bid/ask ratio
        
        self.indicator_calculator = IndicatorCalculator()
        
        logger.info(f"Initialized GreeksStrategy: mode={self.strategy_mode}, "
                   f"delta_range={self.target_delta_range}, direction={self.direction_bias}")
    
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions for Greeks-based entry.
        
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
            
            # Determine market direction and momentum
            market_analysis = self._analyze_market_conditions(historical_data, indicators)
            if not market_analysis:
                return None
            
            # Select optimal option based on Greeks and strategy mode
            option_selection = self._select_optimal_option(options_chain, market_analysis)
            if not option_selection:
                return None
            
            # Validate option meets all criteria
            if not self._validate_option_selection(options_chain, option_selection, market_analysis):
                return None
            
            # Calculate position sizing
            quantity = self._calculate_position_sizing(options_chain, option_selection)
            if quantity <= 0:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                options_chain, option_selection, market_analysis
            )
            
            # Create trading signal
            signal = TradingSignal(
                strategy_name=self.name,
                signal_type=SignalType.BUY,  # Greeks strategy typically buys options
                underlying=options_chain.underlying_symbol,
                strikes=[option_selection['strike']],
                option_types=[option_selection['option_type']],
                quantities=[quantity],
                confidence=confidence,
                timestamp=current_time,
                expiry_date=options_chain.expiry_date,
                target_pnl=self.target_profit_per_trade,
                stop_loss=-self.max_loss_per_trade,
                metadata={
                    'strategy_mode': self.strategy_mode,
                    'selected_greeks': option_selection['greeks'],
                    'market_analysis': market_analysis,
                    'strike': option_selection['strike'],
                    'option_type': option_selection['option_type'].value,
                    'option_premium': option_selection['premium'],
                    'atm_strike': options_chain.atm_strike,
                    'underlying_price': options_chain.underlying_price,
                    'days_to_expiry': self._calculate_days_to_expiry(options_chain.expiry_date),
                    'selection_reason': option_selection['selection_reason']
                }
            )
            
            logger.info(f"Generated Greeks signal: {option_selection['option_type'].value} at {option_selection['strike']}, "
                       f"delta={option_selection['greeks']['delta']:.3f}, "
                       f"gamma={option_selection['greeks']['gamma']:.4f}, "
                       f"confidence={confidence:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating Greeks strategy: {e}")
            return None
    
    def _check_market_conditions(self, options_chain: OptionsChain, current_time: datetime) -> bool:
        """Check basic market conditions for Greeks strategy entry."""
        try:
            # Check days to expiry
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if not (self.min_dte <= days_to_expiry <= self.max_dte):
                logger.debug(f"Days to expiry {days_to_expiry} outside range [{self.min_dte}, {self.max_dte}]")
                return False
            
            # Check market hours
            if not self.is_market_hours():
                return False
            
            # For gamma scalping, avoid entries too close to close
            if self.strategy_mode == 'gamma_scalp' and self.is_early_exit_time():
                logger.debug("Too close to market close for gamma scalping")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False
    
    def _analyze_market_conditions(self, historical_data: List[Dict[str, Any]], 
                                 indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze market conditions for Greeks-based strategy."""
        try:
            if not historical_data or len(historical_data) < self.momentum_lookback + 5:
                logger.debug("Insufficient historical data for market analysis")
                return None
            
            analysis = {}
            
            # Extract price data
            closes = [float(candle.get('close', 0)) for candle in historical_data]
            highs = [float(candle.get('high', 0)) for candle in historical_data]
            lows = [float(candle.get('low', 0)) for candle in historical_data]
            volumes = [float(candle.get('volume', 0)) for candle in historical_data]
            
            # Calculate momentum
            if len(closes) > self.momentum_lookback:
                momentum = (closes[-1] / closes[-self.momentum_lookback - 1] - 1) * 100
                analysis['momentum'] = momentum
                analysis['momentum_strength'] = abs(momentum)
            
            # Determine direction
            if self.direction_bias == 'auto':
                # Auto-detect direction based on momentum and trend
                recent_momentum = analysis.get('momentum', 0)
                
                if recent_momentum > self.momentum_threshold:
                    analysis['direction'] = 'bullish'
                elif recent_momentum < -self.momentum_threshold:
                    analysis['direction'] = 'bearish'
                else:
                    analysis['direction'] = 'neutral'
            else:
                analysis['direction'] = self.direction_bias
            
            # Calculate volatility metrics
            if len(closes) >= 20:
                recent_volatility = self.indicator_calculator.calculate_historical_volatility(
                    historical_data[-20:], 20
                )
                analysis['recent_volatility'] = recent_volatility
            
            # Calculate trend strength
            if len(closes) >= 10:
                sma_short = sum(closes[-5:]) / 5
                sma_long = sum(closes[-10:]) / 10
                trend_strength = abs(sma_short - sma_long) / sma_long if sma_long > 0 else 0
                analysis['trend_strength'] = trend_strength
            
            # Volume analysis
            if volumes:
                avg_volume = sum(volumes[-10:]) / min(len(volumes), 10)
                current_volume = volumes[-1]
                analysis['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Intraday range analysis
            if highs and lows:
                current_range = (highs[-1] - lows[-1]) / closes[-1] if closes[-1] > 0 else 0
                avg_range = sum((h - l) / c for h, l, c in zip(highs[-5:], lows[-5:], closes[-5:]) if c > 0) / 5
                analysis['range_expansion'] = current_range / avg_range if avg_range > 0 else 1.0
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return None
    
    def _select_optimal_option(self, options_chain: OptionsChain, 
                             market_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select optimal option based on Greeks and market conditions."""
        try:
            direction = market_analysis.get('direction', 'neutral')
            
            if direction == 'neutral':
                logger.debug("Neutral market conditions not suitable for Greeks momentum strategy")
                return None
            
            # Determine option type based on direction
            if direction == 'bullish':
                option_type = OptionType.CE
            else:  # bearish
                option_type = OptionType.PE
            
            # Get candidate options
            candidates = self._get_option_candidates(options_chain, option_type)
            if not candidates:
                return None
            
            # Score candidates based on strategy mode
            if self.strategy_mode == 'momentum':
                best_option = self._select_momentum_option(candidates, market_analysis)
            elif self.strategy_mode == 'gamma_scalp':
                best_option = self._select_gamma_scalp_option(candidates, market_analysis)
            elif self.strategy_mode == 'theta_play':
                best_option = self._select_theta_play_option(candidates, market_analysis)
            else:
                best_option = self._select_momentum_option(candidates, market_analysis)
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error selecting optimal option: {e}")
            return None
    
    def _get_option_candidates(self, options_chain: OptionsChain, 
                             option_type: OptionType) -> List[Dict[str, Any]]:
        """Get candidate options for evaluation."""
        try:
            candidates = []
            underlying_price = options_chain.underlying_price
            
            # Sort strikes by distance from ATM
            strikes_data = []
            for strike_data in options_chain.strikes:
                strike = strike_data['strike']
                distance_from_atm = abs(strike - underlying_price)
                strikes_data.append((distance_from_atm, strike, strike_data))
            
            strikes_data.sort()  # Sort by distance from ATM
            
            # Limit evaluation to closest strikes
            max_strikes = min(self.max_strikes_to_evaluate, len(strikes_data))
            
            for i in range(max_strikes):
                _, strike, strike_data = strikes_data[i]
                option_data = strike_data.get(option_type.value.lower())
                
                if not option_data:
                    continue
                
                # Basic filters
                ltp = option_data.get('ltp', 0)
                if not (self.min_option_price <= ltp <= self.max_option_price):
                    continue
                
                # ITM/OTM filters
                is_itm = (option_type == OptionType.CE and strike < underlying_price) or \
                        (option_type == OptionType.PE and strike > underlying_price)
                
                if is_itm and not self.allow_itm_options:
                    continue
                
                # Deep OTM filter
                distance_pct = abs(strike - underlying_price) / underlying_price * 100
                if distance_pct > 10 and not self.allow_deep_otm:  # More than 10% OTM
                    continue
                
                # Extract Greeks
                greeks = {
                    'delta': option_data.get('delta', 0),
                    'gamma': option_data.get('gamma', 0),
                    'theta': option_data.get('theta', 0),
                    'vega': option_data.get('vega', 0)
                }
                
                candidate = {
                    'strike': strike,
                    'option_type': option_type,
                    'option_data': option_data,
                    'greeks': greeks,
                    'premium': ltp,
                    'is_itm': is_itm,
                    'distance_from_atm': abs(strike - underlying_price),
                    'distance_pct': distance_pct
                }
                
                candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error getting option candidates: {e}")
            return []
    
    def _select_momentum_option(self, candidates: List[Dict[str, Any]], 
                              market_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select option optimized for momentum trading."""
        try:
            best_option = None
            best_score = 0
            
            momentum_strength = market_analysis.get('momentum_strength', 0)
            
            for candidate in candidates:
                greeks = candidate['greeks']
                delta = abs(greeks['delta'])
                gamma = greeks['gamma']
                theta = greeks['theta']
                
                # Score based on momentum criteria
                score = 0
                
                # Delta score (prefer moderate to high delta for momentum)
                if self.target_delta_range[0] <= delta <= self.target_delta_range[1]:
                    score += 40
                elif delta > self.target_delta_range[1]:
                    score += 30  # High delta is still good for strong momentum
                elif delta > 0.2:
                    score += 20
                
                # Gamma score (prefer some gamma for acceleration)
                if gamma >= self.min_gamma:
                    score += 20
                    if gamma >= 0.005:  # High gamma
                        score += 10
                
                # Theta penalty (avoid excessive time decay)
                if theta > self.max_theta_decay:
                    score += 15
                elif theta > -10:
                    score += 10
                else:
                    score -= 10  # Heavy theta decay penalty
                
                # Premium efficiency (prefer reasonable premium)
                premium = candidate['premium']
                if 20 <= premium <= 200:
                    score += 15
                elif 10 <= premium <= 300:
                    score += 10
                
                # Momentum alignment bonus
                if momentum_strength > 2.0:
                    score += 10
                
                candidate['momentum_score'] = score
                
                if score > best_score:
                    best_score = score
                    best_option = candidate
            
            if best_option:
                best_option['selection_reason'] = f"Momentum play (score: {best_score})"
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error selecting momentum option: {e}")
            return None
    
    def _select_gamma_scalp_option(self, candidates: List[Dict[str, Any]], 
                                 market_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select option optimized for gamma scalping."""
        try:
            best_option = None
            best_gamma = 0
            
            for candidate in candidates:
                greeks = candidate['greeks']
                delta = abs(greeks['delta'])
                gamma = greeks['gamma']
                
                # Gamma scalping criteria
                if gamma < self.gamma_scalp_min_gamma:
                    continue
                
                if delta > self.gamma_scalp_max_delta:
                    continue
                
                # Prefer highest gamma within constraints
                if gamma > best_gamma:
                    best_gamma = gamma
                    best_option = candidate
            
            if best_option:
                best_option['selection_reason'] = f"Gamma scalp (gamma: {best_gamma:.4f})"
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error selecting gamma scalp option: {e}")
            return None
    
    def _select_theta_play_option(self, candidates: List[Dict[str, Any]], 
                                market_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select option optimized for theta decay plays."""
        try:
            best_option = None
            best_theta_ratio = 0
            
            for candidate in candidates:
                greeks = candidate['greeks']
                delta = abs(greeks['delta'])
                theta = greeks['theta']
                premium = candidate['premium']
                
                # Theta play criteria
                if theta > self.theta_play_min_theta:
                    continue
                
                if delta > self.theta_play_max_delta:
                    continue
                
                # Calculate theta efficiency (theta decay relative to premium)
                if premium > 0:
                    theta_ratio = abs(theta) / premium
                    
                    if theta_ratio > best_theta_ratio:
                        best_theta_ratio = theta_ratio
                        best_option = candidate
            
            if best_option:
                best_option['selection_reason'] = f"Theta play (ratio: {best_theta_ratio:.4f})"
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error selecting theta play option: {e}")
            return None
    
    def _validate_option_selection(self, options_chain: OptionsChain, 
                                 option_selection: Dict[str, Any], 
                                 market_analysis: Dict[str, Any]) -> bool:
        """Validate the selected option meets all criteria."""
        try:
            option_data = option_selection['option_data']
            greeks = option_selection['greeks']
            
            # Enhanced liquidity validation
            if not self.validate_option_liquidity(option_data):
                logger.debug("Option failed liquidity validation")
                return False
            
            # Bid-ask ratio check
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            if ask > 0:
                bid_ask_ratio = bid / ask
                if bid_ask_ratio < self.min_bid_ask_ratio:
                    logger.debug(f"Bid-ask ratio {bid_ask_ratio:.2f} below minimum {self.min_bid_ask_ratio}")
                    return False
            
            # Greeks validation
            if abs(greeks['vega']) > self.max_vega_exposure:
                logger.debug(f"Vega exposure {abs(greeks['vega']):.1f} exceeds maximum {self.max_vega_exposure}")
                return False
            
            # Strategy-specific validations
            if self.strategy_mode == 'momentum':
                delta = abs(greeks['delta'])
                if delta < 0.2:  # Too low delta for momentum
                    logger.debug(f"Delta {delta:.3f} too low for momentum strategy")
                    return False
            
            elif self.strategy_mode == 'gamma_scalp':
                if greeks['gamma'] < self.gamma_scalp_min_gamma:
                    logger.debug(f"Gamma {greeks['gamma']:.4f} too low for gamma scalping")
                    return False
            
            elif self.strategy_mode == 'theta_play':
                if greeks['theta'] > self.theta_play_min_theta:
                    logger.debug(f"Theta {greeks['theta']:.2f} not suitable for theta play")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating option selection: {e}")
            return False
    
    def _calculate_position_sizing(self, options_chain: OptionsChain, 
                                 option_selection: Dict[str, Any]) -> int:
        """Calculate position sizing based on Greeks and risk."""
        try:
            base_quantity = 1
            
            # Adjust based on option premium
            premium = option_selection['premium']
            
            # For expensive options, reduce quantity
            if premium > 500:
                base_quantity = 1
            elif premium > 200:
                base_quantity = 1
            elif premium < 50:
                base_quantity = 2  # Can afford more of cheaper options
            
            # Adjust based on Greeks risk
            greeks = option_selection['greeks']
            vega = abs(greeks['vega'])
            
            # Limit vega exposure
            if vega > 0:
                max_quantity_by_vega = int(self.max_vega_exposure / vega)
                base_quantity = min(base_quantity, max_quantity_by_vega)
            
            return max(1, base_quantity)
            
        except Exception as e:
            logger.error(f"Error calculating position sizing: {e}")
            return 1
    
    def _calculate_confidence_score(self, options_chain: OptionsChain, 
                                  option_selection: Dict[str, Any], 
                                  market_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for Greeks-based signal."""
        try:
            base_confidence = 0.5
            
            # Market momentum contribution
            momentum_strength = market_analysis.get('momentum_strength', 0)
            if momentum_strength > 3.0:
                base_confidence += 0.2
            elif momentum_strength > 2.0:
                base_confidence += 0.15
            elif momentum_strength > 1.0:
                base_confidence += 0.1
            
            # Greeks quality contribution
            greeks = option_selection['greeks']
            delta = abs(greeks['delta'])
            gamma = greeks['gamma']
            
            # Delta contribution
            if self.target_delta_range[0] <= delta <= self.target_delta_range[1]:
                base_confidence += 0.15
            elif delta > 0.3:
                base_confidence += 0.1
            
            # Gamma contribution
            if gamma >= 0.005:
                base_confidence += 0.1
            elif gamma >= self.min_gamma:
                base_confidence += 0.05
            
            # Volume confirmation
            volume_ratio = market_analysis.get('volume_ratio', 1.0)
            if volume_ratio > 1.5:
                base_confidence += 0.1
            elif volume_ratio > 1.2:
                base_confidence += 0.05
            
            # Trend strength contribution
            trend_strength = market_analysis.get('trend_strength', 0)
            if trend_strength > 0.02:
                base_confidence += 0.1
            elif trend_strength > 0.01:
                base_confidence += 0.05
            
            # Strategy mode specific adjustments
            if self.strategy_mode == 'momentum':
                # Bonus for strong momentum alignment
                if momentum_strength > 2.0 and delta > 0.4:
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