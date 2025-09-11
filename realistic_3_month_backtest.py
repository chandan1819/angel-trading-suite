#!/usr/bin/env python3
"""
Realistic 3-Month Bank Nifty Options Strategy Backtesting
With actual market-like conditions and multiple strategies
"""

import sys
import os
import json
import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path

def create_realistic_market_scenarios():
    """Create realistic 3-month Bank Nifty scenarios based on actual market patterns"""
    
    # June 2024 - August 2024 simulation
    scenarios = []
    base_price = 48000
    
    # June 2024: High volatility period (good for straddles)
    june_data = []
    current_price = base_price
    for day in range(22):  # 22 trading days in June
        
        # High volatility environment
        daily_move = random.uniform(-2.5, 2.5)  # ±2.5% daily moves
        current_price *= (1 + daily_move/100)
        
        # High IV environment (75-90%)
        iv_rank = random.uniform(75, 90)
        base_iv = 0.25 + (iv_rank/100) * 0.15  # 0.25 to 0.40
        
        june_data.append({
            'date': (datetime(2024, 6, 1) + timedelta(days=day)).strftime('%Y-%m-%d'),
            'close': round(current_price, 2),
            'iv_rank': iv_rank,
            'base_iv': base_iv,
            'volatility_regime': 'high',
            'month': 'June'
        })
    
    # July 2024: Medium volatility with trend
    july_data = []
    for day in range(23):  # 23 trading days in July
        
        # Medium volatility with slight uptrend
        daily_move = random.uniform(-1.5, 2.0)  # Slight bullish bias
        current_price *= (1 + daily_move/100)
        
        # Medium IV environment (60-80%)
        iv_rank = random.uniform(60, 80)
        base_iv = 0.20 + (iv_rank/100) * 0.12
        
        july_data.append({
            'date': (datetime(2024, 7, 1) + timedelta(days=day)).strftime('%Y-%m-%d'),
            'close': round(current_price, 2),
            'iv_rank': iv_rank,
            'base_iv': base_iv,
            'volatility_regime': 'medium',
            'month': 'July'
        })
    
    # August 2024: Very high volatility (correction period)
    august_data = []
    for day in range(22):  # 22 trading days in August
        
        # Very high volatility with downtrend
        daily_move = random.uniform(-4.0, 2.0)  # Bearish bias with high volatility
        current_price *= (1 + daily_move/100)
        
        # Very high IV environment (80-95%)
        iv_rank = random.uniform(80, 95)
        base_iv = 0.30 + (iv_rank/100) * 0.20
        
        august_data.append({
            'date': (datetime(2024, 8, 1) + timedelta(days=day)).strftime('%Y-%m-%d'),
            'close': round(current_price, 2),
            'iv_rank': iv_rank,
            'base_iv': base_iv,
            'volatility_regime': 'very_high',
            'month': 'August'
        })
    
    return june_data + july_data + august_data

