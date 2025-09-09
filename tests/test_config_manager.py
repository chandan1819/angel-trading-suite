"""
Unit tests for ConfigManager class.

Tests configuration loading, validation, environment variable substitution,
and error handling scenarios.
"""

import os
import json
import yaml
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from src.config.config_manager import ConfigManager, ConfigurationError
from src.models.config_models import TradingConfig, TradingMode, LogLevel


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_creates_config_directory(self):
        """Test that ConfigManager creates config directory if it doesn't exist."""
        new_dir = Path(self.temp_dir) / "new_config"
        config_manager = ConfigManager(str(new_dir))
        assert new_dir.exists()
    
    def test_load_default_config_when_file_not_found(self):
        """Test loading default configuration when file doesn't exist."""
        config = self.config_manager.load_config("nonexistent.yaml")
        
        assert isinstance(config, TradingConfig)
        assert config.mode == TradingMode.PAPER
        assert config.validate()
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration file."""
        config_data = {
            'mode': 'paper',  # Use paper mode to avoid credential validation
            'underlying_symbol': 'BANKNIFTY',
            'risk': {
                'profit_target': 3000.0,
                'stop_loss': 1500.0
            }
        }
        
        config_file = Path(self.temp_dir) / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config = self.config_manager.load_config("test_config.yaml")
        
        assert config.mode == TradingMode.PAPER
        assert config.underlying_symbol == 'BANKNIFTY'
        assert config.risk.profit_target == 3000.0
        assert config.risk.stop_loss == 1500.0
    
    def test_load_json_config(self):
        """Test loading JSON configuration file."""
        config_data = {
            'mode': 'paper',
            'underlying_symbol': 'BANKNIFTY',
            'logging': {
                'level': 'DEBUG',
                'enable_console': False
            }
        }
        
        config_file = Path(self.temp_dir) / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = self.config_manager.load_config("test_config.json")
        
        assert config.mode == TradingMode.PAPER
        assert config.logging.level == LogLevel.DEBUG
        assert config.logging.enable_console == False
    
    def test_environment_variable_substitution(self):
        """Test environment variable substitution in configuration."""
        config_data = {
            'api': {
                'credentials': {
                    'api_key': '${TEST_API_KEY}',
                    'client_code': '${TEST_CLIENT_CODE:default_client}',
                    'pin': '${NONEXISTENT_VAR:default_pin}'
                }
            }
        }
        
        config_file = Path(self.temp_dir) / "test_env.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with patch.dict(os.environ, {
            'TEST_API_KEY': 'test_key_123',
            'TEST_CLIENT_CODE': 'test_client_456'
        }):
            config = self.config_manager.load_config("test_env.yaml")
        
        assert config.api.credentials.api_key == 'test_key_123'
        assert config.api.credentials.client_code == 'test_client_456'
        assert config.api.credentials.pin == 'default_pin'
    
    def test_save_yaml_config(self):
        """Test saving configuration to YAML file."""
        config = TradingConfig()
        config.mode = TradingMode.PAPER  # Use paper mode to avoid credential validation
        config.risk.profit_target = 2500.0
        
        self.config_manager.save_config(config, "saved_config.yaml")
        
        config_file = Path(self.temp_dir) / "saved_config.yaml"
        assert config_file.exists()
        
        # Load and verify
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data['mode'] == 'paper'
        assert saved_data['risk']['profit_target'] == 2500.0
    
    def test_save_json_config(self):
        """Test saving configuration to JSON file."""
        config = TradingConfig()
        config.mode = TradingMode.PAPER
        config.logging.level = LogLevel.WARNING
        
        self.config_manager.save_config(config, "saved_config.json")
        
        config_file = Path(self.temp_dir) / "saved_config.json"
        assert config_file.exists()
        
        # Load and verify
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['mode'] == 'paper'
        assert saved_data['logging']['level'] == 'WARNING'
    
    def test_sanitize_credentials_on_save(self):
        """Test that credentials are sanitized when saving configuration."""
        config = TradingConfig()
        config.api.credentials.api_key = "secret_key_123"
        config.api.credentials.client_code = "secret_client_456"
        
        self.config_manager.save_config(config, "sanitized_config.yaml")
        
        config_file = Path(self.temp_dir) / "sanitized_config.yaml"
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        # Credentials should be replaced with environment variable references
        creds = saved_data['api']['credentials']
        assert creds['api_key'] == "${ANGEL_API_KEY}"
        assert creds['client_code'] == "${ANGEL_CLIENT_CODE}"
    
    def test_create_default_config(self):
        """Test creating default configuration file."""
        config = self.config_manager.create_default_config("default.yaml")
        
        assert isinstance(config, TradingConfig)
        assert config.validate()
        
        config_file = Path(self.temp_dir) / "default.yaml"
        assert config_file.exists()
    
    def test_validate_credentials(self):
        """Test credential validation."""
        config = TradingConfig()
        
        # Invalid credentials (empty)
        assert not self.config_manager.validate_credentials(config)
        
        # Valid credentials
        config.api.credentials.api_key = "test_key"
        config.api.credentials.client_code = "test_client"
        config.api.credentials.pin = "1234"
        config.api.credentials.totp_secret = "secret"
        
        assert self.config_manager.validate_credentials(config)
    
    def test_config_caching(self):
        """Test configuration caching functionality."""
        config_data = {'mode': 'paper'}
        config_file = Path(self.temp_dir) / "cached_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Load config (should be cached)
        config1 = self.config_manager.load_config("cached_config.yaml")
        
        # Get cached config
        cached_config = self.config_manager.get_cached_config("cached_config.yaml")
        assert cached_config is config1
        
        # Clear cache
        self.config_manager.clear_cache()
        cached_config = self.config_manager.get_cached_config("cached_config.yaml")
        assert cached_config is None
    
    def test_invalid_yaml_format(self):
        """Test handling of invalid YAML format."""
        config_file = Path(self.temp_dir) / "invalid.yaml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with pytest.raises(ConfigurationError, match="Invalid YAML format"):
            self.config_manager.load_config("invalid.yaml")
    
    def test_invalid_json_format(self):
        """Test handling of invalid JSON format."""
        config_file = Path(self.temp_dir) / "invalid.json"
        with open(config_file, 'w') as f:
            f.write('{"invalid": json content}')
        
        with pytest.raises(ConfigurationError, match="Invalid JSON format"):
            self.config_manager.load_config("invalid.json")
    
    def test_unsupported_file_format(self):
        """Test handling of unsupported file formats."""
        with pytest.raises(ConfigurationError, match="Unsupported config file format"):
            self.config_manager.load_config("config.txt")
    
    def test_save_invalid_config(self):
        """Test that saving invalid configuration raises error."""
        config = TradingConfig()
        config.risk.profit_target = -1000.0  # Invalid negative target
        
        with pytest.raises(ConfigurationError, match="Cannot save invalid configuration"):
            self.config_manager.save_config(config, "invalid_config.yaml")
    
    def test_environment_variable_substitution_edge_cases(self):
        """Test edge cases in environment variable substitution."""
        test_cases = [
            ("${VAR}", ""),  # Non-existent variable, no default
            ("${VAR:}", ""),  # Empty default
            ("${VAR:default}", "default"),  # Default value
            ("prefix_${VAR:test}_suffix", "prefix_test_suffix"),  # Embedded
            ("no_vars_here", "no_vars_here"),  # No variables
            ("${VAR1:${VAR2:nested}}", "${VAR2:nested}"),  # Nested (not supported)
        ]
        
        for input_str, expected in test_cases:
            result = self.config_manager._substitute_string_env_vars(input_str)
            assert result == expected, f"Failed for input: {input_str}"
    
    def test_complex_nested_config_conversion(self):
        """Test conversion of complex nested configuration."""
        config_data = {
            'mode': 'paper',
            'strategy': {
                'enabled_strategies': ['straddle', 'directional'],
                'straddle': {
                    'enabled': True,
                    'min_iv_rank': 0.7,
                    'max_dte': 5
                },
                'directional': {
                    'enabled': False,
                    'ema_period': 15
                }
            },
            'notification': {
                'enabled': False,  # Disable notifications to avoid validation issues
                'types': []
            }
        }
        
        config_file = Path(self.temp_dir) / "complex_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config = self.config_manager.load_config("complex_config.yaml")
        
        assert config.mode == TradingMode.PAPER
        assert 'straddle' in config.strategy.enabled_strategies
        assert 'directional' in config.strategy.enabled_strategies
        assert config.strategy.straddle.min_iv_rank == 0.7
        assert config.strategy.straddle.max_dte == 5
        assert config.strategy.directional.enabled == False
        assert config.strategy.directional.ema_period == 15
        assert config.notification.enabled == False


if __name__ == "__main__":
    pytest.main([__file__])