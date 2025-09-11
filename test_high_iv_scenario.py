#!/usr/bin/env python3
"""
High IV Market Scenario Test - Shows what happens when trading conditions ARE met

This script simulates a high volatility market environment where straddle 
conditions are favorable and shows the complete data flow and signal generation.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def setup_detailed_logging():
    """Setup detailed logging to see all data fetching"""
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Setup logging with detailed format
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'logs/high_iv_scenario_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    
    return logging.getLogger(__name__)

def simulate_high_iv_market_data():
    """Simulate high IV market conditions where straddle conditions are met"""
    logger = logging.getLogger(__name__)
    
    logger.info("📊 Simulating HIGH VOLATILITY market conditions...")
    logger.info("🔥 Market Scenario: Post-earnings volatility spike")
    
    # Simulate current market data
    current_time = datetime.now().replace(hour=11, minute=30)  # Market hours
    
    # Simulate Bank Nifty spot price during high volatility
    banknifty_spot = 51750.25  # Slightly different level
    
    logger.info(f"🎯 BANK NIFTY SPOT DATA (High Volatility Scenario):")
    logger.info(f"   Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Spot Price: ₹{banknifty_spot:,.2f}")
    logger.info(f"   Market Status: OPEN")
    logger.info(f"   Market Condition: HIGH VOLATILITY")
    logger.info(f"   VIX Level: 28.5 (High)")
    
    # Calculate ATM strike
    atm_strike = round(banknifty_spot / 100) * 100
    logger.info(f"   ATM Strike: {atm_strike}")
    
    # Simulate options chain data with HIGH IV
    logger.info(f"\n📋 FETCHING OPTIONS CHAIN DATA (High IV Environment):")
    logger.info(f"   Underlying: BANKNIFTY")
    logger.info(f"   Expiry: Current week")
    logger.info(f"   Strikes: {atm_strike-500} to {atm_strike+500} (11 strikes)")
    logger.info(f"   Market Condition: High volatility after major news")
    
    # Create realistic options data with HIGH IV
    options_data = {}
    
    for i in range(-5, 6):  # 11 strikes around ATM
        strike = atm_strike + (i * 100)
        
        # Simulate option prices with HIGH IV
        call_intrinsic = max(0, banknifty_spot - strike)
        put_intrinsic = max(0, strike - banknifty_spot)
        
        # Higher time value due to high IV
        time_value = max(80, 350 - abs(i) * 40)  # Much higher time value
        
        call_price = call_intrinsic + time_value
        put_price = put_intrinsic + time_value
        
        # Simulate HIGH IV and better liquidity
        call_iv = 0.32 + abs(i) * 0.015  # Much higher IV (32%+)
        put_iv = 0.32 + abs(i) * 0.015
        
        # Better liquidity in high IV environment
        volume = max(500, 2500 - abs(i) * 200)  # Higher volumes
        oi = max(2000, 8000 - abs(i) * 600)     # Higher OI
        
        # Tighter spreads due to high activity
        spread_factor = 0.015 if abs(i) <= 2 else 0.025  # Tighter spreads
        
        options_data[strike] = {
            'call': {
                'ltp': round(call_price, 2),
                'bid': round(call_price * (1 - spread_factor), 2),
                'ask': round(call_price * (1 + spread_factor), 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(call_iv, 3),
                'delta': round(0.5 + i * 0.08, 2),
                'theta': round(-25 - abs(i) * 3, 2),  # Higher theta
                'vega': round(35 - abs(i) * 4, 2)     # Higher vega
            },
            'put': {
                'ltp': round(put_price, 2),
                'bid': round(put_price * (1 - spread_factor), 2),
                'ask': round(put_price * (1 + spread_factor), 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(put_iv, 3),
                'delta': round(-0.5 - i * 0.08, 2),
                'theta': round(-25 - abs(i) * 3, 2),
                'vega': round(35 - abs(i) * 4, 2)
            }
        }
        
        logger.debug(f"   Strike {strike}: Call ₹{call_price:.2f} (IV:{call_iv:.1%}), Put ₹{put_price:.2f} (IV:{put_iv:.1%}), Vol {volume}, OI {oi}")
    
    logger.info(f"✅ Options chain data fetched for {len(options_data)} strikes")
    logger.info(f"🔥 High IV environment detected - premiums are elevated!")
    
    return {
        'spot_price': banknifty_spot,
        'atm_strike': atm_strike,
        'current_time': current_time,
        'options_data': options_data,
        'market_condition': 'HIGH_VOLATILITY'
    }

def calculate_high_iv_indicators(market_data):
    """Calculate market indicators for high IV scenario"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n📈 CALCULATING MARKET INDICATORS (High IV Scenario):")
    
    # Simulate historical volatility calculation
    historical_vol = 0.18  # 18% annual volatility (base)
    logger.info(f"   Historical Volatility (20-day): {historical_vol:.1%}")
    
    # Calculate current IV from ATM options (HIGH)
    atm_options = market_data['options_data'][market_data['atm_strike']]
    current_iv = (atm_options['call']['iv'] + atm_options['put']['iv']) / 2
    logger.info(f"   Current ATM IV: {current_iv:.1%} 🔥 HIGH!")
    
    # Calculate IV Rank (HIGH)
    iv_rank = ((current_iv - 0.15) / (0.40 - 0.15)) * 100  # Scale to 0-100
    iv_rank = max(0, min(100, iv_rank))
    logger.info(f"   IV Rank: {iv_rank:.1f}% 🎯 EXCELLENT for straddles!")
    
    # Calculate IV Percentile
    iv_percentile = iv_rank * 0.95  # Higher percentile
    logger.info(f"   IV Percentile: {iv_percentile:.1f}%")
    
    # Market trend analysis (favorable for straddles)
    trend_direction = "SIDEWAYS"  # Perfect for straddles
    trend_strength = 0.2  # Low trend strength
    logger.info(f"   Trend Direction: {trend_direction} ✅ Perfect for straddles")
    logger.info(f"   Trend Strength: {trend_strength:.1f} ✅ Low directional bias")
    
    # Volume analysis (high activity)
    total_call_volume = sum([data['call']['volume'] for data in market_data['options_data'].values()])
    total_put_volume = sum([data['put']['volume'] for data in market_data['options_data'].values()])
    pcr = total_put_volume / total_call_volume if total_call_volume > 0 else 1.0
    
    logger.info(f"   Total Call Volume: {total_call_volume:,} 📈 High activity!")
    logger.info(f"   Total Put Volume: {total_put_volume:,} 📈 High activity!")
    logger.info(f"   Put-Call Ratio: {pcr:.2f}")
    
    # Additional high IV indicators
    logger.info(f"   VIX Level: 28.5 (High)")
    logger.info(f"   Market Regime: Post-earnings volatility")
    logger.info(f"   Options Activity: Elevated across all strikes")
    
    return {
        'historical_vol': historical_vol,
        'current_iv': current_iv,
        'iv_rank': iv_rank,
        'iv_percentile': iv_percentile,
        'trend_direction': trend_direction,
        'trend_strength': trend_strength,
        'pcr': pcr,
        'total_call_volume': total_call_volume,
        'total_put_volume': total_put_volume,
        'vix_level': 28.5,
        'market_regime': 'high_volatility'
    }

