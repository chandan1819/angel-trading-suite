"""
Iron Condor Strategy implementation for Bank Nifty Options Trading.

This strategy creates a defined-risk spread by selling an OTM call spread
and an OTM put spread around the ATM strike, profiting from low volatility
and time decay within a specific price range.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from ..data.indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy.
    
    Creates a defined-risk neutral strategy by:
    1. Selling OTM call spread (short call + long call further OTM)
    2. Selling OTM put spread (short put + long put further OTM)
    
    Profits when underlying stays within the short strikes at expiration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Iron Condor Strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("IronCondorStrategy", config)
        
        # Wing distance parameters
        self.wing_distance_points = config.get('wing_distance_points', 200.0)  # Points between short and long
        self.wing_distance_pct = config.get('wing_distance_pct', 0.0)  # Alternative: % of underlying price
        self.symmetric_wings = config.get('symmetric_wings', True)  # Same wing distance for calls and puts
        
        # Strike selection parameters
        self.short_strike_distance_points = config.get('short_strike_distance_points', 300.0)  # Points OTM
        self.short_strike_distance_pct = config.get('short_strike_distance_pct', 1.5)  # % OTM from ATM
        self.strike_selection_method = config.get('strike_selection_method', 'percentage')  # 'points' or 'percentage'
        
        # Profit and risk parameters
        self.min_credit_received = config.get('min_credit_received', 50.0)  # Minimum net credit
        self.max_risk_per_spread = config.get('max_risk_per_spread', 1000.0)  # Max risk per iron condor
        self.profit_target_pct = config.get('profit_target_pct', 50.0)  # % of max profit to target
        self.stop_loss_pct = config.get('stop_loss_pct', 200.0)  # % of credit received as stop loss
        
        # Market condition filters
        self.min_iv_rank = config.get('min_iv_rank', 40.0)  # Minimum IV rank
        self.max_iv_rank = config.get('max_iv_rank', 80.0)  # Maximum IV rank
        self.max_trend_strength = config.get('max_trend_strength', 0.02)  # Max trend for neutral strategy
        self.range_bound_lookback = config.get('range_bound_lookback', 10)  # Days to check for range-bound market
        
        # Time parameters
        self.min_dte = config.get('min_dte', 7)  # Minimum days to expiry
        self.max_dte = config.get('max_dte', 45)  # Maximum days to expiry
        self.preferred_dte_range = config.get('preferred_dte_range', [14, 30])  # Preferred DTE range
        
        # Greeks and risk management
        self.max_net_delta = config.get('max_net_delta', 0.1)  # Maximum net delta
        self.min_theta = config.get('min_theta', 5.0)  # Minimum theta (time decay benefit)
        self.max_vega = config.get('max_vega', 50.0)  # Maximum vega exposure
        
        # Liquidity requirements (stricter for spreads)
        self.min_volume = config.get('min_volume', 200)
        self.min_open_interest = config.get('min_open_interest', 500)
        self.max_bid_ask_spread_pct = config.get('max_bid_ask_spread_pct', 4.0)
        
        self.indicator_calculator = IndicatorCalculator()
        
        logger.info(f"Initialized IronCondorStrategy: wing_distance={self.wing_distance_points}pts, "
                   f"short_distance={self.short_strike_distance_points}pts, "
                   f"IV_range=[{self.min_iv_rank}, {self.max_iv_rank}]")
    
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions for iron condor entry.
        
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
            
            # Check market neutrality conditions
            if not self._check_neutral_market_conditions(historical_data, indicators):
                return None
            
            # Select iron condor strikes
            strikes_config = self._select_iron_condor_strikes(options_chain)
            if not strikes_config:
                return None
            
            # Validate all options liquidity
            if not self._validate_spread_liquidity(options_chain, strikes_config):
                return None
            
            # Calculate spread economics
            spread_metrics = self._calculate_spread_metrics(options_chain, strikes_config)
            if not self._validate_spread_economics(spread_metrics):
                return None
            
            # Calculate position sizing
            quantity = self._calculate_position_sizing(spread_metrics)
            if quantity <= 0:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                options_chain, iv_metrics, spread_metrics, historical_data
            )
            
            # Create trading signal
            strikes = [
                strikes_config['short_put'],
                strikes_config['long_put'],
                strikes_config['short_call'],
                strikes_config['long_call']
            ]
            
            option_types = [OptionType.PE, OptionType.PE, OptionType.CE, OptionType.CE]
            quantities = [quantity, quantity, quantity, quantity]  # Equal quantities for iron condor
            
            signal = TradingSignal(
                strategy_name=self.name,
                signal_type=SignalType.IRON_CONDOR,
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
                    'strikes_config': strikes_config,
                    'spread_metrics': spread_metrics,
                    'iv_rank': iv_metrics.get('iv_rank', 0),
                    'atm_strike': options_chain.atm_strike,
                    'underlying_price': options_chain.underlying_price,
                    'net_credit': spread_metrics.get('net_credit', 0),
                    'max_risk': spread_metrics.get('max_risk', 0),
                    'max_profit': spread_metrics.get('max_profit', 0),
                    'breakeven_lower': spread_metrics.get('breakeven_lower', 0),
                    'breakeven_upper': spread_metrics.get('breakeven_upper', 0),
                    'days_to_expiry': self._calculate_days_to_expiry(options_chain.expiry_date),
                    'net_delta': spread_metrics.get('net_delta', 0),
                    'net_theta': spread_metrics.get('net_theta', 0),
                    'net_vega': spread_metrics.get('net_vega', 0)
                }
            )
            
            logger.info(f"Generated iron condor signal: strikes={strikes}, "
                       f"credit={spread_metrics.get('net_credit', 0):.1f}, "
                       f"confidence={confidence:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating iron condor strategy: {e}")
            return None
    
    def _check_market_conditions(self, options_chain: OptionsChain, current_time: datetime) -> bool:
        """Check basic market conditions for iron condor entry."""
        try:
            # Check days to expiry
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if not (self.min_dte <= days_to_expiry <= self.max_dte):
                logger.debug(f"Days to expiry {days_to_expiry} outside range [{self.min_dte}, {self.max_dte}]")
                return False
            
            # Check market hours
            if not self.is_market_hours():
                return False
            
            # Avoid entries too close to market close
            if self.is_early_exit_time():
                logger.debug("Too close to market close for new iron condor entries")
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
            
            # Calculate IV rank if historical data available
            if historical_data and len(historical_data) >= 252:
                historical_vols = []
                for i in range(len(historical_data) - 20):
                    period_data = historical_data[i:i+20]
                    hv = self.indicator_calculator.calculate_historical_volatility(period_data, 20)
                    if hv > 0:
                        historical_vols.append(hv * 100)
                
                if historical_vols:
                    min_hv = min(historical_vols)
                    max_hv = max(historical_vols)
                    if max_hv > min_hv:
                        iv_rank = ((atm_iv - min_hv) / (max_hv - min_hv)) * 100
                        iv_metrics['iv_rank'] = max(0, min(100, iv_rank))
            
            # Fallback IV rank estimation
            if 'iv_rank' not in iv_metrics:
                if atm_iv > 25:
                    iv_metrics['iv_rank'] = 70.0
                elif atm_iv > 20:
                    iv_metrics['iv_rank'] = 55.0
                elif atm_iv > 15:
                    iv_metrics['iv_rank'] = 40.0
                else:
                    iv_metrics['iv_rank'] = 25.0
            
            return iv_metrics
            
        except Exception as e:
            logger.error(f"Error calculating IV metrics: {e}")
            return {'atm_iv': 0.0, 'iv_rank': 0.0}
    
    def _check_volatility_conditions(self, iv_metrics: Dict[str, float]) -> bool:
        """Check if volatility conditions favor iron condor."""
        try:
            iv_rank = iv_metrics.get('iv_rank', 0.0)
            
            # Iron condor works best in moderate IV environments
            if not (self.min_iv_rank <= iv_rank <= self.max_iv_rank):
                logger.debug(f"IV rank {iv_rank:.1f} outside range [{self.min_iv_rank}, {self.max_iv_rank}]")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking volatility conditions: {e}")
            return False
    
    def _check_neutral_market_conditions(self, historical_data: List[Dict[str, Any]], 
                                       indicators: Dict[str, Any]) -> bool:
        """Check if market conditions favor neutral strategies."""
        try:
            if not historical_data or len(historical_data) < self.range_bound_lookback:
                return True  # Assume neutral if insufficient data
            
            # Calculate trend strength
            recent_data = historical_data[-self.range_bound_lookback:]
            prices = [float(candle.get('close', 0)) for candle in recent_data]
            
            if not prices:
                return True
            
            # Linear regression slope for trend strength
            x_values = list(range(len(prices)))
            n = len(prices)
            
            sum_x = sum(x_values)
            sum_y = sum(prices)
            sum_xy = sum(x * y for x, y in zip(x_values, prices))
            sum_x2 = sum(x * x for x in x_values)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Normalize trend strength
            price_range = max(prices) - min(prices)
            if price_range > 0:
                trend_strength = abs(slope * n) / price_range
            else:
                trend_strength = 0.0
            
            if trend_strength > self.max_trend_strength:
                logger.debug(f"Trend strength {trend_strength:.3f} too high for neutral strategy")
                return False
            
            # Check for range-bound behavior
            current_price = prices[-1]
            price_range_pct = (price_range / current_price) * 100
            
            # Prefer markets with some range but not too volatile
            if price_range_pct < 1.0:  # Too tight range
                logger.debug(f"Price range {price_range_pct:.1f}% too tight")
                return False
            elif price_range_pct > 8.0:  # Too volatile
                logger.debug(f"Price range {price_range_pct:.1f}% too wide")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking neutral market conditions: {e}")
            return True
    
    def _select_iron_condor_strikes(self, options_chain: OptionsChain) -> Optional[Dict[str, float]]:
        """Select strikes for iron condor construction."""
        try:
            atm_strike = options_chain.atm_strike
            underlying_price = options_chain.underlying_price
            available_strikes = sorted([strike_data['strike'] for strike_data in options_chain.strikes])
            
            # Calculate short strike distances
            if self.strike_selection_method == 'percentage':
                short_distance = underlying_price * (self.short_strike_distance_pct / 100)
            else:
                short_distance = self.short_strike_distance_points
            
            # Calculate wing distances
            if self.wing_distance_pct > 0:
                wing_distance = underlying_price * (self.wing_distance_pct / 100)
            else:
                wing_distance = self.wing_distance_points
            
            # Find short strikes (OTM)
            short_call_target = underlying_price + short_distance
            short_put_target = underlying_price - short_distance
            
            short_call = min(available_strikes, key=lambda x: abs(x - short_call_target) if x >= short_call_target else float('inf'))
            short_put = min(available_strikes, key=lambda x: abs(x - short_put_target) if x <= short_put_target else float('inf'))
            
            # Find long strikes (further OTM)
            long_call_target = short_call + wing_distance
            long_put_target = short_put - wing_distance
            
            long_call = min(available_strikes, key=lambda x: abs(x - long_call_target) if x >= long_call_target else float('inf'))
            long_put = min(available_strikes, key=lambda x: abs(x - long_put_target) if x <= long_put_target else float('inf'))
            
            # Validate strike selection
            if not all([short_call > underlying_price, short_put < underlying_price,
                       long_call > short_call, long_put < short_put]):
                logger.debug("Invalid strike selection for iron condor")
                return None
            
            strikes_config = {
                'short_call': short_call,
                'long_call': long_call,
                'short_put': short_put,
                'long_put': long_put,
                'atm_strike': atm_strike,
                'underlying_price': underlying_price
            }
            
            return strikes_config
            
        except Exception as e:
            logger.error(f"Error selecting iron condor strikes: {e}")
            return None
    
    def _validate_spread_liquidity(self, options_chain: OptionsChain, 
                                 strikes_config: Dict[str, float]) -> bool:
        """Validate liquidity for all options in the iron condor."""
        try:
            strikes_to_check = [
                (strikes_config['short_call'], 'call'),
                (strikes_config['long_call'], 'call'),
                (strikes_config['short_put'], 'put'),
                (strikes_config['long_put'], 'put')
            ]
            
            for strike, option_type in strikes_to_check:
                option_data = self.get_option_by_strike_type(options_chain, strike, option_type)
                
                if not option_data:
                    logger.debug(f"No data for {option_type} option at strike {strike}")
                    return False
                
                if not self.validate_option_liquidity(option_data):
                    logger.debug(f"Liquidity check failed for {option_type} option at strike {strike}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating spread liquidity: {e}")
            return False
    
    def _calculate_spread_metrics(self, options_chain: OptionsChain, 
                                strikes_config: Dict[str, float]) -> Dict[str, float]:
        """Calculate economic metrics for the iron condor spread."""
        try:
            metrics = {}
            
            # Get option data
            short_call_data = self.get_option_by_strike_type(options_chain, strikes_config['short_call'], 'call')
            long_call_data = self.get_option_by_strike_type(options_chain, strikes_config['long_call'], 'call')
            short_put_data = self.get_option_by_strike_type(options_chain, strikes_config['short_put'], 'put')
            long_put_data = self.get_option_by_strike_type(options_chain, strikes_config['long_put'], 'put')
            
            if not all([short_call_data, long_call_data, short_put_data, long_put_data]):
                return {}
            
            # Calculate net credit (what we receive)
            credit_from_short_call = short_call_data.get('bid', 0)
            cost_of_long_call = long_call_data.get('ask', 0)
            credit_from_short_put = short_put_data.get('bid', 0)
            cost_of_long_put = long_put_data.get('ask', 0)
            
            call_spread_credit = credit_from_short_call - cost_of_long_call
            put_spread_credit = credit_from_short_put - cost_of_long_put
            net_credit = call_spread_credit + put_spread_credit
            
            metrics['net_credit'] = net_credit
            metrics['call_spread_credit'] = call_spread_credit
            metrics['put_spread_credit'] = put_spread_credit
            
            # Calculate maximum risk and profit
            call_wing_width = strikes_config['long_call'] - strikes_config['short_call']
            put_wing_width = strikes_config['short_put'] - strikes_config['long_put']
            
            max_risk_call = call_wing_width - call_spread_credit
            max_risk_put = put_wing_width - put_spread_credit
            max_risk = max(max_risk_call, max_risk_put)  # Maximum of the two spreads
            
            metrics['max_risk'] = max_risk
            metrics['max_profit'] = net_credit
            
            # Calculate breakeven points
            breakeven_upper = strikes_config['short_call'] + net_credit
            breakeven_lower = strikes_config['short_put'] - net_credit
            
            metrics['breakeven_upper'] = breakeven_upper
            metrics['breakeven_lower'] = breakeven_lower
            
            # Calculate Greeks (if available)
            net_delta = (
                -short_call_data.get('delta', 0) + long_call_data.get('delta', 0) +
                -short_put_data.get('delta', 0) + long_put_data.get('delta', 0)
            )
            
            net_theta = (
                -short_call_data.get('theta', 0) + long_call_data.get('theta', 0) +
                -short_put_data.get('theta', 0) + long_put_data.get('theta', 0)
            )
            
            net_vega = (
                -short_call_data.get('vega', 0) + long_call_data.get('vega', 0) +
                -short_put_data.get('vega', 0) + long_put_data.get('vega', 0)
            )
            
            metrics['net_delta'] = net_delta
            metrics['net_theta'] = net_theta
            metrics['net_vega'] = net_vega
            
            # Calculate profit probability (rough estimate)
            underlying_price = options_chain.underlying_price
            range_width = breakeven_upper - breakeven_lower
            profit_probability = min(90.0, (range_width / underlying_price) * 100 * 2)  # Rough estimate
            
            metrics['profit_probability'] = profit_probability
            metrics['range_width'] = range_width
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating spread metrics: {e}")
            return {}
    
    def _validate_spread_economics(self, spread_metrics: Dict[str, float]) -> bool:
        """Validate if the spread economics are acceptable."""
        try:
            net_credit = spread_metrics.get('net_credit', 0)
            max_risk = spread_metrics.get('max_risk', 0)
            net_delta = spread_metrics.get('net_delta', 0)
            net_theta = spread_metrics.get('net_theta', 0)
            net_vega = spread_metrics.get('net_vega', 0)
            
            # Check minimum credit received
            if net_credit < self.min_credit_received:
                logger.debug(f"Net credit {net_credit:.1f} below minimum {self.min_credit_received}")
                return False
            
            # Check maximum risk
            if max_risk > self.max_risk_per_spread:
                logger.debug(f"Max risk {max_risk:.1f} above maximum {self.max_risk_per_spread}")
                return False
            
            # Check risk-reward ratio
            if max_risk > 0:
                risk_reward_ratio = net_credit / max_risk
                if risk_reward_ratio < 0.2:  # At least 20% return on risk
                    logger.debug(f"Risk-reward ratio {risk_reward_ratio:.2f} too low")
                    return False
            
            # Check delta neutrality
            if abs(net_delta) > self.max_net_delta:
                logger.debug(f"Net delta {net_delta:.3f} exceeds maximum {self.max_net_delta}")
                return False
            
            # Check theta (should be positive for time decay benefit)
            if net_theta < self.min_theta:
                logger.debug(f"Net theta {net_theta:.2f} below minimum {self.min_theta}")
                return False
            
            # Check vega exposure
            if abs(net_vega) > self.max_vega:
                logger.debug(f"Net vega {abs(net_vega):.1f} exceeds maximum {self.max_vega}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating spread economics: {e}")
            return False
    
    def _calculate_position_sizing(self, spread_metrics: Dict[str, float]) -> int:
        """Calculate position sizing for iron condor."""
        try:
            # For iron condor, typically start with 1 spread
            # Could be enhanced based on:
            # - Available capital
            # - Risk tolerance
            # - Spread credit and risk
            
            base_quantity = 1
            
            # Adjust based on spread economics
            net_credit = spread_metrics.get('net_credit', 0)
            max_risk = spread_metrics.get('max_risk', 0)
            
            if max_risk > 0:
                # Ensure total risk doesn't exceed our limits
                max_spreads = int(self.max_loss_per_trade / max_risk)
                base_quantity = min(base_quantity, max_spreads)
            
            return max(1, base_quantity)
            
        except Exception as e:
            logger.error(f"Error calculating position sizing: {e}")
            return 1
    
    def _calculate_confidence_score(self, options_chain: OptionsChain, 
                                  iv_metrics: Dict[str, float], 
                                  spread_metrics: Dict[str, float],
                                  historical_data: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for iron condor strategy."""
        try:
            base_confidence = 0.5
            
            # IV rank contribution (moderate IV is preferred)
            iv_rank = iv_metrics.get('iv_rank', 0.0)
            if 50 <= iv_rank <= 70:
                base_confidence += 0.2
            elif 40 <= iv_rank <= 80:
                base_confidence += 0.1
            
            # Spread economics contribution
            net_credit = spread_metrics.get('net_credit', 0)
            max_risk = spread_metrics.get('max_risk', 1)
            
            if max_risk > 0:
                risk_reward = net_credit / max_risk
                if risk_reward >= 0.4:
                    base_confidence += 0.15
                elif risk_reward >= 0.3:
                    base_confidence += 0.1
                elif risk_reward >= 0.2:
                    base_confidence += 0.05
            
            # Delta neutrality contribution
            net_delta = abs(spread_metrics.get('net_delta', 0))
            if net_delta <= 0.05:
                base_confidence += 0.1
            elif net_delta <= 0.1:
                base_confidence += 0.05
            
            # Theta contribution (time decay benefit)
            net_theta = spread_metrics.get('net_theta', 0)
            if net_theta >= 10:
                base_confidence += 0.1
            elif net_theta >= 5:
                base_confidence += 0.05
            
            # Days to expiry contribution
            days_to_expiry = self._calculate_days_to_expiry(options_chain.expiry_date)
            if self.preferred_dte_range[0] <= days_to_expiry <= self.preferred_dte_range[1]:
                base_confidence += 0.1
            
            # Profit probability contribution
            profit_prob = spread_metrics.get('profit_probability', 0)
            if profit_prob >= 70:
                base_confidence += 0.1
            elif profit_prob >= 60:
                base_confidence += 0.05
            
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