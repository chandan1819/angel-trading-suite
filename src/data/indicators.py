"""
Technical indicator calculations for historical data processing.

This module provides calculations for:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Average True Range (ATR)
- Implied Volatility (IV) rank and percentile
- Bid-ask spread analysis
- Volume analysis
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class HistoricalDataPoint:
    """Historical data point structure"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class IndicatorResult:
    """Result of indicator calculation"""
    values: List[float]
    timestamps: List[datetime]
    parameters: Dict[str, Any]
    calculation_time: datetime


@dataclass
class IVAnalysis:
    """Implied Volatility analysis result"""
    current_iv: float
    iv_rank: float  # 0-100 percentile rank over lookback period
    iv_percentile: float  # 0-100 percentile
    mean_iv: float
    std_iv: float
    lookback_days: int


@dataclass
class SpreadAnalysis:
    """Bid-ask spread analysis result"""
    current_spread: float
    current_spread_pct: float  # As percentage of mid price
    mean_spread: float
    mean_spread_pct: float
    max_spread: float
    min_spread: float
    spread_quality_score: float  # 0-100, higher is better liquidity


@dataclass
class VolumeAnalysis:
    """Volume analysis result"""
    current_volume: int
    mean_volume: float
    volume_ratio: float  # Current vs mean
    volume_trend: str  # 'increasing', 'decreasing', 'stable'
    volume_percentile: float  # 0-100 percentile


