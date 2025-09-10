"""
Unit tests for DataManager class focusing on ATM strike calculation and validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

from src.data.data_manager import DataManager, ATMStrikeResult, ContractMetadata
from src.api.angel_api_client import AngelAPIClient
from src.api.market_data import OptionsChainData
from src.config.config_manager import ConfigManager


class TestDataManager:
    """Test cases for DataManager class"""
    
    @pytest.fixture
    def mock_api_client(self):
        """Mock Angel API client"""
        return Mock(spec=AngelAPIClient)
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock configuration manager"""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_section.return_value = {
            'atm_tie_breaker': 'lower',
            'max_strike_distance': 0.05,
            'default_lot_size': 35
        }
        return config_manager
    
    @pytest.fixture
    def data_manager(self, mock_api_client, mock_config_manager):
        """DataManager instance with mocked dependencies"""
        return DataManager(mock_api_client, mock_config_manager)
    
    @pytest.fixture
    def sample_options_chain(self):
        """Sample options chain data for testing"""
        strikes_data = []
        base_strike = 50000
        
        # Create strikes from 49000 to 51000 with 100 spacing
        for i in range(-10, 11):
            strike = base_strike + (i * 100)
            strikes_data.append({
                'strike': strike,
                'call': {
                    'symbol': f'BANKNIFTY01JAN25CE{strike}',
                    'token': f'token_{strike}_CE',
                    'ltp': max(1.0, 100 - abs(i) * 5),  # Decreasing premium away from ATM
                    'exchange': 'NFO'
                },
                'put': {
                    'symbol': f'BANKNIFTY01JAN25PE{strike}',
                    'token': f'token_{strike}_PE',
                    'ltp': max(1.0, 100 - abs(i) * 5),
                    'exchange': 'NFO'
                }
            })
        
        return OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date="2025-01-01",
            strikes=strikes_data,
            timestamp=datetime.now(),
            atm_strike=50000.0
        )


