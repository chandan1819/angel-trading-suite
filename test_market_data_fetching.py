#!/usr/bin/env python3
"""
Market Data Fetching and Strategy Evaluation Test Script

This script shows exactly what data is being fetched and how strategy conditions
are evaluated, with detailed logging of all market data and decision points.
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
            logging.FileHandler(f'logs/market_data_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    
    return logging.getLogger(__name__)

def load_credentials():
    """Load API credentials with detailed logging"""
    logger = logging.getLogger(__name__)
    
    logger.info("🔐 Loading API credentials...")
    
    try:
        config_file = "config/config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            required_keys = ['api_key', 'client_code', 'pin', 'totp_secret']
            missing = []
            
            for key in required_keys:
                if not config_data.get(key):
                    missing.append(key)
                else:
                    logger.debug(f"✅ Found credential: {key}")
            
            if not missing:
                # Set environment variables from config file
                os.environ['ANGEL_API_KEY'] = config_data['api_key']
                os.environ['ANGEL_CLIENT_CODE'] = config_data['client_code']
                os.environ['ANGEL_PIN'] = config_data['pin']
                os.environ['ANGEL_TOTP_SECRET'] = config_data['totp_secret']
                
                logger.info(f"✅ Loaded credentials from {config_file}")
                logger.debug(f"   API Key: {config_data['api_key'][:6]}...")
                logger.debug(f"   Client Code: {config_data['client_code']}")
                logger.debug(f"   PIN: {'*' * len(config_data['pin'])}")
                logger.debug(f"   TOTP Secret: {config_data['totp_secret'][:6]}...")
                
                return True
            else:
                logger.error(f"❌ Missing credentials in config.json: {missing}")
                return False
    
    except Exception as e:
        logger.error(f"❌ Error loading credentials: {e}")
        return False

def simulate_live_data_fetching():
    """Simulate fetching live Bank Nifty data with detailed logging"""
    logger = logging.getLogger(__name__)
    
    logger.info("📊 Simulating live Bank Nifty data fetching...")
    
    # Simulate current market data
    current_time = datetime.now()
    
    # Simulate Bank Nifty spot price
    banknifty_spot = 51850.75  # Current realistic level
    
    logger.info(f"🎯 BANK NIFTY SPOT DATA:")
    logger.info(f"   Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Spot Price: ₹{banknifty_spot:,.2f}")
    logger.info(f"   Market Status: {'OPEN' if 9 <= current_time.hour <= 15 else 'CLOSED'}")
    
    # Calculate ATM strike
    atm_strike = round(banknifty_spot / 100) * 100
    logger.info(f"   ATM Strike: {atm_strike}")
    
    # Simulate options chain data
    logger.info(f"\n📋 FETCHING OPTIONS CHAIN DATA:")
    logger.info(f"   Underlying: BANKNIFTY")
    logger.info(f"   Expiry: Current week")
    logger.info(f"   Strikes: {atm_strike-500} to {atm_strike+500} (11 strikes)")
    
    # Create realistic options data
    options_data = {}
    
    for i in range(-5, 6):  # 11 strikes around ATM
        strike = atm_strike + (i * 100)
        
        # Simulate option prices
        call_intrinsic = max(0, banknifty_spot - strike)
        put_intrinsic = max(0, strike - banknifty_spot)
        
        # Time value based on distance from ATM
        time_value = max(50, 200 - abs(i) * 30)
        
        call_price = call_intrinsic + time_value
        put_price = put_intrinsic + time_value
        
        # Simulate Greeks and other data
        call_iv = 0.22 + abs(i) * 0.01  # IV smile
        put_iv = 0.22 + abs(i) * 0.01
        
        volume = max(100, 1000 - abs(i) * 150)
        oi = max(500, 3000 - abs(i) * 400)
        
        options_data[strike] = {
            'call': {
                'ltp': round(call_price, 2),
                'bid': round(call_price * 0.98, 2),
                'ask': round(call_price * 1.02, 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(call_iv, 3),
                'delta': round(0.5 + i * 0.1, 2),
                'theta': round(-15 - abs(i) * 2, 2),
                'vega': round(25 - abs(i) * 3, 2)
            },
            'put': {
                'ltp': round(put_price, 2),
                'bid': round(put_price * 0.98, 2),
                'ask': round(put_price * 1.02, 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(put_iv, 3),
                'delta': round(-0.5 - i * 0.1, 2),
                'theta': round(-15 - abs(i) * 2, 2),
                'vega': round(25 - abs(i) * 3, 2)
            }
        }
        
        logger.debug(f"   Strike {strike}: Call ₹{call_price:.2f}, Put ₹{put_price:.2f}, Vol {volume}, OI {oi}")
    
    logger.info(f"✅ Options chain data fetched for {len(options_data)} strikes")
    
    return {
        'spot_price': banknifty_spot,
        'atm_strike': atm_strike,
        'current_time': current_time,
        'options_data': options_data
    }

def calculate_market_indicators(market_data):
    """Calculate market indicators with detailed logging"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n📈 CALCULATING MARKET INDICATORS:")
    
    # Simulate historical volatility calculation
    historical_vol = 0.18  # 18% annual volatility
    logger.info(f"   Historical Volatility (20-day): {historical_vol:.1%}")
    
    # Calculate current IV from ATM options
    atm_options = market_data['options_data'][market_data['atm_strike']]
    current_iv = (atm_options['call']['iv'] + atm_options['put']['iv']) / 2
    logger.info(f"   Current ATM IV: {current_iv:.1%}")
    
    # Calculate IV Rank
    iv_rank = ((current_iv - 0.15) / (0.35 - 0.15)) * 100  # Scale to 0-100
    iv_rank = max(0, min(100, iv_rank))
    logger.info(f"   IV Rank: {iv_rank:.1f}%")
    
    # Calculate IV Percentile (simulated)
    iv_percentile = iv_rank * 0.9  # Approximate
    logger.info(f"   IV Percentile: {iv_percentile:.1f}%")
    
    # Market trend analysis (simulated)
    trend_direction = "SIDEWAYS"  # Could be BULLISH, BEARISH, SIDEWAYS
    trend_strength = 0.3  # 0-1 scale
    logger.info(f"   Trend Direction: {trend_direction}")
    logger.info(f"   Trend Strength: {trend_strength:.1f}")
    
    # Volume analysis
    total_call_volume = sum([data['call']['volume'] for data in market_data['options_data'].values()])
    total_put_volume = sum([data['put']['volume'] for data in market_data['options_data'].values()])
    pcr = total_put_volume / total_call_volume if total_call_volume > 0 else 1.0
    
    logger.info(f"   Total Call Volume: {total_call_volume:,}")
    logger.info(f"   Total Put Volume: {total_put_volume:,}")
    logger.info(f"   Put-Call Ratio: {pcr:.2f}")
    
    return {
        'historical_vol': historical_vol,
        'current_iv': current_iv,
        'iv_rank': iv_rank,
        'iv_percentile': iv_percentile,
        'trend_direction': trend_direction,
        'trend_strength': trend_strength,
        'pcr': pcr,
        'total_call_volume': total_call_volume,
        'total_put_volume': total_put_volume
    }