class IndicatorCalculator:
    """
    Calculator for technical indicators and market analysis.
    """
    
    def __init__(self):
        """Initialize indicator calculator"""
        self.default_periods = {
            'sma_short': 10,
            'sma_long': 20,
            'ema_short': 12,
            'ema_long': 26,
            'atr_period': 14,
            'iv_lookback': 252,  # 1 year of trading days
            'volume_lookback': 20
        }
    
    def calculate_sma(self, data: List[HistoricalDataPoint], 
                     period: int = 20, 
                     price_field: str = 'close') -> IndicatorResult:
        """
        Calculate Simple Moving Average.
        
        Args:
            data: Historical data points
            period: SMA period
            price_field: Price field to use ('open', 'high', 'low', 'close')
            
        Returns:
            IndicatorResult with SMA values
        """
        try:
            if len(data) < period:
                logger.warning(f"Insufficient data for SMA calculation: {len(data)} < {period}")
                return IndicatorResult([], [], {'period': period, 'field': price_field}, datetime.now())
            
            prices = [getattr(point, price_field) for point in data]
            timestamps = [point.timestamp for point in data]
            
            sma_values = []
            sma_timestamps = []
            
            for i in range(period - 1, len(prices)):
                sma_value = sum(prices[i - period + 1:i + 1]) / period
                sma_values.append(sma_value)
                sma_timestamps.append(timestamps[i])
            
            logger.debug(f"Calculated SMA({period}) with {len(sma_values)} values")
            
            return IndicatorResult(
                values=sma_values,
                timestamps=sma_timestamps,
                parameters={'period': period, 'field': price_field},
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return IndicatorResult([], [], {'period': period, 'field': price_field}, datetime.now())
    
    def calculate_ema(self, data: List[HistoricalDataPoint], 
                     period: int = 20, 
                     price_field: str = 'close') -> IndicatorResult:
        """
        Calculate Exponential Moving Average.
        
        Args:
            data: Historical data points
            period: EMA period
            price_field: Price field to use
            
        Returns:
            IndicatorResult with EMA values
        """
        try:
            if len(data) < period:
                logger.warning(f"Insufficient data for EMA calculation: {len(data)} < {period}")
                return IndicatorResult([], [], {'period': period, 'field': price_field}, datetime.now())
            
            prices = [getattr(point, price_field) for point in data]
            timestamps = [point.timestamp for point in data]
            
            # Calculate smoothing factor
            alpha = 2.0 / (period + 1)
            
            ema_values = []
            ema_timestamps = []
            
            # Initialize EMA with first SMA value
            sma_initial = sum(prices[:period]) / period
            ema = sma_initial
            
            for i in range(period - 1, len(prices)):
                if i == period - 1:
                    ema = sma_initial
                else:
                    ema = alpha * prices[i] + (1 - alpha) * ema
                
                ema_values.append(ema)
                ema_timestamps.append(timestamps[i])
            
            logger.debug(f"Calculated EMA({period}) with {len(ema_values)} values")
            
            return IndicatorResult(
                values=ema_values,
                timestamps=ema_timestamps,
                parameters={'period': period, 'field': price_field, 'alpha': alpha},
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return IndicatorResult([], [], {'period': period, 'field': price_field}, datetime.now())
    
    def calculate_atr(self, data: List[HistoricalDataPoint], 
                     period: int = 14) -> IndicatorResult:
        """
        Calculate Average True Range.
        
        Args:
            data: Historical data points
            period: ATR period
            
        Returns:
            IndicatorResult with ATR values
        """
        try:
            if len(data) < period + 1:  # Need one extra day for true range calculation
                logger.warning(f"Insufficient data for ATR calculation: {len(data)} < {period + 1}")
                return IndicatorResult([], [], {'period': period}, datetime.now())
            
            # Calculate True Range for each day
            true_ranges = []
            for i in range(1, len(data)):
                current = data[i]
                previous = data[i - 1]
                
                tr1 = current.high - current.low
                tr2 = abs(current.high - previous.close)
                tr3 = abs(current.low - previous.close)
                
                true_range = max(tr1, tr2, tr3)
                true_ranges.append(true_range)
            
            # Calculate ATR using EMA of True Range
            atr_values = []
            atr_timestamps = []
            
            # Initialize with SMA of first 'period' true ranges
            atr = sum(true_ranges[:period]) / period
            
            for i in range(period - 1, len(true_ranges)):
                if i == period - 1:
                    atr = sum(true_ranges[:period]) / period
                else:
                    # Use EMA formula: ATR = (TR * 2/(period+1)) + (previous_ATR * (period-1)/(period+1))
                    alpha = 2.0 / (period + 1)
                    atr = alpha * true_ranges[i] + (1 - alpha) * atr
                
                atr_values.append(atr)
                atr_timestamps.append(data[i + 1].timestamp)  # +1 because TR starts from index 1
            
            logger.debug(f"Calculated ATR({period}) with {len(atr_values)} values")
            
            return IndicatorResult(
                values=atr_values,
                timestamps=atr_timestamps,
                parameters={'period': period},
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return IndicatorResult([], [], {'period': period}, datetime.now())
    
    def calculate_iv_rank_percentile(self, iv_data: List[Tuple[datetime, float]], 
                                   lookback_days: int = 252) -> Optional[IVAnalysis]:
        """
        Calculate IV rank and percentile.
        
        Args:
            iv_data: List of (timestamp, iv_value) tuples
            lookback_days: Number of days to look back for ranking
            
        Returns:
            IVAnalysis object or None
        """
        try:
            if len(iv_data) < 2:
                logger.warning("Insufficient IV data for analysis")
                return None
            
            # Sort by timestamp
            iv_data_sorted = sorted(iv_data, key=lambda x: x[0])
            
            # Get current IV (most recent)
            current_iv = iv_data_sorted[-1][1]
            
            # Get lookback period data
            lookback_data = iv_data_sorted[-lookback_days:] if len(iv_data_sorted) >= lookback_days else iv_data_sorted
            iv_values = [iv for _, iv in lookback_data]
            
            # Calculate statistics
            mean_iv = sum(iv_values) / len(iv_values)
            variance = sum((iv - mean_iv) ** 2 for iv in iv_values) / len(iv_values)
            std_iv = math.sqrt(variance)
            
            # Calculate rank (percentage of values below current IV)
            values_below = sum(1 for iv in iv_values if iv < current_iv)
            iv_rank = (values_below / len(iv_values)) * 100
            
            # Calculate percentile (more precise ranking)
            sorted_ivs = sorted(iv_values)
            percentile_position = 0
            for i, iv in enumerate(sorted_ivs):
                if current_iv <= iv:
                    percentile_position = i
                    break
            else:
                percentile_position = len(sorted_ivs) - 1
            
            iv_percentile = (percentile_position / (len(sorted_ivs) - 1)) * 100 if len(sorted_ivs) > 1 else 50
            
            logger.debug(f"IV Analysis: current={current_iv:.2f}, rank={iv_rank:.1f}%, "
                        f"percentile={iv_percentile:.1f}%")
            
            return IVAnalysis(
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                mean_iv=mean_iv,
                std_iv=std_iv,
                lookback_days=len(lookback_data)
            )
            
        except Exception as e:
            logger.error(f"Error calculating IV rank/percentile: {e}")
            return None
    
    def analyze_bid_ask_spread(self, spread_data: List[Tuple[datetime, float, float, float]], 
                              lookback_days: int = 20) -> Optional[SpreadAnalysis]:
        """
        Analyze bid-ask spread patterns.
        
        Args:
            spread_data: List of (timestamp, bid, ask, mid_price) tuples
            lookback_days: Number of days for analysis
            
        Returns:
            SpreadAnalysis object or None
        """
        try:
            if len(spread_data) < 2:
                logger.warning("Insufficient spread data for analysis")
                return None
            
            # Sort by timestamp and get recent data
            spread_data_sorted = sorted(spread_data, key=lambda x: x[0])
            recent_data = spread_data_sorted[-lookback_days:] if len(spread_data_sorted) >= lookback_days else spread_data_sorted
            
            # Calculate spreads and percentages
            spreads = []
            spread_pcts = []
            
            for timestamp, bid, ask, mid_price in recent_data:
                if bid > 0 and ask > 0 and ask > bid:
                    spread = ask - bid
                    spread_pct = (spread / mid_price) * 100 if mid_price > 0 else 0
                    
                    spreads.append(spread)
                    spread_pcts.append(spread_pct)
            
            if not spreads:
                logger.warning("No valid spread data found")
                return None
            
            # Current values (most recent)
            current_spread = spreads[-1]
            current_spread_pct = spread_pcts[-1]
            
            # Statistics
            mean_spread = sum(spreads) / len(spreads)
            mean_spread_pct = sum(spread_pcts) / len(spread_pcts)
            max_spread = max(spreads)
            min_spread = min(spreads)
            
            # Quality score (lower spread percentage = higher quality)
            # Score from 0-100, where 100 is best liquidity
            max_acceptable_spread_pct = 5.0  # 5% spread considered poor
            spread_quality_score = max(0, min(100, (max_acceptable_spread_pct - current_spread_pct) / max_acceptable_spread_pct * 100))
            
            logger.debug(f"Spread Analysis: current={current_spread:.2f} ({current_spread_pct:.2f}%), "
                        f"quality={spread_quality_score:.1f}")
            
            return SpreadAnalysis(
                current_spread=current_spread,
                current_spread_pct=current_spread_pct,
                mean_spread=mean_spread,
                mean_spread_pct=mean_spread_pct,
                max_spread=max_spread,
                min_spread=min_spread,
                spread_quality_score=spread_quality_score
            )
            
        except Exception as e:
            logger.error(f"Error analyzing bid-ask spread: {e}")
            return None
    
    def analyze_volume(self, volume_data: List[Tuple[datetime, int]], 
                      lookback_days: int = 20) -> Optional[VolumeAnalysis]:
        """
        Analyze volume patterns.
        
        Args:
            volume_data: List of (timestamp, volume) tuples
            lookback_days: Number of days for analysis
            
        Returns:
            VolumeAnalysis object or None
        """
        try:
            if len(volume_data) < 2:
                logger.warning("Insufficient volume data for analysis")
                return None
            
            # Sort by timestamp and get recent data
            volume_data_sorted = sorted(volume_data, key=lambda x: x[0])
            recent_data = volume_data_sorted[-lookback_days:] if len(volume_data_sorted) >= lookback_days else volume_data_sorted
            
            volumes = [volume for _, volume in recent_data]
            current_volume = volumes[-1]
            
            # Calculate statistics
            mean_volume = sum(volumes) / len(volumes)
            volume_ratio = current_volume / mean_volume if mean_volume > 0 else 1.0
            
            # Calculate percentile
            sorted_volumes = sorted(volumes)
            percentile_position = 0
            for i, vol in enumerate(sorted_volumes):
                if current_volume <= vol:
                    percentile_position = i
                    break
            else:
                percentile_position = len(sorted_volumes) - 1
            
            volume_percentile = (percentile_position / (len(sorted_volumes) - 1)) * 100 if len(sorted_volumes) > 1 else 50
            
            # Determine trend (compare recent vs older volumes)
            if len(volumes) >= 6:
                recent_avg = sum(volumes[-3:]) / 3
                older_avg = sum(volumes[-6:-3]) / 3
                
                if recent_avg > older_avg * 1.2:
                    volume_trend = 'increasing'
                elif recent_avg < older_avg * 0.8:
                    volume_trend = 'decreasing'
                else:
                    volume_trend = 'stable'
            else:
                volume_trend = 'stable'
            
            logger.debug(f"Volume Analysis: current={current_volume}, ratio={volume_ratio:.2f}, "
                        f"trend={volume_trend}, percentile={volume_percentile:.1f}%")
            
            return VolumeAnalysis(
                current_volume=current_volume,
                mean_volume=mean_volume,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
                volume_percentile=volume_percentile
            )
            
        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return None
    
    def calculate_multiple_indicators(self, data: List[HistoricalDataPoint], 
                                    indicators: List[str] = None) -> Dict[str, IndicatorResult]:
        """
        Calculate multiple indicators at once.
        
        Args:
            data: Historical data points
            indicators: List of indicator names to calculate (None for all)
            
        Returns:
            Dictionary of indicator results
        """
        if indicators is None:
            indicators = ['sma_short', 'sma_long', 'ema_short', 'ema_long', 'atr']
        
        results = {}
        
        try:
            for indicator in indicators:
                if indicator == 'sma_short':
                    results[indicator] = self.calculate_sma(data, self.default_periods['sma_short'])
                elif indicator == 'sma_long':
                    results[indicator] = self.calculate_sma(data, self.default_periods['sma_long'])
                elif indicator == 'ema_short':
                    results[indicator] = self.calculate_ema(data, self.default_periods['ema_short'])
                elif indicator == 'ema_long':
                    results[indicator] = self.calculate_ema(data, self.default_periods['ema_long'])
                elif indicator == 'atr':
                    results[indicator] = self.calculate_atr(data, self.default_periods['atr_period'])
                else:
                    logger.warning(f"Unknown indicator: {indicator}")
            
            logger.info(f"Calculated {len(results)} indicators")
            return results
            
        except Exception as e:
            logger.error(f"Error calculating multiple indicators: {e}")
            return {}
    
    def get_indicator_summary(self, data: List[HistoricalDataPoint]) -> Dict[str, Any]:
        """
        Get a comprehensive summary of all indicators.
        
        Args:
            data: Historical data points
            
        Returns:
            Summary dictionary with all indicator values
        """
        try:
            if not data:
                return {}
            
            # Calculate all indicators
            indicators = self.calculate_multiple_indicators(data)
            
            # Get latest values
            summary = {
                'timestamp': data[-1].timestamp.isoformat(),
                'data_points': len(data),
                'price': {
                    'current': data[-1].close,
                    'open': data[-1].open,
                    'high': data[-1].high,
                    'low': data[-1].low,
                    'volume': data[-1].volume
                },
                'indicators': {}
            }
            
            # Add indicator values
            for name, result in indicators.items():
                if result.values:
                    summary['indicators'][name] = {
                        'current': result.values[-1],
                        'values_count': len(result.values),
                        'parameters': result.parameters
                    }
            
            # Add derived signals
            if 'sma_short' in indicators and 'sma_long' in indicators:
                sma_short = indicators['sma_short']
                sma_long = indicators['sma_long']
                
                if sma_short.values and sma_long.values:
                    summary['signals'] = {
                        'sma_crossover': 'bullish' if sma_short.values[-1] > sma_long.values[-1] else 'bearish'
                    }
            
            if 'ema_short' in indicators and 'ema_long' in indicators:
                ema_short = indicators['ema_short']
                ema_long = indicators['ema_long']
                
                if ema_short.values and ema_long.values:
                    if 'signals' not in summary:
                        summary['signals'] = {}
                    summary['signals']['ema_crossover'] = 'bullish' if ema_short.values[-1] > ema_long.values[-1] else 'bearish'
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating indicator summary: {e}")
            return {}
    
    def validate_data_quality(self, data: List[HistoricalDataPoint]) -> Dict[str, Any]:
        """
        Validate the quality of historical data for indicator calculations.
        
        Args:
            data: Historical data points
            
        Returns:
            Data quality report
        """
        try:
            if not data:
                return {'valid': False, 'issues': ['No data provided']}
            
            issues = []
            warnings = []
            
            # Check data completeness
            if len(data) < 20:
                warnings.append(f"Limited data points: {len(data)} (recommended: 20+)")
            
            # Check for missing or invalid values
            for i, point in enumerate(data):
                if point.open <= 0 or point.high <= 0 or point.low <= 0 or point.close <= 0:
                    issues.append(f"Invalid price data at index {i}")
                
                if point.high < point.low:
                    issues.append(f"High < Low at index {i}")
                
                if point.high < point.open or point.high < point.close:
                    issues.append(f"High price inconsistency at index {i}")
                
                if point.low > point.open or point.low > point.close:
                    issues.append(f"Low price inconsistency at index {i}")
                
                if point.volume < 0:
                    issues.append(f"Negative volume at index {i}")
            
            # Check for data gaps
            if len(data) > 1:
                timestamps = [point.timestamp for point in data]
                for i in range(1, len(timestamps)):
                    time_diff = timestamps[i] - timestamps[i-1]
                    if time_diff.days > 7:  # More than a week gap
                        warnings.append(f"Large time gap detected: {time_diff.days} days")
            
            # Check for duplicate timestamps
            timestamps = [point.timestamp for point in data]
            if len(timestamps) != len(set(timestamps)):
                issues.append("Duplicate timestamps found")
            
            is_valid = len(issues) == 0
            
            quality_report = {
                'valid': is_valid,
                'data_points': len(data),
                'issues': issues,
                'warnings': warnings,
                'date_range': {
                    'start': data[0].timestamp.isoformat() if data else None,
                    'end': data[-1].timestamp.isoformat() if data else None
                }
            }
            
            if is_valid:
                logger.info(f"Data quality validation passed for {len(data)} points")
            else:
                logger.warning(f"Data quality issues found: {len(issues)} issues, {len(warnings)} warnings")
            
            return quality_report
            
        except Exception as e:
            logger.error(f"Error validating data quality: {e}")
            return {'valid': False, 'issues': [f'Validation error: {str(e)}']}