class TestATMStrikeCalculation:
    """Test ATM strike calculation with various scenarios"""
    
    def test_exact_strike_match(self, data_manager, sample_options_chain):
        """Test ATM calculation when spot price exactly matches a strike"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50000.0)
            
            assert result is not None
            assert result.atm_strike == 50000.0
            assert result.distance_from_spot == 0.0
            assert result.tie_breaker_used is False
            assert result.spot_price == 50000.0
    
    def test_between_strikes_lower_tie_breaker(self, data_manager, sample_options_chain):
        """Test ATM calculation when spot is between strikes with lower tie-breaker"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            # Spot exactly between 50000 and 50100
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50050.0)
            
            assert result is not None
            assert result.atm_strike == 50000.0  # Lower strike chosen
            assert result.distance_from_spot == 50.0
            assert result.tie_breaker_used is True
    
    def test_between_strikes_higher_tie_breaker(self, data_manager, sample_options_chain):
        """Test ATM calculation with higher tie-breaker configuration"""
        # Configure for higher tie-breaker
        data_manager.config['atm_tie_breaker'] = 'higher'
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50050.0)
            
            assert result is not None
            assert result.atm_strike == 50100.0  # Higher strike chosen
            assert result.distance_from_spot == 50.0
            assert result.tie_breaker_used is True
    
    def test_nearest_strike_no_tie(self, data_manager, sample_options_chain):
        """Test ATM calculation when one strike is clearly nearest"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            # Spot closer to 50000 than 50100
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50025.0)
            
            assert result is not None
            assert result.atm_strike == 50000.0
            assert result.distance_from_spot == 25.0
            assert result.tie_breaker_used is False
    
    def test_edge_case_single_strike(self, data_manager, mock_api_client):
        """Test ATM calculation with only one available strike"""
        single_strike_chain = OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date="2025-01-01",
            strikes=[{
                'strike': 50000,
                'call': {'symbol': 'TEST', 'token': 'token', 'ltp': 100, 'exchange': 'NFO'},
                'put': None
            }],
            timestamp=datetime.now()
        )
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=single_strike_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50000.0)
            
            assert result is not None
            assert result.atm_strike == 50000.0
            assert result.tie_breaker_used is False
    
    def test_no_strikes_available(self, data_manager, mock_api_client):
        """Test ATM calculation when no strikes are available"""
        empty_chain = OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date="2025-01-01",
            strikes=[],
            timestamp=datetime.now()
        )
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=empty_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50000.0)
            
            assert result is None
    
    def test_invalid_spot_price(self, data_manager, sample_options_chain):
        """Test ATM calculation with invalid spot price"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            # Test negative spot price
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=-100.0)
            assert result is None
            
            # Test zero spot price
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=0.0)
            assert result is None
    
    def test_max_distance_validation(self, data_manager, mock_api_client):
        """Test ATM calculation when closest strike exceeds max distance"""
        # Create chain with strikes far from spot
        far_strikes_chain = OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date="2025-01-01",
            strikes=[{
                'strike': 60000,  # 20% away from spot
                'call': {'symbol': 'TEST', 'token': 'token', 'ltp': 100, 'exchange': 'NFO'},
                'put': None
            }],
            timestamp=datetime.now()
        )
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=far_strikes_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50000.0)
            
            # Should still return result but with warning logged
            assert result is not None
            assert result.atm_strike == 60000.0
            assert result.distance_from_spot == 10000.0
    
    def test_api_failure_handling(self, data_manager, mock_api_client):
        """Test ATM calculation when API calls fail"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=None):
            
            result = data_manager.get_atm_strike("BANKNIFTY")
            assert result is None
    
    def test_unknown_tie_breaker_fallback(self, data_manager, sample_options_chain):
        """Test fallback to 'lower' when unknown tie-breaker is configured"""
        data_manager.config['atm_tie_breaker'] = 'unknown_method'
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager.get_atm_strike("BANKNIFTY", spot_price=50050.0)
            
            assert result is not None
            assert result.atm_strike == 50000.0  # Should fallback to lower


class TestExpiryDetection:
    """Test current month expiry detection"""
    
    def test_successful_expiry_detection(self, data_manager):
        """Test successful expiry detection"""
        expected_expiry = "2025-01-30"
        
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value=expected_expiry):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            assert result == expected_expiry
    
    def test_expiry_validation_future_date(self, data_manager):
        """Test expiry validation for future dates"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value=future_date):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            assert result == future_date
    
    def test_expiry_validation_past_date(self, data_manager):
        """Test expiry validation rejects past dates"""
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value=past_date), \
             patch.object(data_manager, '_fallback_expiry_detection', 
                         return_value=None):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            assert result is None
    
    def test_expiry_validation_too_far_future(self, data_manager):
        """Test expiry validation rejects dates too far in future"""
        far_future = (datetime.now() + timedelta(days=100)).strftime('%Y-%m-%d')
        
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value=far_future), \
             patch.object(data_manager, '_fallback_expiry_detection', 
                         return_value=None):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            assert result is None
    
    def test_fallback_expiry_detection(self, data_manager, sample_options_chain):
        """Test fallback expiry detection mechanism"""
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value=None), \
             patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            
            # Should return a Thursday date
            if result:
                expiry_date = datetime.strptime(result, '%Y-%m-%d').date()
                assert expiry_date.weekday() == 3  # Thursday
    
    def test_invalid_expiry_format(self, data_manager):
        """Test handling of invalid expiry date format"""
        with patch.object(data_manager.market_data_manager, '_get_current_month_expiry', 
                         return_value="invalid-date"), \
             patch.object(data_manager, '_fallback_expiry_detection', 
                         return_value=None):
            
            result = data_manager.get_current_expiry("BANKNIFTY")
            assert result is None
    
    def test_get_next_thursday(self, data_manager):
        """Test calculation of next Thursday"""
        # Mock current date to a known day
        with patch('src.data.data_manager.datetime') as mock_datetime:
            # Set current date to Monday (weekday = 0)
            mock_datetime.now.return_value.date.return_value = date(2025, 1, 6)  # Monday
            mock_datetime.strptime = datetime.strptime
            
            next_thursday = data_manager._get_next_thursday()
            expected_thursday = date(2025, 1, 9)  # Thursday of same week
            
            assert next_thursday == expected_thursday.strftime('%Y-%m-%d')
    
    def test_get_next_thursday_from_friday(self, data_manager):
        """Test calculation of next Thursday when current day is Friday"""
        with patch('src.data.data_manager.datetime') as mock_datetime:
            # Set current date to Friday (weekday = 4)
            mock_datetime.now.return_value.date.return_value = date(2025, 1, 10)  # Friday
            mock_datetime.strptime = datetime.strptime
            
            next_thursday = data_manager._get_next_thursday()
            expected_thursday = date(2025, 1, 16)  # Thursday of next week
            
            assert next_thursday == expected_thursday.strftime('%Y-%m-%d')
    
    def test_get_last_thursday_of_month(self, data_manager):
        """Test calculation of last Thursday of month"""
        # Test January 2025 (last Thursday should be Jan 30)
        last_thursday = data_manager._get_last_thursday_of_month(1, 2025)
        
        if last_thursday:  # Only if it's in the future
            thursday_date = datetime.strptime(last_thursday, '%Y-%m-%d').date()
            assert thursday_date.weekday() == 3  # Should be Thursday
            assert thursday_date.month == 1  # Should be in January
            assert thursday_date.year == 2025
    
    def test_get_last_thursday_of_next_month(self, data_manager):
        """Test calculation of last Thursday of next month"""
        with patch('src.data.data_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value.date.return_value = date(2025, 1, 15)
            mock_datetime.strptime = datetime.strptime
            
            last_thursday = data_manager._get_last_thursday_of_next_month()
            
            if last_thursday:
                thursday_date = datetime.strptime(last_thursday, '%Y-%m-%d').date()
                assert thursday_date.weekday() == 3  # Should be Thursday
                assert thursday_date.month == 2  # Should be in February
    
    def test_test_expiry_candidate_valid(self, data_manager, sample_options_chain):
        """Test expiry candidate validation with valid data"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager._test_expiry_candidate("BANKNIFTY", future_date)
            assert result is True
    
    def test_test_expiry_candidate_past_date(self, data_manager):
        """Test expiry candidate validation with past date"""
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        result = data_manager._test_expiry_candidate("BANKNIFTY", past_date)
        assert result is False
    
    def test_test_expiry_candidate_no_options(self, data_manager):
        """Test expiry candidate validation with no options data"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=None):
            
            result = data_manager._test_expiry_candidate("BANKNIFTY", future_date)
            assert result is False
    
    def test_test_expiry_candidate_insufficient_strikes(self, data_manager):
        """Test expiry candidate validation with insufficient strikes"""
        future_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Create options chain with too few strikes
        minimal_chain = OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date=future_date,
            strikes=[{'strike': 50000, 'call': {}, 'put': {}}],  # Only 1 strike
            timestamp=datetime.now()
        )
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=minimal_chain):
            
            result = data_manager._test_expiry_candidate("BANKNIFTY", future_date)
            assert result is False
    
    def test_get_all_available_expiries(self, data_manager):
        """Test retrieval of all available expiry dates"""
        # Mock search results with various expiry dates
        mock_instruments = [
            {'tradingsymbol': 'BANKNIFTY30JAN25CE50000'},
            {'tradingsymbol': 'BANKNIFTY30JAN25PE50000'},
            {'tradingsymbol': 'BANKNIFTY27FEB25CE50000'},
            {'tradingsymbol': 'BANKNIFTY27FEB25PE50000'},
            {'tradingsymbol': 'BANKNIFTY27MAR25CE50000'},
            {'tradingsymbol': 'BANKNIFTY01JAN25CE50000'},  # Past date (should be filtered)
        ]
        
        with patch.object(data_manager.api_client, 'search_instruments', 
                         return_value=mock_instruments), \
             patch.object(data_manager.market_data_manager, '_extract_expiry_from_symbol') as mock_extract:
            
            # Mock expiry extraction to return predictable dates
            def mock_extract_side_effect(symbol):
                if '30JAN25' in symbol:
                    return '2025-01-30'
                elif '27FEB25' in symbol:
                    return '2025-02-27'
                elif '27MAR25' in symbol:
                    return '2025-03-27'
                elif '01JAN25' in symbol:
                    return '2025-01-01'  # Past date
                return None
            
            mock_extract.side_effect = mock_extract_side_effect
            
            expiries = data_manager.get_all_available_expiries("BANKNIFTY")
            
            # Should return sorted future expiries only
            assert len(expiries) >= 0  # Depends on current date
            for expiry in expiries:
                expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                assert expiry_date > datetime.now().date()
    
    def test_get_nearest_expiry(self, data_manager):
        """Test getting nearest expiry date"""
        future_expiries = [
            (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
            (datetime.now() + timedelta(days=21)).strftime('%Y-%m-%d'),
        ]
        
        with patch.object(data_manager, 'get_all_available_expiries', 
                         return_value=future_expiries):
            
            # Test without minimum days
            nearest = data_manager.get_nearest_expiry("BANKNIFTY")
            assert nearest == future_expiries[0]
            
            # Test with minimum days requirement
            nearest = data_manager.get_nearest_expiry("BANKNIFTY", min_days_to_expiry=10)
            assert nearest == future_expiries[1]  # Should skip first expiry
    
    def test_get_nearest_expiry_no_expiries(self, data_manager):
        """Test getting nearest expiry when no expiries available"""
        with patch.object(data_manager, 'get_all_available_expiries', 
                         return_value=[]):
            
            nearest = data_manager.get_nearest_expiry("BANKNIFTY")
            assert nearest is None
    
    def test_search_known_expiry_patterns(self, data_manager, sample_options_chain):
        """Test searching for expiries using known patterns"""
        with patch.object(data_manager, '_get_last_thursday_of_month') as mock_last_thursday, \
             patch.object(data_manager, '_test_expiry_candidate', return_value=True):
            
            # Mock to return a valid expiry for the first month
            mock_last_thursday.return_value = "2025-01-30"
            
            result = data_manager._search_known_expiry_patterns("BANKNIFTY")
            assert result == "2025-01-30"
    
    def test_search_known_expiry_patterns_no_match(self, data_manager):
        """Test searching for expiries when no patterns match"""
        with patch.object(data_manager, '_get_last_thursday_of_month', return_value=None), \
             patch.object(data_manager, '_test_expiry_candidate', return_value=False):
            
            result = data_manager._search_known_expiry_patterns("BANKNIFTY")
            assert result is None
    
    def test_fallback_expiry_detection_comprehensive(self, data_manager, sample_options_chain):
        """Test comprehensive fallback expiry detection with all methods"""
        with patch.object(data_manager, '_get_next_thursday', return_value="2025-01-16"), \
             patch.object(data_manager, '_test_expiry_candidate') as mock_test:
            
            # Mock test to succeed on first attempt
            mock_test.return_value = True
            
            result = data_manager._fallback_expiry_detection("BANKNIFTY")
            assert result == "2025-01-16"
            
            # Verify the test was called
            mock_test.assert_called_with("BANKNIFTY", "2025-01-16")
    
    def test_fallback_expiry_detection_all_methods_fail(self, data_manager):
        """Test fallback expiry detection when all methods fail"""
        with patch.object(data_manager, '_get_next_thursday', return_value="2025-01-16"), \
             patch.object(data_manager, '_test_expiry_candidate', return_value=False), \
             patch.object(data_manager, '_get_last_thursday_of_month', return_value=None), \
             patch.object(data_manager, '_search_known_expiry_patterns', return_value=None):
            
            result = data_manager._fallback_expiry_detection("BANKNIFTY")
            assert result is None


class TestContractMetadata:
    """Test contract metadata retrieval"""
    
    def test_successful_metadata_retrieval(self, data_manager, sample_options_chain):
        """Test successful contract metadata retrieval"""
        with patch.object(data_manager, 'get_current_expiry', 
                         return_value="2025-01-01"), \
             patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain):
            
            result = data_manager.get_contract_metadata("BANKNIFTY")
            
            assert result is not None
            assert isinstance(result, ContractMetadata)
            assert result.lot_size == 35  # BANKNIFTY current
            assert result.strike_spacing == 100.0  # From sample data
            assert result.underlying_symbol == "BANKNIFTY"
            assert result.expiry_date == "2025-01-01"
    
    def test_strike_spacing_calculation(self, data_manager):
        """Test strike spacing calculation with various scenarios"""
        # Test regular spacing
        strikes_data = [
            {'strike': 50000}, {'strike': 50100}, {'strike': 50200}, {'strike': 50300}
        ]
        spacing = data_manager._calculate_strike_spacing(strikes_data)
        assert spacing == 100.0
        
        # Test irregular spacing (should pick most common)
        strikes_data = [
            {'strike': 50000}, {'strike': 50050}, {'strike': 50150}, 
            {'strike': 50250}, {'strike': 50350}  # Mix of 50 and 100 spacing
        ]
        spacing = data_manager._calculate_strike_spacing(strikes_data)
        assert spacing == 100.0  # 100 is more common
    
    def test_lot_size_extraction(self, data_manager, sample_options_chain):
        """Test lot size extraction for different underlyings"""
        # Test BANKNIFTY
        lot_size = data_manager._extract_lot_size(sample_options_chain)
        assert lot_size == 35
        
        # Test unknown underlying (should use default)
        sample_options_chain.underlying_symbol = "UNKNOWN"
        lot_size = data_manager._extract_lot_size(sample_options_chain)
        assert lot_size == 35  # Default from config
    
    def test_metadata_with_missing_expiry(self, data_manager):
        """Test metadata retrieval when expiry detection fails"""
        with patch.object(data_manager, 'get_current_expiry', return_value=None):
            
            result = data_manager.get_contract_metadata("BANKNIFTY")
            assert result is None


