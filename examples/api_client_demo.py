#!/usr/bin/env python3
"""
Demo script showing usage of the enhanced Angel API client.
"""

import os
import logging
from datetime import datetime

from src.api.angel_api_client import AngelAPIClient, APICredentials, ConnectionConfig
from src.api.market_data import MarketDataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Demonstrate the enhanced API client functionality."""
    
    # Load credentials from environment variables
    credentials = APICredentials(
        api_key=os.getenv('ANGEL_API_KEY', 'demo_api_key'),
        client_code=os.getenv('ANGEL_CLIENT_CODE', 'demo_client'),
        pin=os.getenv('ANGEL_PIN', '1234'),
        totp_secret=os.getenv('ANGEL_TOTP_SECRET')  # Optional
    )
    
    # Configure connection settings
    config = ConnectionConfig(
        timeout=10,
        max_retries=3,
        rate_limit_per_second=5.0,  # Conservative rate limiting
        connection_pool_size=5
    )
    
    logger.info("Starting Angel API client demo...")
    
    try:
        # Initialize API client
        with AngelAPIClient(credentials, config) as api_client:
            logger.info("API client initialized and authenticated successfully")
            
            # Display connection status
            status = api_client.get_connection_status()
            logger.info(f"Connection status: {status}")
            
            # Initialize market data manager
            market_data = MarketDataManager(api_client)
            
            # Demo 1: Search for instruments
            logger.info("\n=== Demo 1: Searching for instruments ===")
            instruments = api_client.search_instruments("NFO", "BANKNIFTY")
            logger.info(f"Found {len(instruments)} BANKNIFTY instruments")
            
            if instruments:
                # Show first few instruments
                for i, instrument in enumerate(instruments[:3]):
                    logger.info(f"  {i+1}. {instrument.get('tradingsymbol')} - Token: {instrument.get('symboltoken')}")
            
            # Demo 2: Get options chain (this will use mock data in demo mode)
            logger.info("\n=== Demo 2: Getting options chain ===")
            try:
                options_chain = market_data.get_options_chain("BANKNIFTY")
                if options_chain:
                    logger.info(f"Options chain retrieved:")
                    logger.info(f"  Underlying: {options_chain.underlying_symbol}")
                    logger.info(f"  Price: {options_chain.underlying_price}")
                    logger.info(f"  Expiry: {options_chain.expiry_date}")
                    logger.info(f"  ATM Strike: {options_chain.atm_strike}")
                    logger.info(f"  Total strikes: {len(options_chain.strikes)}")
                else:
                    logger.warning("Could not retrieve options chain")
            except Exception as e:
                logger.error(f"Error getting options chain: {e}")
            
            # Demo 3: Get historical data
            logger.info("\n=== Demo 3: Getting historical data ===")
            if instruments:
                try:
                    instrument = instruments[0]
                    historical_data = market_data.get_historical_data(
                        symbol=instrument['tradingsymbol'],
                        token=instrument['symboltoken'],
                        exchange=instrument['exchange'],
                        interval="ONE_DAY"
                    )
                    logger.info(f"Retrieved {len(historical_data)} historical data points")
                    
                    if historical_data:
                        latest = historical_data[-1]
                        logger.info(f"  Latest data: {latest.timestamp} - Close: {latest.close}")
                
                except Exception as e:
                    logger.error(f"Error getting historical data: {e}")
            
            # Demo 4: Cache information
            logger.info("\n=== Demo 4: Cache information ===")
            cache_info = market_data.get_cached_data_info()
            logger.info(f"Cache contains {cache_info['total_entries']} entries")
            
            for key, info in cache_info['entries'].items():
                logger.info(f"  {key}: {info['data_type']} (expired: {info['expired']})")
            
            # Demo 5: Real-time monitoring (brief demo)
            logger.info("\n=== Demo 5: Real-time monitoring (5 seconds) ===")
            if instruments:
                try:
                    # Monitor first instrument for 5 seconds
                    monitor_symbols = [{
                        'exchange': instruments[0]['exchange'],
                        'symbol': instruments[0]['tradingsymbol'],
                        'token': instruments[0]['symboltoken']
                    }]
                    
                    def price_callback(price_data):
                        logger.info(f"Price update: {price_data.symbol} = {price_data.ltp}")
                    
                    market_data.start_real_time_monitoring(
                        monitor_symbols, 
                        price_callback, 
                        interval_seconds=2
                    )
                    
                    # Let it run for 5 seconds
                    import time
                    time.sleep(5)
                    
                    market_data.stop_real_time_monitoring()
                    logger.info("Real-time monitoring stopped")
                
                except Exception as e:
                    logger.error(f"Error in real-time monitoring: {e}")
            
            logger.info("\n=== Demo completed successfully ===")
    
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())