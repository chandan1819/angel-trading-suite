# 🔧 Bank Nifty Lot Size Update Plan

## 📊 **Current Issue**
The trading system is using **outdated lot sizes** (15, 25, 30) instead of the current Bank Nifty lot size of **35**.

## 🎯 **Required Update**
- **Old Lot Size**: 25 (most common), some references to 15 and 30
- **New Lot Size**: 35 (effective July 2025 onwards)
- **Impact**: Position sizing, risk calculations, P&L computations, margin requirements

## 📁 **Files That Need Updates**

### **1. Core Data Models**
- `src/models/trading_models.py` - Line 60: `lot_size: int = 25` → `lot_size: int = 35`

### **2. Data Management**
- `src/data/data_manager.py`:
  - Line 80: `'default_lot_size': 25` → `'default_lot_size': 35`
  - Line 787: Comment "lot size is typically 25" → "lot size is typically 35"
  - Line 791: Return value needs update

### **3. Order Validation**
- `src/orders/order_validator.py` - Line 40: `self.lot_size = config.get('lot_size', 25)` → `self.lot_size = config.get('lot_size', 35)`

### **4. Configuration Files**
- `config/live_trading_config.yaml` - Line 35: `max_position_size: 25` → `max_position_size: 35` (or multiple of 35)
- `config/trading_config.example.yaml` - Line 37: `max_position_size: 100` → Update to multiple of 35

### **5. Demo/Test Files**
- `show_api_structure.py` - Lines 30, 41: `"lotsize": "25"` → `"lotsize": "35"`

## 🧮 **Impact Analysis**

### **Position Sizing Impact**
```python
# OLD: With lot size 25
1 lot = 25 contracts
2 lots = 50 contracts
Max position (100 lots) = 2,500 contracts

# NEW: With lot size 35  
1 lot = 35 contracts
2 lots = 70 contracts
Max position (100 lots) = 3,500 contracts
```

### **Risk Management Impact**
```python
# Example: ₹2,000 profit target
# OLD: ₹2,000 ÷ 25 contracts = ₹80 per contract
# NEW: ₹2,000 ÷ 35 contracts = ₹57.14 per contract

# Stop-loss calculation also changes proportionally
```

### **Margin Requirements Impact**
```python
# Margin per lot increases with lot size
# OLD: Margin for 25 contracts
# NEW: Margin for 35 contracts (40% increase)
```

## ✅ **Update Checklist**

### **Phase 1: Core Updates**
- [ ] Update `src/models/trading_models.py` - Option.lot_size default
- [ ] Update `src/data/data_manager.py` - default_lot_size config
- [ ] Update `src/orders/order_validator.py` - lot_size default
- [ ] Update data extraction logic in DataManager._extract_lot_size()

### **Phase 2: Configuration Updates**
- [ ] Update `config/live_trading_config.yaml` - max_position_size
- [ ] Update `config/trading_config.example.yaml` - max_position_size  
- [ ] Update strategy configuration files if they reference lot sizes
- [ ] Update any hardcoded position size limits to be multiples of 35

### **Phase 3: Test Updates**
- [ ] Update test cases that assume lot size of 25
- [ ] Update mock data in test files
- [ ] Update `show_api_structure.py` demo file
- [ ] Verify all position sizing tests with new lot size

### **Phase 4: Documentation Updates**
- [ ] Update README.md if it mentions lot sizes
- [ ] Update any documentation that references position sizing
- [ ] Update configuration guides with correct lot size

## 🚨 **Critical Considerations**

### **1. Position Size Validation**
```python
# Ensure all quantities are multiples of 35
if quantity % 35 != 0:
    raise ValueError("Quantity must be multiple of lot size (35)")
```

### **2. Risk Calculations**
```python
# P&L per point changes with lot size
# OLD: 1 point move = ₹25 (for 1 lot)
# NEW: 1 point move = ₹35 (for 1 lot)
```

### **3. Margin Requirements**
```python
# Margin calculations need to account for larger lot size
# This affects maximum position sizes and risk limits
```

## 🔄 **Implementation Steps**

### **Step 1: Update Constants**
```python
# In src/models/trading_models.py
BANKNIFTY_LOT_SIZE = 35  # Updated from 25

# In configuration files
default_lot_size: 35
max_position_size: 70  # Multiple of 35
```

### **Step 2: Update Risk Calculations**
```python
# Ensure all risk calculations use the new lot size
position_value = quantity * price  # quantity already in multiples of 35
margin_required = base_margin * (quantity / 35)  # per lot calculation
```

### **Step 3: Update Validation Logic**
```python
# In order validation
def validate_quantity(self, quantity: int) -> bool:
    return quantity % 35 == 0  # Must be multiple of 35
```

### **Step 4: Test Thoroughly**
- [ ] Run all unit tests
- [ ] Test position sizing calculations
- [ ] Test risk management with new lot size
- [ ] Test paper trading with realistic quantities

## 📈 **Expected Benefits**

1. **Accurate Position Sizing**: Correct lot size ensures proper position calculations
2. **Correct Risk Management**: P&L and risk limits calculated accurately  
3. **Proper Margin Usage**: Margin calculations reflect actual requirements
4. **Compliance**: System matches current NSE specifications

## ⚠️ **Important Notes**

- **Backward Compatibility**: Old trades/logs may reference old lot sizes
- **Configuration Migration**: Existing configs need manual updates
- **Testing Required**: Thorough testing needed before live trading
- **Documentation**: All docs need updates to reflect new lot size

**This update is CRITICAL for accurate trading and risk management!**