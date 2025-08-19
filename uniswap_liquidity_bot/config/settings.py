import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class BotConfig:
    """Main bot configuration structure"""
    
    # Network settings
    network: str = "ethereum"
    rpc_url: str = ""
    
    # Wallet settings
    private_key: str = ""
    wallet_address: str = ""
    
    # Trading parameters
    budget_usd: float = 100.0
    price_range_percent: float = 5.0  # Default range percentage
    min_price_range_percent: float = 1.0  # Minimum allowed range
    max_price_range_percent: float = 20.0  # Maximum allowed range
    dynamic_range: bool = True  # Enable dynamic range adjustment
    volatility_multiplier: float = 1.5  # Multiply range by volatility
    rebalance_threshold: float = 80.0  # Rebalance when position is 80% out of range
    
    # Token pair
    token0_address: str = ""
    token1_address: str = ""
    pool_fee: int = 3000  # 0.3% fee tier
    
    # Risk management
    max_slippage: float = 0.5  # 0.5% max slippage
    gas_price_gwei: Optional[int] = None  # Auto if None
    min_gas_balance: float = 0.01  # Minimum native token balance for gas
    
    # Range calculation settings
    range_calculation_method: str = "adaptive"  # "fixed", "adaptive", "volatility_based"
    tick_spacing: int = 60  # Tick spacing for the pool fee tier
    range_buffer_percent: float = 10.0  # Buffer to prevent immediate out-of-range
    
    # Monitoring
    check_interval: int = 30  # Check positions every 30 seconds
    auto_compound: bool = True
    price_check_periods: int = 10  # Periods to check for volatility calculation
    
    # Logging
    log_level: str = "INFO"

class ConfigManager:
    """Manages bot configuration loading and saving"""
    
    def __init__(self, config_path: str = "data/config.json"):
        self.config_path = config_path
        self.config = BotConfig()
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
    
    def load_config(self) -> BotConfig:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                
                # Update config with loaded values
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                
                # Validate range settings
                self._validate_range_settings()
                
                print(f"Configuration loaded from {self.config_path}")
            else:
                self.save_config()  # Create default config file
                print(f"Default configuration created at {self.config_path}")
        
        except Exception as e:
            print(f"Error loading config: {e}")
            print("Using default configuration")
        
        return self.config
    
    def _validate_range_settings(self):
        """Validate and adjust range settings"""
        # Ensure min < default < max
        if self.config.min_price_range_percent >= self.config.price_range_percent:
            self.config.min_price_range_percent = self.config.price_range_percent * 0.5
        
        if self.config.max_price_range_percent <= self.config.price_range_percent:
            self.config.max_price_range_percent = self.config.price_range_percent * 3
        
        # Ensure reasonable thresholds
        if self.config.rebalance_threshold < 50:
            self.config.rebalance_threshold = 50
        elif self.config.rebalance_threshold > 95:
            self.config.rebalance_threshold = 95
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            config_dict = {
                key: value for key, value in self.config.__dict__.items()
                if not key.startswith('_')
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            print(f"Configuration saved to {self.config_path}")
        
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def update_config(self, updates: Dict):
        """Update configuration with new values"""
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._validate_range_settings()
        self.save_config()
    
    def validate_config(self) -> bool:
        """Validate configuration completeness"""
        required_fields = [
            'rpc_url', 'private_key', 'token0_address', 'token1_address'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(self.config, field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"Missing required configuration: {missing_fields}")
            return False
        
        return True
    
    def get_sample_config(self) -> Dict:
        """Return sample configuration for user reference"""
        return {
            "network": "polygon",
            "rpc_url": "https://polygon-rpc.com",
            "private_key": "YOUR_PRIVATE_KEY_HERE",
            "wallet_address": "YOUR_WALLET_ADDRESS",
            "budget_usd": 100.0,
            "price_range_percent": 5.0,
            "min_price_range_percent": 1.0,
            "max_price_range_percent": 20.0,
            "dynamic_range": True,
            "volatility_multiplier": 1.5,
            "rebalance_threshold": 80.0,
            "token0_address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "token1_address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "pool_fee": 500,
            "max_slippage": 0.5,
            "gas_price_gwei": None,
            "min_gas_balance": 0.01,
            "range_calculation_method": "adaptive",
            "tick_spacing": 10,
            "range_buffer_percent": 10.0,
            "check_interval": 30,
            "auto_compound": True,
            "price_check_periods": 10,
            "log_level": "INFO"
        }
    
    def get_range_info(self) -> Dict:
        """Get current range configuration info"""
        return {
            "current_range_percent": self.config.price_range_percent,
            "min_range_percent": self.config.min_price_range_percent,
            "max_range_percent": self.config.max_price_range_percent,
            "dynamic_range_enabled": self.config.dynamic_range,
            "calculation_method": self.config.range_calculation_method,
            "volatility_multiplier": self.config.volatility_multiplier,
            "range_buffer": self.config.range_buffer_percent
        }