# Bank Nifty Options Trading System - Test Suite

This directory contains a comprehensive test suite for the Bank Nifty Options Trading System, providing thorough coverage of all critical trading functions, risk management, and system integration.

## 📋 Test Overview

The test suite is designed to achieve **minimum 80% code coverage** for critical trading functions and includes:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test complete workflows and component interactions  
- **Mock Infrastructure**: Realistic API simulation for testing
- **Performance Tests**: Validate system performance requirements
- **Error Recovery Tests**: Test system resilience and error handling

## 🏗️ Test Structure

### Unit Tests

#### `test_atm_strike_comprehensive.py`
Comprehensive tests for ATM strike selection algorithm:
- ✅ Exact strike matches with various spot prices
- ✅ Tie-breaker logic (lower, higher, nearest)
- ✅ Asymmetric and wide strike spacing scenarios
- ✅ Edge cases (single strike, two strikes)
- ✅ Performance testing with large datasets
- ✅ Market condition variations
- ✅ Floating point precision handling

#### `test_position_sizing_pnl.py`
Position sizing and P&L calculation tests:
- ✅ Fixed, percentage, and Kelly criterion position sizing
- ✅ Confidence factor adjustments
- ✅ Risk amount variations and limits
- ✅ Single-leg and multi-leg P&L calculations
- ✅ Straddle, strangle, and iron condor P&L
- ✅ Target and stop-loss detection
- ✅ High precision P&L calculations
- ✅ Performance testing with many positions

#### `test_risk_management_validation.py`
Risk management validation and enforcement:
- ✅ Daily loss limit validation
- ✅ Position limit enforcement
- ✅ Trade count limits
- ✅ Emergency stop mechanisms
- ✅ Signal structure validation
- ✅ Margin requirement validation
- ✅ Risk alert generation and prioritization
- ✅ Multiple violation scenarios

### Integration Tests

#### `test_integration_paper_trading.py`
Complete paper trading workflow testing:
- ✅ End-to-end trading cycle execution
- ✅ Order placement and position management
- ✅ Profit target and stop-loss monitoring
- ✅ Risk management integration
- ✅ Emergency stop handling
- ✅ Session lifecycle management
- ✅ Performance and error recovery

#### `test_integration_strategy_evaluation.py`
Strategy evaluation workflow testing:
- ✅ Individual strategy evaluation (straddle, directional, iron condor, Greeks, volatility)
- ✅ Multiple strategy coordination
- ✅ Market condition adaptability
- ✅ Signal filtering and prioritization
- ✅ Performance requirements validation
- ✅ Error handling during evaluation
- ✅ Concurrent strategy evaluation

#### `test_integration_error_recovery.py`
Error handling and recovery testing:
- ✅ API connection failures and recovery
- ✅ Network timeout handling with backoff
- ✅ Rate limiting and exponential backoff
- ✅ Partial API failure scenarios
- ✅ Malformed response handling
- ✅ System recovery mechanisms
- ✅ Data integrity and reconciliation
- ✅ Performance degradation handling

### Mock Infrastructure

#### `mock_angel_api.py`
Comprehensive mock Angel API implementation:
- ✅ Realistic market data simulation
- ✅ Multiple test scenarios (normal, error, rate-limited, network issues)
- ✅ Order lifecycle simulation
- ✅ Position management simulation
- ✅ Historical data generation
- ✅ Error condition simulation
- ✅ Performance characteristics simulation

#### `conftest.py`
Test configuration and shared fixtures:
- ✅ Common test fixtures and utilities
- ✅ Test data generators
- ✅ Performance timing utilities
- ✅ Custom assertions for trading objects
- ✅ Automatic cleanup mechanisms

## 🚀 Running Tests

### Prerequisites

Install test dependencies:
```bash
python3 run_tests.py --install-deps
```

### Test Execution Options

#### Run All Tests with Coverage
```bash
python3 run_tests.py --all --coverage
```

#### Run Unit Tests Only
```bash
python3 run_tests.py --unit --coverage --verbose
```

#### Run Integration Tests Only
```bash
python3 run_tests.py --integration --verbose
```

#### Run Performance Tests
```bash
python3 run_tests.py --performance
```

#### Run Specific Test Pattern
```bash
python3 run_tests.py --pattern "atm_strike"
python3 run_tests.py --pattern "risk_management"
python3 run_tests.py --pattern "paper_trading"
```

#### Run Tests in Parallel
```bash
python3 run_tests.py --all --parallel --coverage
```

### Using pytest directly

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_atm_strike_comprehensive.py -v

# Run specific test method
pytest tests/test_position_sizing_pnl.py::TestPositionSizing::test_fixed_position_sizing -v