def evaluate_straddle_in_high_iv(market_data, indicators):
    """Evaluate straddle strategy in high IV environment"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n🎯 EVALUATING STRADDLE STRATEGY (High IV Environment):")
    
    # Strategy parameters (same as before)
    strategy_params = {
        'min_iv_rank': 70.0,
        'max_iv_rank': 95.0,
        'min_volume': 500,
        'min_oi': 2000,
        'max_bid_ask_spread': 3.0,
        'profit_target': 2000,
        'stop_loss': 1000,
        'lot_size': 35
    }
    
    logger.info(f"📋 STRATEGY PARAMETERS:")
    for param, value in strategy_params.items():
        logger.info(f"   {param}: {value}")
    
    # Check each condition
    conditions_met = {}
    
    # 1. IV Rank Check (SHOULD PASS)
    iv_rank = indicators['iv_rank']
    iv_condition = strategy_params['min_iv_rank'] <= iv_rank <= strategy_params['max_iv_rank']
    conditions_met['iv_rank'] = iv_condition
    
    logger.info(f"\n🔍 CONDITION CHECKS:")
    logger.info(f"   1. IV Rank Check:")
    logger.info(f"      Current IV Rank: {iv_rank:.1f}% 🔥")
    logger.info(f"      Required Range: {strategy_params['min_iv_rank']:.1f}% - {strategy_params['max_iv_rank']:.1f}%")
    logger.info(f"      Status: {'✅ PASS - Perfect IV environment!' if iv_condition else '❌ FAIL'}")
    
    # 2. Liquidity Check (SHOULD PASS)
    atm_options = market_data['options_data'][market_data['atm_strike']]
    call_volume = atm_options['call']['volume']
    put_volume = atm_options['put']['volume']
    call_oi = atm_options['call']['oi']
    put_oi = atm_options['put']['oi']
    
    volume_condition = call_volume >= strategy_params['min_volume'] and put_volume >= strategy_params['min_volume']
    oi_condition = call_oi >= strategy_params['min_oi'] and put_oi >= strategy_params['min_oi']
    liquidity_condition = volume_condition and oi_condition
    conditions_met['liquidity'] = liquidity_condition
    
    logger.info(f"   2. Liquidity Check:")
    logger.info(f"      ATM Call Volume: {call_volume} (min: {strategy_params['min_volume']}) ✅")
    logger.info(f"      ATM Put Volume: {put_volume} (min: {strategy_params['min_volume']}) ✅")
    logger.info(f"      ATM Call OI: {call_oi} (min: {strategy_params['min_oi']}) ✅")
    logger.info(f"      ATM Put OI: {put_oi} (min: {strategy_params['min_oi']}) ✅")
    logger.info(f"      Status: {'✅ PASS - Excellent liquidity!' if liquidity_condition else '❌ FAIL'}")
    
    # 3. Bid-Ask Spread Check (SHOULD PASS)
    call_spread = (atm_options['call']['ask'] - atm_options['call']['bid']) / atm_options['call']['ltp'] * 100
    put_spread = (atm_options['put']['ask'] - atm_options['put']['bid']) / atm_options['put']['ltp'] * 100
    spread_condition = call_spread <= strategy_params['max_bid_ask_spread'] and put_spread <= strategy_params['max_bid_ask_spread']
    conditions_met['spread'] = spread_condition
    
    logger.info(f"   3. Bid-Ask Spread Check:")
    logger.info(f"      Call Spread: {call_spread:.2f}% (max: {strategy_params['max_bid_ask_spread']:.1f}%) ✅")
    logger.info(f"      Put Spread: {put_spread:.2f}% (max: {strategy_params['max_bid_ask_spread']:.1f}%) ✅")
    logger.info(f"      Status: {'✅ PASS - Tight spreads!' if spread_condition else '❌ FAIL'}")
    
    # 4. Market Hours Check (SHOULD PASS)
    current_time = market_data['current_time']
    market_hours_condition = 9 <= current_time.hour <= 15
    conditions_met['market_hours'] = market_hours_condition
    
    logger.info(f"   4. Market Hours Check:")
    logger.info(f"      Current Time: {current_time.strftime('%H:%M:%S')} ✅")
    logger.info(f"      Market Hours: 09:00 - 15:30")
    logger.info(f"      Status: {'✅ PASS - Market is open!' if market_hours_condition else '❌ FAIL'}")
    
    # 5. Trend Filter (SHOULD PASS)
    trend_condition = indicators['trend_direction'] == 'SIDEWAYS' or indicators['trend_strength'] < 0.7
    conditions_met['trend'] = trend_condition
    
    logger.info(f"   5. Trend Filter Check:")
    logger.info(f"      Trend Direction: {indicators['trend_direction']} ✅")
    logger.info(f"      Trend Strength: {indicators['trend_strength']:.1f} ✅")
    logger.info(f"      Status: {'✅ PASS - Perfect for straddles!' if trend_condition else '❌ FAIL'}")
    
    # Overall decision
    all_conditions_met = all(conditions_met.values())
    
    logger.info(f"\n📊 STRATEGY EVALUATION SUMMARY:")
    logger.info(f"   Conditions Passed: {sum(conditions_met.values())}/{len(conditions_met)} 🎯")
    
    for condition, status in conditions_met.items():
        logger.info(f"   {condition.replace('_', ' ').title()}: {'✅' if status else '❌'}")
    
    if all_conditions_met:
        # Calculate trade details
        premium_collected = (atm_options['call']['bid'] + atm_options['put']['bid']) * strategy_params['lot_size']
        
        logger.info(f"\n🎉 TRADE SIGNAL GENERATED! 🎉")
        logger.info(f"   Strategy: Short Straddle")
        logger.info(f"   Strike: {market_data['atm_strike']}")
        logger.info(f"   Call Bid Price: ₹{atm_options['call']['bid']:.2f}")
        logger.info(f"   Put Bid Price: ₹{atm_options['put']['bid']:.2f}")
        logger.info(f"   Premium Collected: ₹{premium_collected:,.2f} 💰")
        logger.info(f"   Lot Size: {strategy_params['lot_size']} contracts")
        logger.info(f"   Profit Target: ₹{strategy_params['profit_target']:,}")
        logger.info(f"   Stop Loss: ₹{strategy_params['stop_loss']:,}")
        logger.info(f"   Risk-Reward Ratio: 1:{strategy_params['profit_target']/strategy_params['stop_loss']:.1f}")
        
        # Additional trade analysis
        logger.info(f"\n📊 TRADE ANALYSIS:")
        logger.info(f"   Call IV: {atm_options['call']['iv']:.1%}")
        logger.info(f"   Put IV: {atm_options['put']['iv']:.1%}")
        logger.info(f"   Combined Delta: {atm_options['call']['delta'] + atm_options['put']['delta']:.2f} (near zero ✅)")
        logger.info(f"   Combined Theta: {atm_options['call']['theta'] + atm_options['put']['theta']:.2f} (time decay benefit)")
        logger.info(f"   Combined Vega: {atm_options['call']['vega'] + atm_options['put']['vega']:.2f} (IV risk)")
        
        return {
            'signal_generated': True,
            'strategy': 'short_straddle',
            'strike': market_data['atm_strike'],
            'premium_collected': premium_collected,
            'conditions_met': conditions_met,
            'call_price': atm_options['call']['bid'],
            'put_price': atm_options['put']['bid'],
            'iv_rank': iv_rank
        }
    else:
        logger.info(f"\n⚪ NO TRADING SIGNAL GENERATED")
        logger.info(f"   Reason: Not all conditions met")
        
        # Show which conditions failed
        failed_conditions = [condition for condition, status in conditions_met.items() if not status]
        logger.info(f"   Failed Conditions: {', '.join(failed_conditions)}")
        
        return {
            'signal_generated': False,
            'failed_conditions': failed_conditions,
            'conditions_met': conditions_met
        }

def main():
    """Main function to test high IV scenario"""
    
    # Setup logging
    logger = setup_detailed_logging()
    
    print("🔥 HIGH VOLATILITY MARKET SCENARIO TEST")
    print("=" * 60)
    print("This script simulates favorable market conditions")
    print("where straddle trading signals SHOULD be generated.")
    print("=" * 60)
    
    try:
        # Simulate high IV environment
        logger.info("\n" + "="*50)
        logger.info("HIGH VOLATILITY MARKET ANALYSIS")
        logger.info("="*50)
        
        market_data = simulate_high_iv_market_data()
        
        # Calculate indicators
        indicators = calculate_high_iv_indicators(market_data)
        
        # Evaluate strategy
        result = evaluate_straddle_in_high_iv(market_data, indicators)
        
        # Final summary
        logger.info(f"\n" + "="*50)
        logger.info("FINAL SUMMARY - HIGH IV SCENARIO")
        logger.info("="*50)
        
        if result['signal_generated']:
            logger.info("🎯 RESULT: TRADING SIGNAL GENERATED! 🎉")
            logger.info(f"   Premium to collect: ₹{result['premium_collected']:,.2f}")
            logger.info(f"   IV Rank: {result['iv_rank']:.1f}% (Excellent)")
            logger.info(f"   Call + Put Premium: ₹{result['call_price']:.2f} + ₹{result['put_price']:.2f}")
            logger.info(f"   This is exactly what we want to see! 🚀")
        else:
            logger.info("⚪ RESULT: NO TRADING SIGNAL")
            logger.info(f"   Reasons: {', '.join(result['failed_conditions'])}")
        
        print(f"\n📋 Detailed logs saved to: logs/high_iv_scenario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)