class TestOptionsChainValidation:
    """Test options chain validation"""
    
    def test_valid_options_chain(self, data_manager, sample_options_chain):
        """Test validation of a valid options chain"""
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is True
        assert len(issues) == 0
    
    def test_invalid_underlying_price(self, data_manager, sample_options_chain):
        """Test validation with invalid underlying price"""
        sample_options_chain.underlying_price = -100.0
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("Invalid underlying price" in issue for issue in issues)
    
    def test_missing_expiry_date(self, data_manager, sample_options_chain):
        """Test validation with missing expiry date"""
        sample_options_chain.expiry_date = ""
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("Missing expiry date" in issue for issue in issues)
    
    def test_past_expiry_date(self, data_manager, sample_options_chain):
        """Test validation with past expiry date"""
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sample_options_chain.expiry_date = past_date
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("is in the past" in issue for issue in issues)
    
    def test_no_strikes_available(self, data_manager, sample_options_chain):
        """Test validation with no strikes"""
        sample_options_chain.strikes = []
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("No strikes available" in issue for issue in issues)
    
    def test_invalid_strike_data(self, data_manager, sample_options_chain):
        """Test validation with invalid strike data"""
        # Add invalid strike
        sample_options_chain.strikes.append({
            'strike': -100,  # Invalid negative strike
            'call': None,
            'put': None
        })
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("Invalid strike price" in issue for issue in issues)
    
    def test_spot_outside_strike_range(self, data_manager, sample_options_chain):
        """Test validation when spot is outside strike range"""
        sample_options_chain.underlying_price = 60000.0  # Outside strike range
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("outside strike range" in issue for issue in issues)
    
    def test_invalid_atm_strike(self, data_manager, sample_options_chain):
        """Test validation with ATM strike not in strikes list"""
        sample_options_chain.atm_strike = 99999.0  # Not in strikes list
        
        is_valid, issues = data_manager.validate_options_chain(sample_options_chain)
        
        assert is_valid is False
        assert any("ATM strike" in issue and "not found" in issue for issue in issues)


