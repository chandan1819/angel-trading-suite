"""
Configuration Manager for the Bank Nifty Options Trading System.

This module provides the ConfigManager class that handles loading, validation,
and management of configuration files in YAML and JSON formats with secure
credential handling from environment variables.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import asdict

try:
    from ..models.config_models import (
        TradingConfig, APIConfig, RiskConfig, StrategyConfig,
        LoggingConfig, NotificationConfig, BacktestConfig,
        TradingMode, LogLevel, NotificationType
    )
except ImportError:
    from models.config_models import (
        TradingConfig, APIConfig, RiskConfig, StrategyConfig,
        LoggingConfig, NotificationConfig, BacktestConfig,
        TradingMode, LogLevel, NotificationType
    )


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors"""
    pass


class ConfigManager:
    """
    Manages configuration loading, validation, and secure credential handling.
    
    Supports both YAML and JSON configuration files with environment variable
    substitution for sensitive credentials.
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize ConfigManager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger(__name__)
        self._config_cache: Dict[str, Any] = {}
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
    
    def load_config(self, config_file: str = "trading_config.yaml") -> TradingConfig:
        """
        Load trading configuration from file.
        
        Args:
            config_file: Configuration file name (supports .yaml, .yml, .json)
            
        Returns:
            TradingConfig: Loaded and validated configuration
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        config_path = self.config_dir / config_file
        
        try:
            # Load configuration data
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                config_data = self._load_yaml(config_path)
            elif config_path.suffix.lower() == '.json':
                config_data = self._load_json(config_path)
            else:
                raise ConfigurationError(f"Unsupported config file format: {config_path.suffix}")
            
            # Substitute environment variables
            config_data = self._substitute_env_vars(config_data)
            
            # Convert to TradingConfig object
            trading_config = self._dict_to_trading_config(config_data)
            
            # Validate configuration
            if not trading_config.validate():
                raise ConfigurationError("Configuration validation failed")
            
            # Cache the configuration
            self._config_cache[config_file] = trading_config
            
            self.logger.info(f"Successfully loaded configuration from {config_path}")
            return trading_config
            
        except FileNotFoundError:
            self.logger.warning(f"Configuration file not found: {config_path}")
            # Return default configuration
            default_config = TradingConfig()
            if not default_config.validate():
                raise ConfigurationError("Default configuration is invalid")
            return default_config
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    
    def save_config(self, config: TradingConfig, config_file: str = "trading_config.yaml") -> None:
        """
        Save trading configuration to file.
        
        Args:
            config: TradingConfig object to save
            config_file: Configuration file name
            
        Raises:
            ConfigurationError: If configuration saving fails
        """
        config_path = self.config_dir / config_file
        
        try:
            # Validate configuration before saving
            if not config.validate():
                raise ConfigurationError("Cannot save invalid configuration")
            
            # Convert to dictionary
            config_dict = asdict(config)
            
            # Remove sensitive data before saving
            config_dict = self._sanitize_config_for_save(config_dict)
            
            # Save based on file extension
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                self._save_yaml(config_dict, config_path)
            elif config_path.suffix.lower() == '.json':
                self._save_json(config_dict, config_path)
            else:
                raise ConfigurationError(f"Unsupported config file format: {config_path.suffix}")
            
            self.logger.info(f"Successfully saved configuration to {config_path}")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {str(e)}")
    
    def create_default_config(self, config_file: str = "trading_config.yaml") -> TradingConfig:
        """
        Create and save a default configuration file.
        
        Args:
            config_file: Configuration file name
            
        Returns:
            TradingConfig: Default configuration
        """
        default_config = TradingConfig()
        
        # Customize some default values
        default_config.mode = TradingMode.PAPER
        default_config.logging.level = LogLevel.INFO
        default_config.logging.enable_console = True
        default_config.logging.enable_file = True
        
        # Save the default configuration
        self.save_config(default_config, config_file)
        
        return default_config
    
    def validate_credentials(self, config: TradingConfig) -> bool:
        """
        Validate API credentials.
        
        Args:
            config: TradingConfig to validate
            
        Returns:
            bool: True if credentials are valid
        """
        return config.api.credentials.validate()
    
    def get_cached_config(self, config_file: str) -> Optional[TradingConfig]:
        """
        Get cached configuration if available.
        
        Args:
            config_file: Configuration file name
            
        Returns:
            Optional[TradingConfig]: Cached configuration or None
        """
        return self._config_cache.get(config_file)
    
    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._config_cache.clear()
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format in {file_path}: {str(e)}")
    
    def _load_json(self, file_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON format in {file_path}: {str(e)}")
    
    def _save_yaml(self, data: Dict[str, Any], file_path: Path) -> None:
        """Save data to YAML file."""
        # Convert enums to their values for serialization
        serializable_data = self._convert_enums_to_values(data)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(serializable_data, f, default_flow_style=False, indent=2, sort_keys=False)
    
    def _save_json(self, data: Dict[str, Any], file_path: Path) -> None:
        """Save data to JSON file."""
        # Convert enums to their values for serialization
        serializable_data = self._convert_enums_to_values(data)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, sort_keys=False)
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """
        Recursively substitute environment variables in configuration data.
        
        Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax.
        """
        if isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_string_env_vars(data)
        else:
            return data
    
    def _substitute_string_env_vars(self, text: str) -> str:
        """Substitute environment variables in a string."""
        import re
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, text)
    
    def _sanitize_config_for_save(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove or mask sensitive data before saving configuration.
        
        Replaces actual credentials with environment variable references.
        """
        # Create a copy to avoid modifying the original
        sanitized = config_dict.copy()
        
        # Replace API credentials with environment variable references
        if 'api' in sanitized and 'credentials' in sanitized['api']:
            creds = sanitized['api']['credentials']
            creds['api_key'] = "${ANGEL_API_KEY}"
            creds['client_code'] = "${ANGEL_CLIENT_CODE}"
            creds['pin'] = "${ANGEL_PIN}"
            creds['totp_secret'] = "${ANGEL_TOTP_SECRET}"
        
        # Replace notification credentials
        if 'notification' in sanitized:
            notif = sanitized['notification']
            if 'email_password' in notif:
                notif['email_password'] = "${EMAIL_PASSWORD}"
            if 'telegram_bot_token' in notif:
                notif['telegram_bot_token'] = "${TELEGRAM_BOT_TOKEN}"
        
        return sanitized
    
    def _dict_to_trading_config(self, data: Dict[str, Any]) -> TradingConfig:
        """
        Convert dictionary to TradingConfig object.
        
        Handles nested configuration objects and enum conversions.
        """
        try:
            # Handle mode conversion
            if 'mode' in data:
                if isinstance(data['mode'], str):
                    data['mode'] = TradingMode(data['mode'].lower())
            
            # Handle logging level conversion
            if 'logging' in data and 'level' in data['logging']:
                if isinstance(data['logging']['level'], str):
                    data['logging']['level'] = LogLevel(data['logging']['level'].upper())
            
            # Handle notification types conversion
            if 'notification' in data and 'types' in data['notification']:
                if isinstance(data['notification']['types'], list):
                    data['notification']['types'] = [
                        NotificationType(t) if isinstance(t, str) else t
                        for t in data['notification']['types']
                    ]
            
            # Create TradingConfig object
            # Note: This is a simplified conversion. In a production system,
            # you might want to use a more sophisticated approach like
            # dacite or cattrs for complex dataclass deserialization
            
            config = TradingConfig()
            
            # Update fields from data
            for key, value in data.items():
                if hasattr(config, key):
                    if key == 'api' and isinstance(value, dict):
                        self._update_api_config(config.api, value)
                    elif key == 'risk' and isinstance(value, dict):
                        self._update_risk_config(config.risk, value)
                    elif key == 'strategy' and isinstance(value, dict):
                        self._update_strategy_config(config.strategy, value)
                    elif key == 'logging' and isinstance(value, dict):
                        self._update_logging_config(config.logging, value)
                    elif key == 'notification' and isinstance(value, dict):
                        self._update_notification_config(config.notification, value)
                    elif key == 'backtest' and isinstance(value, dict):
                        self._update_backtest_config(config.backtest, value)
                    else:
                        setattr(config, key, value)
            
            return config
            
        except Exception as e:
            raise ConfigurationError(f"Failed to convert dictionary to TradingConfig: {str(e)}")
    
    def _update_api_config(self, api_config: APIConfig, data: Dict[str, Any]) -> None:
        """Update APIConfig from dictionary data."""
        for key, value in data.items():
            if key == 'credentials' and isinstance(value, dict):
                for cred_key, cred_value in value.items():
                    if hasattr(api_config.credentials, cred_key):
                        setattr(api_config.credentials, cred_key, cred_value)
            elif hasattr(api_config, key):
                setattr(api_config, key, value)
    
    def _update_risk_config(self, risk_config: RiskConfig, data: Dict[str, Any]) -> None:
        """Update RiskConfig from dictionary data."""
        for key, value in data.items():
            if hasattr(risk_config, key):
                setattr(risk_config, key, value)
    
    def _update_strategy_config(self, strategy_config: StrategyConfig, data: Dict[str, Any]) -> None:
        """Update StrategyConfig from dictionary data."""
        for key, value in data.items():
            if hasattr(strategy_config, key):
                if key in ['straddle', 'directional', 'iron_condor', 'greeks', 'volatility']:
                    # Update nested strategy configs
                    nested_config = getattr(strategy_config, key)
                    if isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            if hasattr(nested_config, nested_key):
                                setattr(nested_config, nested_key, nested_value)
                else:
                    setattr(strategy_config, key, value)
    
    def _update_logging_config(self, logging_config: LoggingConfig, data: Dict[str, Any]) -> None:
        """Update LoggingConfig from dictionary data."""
        for key, value in data.items():
            if hasattr(logging_config, key):
                setattr(logging_config, key, value)
    
    def _update_notification_config(self, notification_config: NotificationConfig, data: Dict[str, Any]) -> None:
        """Update NotificationConfig from dictionary data."""
        for key, value in data.items():
            if hasattr(notification_config, key):
                setattr(notification_config, key, value)
    
    def _update_backtest_config(self, backtest_config: BacktestConfig, data: Dict[str, Any]) -> None:
        """Update BacktestConfig from dictionary data."""
        for key, value in data.items():
            if hasattr(backtest_config, key):
                setattr(backtest_config, key, value)
    
    def _convert_enums_to_values(self, data: Any) -> Any:
        """
        Recursively convert enum objects to their values for serialization.
        """
        from enum import Enum
        
        if isinstance(data, Enum):
            return data.value
        elif isinstance(data, dict):
            return {key: self._convert_enums_to_values(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_enums_to_values(item) for item in data]
        else:
            return data