# Run tests by marker
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v
pytest tests/ -m "performance" -v
```

## 📊 Test Coverage Requirements

The test suite is designed to meet the following coverage requirements:

### Critical Trading Functions (Minimum 80% Coverage)
- ✅ ATM strike selection algorithms
- ✅ Position sizing calculations  
- ✅ P&L calculations for all strategy types
- ✅ Risk management validation and enforcement
- ✅ Order placement and management
- ✅ Strategy evaluation logic

### Integration Workflows (Comprehensive Coverage)
- ✅ Complete paper trading workflow
- ✅ Strategy evaluation and coordination
- ✅ Error handling and recovery
- ✅ API integration with mocking
- ✅ System resilience testing

### Performance Requirements
- ✅ ATM strike calculation: < 2 seconds
- ✅ Strategy evaluation: < 5 seconds  
- ✅ Order placement: < 3 seconds
- ✅ Position monitoring: < 30 seconds
- ✅ Complete trading cycle: < 10 seconds

## 🎯 Test Categories and Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow running tests (> 5 seconds)
- `@pytest.mark.api` - Tests requiring API mocking
- `@pytest.mark.risk` - Risk management tests
- `@pytest.mark.strategy` - Trading strategy tests
- `@pytest.mark.performance` - Performance tests

## 📈 Coverage Reports

After running tests with coverage, reports are generated:

- **HTML Report**: `htmlcov/index.html` - Interactive coverage report
- **Terminal Report**: Shows coverage summary and missing lines
- **XML Report**: `coverage.xml` - For CI/CD integration

## 🔧 Test Configuration

### pytest.ini
Contains pytest configuration including:
- Test discovery patterns
- Marker definitions
- Coverage settings
- Output formatting

### conftest.py
Provides shared test infrastructure:
- Common fixtures for all tests
- Mock API instances
- Test data generators
- Custom assertions
- Performance timing utilities

## 🧪 Test Data and Scenarios

### Market Data Scenarios
- Normal market conditions
- High volatility periods
- Low volatility periods
- Market gaps and unusual movements
- Options chain variations

### Error Scenarios
- API connection failures
- Network timeouts
- Rate limiting
- Malformed responses
- Partial data availability

### Risk Scenarios
- Daily loss limit breaches
- Position limit violations
- Emergency stop conditions
- Margin insufficiency
- Multiple risk violations

## 📝 Writing New Tests

### Unit Test Template
```python
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """Test new feature functionality"""
    
    @pytest.fixture
    def setup_data(self):
        """Setup test data"""
        return {"test": "data"}
    
    def test_basic_functionality(self, setup_data):
        """Test basic functionality"""
        # Arrange
        # Act  
        # Assert
        pass
    
    def test_error_conditions(self):
        """Test error handling"""
        pass
    
    def test_edge_cases(self):
        """Test edge cases"""
        pass
```

### Integration Test Template
```python
import pytest
from unittest.mock import Mock, patch

class TestNewIntegration:
    """Test new integration workflow"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""
        return Mock()
    
    def test_complete_workflow(self, mock_dependencies):
        """Test complete workflow"""
        pass
    
    def test_error_recovery(self):
        """Test error recovery"""
        pass
```

## 🚨 Troubleshooting Tests

### Common Issues

1. **Import Errors**: Ensure `src/` is in Python path
2. **Mock API Issues**: Check mock_angel_api.py configuration
3. **Timeout Issues**: Increase timeout values for slow systems
4. **Coverage Issues**: Ensure all critical paths are tested

### Debug Mode
```bash
# Run with debug output
pytest tests/ -v -s --tb=long

# Run single test with debugging
pytest tests/test_file.py::test_method -v -s --pdb
```

## 📋 Test Checklist

Before submitting code, ensure:

- [ ] All new code has corresponding unit tests
- [ ] Integration tests cover new workflows
- [ ] Tests pass with minimum 80% coverage
- [ ] Performance requirements are met
- [ ] Error conditions are tested
- [ ] Mock scenarios are realistic
- [ ] Tests are properly categorized with markers
- [ ] Documentation is updated

## 🎉 Test Results

The comprehensive test suite provides:

✅ **High Confidence**: Thorough testing of all critical functions  
✅ **Risk Mitigation**: Extensive risk management validation  
✅ **Performance Assurance**: Performance requirement validation  
✅ **Error Resilience**: Comprehensive error handling testing  
✅ **Integration Validation**: End-to-end workflow testing  
✅ **Maintainability**: Well-structured and documented tests  

This test suite ensures the Bank Nifty Options Trading System is robust, reliable, and ready for production use.