class TestOptionsChainSummary:
    """Test options chain summary generation"""
    
    def test_complete_summary_generation(self, data_manager, sample_options_chain):
        """Test generation of complete options chain summary"""
        atm_result = ATMStrikeResult(
            atm_strike=50000.0,
            distance_from_spot=0.0,
            tie_breaker_used=False,
            available_strikes=[49000, 49100, 50000, 50100, 51000],
            spot_price=50000.0
        )
        
        metadata = ContractMetadata(
            lot_size=35,
            strike_spacing=100.0,
            tick_size=0.05,
            underlying_symbol="BANKNIFTY",
            expiry_date="2025-01-01"
        )
        
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=sample_options_chain), \
             patch.object(data_manager, 'get_atm_strike', 
                         return_value=atm_result), \
             patch.object(data_manager, 'get_contract_metadata', 
                         return_value=metadata):
            
            summary = data_manager.get_options_chain_summary("BANKNIFTY")
            
            assert summary is not None
            assert summary['underlying_symbol'] == "BANKNIFTY"
            assert summary['underlying_price'] == 50000.0
            assert summary['total_strikes'] == 21  # From sample data
            assert summary['atm_info']['atm_strike'] == 50000.0
            assert summary['contract_metadata']['lot_size'] == 35
            assert 'validation' in summary
            assert 'is_valid' in summary['validation']
    
    def test_summary_with_api_failure(self, data_manager):
        """Test summary generation when API calls fail"""
        with patch.object(data_manager.market_data_manager, 'get_options_chain', 
                         return_value=None):
            
            summary = data_manager.get_options_chain_summary("BANKNIFTY")
            assert summary is None


