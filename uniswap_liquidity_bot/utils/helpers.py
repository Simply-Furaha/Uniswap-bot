import time
import math
from typing import Optional, Dict, Any
from web3 import Web3

def wait_for_confirmation(w3: Web3, tx_hash: str, timeout: int = 120) -> bool:
    """Wait for transaction confirmation with timeout"""
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt.status == 1
    except Exception as e:
        print(f"Transaction confirmation failed: {e}")
        return False

def format_token_amount(amount: int, decimals: int) -> float:
    """Convert token amount from wei to decimal format"""
    return amount / (10 ** decimals)

def to_wei_amount(amount: float, decimals: int) -> int:
    """Convert decimal amount to wei format"""
    return int(amount * (10 ** decimals))

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def format_address(address: str) -> str:
    """Format address for display (shortened)"""
    if len(address) < 10:
        return address
    return f"{address[:6]}...{address[-4:]}"

def validate_address(address: str) -> bool:
    """Validate Ethereum address format"""
    try:
        Web3.to_checksum_address(address)
        return True
    except:
        return False

def calculate_gas_cost(gas_used: int, gas_price: int, decimals: int = 18) -> float:
    """Calculate gas cost in native token"""
    return (gas_used * gas_price) / (10 ** decimals)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def safe_division(a: float, b: float, default: float = 0.0) -> float:
    """Safe division that returns default on division by zero"""
    try:
        return a / b if b != 0 else default
    except:
        return default

def format_timestamp(timestamp: float) -> str:
    """Format timestamp to readable string"""
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

def calculate_slippage_amount(amount: int, slippage_percent: float) -> int:
    """Calculate minimum amount considering slippage"""
    return int(amount * (1 - slippage_percent / 100))

def price_to_tick(price: float) -> int:
    """Convert price to tick (Uniswap V3)"""
    return int(math.log(price) / math.log(1.0001))

def tick_to_price(tick: int) -> float:
    """Convert tick to price (Uniswap V3)"""
    return 1.0001 ** tick