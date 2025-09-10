#!/usr/bin/env python3
"""
Simple Options Chain Display Demo
Shows exactly how options chain data looks and is processed
"""

import json
import random
from datetime import datetime

def show_options_chain_structure():
    """Show the complete options chain structure and API flow"""
    
    print("🔍 BANK NIFTY OPTIONS CHAIN - COMPLETE FLOW")
    print("=" * 70)
    
    # Simulate current market data
    banknifty_spot = 45150.75
    current_time = datetime.now()
    
    print(f"📊 STEP 1: MARKET DATA COLLECTION")
    print("-" * 40)
    print(f"⏰ Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💹 BANKNIFTY Spot Price: ₹{banknifty_spot:,.2f}")
    print(f"📡 API Call: angel_api.get_options_chain('BANKNIFTY')")
    print(f"🔄 Processing: Fetching all option contracts...")
    print()
    
    # Calculate ATM strike
    atm_strike = round(banknifty_spot / 100) * 100
    print(f"🎯 STEP 2: ATM STRIKE CALCULATION")
    print("-" * 40)
    print(f"Spot Price: ₹{banknifty_spot:,.2f}")
    print(f"Available Strikes: 44800, 44900, 45000, 45100, 45200, 45300...")
    print(f"Distance Calculation:")
    print(f"  |{banknifty_spot} - 45100| = {abs(banknifty_spot - 45100):.2f}")
    print(f"  |{banknifty_spot} - 45200| = {abs(banknifty_spot - 45200):.2f}")
    print(f"🎯 ATM Strike Selected: {atm_strike} (closest to spot)")
    print()
    
    # Generate realistic options chain data
    print(f"📋 STEP 3: COMPLETE OPTIONS CHAIN DATA")
    print("-" * 40)
    
    options_chain = generate_realistic_options_chain(banknifty_spot, atm_strike)
    
    # Display the chain
    print(f"{'Strike':<8} {'Call LTP':<10} {'Call Bid':<10} {'Call Ask':<10} {'Call Vol':<10} {'Call OI':<12} {'Put LTP':<10} {'Put Bid':<10} {'Put Ask':<10} {'Put Vol':<10} {'Put OI':<10}")
    print("-" * 120)
    
    for strike_data in options_chain:
        strike = strike_data['strike']
        call = strike_data['call']
        put = strike_data['put']
        
        marker = " 🎯" if strike == atm_strike else ""
        
        print(f"{strike:<8.0f} "
              f"{call['ltp']:<10.2f} {call['bid']:<10.2f} {call['ask']:<10.2f} "
              f"{call['volume']:<10} {call['oi']:<12} "
              f"{put['ltp']:<10.2f} {put['bid']:<10.2f} {put['ask']:<10.2f} "
              f"{put['volume']:<10} {put['oi']:<10}{marker}")
    
    print("-" * 120)
    print()
    
    # Show strategy analysis
    print(f"🎲 STEP 4: STRADDLE STRATEGY ANALYSIS")
    print("-" * 40)
    
    # Find ATM data
    atm_data = next(s for s in options_chain if s['strike'] == atm_strike)
    call_ltp = atm_data['call']['ltp']
    put_ltp = atm_data['put']['ltp']
    call_bid = atm_data['call']['bid']
    call_ask = atm_data['call']['ask']
    put_bid = atm_data['put']['bid']
    put_ask = atm_data['put']['ask']
    
    # Calculate spreads
    call_spread = call_ask - call_bid
    put_spread = put_ask - put_bid
    
    print(f"ATM Strike: {atm_strike}")
    print(f"Call Option ({atm_strike}CE):")
    print(f"  LTP: ₹{call_ltp:.2f}")
    print(f"  Bid: ₹{call_bid:.2f}, Ask: ₹{call_ask:.2f}")
    print(f"  Spread: ₹{call_spread:.2f}")
    print(f"  Volume: {atm_data['call']['volume']:,}")
    print(f"  Open Interest: {atm_data['call']['oi']:,}")
    print()
    print(f"Put Option ({atm_strike}PE):")
    print(f"  LTP: ₹{put_ltp:.2f}")
    print(f"  Bid: ₹{put_bid:.2f}, Ask: ₹{put_ask:.2f}")
    print(f"  Spread: ₹{put_spread:.2f}")
    print(f"  Volume: {atm_data['put']['volume']:,}")
    print(f"  Open Interest: {atm_data['put']['oi']:,}")
    print()
    
    # Straddle analysis
    straddle_premium = call_ltp + put_ltp
    breakeven_high = atm_strike + straddle_premium
    breakeven_low = atm_strike - straddle_premium
    
    print(f"🎯 STRADDLE TRADE ANALYSIS:")
    print(f"  Total Premium Collected: ₹{straddle_premium:.2f}")
    print(f"  Breakeven Points: ₹{breakeven_low:.2f} - ₹{breakeven_high:.2f}")
    print(f"  Profit Zone: BANKNIFTY stays between breakevens")
    print(f"  Max Profit: ₹{straddle_premium:.2f} (if expires exactly at {atm_strike})")
    print()
    
    # Liquidity check
    print(f"💧 STEP 5: LIQUIDITY VALIDATION")
    print("-" * 40)
    
    min_volume = 500
    max_spread = 3.0
    min_oi = 2000
    
    call_volume_ok = atm_data['call']['volume'] >= min_volume
    put_volume_ok = atm_data['put']['volume'] >= min_volume
    call_spread_ok = call_spread <= max_spread
    put_spread_ok = put_spread <= max_spread
    call_oi_ok = atm_data['call']['oi'] >= min_oi
    put_oi_ok = atm_data['put']['oi'] >= min_oi
    
    print(f"Call Volume: {atm_data['call']['volume']:,} {'✅' if call_volume_ok else '❌'} (need ≥{min_volume})")
    print(f"Put Volume: {atm_data['put']['volume']:,} {'✅' if put_volume_ok else '❌'} (need ≥{min_volume})")
    print(f"Call Spread: ₹{call_spread:.2f} {'✅' if call_spread_ok else '❌'} (need ≤₹{max_spread})")
    print(f"Put Spread: ₹{put_spread:.2f} {'✅' if put_spread_ok else '❌'} (need ≤₹{max_spread})")
    print(f"Call OI: {atm_data['call']['oi']:,} {'✅' if call_oi_ok else '❌'} (need ≥{min_oi:,})")
    print(f"Put OI: {atm_data['put']['oi']:,} {'✅' if put_oi_ok else '❌'} (need ≥{min_oi:,})")
    
    liquidity_ok = all([call_volume_ok, put_volume_ok, call_spread_ok, put_spread_ok, call_oi_ok, put_oi_ok])
    print(f"\n🎯 Liquidity Check: {'✅ PASSED' if liquidity_ok else '❌ FAILED'}")
    print()
    
    # IV Analysis
    print(f"📈 STEP 6: IMPLIED VOLATILITY ANALYSIS")
    print("-" * 40)
    
    # Simulate IV data
    current_iv = random.uniform(15, 25)
    iv_30d_low = 12
    iv_30d_high = 28
    iv_rank = (current_iv - iv_30d_low) / (iv_30d_high - iv_30d_low) * 100
    
    print(f"Current ATM IV: {current_iv:.1f}%")
    print(f"30-day IV Range: {iv_30d_low}% - {iv_30d_high}%")
    print(f"IV Rank: {iv_rank:.1f}%")
    
    iv_ok = iv_rank >= 70
    print(f"IV Requirement: ≥70% {'✅ PASSED' if iv_ok else '❌ FAILED'}")
    print()
    
    # Final decision
    print(f"🚀 STEP 7: TRADING DECISION")
    print("-" * 40)
    
    conditions = {
        'Liquidity': liquidity_ok,
        'IV Rank': iv_ok,
        'Market Hours': True,  # Assume market is open
        'Risk Limits': True    # Assume within limits
    }
    
    for condition, status in conditions.items():
        print(f"{condition}: {'✅ PASSED' if status else '❌ FAILED'}")
    
    all_conditions_met = all(conditions.values())
    
    print(f"\n🎯 FINAL DECISION: {'🚀 EXECUTE STRADDLE TRADE' if all_conditions_met else '⏸️ NO TRADE - CONDITIONS NOT MET'}")
    
    if all_conditions_met:
        print(f"\n📋 TRADE EXECUTION:")
        print(f"  SELL {atm_strike}CE @ ₹{call_ltp:.2f} × 25 lots = ₹{call_ltp * 25:,.0f}")
        print(f"  SELL {atm_strike}PE @ ₹{put_ltp:.2f} × 25 lots = ₹{put_ltp * 25:,.0f}")
        print(f"  Total Credit: ₹{(call_ltp + put_ltp) * 25:,.0f}")
        print(f"  Profit Target: ₹2,000")
        print(f"  Stop Loss: ₹1,000")
    
    print()