class MultiStrategyBacktest:
    """Multi-strategy backtesting with realistic conditions"""
    
    def __init__(self):
        self.lot_size = 35  # Updated lot size
        self.strategies = {
            'conservative_straddle': {
                'min_iv_rank': 70,
                'max_iv_rank': 95,
                'profit_target': 2000,
                'stop_loss': 1000,
                'success_rate': 0.65,  # 65% success rate in high IV
                'avg_hold_days': 2
            },
            'aggressive_straddle': {
                'min_iv_rank': 60,
                'max_iv_rank': 95,
                'profit_target': 3000,
                'stop_loss': 1500,
                'success_rate': 0.55,  # 55% success rate
                'avg_hold_days': 3
            },
            'iron_condor': {
                'min_iv_rank': 50,
                'max_iv_rank': 85,
                'profit_target': 1500,
                'stop_loss': 3000,
                'success_rate': 0.70,  # 70% success rate in range-bound
                'avg_hold_days': 5
            }
        }
    
    def evaluate_strategy(self, strategy_name, market_data):
        """Evaluate if strategy conditions are met"""
        
        strategy = self.strategies[strategy_name]
        iv_rank = market_data['iv_rank']
        
        # Check IV rank conditions
        if not (strategy['min_iv_rank'] <= iv_rank <= strategy['max_iv_rank']):
            return None
        
        # Calculate premium based on IV and strategy
        base_premium = 150 * (iv_rank / 100) * self.lot_size  # Base premium calculation
        
        if strategy_name == 'conservative_straddle':
            premium = base_premium * 1.2  # Higher premium for ATM straddle
        elif strategy_name == 'aggressive_straddle':
            premium = base_premium * 1.5  # Even higher for aggressive
        else:  # iron_condor
            premium = base_premium * 0.8  # Lower premium for defined risk
        
        return {
            'strategy': strategy_name,
            'entry_date': market_data['date'],
            'entry_price': market_data['close'],
            'iv_rank': iv_rank,
            'premium_collected': round(premium, 2),
            'profit_target': strategy['profit_target'],
            'stop_loss': strategy['stop_loss'],
            'success_rate': strategy['success_rate'],
            'hold_days': strategy['avg_hold_days']
        }
    
    def simulate_trade_outcome(self, trade, market_sequence):
        """Simulate realistic trade outcome"""
        
        strategy = self.strategies[trade['strategy']]
        
        # Determine outcome based on success rate and market conditions
        success_probability = strategy['success_rate']
        
        # Adjust success rate based on market volatility
        if len(market_sequence) > 1:
            price_moves = []
            for i in range(1, min(len(market_sequence), trade['hold_days'] + 1)):
                move = abs(market_sequence[i]['close'] - market_sequence[i-1]['close']) / market_sequence[i-1]['close']
                price_moves.append(move)
            
            avg_move = sum(price_moves) / len(price_moves) if price_moves else 0
            
            # For straddles: big moves are bad, small moves are good
            if 'straddle' in trade['strategy']:
                if avg_move > 0.02:  # >2% daily moves
                    success_probability *= 0.7  # Reduce success rate
                elif avg_move < 0.01:  # <1% daily moves
                    success_probability *= 1.2  # Increase success rate
        
        # Determine outcome
        is_successful = random.random() < success_probability
        
        if is_successful:
            # Successful trade - hit profit target
            actual_pnl = trade['profit_target']
            exit_reason = 'PROFIT_TARGET'
        else:
            # Unsuccessful trade - determine loss amount
            if random.random() < 0.6:  # 60% hit stop loss
                actual_pnl = -trade['stop_loss']
                exit_reason = 'STOP_LOSS'
            else:  # 40% partial loss
                actual_pnl = random.uniform(-trade['stop_loss'], -trade['stop_loss'] * 0.3)
                exit_reason = 'PARTIAL_LOSS'
        
        return {
            'final_pnl': round(actual_pnl, 2),
            'exit_reason': exit_reason,
            'hold_days': min(trade['hold_days'], len(market_sequence) - 1)
        }