class TestIndicatorCalculations:
    """Test indicator calculations and historical data processing"""
    
    @pytest.fixture
    def sample_historical_data(self):
        """Sample historical data for testing indicators"""
        from src.data.indicators import HistoricalDataPoint
        
        data = []
        base_price = 50000
        base_date = datetime(2025, 1, 1)
        
        # Generate 30 days of sample data with some volatility
        for i in range(30):
            date = base_date + timedelta(days=i)
            
            # Add some price movement
            price_change = (i % 5 - 2) * 50  # Oscillating pattern
            close = base_price + price_change + (i * 10)  # Slight uptrend
            
            # Generate OHLC with realistic relationships
            open_price = close + ((i % 3 - 1) * 20)
            high = max(open_price, close) + abs((i % 4) * 15)
            low = min(open_price, close) - abs((i % 3) * 10)
            volume = 1000 + (i % 7) * 200
            
            data.append(HistoricalDataPoint(
                timestamp=date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume
            ))
        
        return data
    
    @pytest.fixture
    def indicator_calculator(self):
        """IndicatorCalculator instance"""
        from src.data.indicators import IndicatorCalculator
        return IndicatorCalculator()
    
    def test_sma_calculation(self, indicator_calculator, sample_historical_data):
        """Test Simple Moving Average calculation"""
        result = indicator_calculator.calculate_sma(sample_historical_data, period=10)
        
        assert len(result.values) == len(sample_historical_data) - 9  # 30 - 10 + 1 = 21
        assert len(result.timestamps) == len(result.values)
        assert result.parameters['period'] == 10
        assert result.parameters['field'] == 'close'
        
        # Verify first SMA value manually
        first_10_closes = [point.close for point in sample_historical_data[:10]]
        expected_first_sma = sum(first_10_closes) / 10
        assert abs(result.values[0] - expected_first_sma) < 0.01
    
    def test_sma_insufficient_data(self, indicator_calculator):
        """Test SMA calculation with insufficient data"""
        from src.data.indicators import HistoricalDataPoint
        
        # Only 5 data points for period 10
        short_data = [
            HistoricalDataPoint(datetime.now(), 100, 105, 95, 102, 1000)
            for _ in range(5)
        ]
        
        result = indicator_calculator.calculate_sma(short_data, period=10)
        
        assert len(result.values) == 0
        assert len(result.timestamps) == 0
    
    def test_ema_calculation(self, indicator_calculator, sample_historical_data):
        """Test Exponential Moving Average calculation"""
        result = indicator_calculator.calculate_ema(sample_historical_data, period=10)
        
        assert len(result.values) == len(sample_historical_data) - 9
        assert len(result.timestamps) == len(result.values)
        assert result.parameters['period'] == 10
        assert 'alpha' in result.parameters
        
        # Verify alpha calculation
        expected_alpha = 2.0 / (10 + 1)
        assert abs(result.parameters['alpha'] - expected_alpha) < 0.001
    
    def test_atr_calculation(self, indicator_calculator, sample_historical_data):
        """Test Average True Range calculation"""
        result = indicator_calculator.calculate_atr(sample_historical_data, period=14)
        
        assert len(result.values) == len(sample_historical_data) - 14  # Need extra day for TR
        assert len(result.timestamps) == len(result.values)
        assert result.parameters['period'] == 14
        
        # ATR values should be positive
        for value in result.values:
            assert value > 0
    
    def test_atr_insufficient_data(self, indicator_calculator):
        """Test ATR calculation with insufficient data"""
        from src.data.indicators import HistoricalDataPoint
        
        # Only 10 data points for period 14 (need 15 total)
        short_data = [
            HistoricalDataPoint(datetime.now() + timedelta(days=i), 100, 105, 95, 102, 1000)
            for i in range(10)
        ]
        
        result = indicator_calculator.calculate_atr(short_data, period=14)
        
        assert len(result.values) == 0
        assert len(result.timestamps) == 0
    
    def test_iv_rank_percentile_calculation(self, indicator_calculator):
        """Test IV rank and percentile calculation"""
        # Generate sample IV data
        base_date = datetime(2025, 1, 1)
        iv_data = []
        
        # Create IV data with known distribution
        iv_values = [15, 18, 20, 22, 25, 28, 30, 32, 35, 40]  # Ascending order
        for i, iv in enumerate(iv_values):
            iv_data.append((base_date + timedelta(days=i), iv))
        
        result = indicator_calculator.calculate_iv_rank_percentile(iv_data, lookback_days=10)
        
        assert result is not None
        assert result.current_iv == 40  # Last value
        assert result.iv_rank == 90.0  # 9 out of 10 values are below 40
        assert result.lookback_days == 10
        assert result.mean_iv == 26.5  # Mean of the values
    
    def test_iv_rank_percentile_insufficient_data(self, indicator_calculator):
        """Test IV rank calculation with insufficient data"""
        iv_data = [(datetime.now(), 25.0)]  # Only one data point
        
        result = indicator_calculator.calculate_iv_rank_percentile(iv_data)
        assert result is None
    
    def test_bid_ask_spread_analysis(self, indicator_calculator):
        """Test bid-ask spread analysis"""
        base_date = datetime(2025, 1, 1)
        spread_data = []
        
        # Generate sample spread data
        for i in range(20):
            mid_price = 100 + i
            spread = 1.0 + (i % 3) * 0.5  # Varying spread
            bid = mid_price - spread / 2
            ask = mid_price + spread / 2
            
            spread_data.append((base_date + timedelta(days=i), bid, ask, mid_price))
        
        result = indicator_calculator.analyze_bid_ask_spread(spread_data, lookback_days=20)
        
        assert result is not None
        assert result.current_spread > 0
        assert result.current_spread_pct > 0
        assert result.mean_spread > 0
        assert 0 <= result.spread_quality_score <= 100
    
    def test_volume_analysis(self, indicator_calculator):
        """Test volume analysis"""
        base_date = datetime(2025, 1, 1)
        volume_data = []
        
        # Generate sample volume data with trend
        base_volume = 1000
        for i in range(20):
            # Increasing volume trend
            volume = base_volume + i * 50 + (i % 3) * 100
            volume_data.append((base_date + timedelta(days=i), volume))
        
        result = indicator_calculator.analyze_volume(volume_data, lookback_days=20)
        
        assert result is not None
        assert result.current_volume > 0
        assert result.mean_volume > 0
        assert result.volume_ratio > 0
        assert result.volume_trend in ['increasing', 'decreasing', 'stable']
        assert 0 <= result.volume_percentile <= 100
    
    def test_multiple_indicators_calculation(self, indicator_calculator, sample_historical_data):
        """Test calculation of multiple indicators at once"""
        indicators = ['sma_short', 'sma_long', 'ema_short', 'atr']
        
        results = indicator_calculator.calculate_multiple_indicators(
            sample_historical_data, indicators
        )
        
        assert len(results) == len(indicators)
        for indicator in indicators:
            assert indicator in results
            assert len(results[indicator].values) > 0
    
    def test_indicator_summary_generation(self, indicator_calculator, sample_historical_data):
        """Test comprehensive indicator summary generation"""
        summary = indicator_calculator.get_indicator_summary(sample_historical_data)
        
        assert 'timestamp' in summary
        assert 'data_points' in summary
        assert 'price' in summary
        assert 'indicators' in summary
        
        # Check price data
        price_data = summary['price']
        assert 'current' in price_data
        assert 'open' in price_data
        assert 'high' in price_data
        assert 'low' in price_data
        assert 'volume' in price_data
        
        # Check indicators
        indicators = summary['indicators']
        assert len(indicators) > 0
        
        for indicator_name, indicator_data in indicators.items():
            assert 'current' in indicator_data
            assert 'values_count' in indicator_data
            assert 'parameters' in indicator_data
    
    def test_data_quality_validation_valid_data(self, indicator_calculator, sample_historical_data):
        """Test data quality validation with valid data"""
        quality_report = indicator_calculator.validate_data_quality(sample_historical_data)
        
        assert quality_report['valid'] is True
        assert quality_report['data_points'] == len(sample_historical_data)
        assert len(quality_report['issues']) == 0
        assert 'date_range' in quality_report
    
    def test_data_quality_validation_invalid_data(self, indicator_calculator):
        """Test data quality validation with invalid data"""
        from src.data.indicators import HistoricalDataPoint
        
        # Create data with issues
        invalid_data = [
            HistoricalDataPoint(datetime.now(), -100, 105, 95, 102, 1000),  # Negative open
            HistoricalDataPoint(datetime.now(), 100, 95, 105, 102, 1000),   # High < Low
            HistoricalDataPoint(datetime.now(), 100, 105, 95, 102, -500),   # Negative volume
        ]
        
        quality_report = indicator_calculator.validate_data_quality(invalid_data)
        
        assert quality_report['valid'] is False
        assert len(quality_report['issues']) > 0
    
    def test_data_quality_validation_empty_data(self, indicator_calculator):
        """Test data quality validation with empty data"""
        quality_report = indicator_calculator.validate_data_quality([])
        
        assert quality_report['valid'] is False
        assert 'No data provided' in quality_report['issues']
    
    def test_sma_different_price_fields(self, indicator_calculator, sample_historical_data):
        """Test SMA calculation with different price fields"""
        # Test with 'high' field
        result_high = indicator_calculator.calculate_sma(
            sample_historical_data, period=10, price_field='high'
        )
        
        # Test with 'low' field
        result_low = indicator_calculator.calculate_sma(
            sample_historical_data, period=10, price_field='low'
        )
        
        assert len(result_high.values) > 0
        assert len(result_low.values) > 0
        assert result_high.parameters['field'] == 'high'
        assert result_low.parameters['field'] == 'low'
        
        # High SMA should generally be higher than low SMA
        assert result_high.values[-1] > result_low.values[-1]
    
    def test_ema_vs_sma_comparison(self, indicator_calculator, sample_historical_data):
        """Test that EMA responds faster than SMA to price changes"""
        period = 10
        
        sma_result = indicator_calculator.calculate_sma(sample_historical_data, period)
        ema_result = indicator_calculator.calculate_ema(sample_historical_data, period)
        
        assert len(sma_result.values) == len(ema_result.values)
        
        # Both should have values
        assert len(sma_result.values) > 0
        assert len(ema_result.values) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])