def generate_realistic_options_chain(spot_price, atm_strike):
    """Generate realistic options chain data"""
    
    options_chain = []
    
    # Generate strikes around ATM
    for i in range(-6, 7):  # 13 strikes
        strike = atm_strike + (i * 100)
        
        # Calculate intrinsic values
        call_intrinsic = max(0, spot_price - strike)
        put_intrinsic = max(0, strike - spot_price)
        
        # Add time value (decreases with distance from ATM)
        distance_from_atm = abs(strike - spot_price)
        time_value = max(10, 80 - distance_from_atm * 0.3) + random.uniform(-10, 10)
        
        # Calculate option prices
        call_ltp = call_intrinsic + time_value + random.uniform(-5, 5)
        put_ltp = put_intrinsic + time_value + random.uniform(-5, 5)
        
        # Ensure minimum prices
        call_ltp = max(5, call_ltp)
        put_ltp = max(5, put_ltp)
        
        # Generate bid-ask spreads (tighter for ATM)
        if abs(strike - atm_strike) <= 100:  # ATM and near ATM
            call_spread = random.uniform(1.5, 3.0)
            put_spread = random.uniform(1.5, 3.0)
        else:  # OTM options
            call_spread = random.uniform(2.0, 5.0)
            put_spread = random.uniform(2.0, 5.0)
        
        call_bid = call_ltp - call_spread/2
        call_ask = call_ltp + call_spread/2
        put_bid = put_ltp - put_spread/2
        put_ask = put_ltp + put_spread/2
        
        # Generate volume and OI (higher for ATM)
        if abs(strike - atm_strike) <= 100:  # ATM and near ATM
            call_volume = random.randint(1000, 5000)
            put_volume = random.randint(800, 4500)
            call_oi = random.randint(10000, 50000)
            put_oi = random.randint(8000, 45000)
        else:  # OTM options
            call_volume = random.randint(100, 2000)
            put_volume = random.randint(100, 2000)
            call_oi = random.randint(1000, 20000)
            put_oi = random.randint(1000, 20000)
        
        options_chain.append({
            'strike': strike,
            'call': {
                'ltp': call_ltp,
                'bid': call_bid,
                'ask': call_ask,
                'volume': call_volume,
                'oi': call_oi
            },
            'put': {
                'ltp': put_ltp,
                'bid': put_bid,
                'ask': put_ask,
                'volume': put_volume,
                'oi': put_oi
            }
        })
    
    return options_chain

