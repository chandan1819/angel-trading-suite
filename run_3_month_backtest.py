#!/usr/bin/env python3
"""
3-Month Bank Nifty Options Strategy Backtesting

This script runs a comprehensive 3-month backtest of the Bank Nifty options strategies
with realistic market conditions, proper risk management, and detailed performance analysis.
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def create_realistic_market_data():
    """Create realistic 3-month Bank Nifty market data"""
    
    # 3-month period: June 2024 to August 2024
    start_date = datetime(2024, 6, 1)
    end_date = datetime(2024, 8, 31)
    
    market_data = []
    current_date = start_date
    base_price = 48000  # Starting Bank Nifty level
    
    # Market scenarios for different periods
    scenarios = [
        # June: Sideways with high volatility (good for straddles)
        {"days": 30, "trend": 0.0, "volatility": 0.25, "iv_environment": "high"},
        # July: Mild uptrend with medium volatility
        {"days": 31, "trend": 0.15, "volatility": 0.18, "iv_environment": "medium"},
        # August: Sharp correction with very high volatility
        {"days": 31, "trend": -0.20, "volatility": 0.35, "iv_environment": "very_high"}
    ]
    
    day_count = 0
    
    for scenario in scenarios:
        for day in range(scenario["days"]):
            if current_date.weekday() < 5:  # Only trading days
                
                # Calculate price movement
                daily_return = scenario["trend"] / scenario["days"] + \
                              (scenario["volatility"] * 0.02 * (2 * (day % 2) - 1))  # Random-ish movement
                
                price = base_price * (1 + daily_return)
                base_price = price
                
                # Create realistic OHLC
                high = price * (1 + scenario["volatility"] * 0.01)
                low = price * (1 - scenario["volatility"] * 0.01)
                open_price = price * (1 + (scenario["volatility"] * 0.005 * (day % 3 - 1)))
                
                # Volume patterns
                volume = 1500000 + (day * 10000) + (scenario["volatility"] * 500000)
                
                # IV levels based on environment
                iv_levels = {
                    "low": 0.15,
                    "medium": 0.22,
                    "high": 0.28,
                    "very_high": 0.38
                }
                base_iv = iv_levels[scenario["iv_environment"]]
                
                market_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'open': round(open_price, 2),
                    'high': round(high, 2),
                    'low': round(low, 2),
                    'close': round(price, 2),
                    'volume': int(volume),
                    'iv_environment': scenario["iv_environment"],
                    'base_iv': base_iv,
                    'scenario': f"Period_{len(market_data)//30 + 1}"
                })
                
                day_count += 1
            
            current_date += timedelta(days=1)
    
    return market_data

def create_options_chain_data(underlying_price, base_iv, date):
    """Create realistic options chain data"""
    
    # ATM strike (nearest 100)
    atm_strike = round(underlying_price / 100) * 100
    
    # Create strikes around ATM
    strikes = []
    for i in range(-10, 11):  # 21 strikes total
        strike = atm_strike + (i * 100)
        strikes.append(strike)
    
    options_chain = {
        'underlying_price': underlying_price,
        'atm_strike': atm_strike,
        'expiry_date': date,
        'strikes': []
    }
    
    for strike in strikes:
        # Calculate moneyness
        moneyness = strike / underlying_price
        
        # IV smile (higher IV for OTM options)
        if moneyness < 0.98:  # ITM puts
            iv = base_iv * 1.1
        elif moneyness > 1.02:  # ITM calls
            iv = base_iv * 1.05
        else:  # ATM
            iv = base_iv
        
        # Option pricing (simplified Black-Scholes approximation)
        time_value = max(0.5, 3.0 - abs(strike - underlying_price) / 1000)
        intrinsic_call = max(0, underlying_price - strike)
        intrinsic_put = max(0, strike - underlying_price)
        
        call_price = intrinsic_call + time_value * iv * 100
        put_price = intrinsic_put + time_value * iv * 100
        
        # Liquidity (higher for ATM)
        distance_from_atm = abs(strike - atm_strike)
        volume = max(100, 2000 - distance_from_atm * 5)
        oi = max(500, 5000 - distance_from_atm * 10)
        
        strike_data = {
            'strike': strike,
            'call': {
                'ltp': round(call_price, 2),
                'bid': round(call_price * 0.98, 2),
                'ask': round(call_price * 1.02, 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(iv, 3)
            },
            'put': {
                'ltp': round(put_price, 2),
                'bid': round(put_price * 0.98, 2),
                'ask': round(put_price * 1.02, 2),
                'volume': int(volume),
                'oi': int(oi),
                'iv': round(iv, 3)
            }
        }
        
        options_chain['strikes'].append(strike_data)
    
    return options_chain

class StraddleBacktestStrategy:
    """Realistic straddle strategy for backtesting"""
    
    def __init__(self):
        self.name = "Conservative_Straddle"
        self.min_iv_rank = 70.0
        self.max_iv_rank = 95.0
        self.min_volume = 500
        self.min_oi = 2000
        self.max_bid_ask_spread = 3.0
        self.profit_target = 2000.0
        self.stop_loss = 1000.0
        self.lot_size = 35  # Updated lot size
        
    def evaluate(self, market_data, options_chain):
        """Evaluate straddle entry conditions"""
        
        try:
            # Get IV rank (simplified)
            base_iv = market_data.get('base_iv', 0.2)
            iv_rank = (base_iv - 0.15) / (0.4 - 0.15) * 100  # Scale to 0-100
            
            # Check IV conditions
            if not (self.min_iv_rank <= iv_rank <= self.max_iv_rank):
                return None
            
            # Find ATM options
            atm_strike = options_chain['atm_strike']
            atm_call = None
            atm_put = None
            
            for strike_data in options_chain['strikes']:
                if strike_data['strike'] == atm_strike:
                    atm_call = strike_data['call']
                    atm_put = strike_data['put']
                    break
            
            if not atm_call or not atm_put:
                return None
            
            # Check liquidity
            if (atm_call['volume'] < self.min_volume or 
                atm_put['volume'] < self.min_volume or
                atm_call['oi'] < self.min_oi or 
                atm_put['oi'] < self.min_oi):
                return None
            
            # Check bid-ask spreads
            call_spread = (atm_call['ask'] - atm_call['bid']) / atm_call['ltp'] * 100
            put_spread = (atm_put['ask'] - atm_put['bid']) / atm_put['ltp'] * 100
            
            if call_spread > self.max_bid_ask_spread or put_spread > self.max_bid_ask_spread:
                return None
            
            # Calculate premium collected (selling straddle)
            premium_collected = (atm_call['bid'] + atm_put['bid']) * self.lot_size
            
            # Create signal
            signal = {
                'strategy': self.name,
                'type': 'SHORT_STRADDLE',
                'strike': atm_strike,
                'call_price': atm_call['bid'],
                'put_price': atm_put['bid'],
                'premium_collected': premium_collected,
                'quantity': self.lot_size,
                'iv_rank': iv_rank,
                'confidence': min(0.9, iv_rank / 100),
                'target_profit': self.profit_target,
                'stop_loss': self.stop_loss
            }
            
            return signal
            
        except Exception as e:
            print(f"Error in strategy evaluation: {e}")
            return None

def simulate_trade_outcome(signal, market_data_sequence):
    """Simulate trade outcome over time"""
    
    entry_premium = signal['premium_collected']
    entry_date = market_data_sequence[0]['date']
    
    # Track P&L over trade duration (typically 1-3 days)
    max_profit = 0
    max_loss = 0
    final_pnl = 0
    
    for i, day_data in enumerate(market_data_sequence[1:6]):  # Max 5 days
        
        # Simulate option price decay and movement
        days_passed = i + 1
        time_decay = days_passed * 0.1  # Theta decay
        
        # Price movement impact
        price_change = day_data['close'] - market_data_sequence[0]['close']
        movement_impact = abs(price_change) * 0.8  # Straddle loses on big moves
        
        # Calculate current P&L
        current_pnl = entry_premium - movement_impact + time_decay * entry_premium * 0.1
        
        max_profit = max(max_profit, current_pnl)
        max_loss = min(max_loss, current_pnl)
        
        # Check exit conditions
        if current_pnl >= signal['target_profit']:
            return {
                'exit_reason': 'TARGET_HIT',
                'exit_day': i + 1,
                'final_pnl': signal['target_profit'],
                'max_profit': max_profit,
                'max_loss': max_loss
            }
        
        if current_pnl <= -signal['stop_loss']:
            return {
                'exit_reason': 'STOP_LOSS',
                'exit_day': i + 1,
                'final_pnl': -signal['stop_loss'],
                'max_profit': max_profit,
                'max_loss': max_loss
            }
        
        final_pnl = current_pnl
    
    # Exit at end of period
    return {
        'exit_reason': 'TIME_EXIT',
        'exit_day': len(market_data_sequence) - 1,
        'final_pnl': final_pnl,
        'max_profit': max_profit,
        'max_loss': max_loss
    }

def run_comprehensive_backtest():
    """Run comprehensive 3-month backtest"""
    
    print("🚀 BANK NIFTY OPTIONS - 3 MONTH BACKTEST")
    print("=" * 60)
    print("Period: June 2024 - August 2024")
    print("Strategy: Conservative Short Straddle")
    print("Lot Size: 35 contracts (Updated)")
    print("=" * 60)
    
    # Create market data
    print("\n📊 Generating realistic market data...")
    market_data = create_realistic_market_data()
    print(f"Generated {len(market_data)} trading days")
    
    # Initialize strategy
    strategy = StraddleBacktestStrategy()
    
    # Backtest parameters
    initial_capital = 500000  # ₹5 lakh
    current_capital = initial_capital
    trades = []
    daily_pnl = []
    
    print(f"\n💰 Initial Capital: ₹{initial_capital:,}")
    print(f"🎯 Profit Target: ₹{strategy.profit_target:,} per trade")
    print(f"🛑 Stop Loss: ₹{strategy.stop_loss:,} per trade")
    
    # Run backtest
    print("\n🔄 Running backtest...")
    
    i = 0
    while i < len(market_data) - 5:  # Need at least 5 days for trade duration
        
        day_data = market_data[i]
        
        # Create options chain
        options_chain = create_options_chain_data(
            day_data['close'], 
            day_data['base_iv'], 
            day_data['date']
        )
        
        # Evaluate strategy
        signal = strategy.evaluate(day_data, options_chain)
        
        if signal and current_capital > 50000:  # Minimum capital check
            
            # Simulate trade
            trade_sequence = market_data[i:i+6]
            outcome = simulate_trade_outcome(signal, trade_sequence)
            
            # Record trade
            trade = {
                'trade_id': len(trades) + 1,
                'entry_date': day_data['date'],
                'entry_price': day_data['close'],
                'strike': signal['strike'],
                'premium_collected': signal['premium_collected'],
                'iv_rank': signal['iv_rank'],
                'exit_reason': outcome['exit_reason'],
                'exit_day': outcome['exit_day'],
                'final_pnl': outcome['final_pnl'],
                'max_profit': outcome['max_profit'],
                'max_loss': outcome['max_loss'],
                'capital_before': current_capital,
                'capital_after': current_capital + outcome['final_pnl']
            }
            
            trades.append(trade)
            current_capital += outcome['final_pnl']
            
            # Skip ahead to avoid overlapping trades
            i += max(3, outcome['exit_day'])
            
            print(f"Trade {len(trades)}: {outcome['exit_reason']} - P&L: ₹{outcome['final_pnl']:,.0f}")
        
        else:
            i += 1
        
        # Record daily capital
        daily_pnl.append({
            'date': day_data['date'],
            'capital': current_capital,
            'daily_return': (current_capital - initial_capital) / initial_capital * 100
        })
    
    # Calculate performance metrics
    print("\n📈 Calculating performance metrics...")
    
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t['final_pnl'] > 0])
    losing_trades = total_trades - winning_trades
    
    total_pnl = current_capital - initial_capital
    total_return = (total_pnl / initial_capital) * 100
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = sum([t['final_pnl'] for t in trades if t['final_pnl'] > 0]) / winning_trades if winning_trades > 0 else 0
    avg_loss = sum([t['final_pnl'] for t in trades if t['final_pnl'] < 0]) / losing_trades if losing_trades > 0 else 0
    
    max_drawdown = min([d['daily_return'] for d in daily_pnl])
    
    # Display results
    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS - 3 MONTHS")
    print("=" * 60)
    
    print(f"\n💰 CAPITAL SUMMARY:")
    print(f"   Initial Capital: ₹{initial_capital:,}")
    print(f"   Final Capital: ₹{current_capital:,.0f}")
    print(f"   Total P&L: ₹{total_pnl:,.0f}")
    print(f"   Total Return: {total_return:.2f}%")
    print(f"   Monthly Return: {total_return/3:.2f}%")
    
    print(f"\n📈 TRADE STATISTICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Average Win: ₹{avg_win:,.0f}")
    print(f"   Average Loss: ₹{avg_loss:,.0f}")
    
    print(f"\n⚠️ RISK METRICS:")
    print(f"   Maximum Drawdown: {max_drawdown:.2f}%")
    print(f"   Profit Factor: {abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 else 'N/A'}")
    
    # Monthly breakdown
    print(f"\n📅 MONTHLY BREAKDOWN:")
    months = ['June 2024', 'July 2024', 'August 2024']
    month_trades = [
        [t for t in trades if '2024-06' in t['entry_date']],
        [t for t in trades if '2024-07' in t['entry_date']],
        [t for t in trades if '2024-08' in t['entry_date']]
    ]
    
    for i, month in enumerate(months):
        month_pnl = sum([t['final_pnl'] for t in month_trades[i]])
        month_count = len(month_trades[i])
        print(f"   {month}: {month_count} trades, P&L: ₹{month_pnl:,.0f}")
    
    # Save results
    print(f"\n💾 Saving results...")
    
    # Save trades to CSV
    trades_df = pd.DataFrame(trades)
    trades_df.to_csv('backtest_trades_3months.csv', index=False)
    
    # Save daily P&L
    daily_df = pd.DataFrame(daily_pnl)
    daily_df.to_csv('backtest_daily_pnl_3months.csv', index=False)
    
    # Save summary
    summary = {
        'period': 'June 2024 - August 2024',
        'strategy': 'Conservative Short Straddle',
        'lot_size': 35,
        'initial_capital': initial_capital,
        'final_capital': float(current_capital),
        'total_pnl': float(total_pnl),
        'total_return_pct': float(total_return),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate_pct': float(win_rate),
        'avg_win': float(avg_win),
        'avg_loss': float(avg_loss),
        'max_drawdown_pct': float(max_drawdown),
        'monthly_breakdown': {
            'june_trades': len(month_trades[0]),
            'june_pnl': float(sum([t['final_pnl'] for t in month_trades[0]])),
            'july_trades': len(month_trades[1]),
            'july_pnl': float(sum([t['final_pnl'] for t in month_trades[1]])),
            'august_trades': len(month_trades[2]),
            'august_pnl': float(sum([t['final_pnl'] for t in month_trades[2]]))
        }
    }
    
    with open('backtest_summary_3months.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("   ✅ backtest_trades_3months.csv")
    print("   ✅ backtest_daily_pnl_3months.csv") 
    print("   ✅ backtest_summary_3months.json")
    
    print("\n" + "=" * 60)
    print("🎉 3-MONTH BACKTEST COMPLETED!")
    print("=" * 60)
    
    return summary

if __name__ == "__main__":
    try:
        results = run_comprehensive_backtest()
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)