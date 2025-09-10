"""
Trading System Constants
Contains important constants used throughout the trading system
"""

# Bank Nifty Trading Constants
BANKNIFTY_LOT_SIZE = 35  # Current lot size (July 2025 onwards)
BANKNIFTY_TICK_SIZE = 0.05  # Minimum price movement
BANKNIFTY_STRIKE_SPACING = 100.0  # Standard strike spacing

# Historical lot sizes for reference
BANKNIFTY_LOT_SIZE_HISTORY = {
    "2024": 25,  # Previous lot size
    "2025": 35,  # Current lot size (July 2025 onwards)
}

# Risk Management Constants
DEFAULT_PROFIT_TARGET = 2000.0  # ₹2,000 per trade
DEFAULT_STOP_LOSS = 1000.0      # ₹1,000 per trade

# Position Sizing Constants
MIN_POSITION_SIZE = 35          # Minimum 1 lot
MAX_POSITION_SIZE_CONSERVATIVE = 35   # 1 lot for conservative trading
MAX_POSITION_SIZE_MODERATE = 70       # 2 lots for moderate risk
MAX_POSITION_SIZE_AGGRESSIVE = 105    # 3 lots for aggressive trading

def validate_quantity(quantity: int) -> bool:
    """
    Validate that quantity is a multiple of current lot size
    
    Args:
        quantity: Number of contracts
        
    Returns:
        True if quantity is valid (multiple of lot size)
    """
    return quantity % BANKNIFTY_LOT_SIZE == 0

def round_to_lot_size(quantity: int) -> int:
    """
    Round quantity to nearest valid lot size multiple
    
    Args:
        quantity: Desired quantity
        
    Returns:
        Quantity rounded to nearest lot size multiple
    """
    return max(BANKNIFTY_LOT_SIZE, 
               round(quantity / BANKNIFTY_LOT_SIZE) * BANKNIFTY_LOT_SIZE)

def calculate_lots(quantity: int) -> int:
    """
    Calculate number of lots for given quantity
    
    Args:
        quantity: Number of contracts
        
    Returns:
        Number of lots
    """
    return quantity // BANKNIFTY_LOT_SIZE