def evaluate_straddle_strategy(market_data, indicators):
    """Evaluate straddle strategy with detailed condition checking"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"\n🎯 EVALUATING STRADDLE STRATEGY CONDITIONS:")
    
    # Strategy parameters
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
    
    # 1. IV Rank Check
    iv_rank = indicators['iv_rank']
    iv_condition = strategy_params['min_iv_rank'] <= iv_rank <= strategy_params['max_iv_rank']
    conditions_met['iv_rank'] = iv_condition
    
    logger.info(f"\n🔍 CONDITION CHECKS:")
    logger.info(f"   1. IV Rank Check:")
    logger.info(f"      Current IV Rank: {iv_rank:.1f}%")
    logger.info(f"      Required Range: {strategy_params['min_iv_rank']:.1f}% - {strategy_params['max_iv_rank']:.1f}%")
    logger.info(f"      Status: {'✅ PASS' if iv_condition else '❌ FAIL'}")
    
    # 2. Liquidity Check
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
    logger.info(f"      ATM Call Volume: {call_volume} (min: {strategy_params['min_volume']})")
    logger.info(f"      ATM Put Volume: {put_volume} (min: {strategy_params['min_volume']})")
    logger.info(f"      ATM Call OI: {call_oi} (min: {strategy_params['min_oi']})")
    logger.info(f"      ATM Put OI: {put_oi} (min: {strategy_params['min_oi']})")
    logger.info(f"      Status: {'✅ PASS' if liquidity_condition else '❌ FAIL'}")
    
    # 3. Bid-Ask Spread Check
    call_spread = (atm_options['call']['ask'] - atm_options['call']['bid']) / atm_options['call']['ltp'] * 100
    put_spread = (atm_options['put']['ask'] - atm_options['put']['bid']) / atm_options['put']['ltp'] * 100
    spread_condition = call_spread <= strategy_params['max_bid_ask_spread'] and put_spread <= strategy_params['max_bid_ask_spread']
    conditions_met['spread'] = spread_condition
    
    logger.info(f"   3. Bid-Ask Spread Check:")
    logger.info(f"      Call Spread: {call_spread:.2f}% (max: {strategy_params['max_bid_ask_spread']:.1f}%)")
    logger.info(f"      Put Spread: {put_spread:.2f}% (max: {strategy_params['max_bid_ask_spread']:.1f}%)")
    logger.info(f"      Status: {'✅ PASS' if spread_condition else '❌ FAIL'}")
    
    # 4. Market Hours Check
    current_time = market_data['current_time']
    market_hours_condition = 9 <= current_time.hour <= 15
    conditions_met['market_hours'] = market_hours_condition
    
    logger.info(f"   4. Market Hours Check:")
    logger.info(f"      Current Time: {current_time.strftime('%H:%M:%S')}")
    logger.info(f"      Market Hours: 09:00 - 15:30")
    logger.info(f"      Status: {'✅ PASS' if market_hours_condition else '❌ FAIL'}")
    
    # 5. Trend Filter (optional)
    trend_condition = indicators['trend_direction'] == 'SIDEWAYS' or indicators['trend_strength'] < 0.7
    conditions_met['trend'] = trend_condition
    
    logger.info(f"   5. Trend Filter Check:")
    logger.info(f"      Trend Direction: {indicators['trend_direction']}")
    logger.info(f"      Trend Strength: {indicators['trend_strength']:.1f}")
    logger.info(f"      Status: {'✅ PASS' if trend_condition else '❌ FAIL'}")
    
    # Overall decision
    all_conditions_met = all(conditions_met.values())
    
    logger.info(f"\n📊 STRATEGY EVALUATION SUMMARY:")
    logger.info(f"   Conditions Passed: {sum(conditions_met.values())}/{len(conditions_met)}")
    
    for condition, status in conditions_met.items():
        logger.info(f"   {condition.replace('_', ' ').title()}: {'✅' if status else '❌'}")
    
    if all_conditions_met:
        # Calculate trade details
        premium_collected = (atm_options['call']['bid'] + atm_options['put']['bid']) * strategy_params['lot_size']
        
        logger.info(f"\n🎉 TRADE SIGNAL GENERATED!")
        logger.info(f"   Strategy: Short Straddle")
        logger.info(f"   Strike: {market_data['atm_strike']}")
        logger.info(f"   Call Price: ₹{atm_options['call']['bid']:.2f}")
        logger.info(f"   Put Price: ₹{atm_options['put']['bid']:.2f}")
        logger.info(f"   Premium Collected: ₹{premium_collected:,.2f}")
        logger.info(f"   Lot Size: {strategy_params['lot_size']} contracts")
        logger.info(f"   Profit Target: ₹{strategy_params['profit_target']:,}")
        logger.info(f"   Stop Loss: ₹{strategy_params['stop_loss']:,}")
        
        return {
            'signal_generated': True,
            'strategy': 'short_straddle',
            'strike': market_data['atm_strike'],
            'premium_collected': premium_collected,
            'conditions_met': conditions_met
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
    """Main function to test market data fetching and strategy evaluation"""
    
    # Setup logging
    logger = setup_detailed_logging()
    
    print("🚀 MARKET DATA FETCHING & STRATEGY EVALUATION TEST")
    print("=" * 60)
    print("This script shows exactly what data is being fetched")
    print("and how strategy conditions are evaluated.")
    print("=" * 60)
    
    try:
        # Load credentials
        if not load_credentials():
            logger.error("❌ Failed to load credentials")
            return 1
        
        # Simulate data fetching
        logger.info("\n" + "="*50)
        logger.info("STARTING MARKET DATA ANALYSIS")
        logger.info("="*50)
        
        market_data = simulate_live_data_fetching()
        
        # Calculate indicators
        indicators = calculate_market_indicators(market_data)
        
        # Evaluate strategy
        result = evaluate_straddle_strategy(market_data, indicators)
        
        # Final summary
        logger.info(f"\n" + "="*50)
        logger.info("FINAL SUMMARY")
        logger.info("="*50)
        
        if result['signal_generated']:
            logger.info("🎯 RESULT: TRADING SIGNAL GENERATED")
            logger.info(f"   Premium to collect: ₹{result['premium_collected']:,.2f}")
        else:
            logger.info("⚪ RESULT: NO TRADING SIGNAL")
            logger.info(f"   Reasons: {', '.join(result['failed_conditions'])}")
        
        print(f"\n📋 Detailed logs saved to: logs/market_data_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)