def show_api_call_sequence():
    """Show the exact API call sequence"""
    
    print("\n🔧 EXACT API CALL SEQUENCE")
    print("=" * 50)
    
    api_calls = [
        "1. angel_api.authenticate()",
        "2. angel_api.get_ltp('NSE', 'BANKNIFTY')",
        "3. angel_api.search_instruments('NSE', 'BANKNIFTY')",
        "4. angel_api.get_ltp_batch([all_option_tokens])",
        "5. process_options_chain(raw_data)",
        "6. calculate_atm_strike(spot_price, strikes)",
        "7. validate_liquidity(options_chain)",
        "8. calculate_iv_metrics(options_chain)",
        "9. evaluate_straddle_conditions()",
        "10. generate_trading_signal()"
    ]
    
    for call in api_calls:
        print(f"   {call}")
    
    print("\n📊 DATA FLOW:")
    print("   Raw API Data → Processed Chain → Strategy Analysis → Trading Decision")

if __name__ == '__main__':
    show_options_chain_structure()
    show_api_call_sequence()
    
    print("\n" + "="*70)
    print("🎯 KEY TAKEAWAYS:")
    print("• System fetches complete options chain every 60 seconds")
    print("• Analyzes liquidity, spreads, volume, and open interest")
    print("• Calculates ATM strike based on current spot price")
    print("• Validates all conditions before generating trade signals")
    print("• Only trades when IV rank > 70% and liquidity is good")
    print("• Conservative approach - most cycles result in NO TRADE")
    print("="*70)