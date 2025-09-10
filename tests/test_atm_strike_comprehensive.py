"""
Comprehensive unit tests for ATM strike selection with various market conditions.

This module tests the ATM strike calculation algorithm under different scenarios
including edge cases, tie-breaker logic, and market condition variations.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import List, Dict, Any

from src.data.data_manager import DataManager, ATMStrikeResult
from src.api.market_data import OptionsChainData


class TestATMStrikeComprehensive:
    """Comprehensive tests for ATM strike selection algorithm"""
    
    @pytest.fixture
    def data_manager(self):
        """Create DataManager with mocked dependencies"""
        mock_api_client = Mock()
        mock_config_manager = Mock()
        mock_config_manager.get_section.return_value = {
            'atm_tie_breaker': 'lower',
            'max_strike_distance': 0.05,
            'default_lot_size': 35
        }
        return DataManager(mock_api_client, mock_config_manager)
    
    def create_options_chain(self, strikes: List[float], spot_price: float) -> OptionsChainData:
        """Helper to create options chain with given strikes and spot price"""
        strikes_data = []
        for strike in strikes:
            strikes_data.append({
                'strike': strike,
                'call': {
                    'symbol': f'BANKNIFTY01JAN25CE{int(strike)}',
                    'token': f'token_{int(strike)}_CE',
                    'ltp': max(1.0, abs(spot_price - strike) * 0.1),
                    'exchange': 'NFO'
                },
                'put': {
                    'symbol': f'BANKNIFTY01JAN25PE{int(strike)}',
                    'token': f'token_{int(strike)}_PE',
                    'ltp': max(1.0, abs(spot_price - strike) * 0.1),
                    'exchange': 'NFO'
                }
            })
        
        return OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=spot_price,
            expiry_date="2025-01-30",
            strikes=strikes_data,
            timestamp=datetime.now()
        )
    
    def test_exact_strike_match_scenarios(self, data_manager):
        """Test ATM calculation when spot exactly matches various strikes"""
        test_cases = [
            (50000.0, [49900, 50000, 50100], 50000.0),
            (49500.0, [49400, 49500, 49600], 49500.0),
            (51200.0, [51100, 51200, 51300], 51200.0),
        ]
        
        for spot_price, strikes, expected_atm in test_cases:
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == expected_atm
                assert result.distance_from_spot == 0.0
                assert result.tie_breaker_used is False
                assert result.spot_price == spot_price
    
    def test_tie_breaker_scenarios(self, data_manager):
        """Test tie-breaker logic with various configurations"""
        strikes = [49900, 50000, 50100, 50200]
        spot_price = 50050.0  # Exactly between 50000 and 50100
        
        tie_breaker_tests = [
            ('lower', 50000.0),
            ('higher', 50100.0),
            ('nearest', 50000.0),  # Should pick first when equal distance
        ]
        
        for tie_breaker, expected_atm in tie_breaker_tests:
            data_manager.config['atm_tie_breaker'] = tie_breaker
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == expected_atm
                assert result.distance_from_spot == 50.0
                assert result.tie_breaker_used is True
    
    def test_asymmetric_strike_spacing(self, data_manager):
        """Test ATM calculation with irregular strike spacing"""
        # Irregular spacing: 100, 50, 200, 100
        strikes = [49800, 49900, 49950, 50150, 50250]
        
        test_cases = [
            (49875.0, 49900.0),  # Closer to 49900 than 49950
            (49925.0, 49950.0),  # Closer to 49950 than 49900
            (50050.0, 49950.0),  # Closer to 49950 than 50150
        ]
        
        for spot_price, expected_atm in test_cases:
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == expected_atm
    
    def test_wide_strike_spacing(self, data_manager):
        """Test ATM calculation with wide strike spacing"""
        # Wide spacing: 500 points apart
        strikes = [49000, 49500, 50000, 50500, 51000]
        
        test_cases = [
            (49750.0, 50000.0),  # Closer to 50000
            (49250.0, 49500.0),  # Closer to 49500
            (50750.0, 51000.0),  # Closer to 51000
        ]
        
        for spot_price, expected_atm in test_cases:
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == expected_atm
    
    def test_extreme_spot_prices(self, data_manager):
        """Test ATM calculation with extreme spot prices"""
        strikes = [49000, 49500, 50000, 50500, 51000]
        
        # Test very low spot price
        options_chain = self.create_options_chain(strikes, 48000.0)
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=48000.0)
            
            assert result is not None
            assert result.atm_strike == 49000.0  # Closest available
            assert result.distance_from_spot == 1000.0
        
        # Test very high spot price
        options_chain = self.create_options_chain(strikes, 52000.0)
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=52000.0)
            
            assert result is not None
            assert result.atm_strike == 51000.0  # Closest available
            assert result.distance_from_spot == 1000.0
    
    def test_single_strike_edge_case(self, data_manager):
        """Test ATM calculation with only one strike available"""
        strikes = [50000]
        spot_prices = [49500, 50000, 50500]
        
        for spot_price in spot_prices:
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == 50000.0
                assert result.tie_breaker_used is False
                assert result.distance_from_spot == abs(spot_price - 50000.0)
    
    def test_two_strikes_edge_case(self, data_manager):
        """Test ATM calculation with only two strikes available"""
        strikes = [49500, 50500]
        
        test_cases = [
            (49000.0, 49500.0),  # Closer to lower
            (50000.0, 49500.0),  # Exactly between - should use tie-breaker (lower)
            (51000.0, 50500.0),  # Closer to higher
        ]
        
        for spot_price, expected_atm in test_cases:
            options_chain = self.create_options_chain(strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None
                assert result.atm_strike == expected_atm
    
    def test_max_distance_validation(self, data_manager):
        """Test max distance validation with various thresholds"""
        strikes = [45000, 55000]  # Very wide apart
        spot_price = 50000.0
        
        # Test with default 5% max distance (2500 points)
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            # Should still return result but distance exceeds threshold
            assert result is not None
            assert result.atm_strike == 45000.0  # Closer strike
            assert result.distance_from_spot == 5000.0  # Exceeds 2500 threshold
        
        # Test with tighter max distance
        data_manager.config['max_strike_distance'] = 0.02  # 2%
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            # Should still return result but log warning
            assert result is not None
            assert result.distance_from_spot > spot_price * 0.02
    
    def test_floating_point_precision(self, data_manager):
        """Test ATM calculation with floating point precision issues"""
        # Use strikes that might cause floating point precision issues
        strikes = [49999.95, 50000.05, 50000.15]
        spot_price = 50000.0
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            assert result is not None
            # Should pick the closest strike despite floating point precision
            assert result.atm_strike == 50000.05
            assert abs(result.distance_from_spot - 0.05) < 1e-10
    
    def test_large_number_of_strikes(self, data_manager):
        """Test ATM calculation with many strikes"""
        # Create 100 strikes from 45000 to 55000
        strikes = [45000 + i * 100 for i in range(101)]
        spot_price = 50000.0
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            assert result is not None
            assert result.atm_strike == 50000.0
            assert result.distance_from_spot == 0.0
            assert len(result.available_strikes) == 101
    
    def test_unsorted_strikes(self, data_manager):
        """Test ATM calculation with unsorted strike list"""
        # Provide strikes in random order
        strikes = [50200, 49800, 50000, 49900, 50100]
        spot_price = 50050.0
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            assert result is not None
            # Should handle unsorted strikes correctly
            assert result.atm_strike == 50000.0  # Lower tie-breaker
            assert result.tie_breaker_used is True
    
    def test_duplicate_strikes(self, data_manager):
        """Test ATM calculation with duplicate strikes"""
        # Include duplicate strikes
        strikes = [49900, 50000, 50000, 50100, 50100]
        spot_price = 50000.0
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            assert result is not None
            assert result.atm_strike == 50000.0
            assert result.distance_from_spot == 0.0
    
    def test_invalid_tie_breaker_fallback(self, data_manager):
        """Test fallback behavior with invalid tie-breaker configuration"""
        strikes = [49900, 50000, 50100]
        spot_price = 50050.0
        
        # Set invalid tie-breaker
        data_manager.config['atm_tie_breaker'] = 'invalid_method'
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            
            assert result is not None
            # Should fallback to 'lower' method
            assert result.atm_strike == 50000.0
            assert result.tie_breaker_used is True
    
    def test_performance_with_large_dataset(self, data_manager):
        """Test performance with large number of strikes"""
        import time
        
        # Create 1000 strikes
        strikes = [40000 + i * 10 for i in range(1001)]
        spot_price = 50000.0
        
        options_chain = self.create_options_chain(strikes, spot_price)
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=options_chain):
            
            start_time = time.time()
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
            end_time = time.time()
            
            # Should complete within 2 seconds (requirement)
            assert (end_time - start_time) < 2.0
            assert result is not None
            assert result.atm_strike == 50000.0
    
    def test_market_condition_variations(self, data_manager):
        """Test ATM calculation under different market conditions"""
        base_strikes = [49000, 49500, 50000, 50500, 51000]
        
        # Test different market scenarios
        market_scenarios = [
            # (spot_price, expected_atm, scenario_name)
            (49750.0, 50000.0, "normal_market"),
            (48500.0, 49000.0, "gap_down"),
            (51500.0, 51000.0, "gap_up"),
            (49999.9, 50000.0, "near_strike"),
            (50000.1, 50000.0, "just_above_strike"),
        ]
        
        for spot_price, expected_atm, scenario in market_scenarios:
            options_chain = self.create_options_chain(base_strikes, spot_price)
            
            with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                             return_value=options_chain):
                
                result = data_manager.get_atm_strike("BANKNIFTY", spot_price=spot_price)
                
                assert result is not None, f"Failed for scenario: {scenario}"
                assert result.atm_strike == expected_atm, f"Wrong ATM for scenario: {scenario}"
                assert result.spot_price == spot_price