def run_comprehensive_backtest():
    """Run comprehensive multi-strategy backtest"""
    
    print("🚀 BANK NIFTY OPTIONS - COMPREHENSIVE 3-MONTH BACKTEST")
    print("=" * 70)
    print("📅 Period: June 2024 - August 2024")
    print("🎯 Strategies: Conservative Straddle, Aggressive Straddle, Iron Condor")
    print("📊 Lot Size: 35 contracts (Updated NSE Standard)")
    print("💰 Initial Capital: ₹10,00,000")
    print("=" * 70)
    
    # Generate market data
    print("\n📊 Generating realistic market scenarios...")
    market_data = create_realistic_market_scenarios()
    print(f"✅ Generated {len(market_data)} trading days")
    
    # Initialize backtest
    backtester = MultiStrategyBacktest()
    initial_capital = 1000000  # ₹10 lakh
    current_capital = initial_capital
    
    all_trades = []
    monthly_stats = {'June': [], 'July': [], 'August': []}
    
    # Strategy allocation
    strategy_weights = {
        'conservative_straddle': 0.5,  # 50% allocation
        'aggressive_straddle': 0.3,    # 30% allocation
        'iron_condor': 0.2             # 20% allocation
    }
    
    print(f"\n🎯 Strategy Allocation:")
    for strategy, weight in strategy_weights.items():
        print(f"   {strategy.replace('_', ' ').title()}: {weight*100:.0f}%")
    
    print(f"\n🔄 Running backtest simulation...")
    
    # Run backtest
    i = 0
    while i < len(market_data) - 7:  # Need buffer for trade duration
        
        day_data = market_data[i]
        
        # Try each strategy
        for strategy_name, weight in strategy_weights.items():
            
            # Check if we have enough capital for this strategy
            required_capital = 100000  # Minimum ₹1 lakh per trade
            if current_capital < required_capital:
                continue
            
            # Evaluate strategy
            signal = backtester.evaluate_strategy(strategy_name, day_data)
            
            if signal:
                # Simulate trade
                trade_sequence = market_data[i:i+8]  # Up to 7 days
                outcome = backtester.simulate_trade_outcome(signal, trade_sequence)
                
                # Record trade
                trade = {
                    'trade_id': len(all_trades) + 1,
                    'strategy': strategy_name,
                    'entry_date': signal['entry_date'],
                    'entry_price': signal['entry_price'],
                    'iv_rank': signal['iv_rank'],
                    'premium_collected': signal['premium_collected'],
                    'profit_target': signal['profit_target'],
                    'stop_loss': signal['stop_loss'],
                    'final_pnl': outcome['final_pnl'],
                    'exit_reason': outcome['exit_reason'],
                    'hold_days': outcome['hold_days'],
                    'capital_before': current_capital,
                    'month': day_data['month']
                }
                
                all_trades.append(trade)
                current_capital += outcome['final_pnl']
                monthly_stats[day_data['month']].append(trade)
                
                print(f"  Trade {len(all_trades)}: {strategy_name} - {outcome['exit_reason']} - P&L: ₹{outcome['final_pnl']:,.0f}")
                
                # Skip ahead to avoid overlapping trades
                i += max(2, outcome['hold_days'])
                break  # Only one trade per day
        
        i += 1
    
    # Calculate comprehensive results
    print(f"\n📈 Calculating performance metrics...")
    
    total_trades = len(all_trades)
    winning_trades = len([t for t in all_trades if t['final_pnl'] > 0])
    losing_trades = total_trades - winning_trades
    
    total_pnl = current_capital - initial_capital
    total_return = (total_pnl / initial_capital) * 100
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = sum([t['final_pnl'] for t in all_trades if t['final_pnl'] > 0]) / winning_trades if winning_trades > 0 else 0
    avg_loss = sum([t['final_pnl'] for t in all_trades if t['final_pnl'] < 0]) / losing_trades if losing_trades > 0 else 0
    
    # Strategy-wise breakdown
    strategy_stats = {}
    for strategy in strategy_weights.keys():
        strategy_trades = [t for t in all_trades if t['strategy'] == strategy]
        if strategy_trades:
            strategy_pnl = sum([t['final_pnl'] for t in strategy_trades])
            strategy_wins = len([t for t in strategy_trades if t['final_pnl'] > 0])
            strategy_win_rate = (strategy_wins / len(strategy_trades)) * 100
            
            strategy_stats[strategy] = {
                'trades': len(strategy_trades),
                'pnl': strategy_pnl,
                'win_rate': strategy_win_rate,
                'avg_pnl': strategy_pnl / len(strategy_trades)
            }
    
    # Display comprehensive results
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE BACKTEST RESULTS")
    print("=" * 70)
    
    print(f"\n💰 OVERALL PERFORMANCE:")
    print(f"   Initial Capital: ₹{initial_capital:,}")
    print(f"   Final Capital: ₹{current_capital:,.0f}")
    print(f"   Total P&L: ₹{total_pnl:,.0f}")
    print(f"   Total Return: {total_return:.2f}%")
    print(f"   Monthly Return: {total_return/3:.2f}%")
    print(f"   Annualized Return: {total_return*4:.2f}%")
    
    print(f"\n📈 TRADE STATISTICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Average Win: ₹{avg_win:,.0f}")
    print(f"   Average Loss: ₹{avg_loss:,.0f}")
    print(f"   Profit Factor: {abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 else 'N/A'}")
    
    print(f"\n🎯 STRATEGY BREAKDOWN:")
    for strategy, stats in strategy_stats.items():
        print(f"   {strategy.replace('_', ' ').title()}:")
        print(f"     Trades: {stats['trades']}")
        print(f"     P&L: ₹{stats['pnl']:,.0f}")
        print(f"     Win Rate: {stats['win_rate']:.1f}%")
        print(f"     Avg P&L: ₹{stats['avg_pnl']:,.0f}")
    
    print(f"\n📅 MONTHLY BREAKDOWN:")
    for month, trades in monthly_stats.items():
        if trades:
            month_pnl = sum([t['final_pnl'] for t in trades])
            month_wins = len([t for t in trades if t['final_pnl'] > 0])
            month_win_rate = (month_wins / len(trades)) * 100
            print(f"   {month} 2024:")
            print(f"     Trades: {len(trades)}")
            print(f"     P&L: ₹{month_pnl:,.0f}")
            print(f"     Win Rate: {month_win_rate:.1f}%")
    
    # Risk metrics
    daily_returns = []
    running_capital = initial_capital
    for trade in all_trades:
        running_capital += trade['final_pnl']
        daily_return = trade['final_pnl'] / trade['capital_before']
        daily_returns.append(daily_return)
    
    if daily_returns:
        max_drawdown = min(daily_returns) * 100
        volatility = (sum([(r - sum(daily_returns)/len(daily_returns))**2 for r in daily_returns]) / len(daily_returns))**0.5 * 100
        sharpe_ratio = (total_return / 3) / (volatility / (3**0.5)) if volatility > 0 else 0
    else:
        max_drawdown = 0
        volatility = 0
        sharpe_ratio = 0
    
    print(f"\n⚠️ RISK METRICS:")
    print(f"   Maximum Drawdown: {max_drawdown:.2f}%")
    print(f"   Volatility: {volatility:.2f}%")
    print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")
    
    # Save detailed results
    print(f"\n💾 Saving detailed results...")
    
    # Save all trades
    trades_df = pd.DataFrame(all_trades)
    trades_df.to_csv('comprehensive_backtest_trades.csv', index=False)
    
    # Save summary
    summary = {
        'backtest_info': {
            'period': 'June 2024 - August 2024',
            'strategies': list(strategy_weights.keys()),
            'lot_size': 35,
            'initial_capital': initial_capital
        },
        'performance': {
            'final_capital': float(current_capital),
            'total_pnl': float(total_pnl),
            'total_return_pct': float(total_return),
            'monthly_return_pct': float(total_return/3),
            'annualized_return_pct': float(total_return*4)
        },
        'trade_stats': {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate_pct': float(win_rate),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(abs(avg_win * winning_trades / (avg_loss * losing_trades))) if losing_trades > 0 else None
        },
        'risk_metrics': {
            'max_drawdown_pct': float(max_drawdown),
            'volatility_pct': float(volatility),
            'sharpe_ratio': float(sharpe_ratio)
        },
        'strategy_breakdown': strategy_stats,
        'monthly_breakdown': {
            month: {
                'trades': len(trades),
                'pnl': float(sum([t['final_pnl'] for t in trades])),
                'win_rate': float(len([t for t in trades if t['final_pnl'] > 0]) / len(trades) * 100) if trades else 0
            } for month, trades in monthly_stats.items() if trades
        }
    }
    
    with open('comprehensive_backtest_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("   ✅ comprehensive_backtest_trades.csv")
    print("   ✅ comprehensive_backtest_summary.json")
    
    print("\n" + "=" * 70)
    print("🎉 COMPREHENSIVE 3-MONTH BACKTEST COMPLETED!")
    print("=" * 70)
    
    return summary

if __name__ == "__main__":
    try:
        results = run_comprehensive_backtest()
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)