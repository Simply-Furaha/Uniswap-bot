# COMPREHENSIVE CELO UNISWAP FIX
# Place this in a new file: celo_transaction_fix.py

from web3 import Web3
import math
from typing import Dict, Optional, Tuple
import time

class CeloTransactionFixer:
    """
    Comprehensive fix for CELO Uniswap transactions
    Handles slippage, gas optimization, and CELO-specific issues
    """
    
    def __init__(self, wallet_manager, uniswap_manager, config):
        self.wallet = wallet_manager
        self.uniswap = uniswap_manager
        self.config = config
        
        # CELO-specific settings
        self.CELO_SLIPPAGE = 2.0  # 2% slippage for CELO (higher than default)
        self.CELO_GAS_MULTIPLIER = 1.5  # 50% higher gas for safety
        self.CELO_MAX_RETRIES = 3
        
    def execute_safe_swap(self, token_in: str, token_out: str, amount: float, description: str) -> bool:
        """Execute swap with CELO-specific optimizations"""
        print(f"\n🔧 EXECUTING SAFE CELO SWAP: {description}")
        
        try:
            # Get token info
            token_in_info = self.wallet.get_token_info(token_in)
            token_out_info = self.wallet.get_token_info(token_out)
            
            # Convert to wei
            amount_wei = int(amount * (10 ** token_in_info["decimals"]))
            
            print(f"  Swapping: {amount:.6f} {token_in_info['symbol']} → {token_out_info['symbol']}")
            print(f"  Amount in wei: {amount_wei}")
            
            # Ensure approval with higher amount for safety
            if not self._ensure_router_approval(token_in, amount_wei * 2):
                print(f"  ❌ Failed to approve {token_in_info['symbol']}")
                return False
            
            # Calculate minimum out with CELO slippage
            min_amount_out = self._calculate_min_amount_out(amount_wei, self.CELO_SLIPPAGE)
            
            print(f"  Min amount out: {min_amount_out} (slippage: {self.CELO_SLIPPAGE}%)")
            
            # Retry mechanism for CELO
            for attempt in range(self.CELO_MAX_RETRIES):
                print(f"  Attempt {attempt + 1}/{self.CELO_MAX_RETRIES}")
                
                success = self._execute_swap_attempt(
                    token_in, token_out, amount_wei, min_amount_out, attempt
                )
                
                if success:
                    print(f"  ✅ Swap successful on attempt {attempt + 1}")
                    return True
                else:
                    print(f"  ❌ Attempt {attempt + 1} failed")
                    if attempt < self.CELO_MAX_RETRIES - 1:
                        print(f"  ⏳ Waiting 5 seconds before retry...")
                        time.sleep(5)
            
            print(f"  ❌ All {self.CELO_MAX_RETRIES} attempts failed")
            return False
            
        except Exception as e:
            print(f"  ❌ Safe swap error: {e}")
            return False
    
    def _execute_swap_attempt(self, token_in: str, token_out: str, amount_wei: int, 
                             min_amount_out: int, attempt: int) -> bool:
        """Execute single swap attempt with increasing slippage"""
        try:
            # Increase slippage tolerance with each attempt
            attempt_slippage = self.CELO_SLIPPAGE + (attempt * 1.0)  # +1% per attempt
            adjusted_min_out = self._calculate_min_amount_out(amount_wei, attempt_slippage)
            
            print(f"    Using slippage: {attempt_slippage}%, min out: {adjusted_min_out}")
            
            # Build swap transaction with CELO optimizations
            router_contract = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.uniswap.network_config.uniswap_v3_router),
                abi=self.uniswap.router_abi
            )
            
            # Get deadline (longer for CELO)
            deadline = int(self.wallet.w3.eth.get_block('latest')['timestamp']) + 600  # 10 minutes
            
            # Build swap parameters
            swap_params = (
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                self.config.pool_fee,
                self.wallet.account.address,
                deadline,
                amount_wei,
                adjusted_min_out,
                0  # sqrtPriceLimitX96 (no limit)
            )
            
            # Estimate gas with CELO multiplier
            base_gas = 350000  # Base gas for swaps
            celo_gas = int(base_gas * self.CELO_GAS_MULTIPLIER)
            
            # Build transaction
            transaction = router_contract.functions.exactInputSingle(swap_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': celo_gas,
                'gasPrice': self._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            print(f"    Gas limit: {celo_gas}, Gas price: {self.wallet.w3.from_wei(transaction['gasPrice'], 'gwei'):.2f} gwei")
            
            # Send transaction
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=180):  # 3 min timeout
                print(f"    ✅ Swap successful: {tx_hash}")
                return True
            else:
                print(f"    ❌ Transaction failed or timed out")
                return False
                
        except Exception as e:
            print(f"    ❌ Swap attempt error: {e}")
            return False
    
    def execute_safe_position_creation(self, token0: str, token1: str, amount0: int, amount1: int,
                                     tick_lower: int, tick_upper: int) -> Optional[str]:
        """Create position with CELO-specific optimizations"""
        print(f"\n🔧 EXECUTING SAFE CELO POSITION CREATION")
        
        try:
            # Ensure proper token ordering
            token0, token1, amount0, amount1 = self._ensure_token_ordering(
                token0, token1, amount0, amount1
            )
            
            # Get token info
            token0_info = self.wallet.get_token_info(token0)
            token1_info = self.wallet.get_token_info(token1)
            
            print(f"  Token0: {token0_info['symbol']} ({amount0})")
            print(f"  Token1: {token1_info['symbol']} ({amount1})")
            print(f"  Tick range: {tick_lower} to {tick_upper}")
            
            # Ensure approvals for position manager
            if amount0 > 0 and not self._ensure_position_approval(token0, amount0 * 2):
                return None
            if amount1 > 0 and not self._ensure_position_approval(token1, amount1 * 2):
                return None
            
            # Retry mechanism for position creation
            for attempt in range(self.CELO_MAX_RETRIES):
                print(f"  Position creation attempt {attempt + 1}/{self.CELO_MAX_RETRIES}")
                
                tx_hash = self._execute_position_attempt(
                    token0, token1, amount0, amount1, tick_lower, tick_upper, attempt
                )
                
                if tx_hash:
                    print(f"  ✅ Position created successfully: {tx_hash}")
                    return tx_hash
                else:
                    print(f"  ❌ Attempt {attempt + 1} failed")
                    if attempt < self.CELO_MAX_RETRIES - 1:
                        print(f"  ⏳ Waiting 10 seconds before retry...")
                        time.sleep(10)
            
            print(f"  ❌ All {self.CELO_MAX_RETRIES} position creation attempts failed")
            return None
            
        except Exception as e:
            print(f"  ❌ Safe position creation error: {e}")
            return None
    
    def _execute_position_attempt(self, token0: str, token1: str, amount0: int, amount1: int,
                                 tick_lower: int, tick_upper: int, attempt: int) -> Optional[str]:
        """Execute single position creation attempt"""
        try:
            # Increase slippage tolerance with each attempt
            attempt_slippage = self.CELO_SLIPPAGE + (attempt * 1.0)  # +1% per attempt
            slippage_factor = (100 - attempt_slippage) / 100
            
            # Calculate minimum amounts with progressive slippage
            amount0_min = int(amount0 * slippage_factor) if amount0 > 0 else 0
            amount1_min = int(amount1 * slippage_factor) if amount1 > 0 else 0
            
            print(f"    Slippage: {attempt_slippage}%")
            print(f"    Min amounts: {amount0_min}, {amount1_min}")
            
            # Build position manager transaction
            position_manager = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.uniswap.network_config.position_manager),
                abi=self.uniswap.position_manager_abi
            )
            
            # Get deadline (longer for CELO)
            deadline = int(self.wallet.w3.eth.get_block('latest')['timestamp']) + 900  # 15 minutes
            
            # Build mint parameters
            mint_params = (
                Web3.to_checksum_address(token0),
                Web3.to_checksum_address(token1),
                self.config.pool_fee,
                tick_lower,
                tick_upper,
                amount0,
                amount1,
                amount0_min,
                amount1_min,
                self.wallet.account.address,
                deadline
            )
            
            # Estimate gas with CELO multiplier
            base_gas = 1000000  # Base gas for position creation
            celo_gas = int(base_gas * self.CELO_GAS_MULTIPLIER)
            
            # Build transaction
            transaction = position_manager.functions.mint(mint_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': celo_gas,
                'gasPrice': self._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            print(f"    Gas limit: {celo_gas}, Gas price: {self.wallet.w3.from_wei(transaction['gasPrice'], 'gwei'):.2f} gwei")
            
            # Send transaction
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=300):  # 5 min timeout
                print(f"    ✅ Position creation successful: {tx_hash}")
                return tx_hash
            else:
                print(f"    ❌ Position creation failed or timed out")
                return None
                
        except Exception as e:
            print(f"    ❌ Position creation attempt error: {e}")
            return None
    
    def fix_tick_range(self, current_price: float, range_percent: float) -> Tuple[int, int]:
        """Fix tick range calculation for CELO 0.01% pools"""
        try:
            # CELO-specific tick range calculation
            tick_spacing = 1  # For 0.01% fee pools
            
            # Convert price to tick
            current_tick = int(math.log(current_price) / math.log(1.0001))
            
            # Calculate range
            price_multiplier = 1 + (range_percent / 100)
            upper_price = current_price * price_multiplier
            lower_price = current_price / price_multiplier
            
            upper_tick = int(math.log(upper_price) / math.log(1.0001))
            lower_tick = int(math.log(lower_price) / math.log(1.0001))
            
            # Round to valid tick spacing
            upper_tick = ((upper_tick // tick_spacing) + 1) * tick_spacing
            lower_tick = (lower_tick // tick_spacing) * tick_spacing
            
            # CELO-specific: Ensure minimum viable range
            min_tick_range = 20  # Increased minimum for CELO
            if upper_tick - lower_tick < min_tick_range:
                current_tick_rounded = (current_tick // tick_spacing) * tick_spacing
                upper_tick = current_tick_rounded + (min_tick_range // 2)
                lower_tick = current_tick_rounded - (min_tick_range // 2)
                
                # Ensure tick spacing compliance
                upper_tick = ((upper_tick // tick_spacing) + 1) * tick_spacing
                lower_tick = (lower_tick // tick_spacing) * tick_spacing
            
            # Validate bounds
            MIN_TICK = -887272
            MAX_TICK = 887272
            
            lower_tick = max(lower_tick, MIN_TICK)
            upper_tick = min(upper_tick, MAX_TICK)
            
            print(f"🔧 CELO tick range fix:")
            print(f"  Current price: {current_price:.6f}")
            print(f"  Range: {range_percent:.4f}%")
            print(f"  Fixed ticks: {lower_tick} to {upper_tick}")
            print(f"  Price range: {1.0001**lower_tick:.6f} - {1.0001**upper_tick:.6f}")
            
            return lower_tick, upper_tick
            
        except Exception as e:
            print(f"❌ Tick range fix error: {e}")
            # Fallback to safe range
            return -10, 10
    
    def _ensure_token_ordering(self, token0: str, token1: str, amount0: int, amount1: int):
        """Ensure proper token ordering for Uniswap"""
        token0_addr = Web3.to_checksum_address(token0)
        token1_addr = Web3.to_checksum_address(token1)
        
        # Ensure token0 < token1
        if int(token0_addr, 16) > int(token1_addr, 16):
            return token1_addr, token0_addr, amount1, amount0
        else:
            return token0_addr, token1_addr, amount0, amount1
    
    def _calculate_min_amount_out(self, amount_in: int, slippage_percent: float) -> int:
        """Calculate minimum amount out with slippage"""
        return int(amount_in * (100 - slippage_percent) / 100)
    
    def _get_celo_gas_price(self) -> int:
        """Get optimized gas price for CELO"""
        try:
            base_gas_price = self.wallet.w3.eth.gas_price
            # CELO gas is very cheap, but add buffer for reliability
            return int(base_gas_price * 1.1)
        except:
            # Fallback gas price for CELO
            return self.wallet.w3.to_wei(2, 'gwei')
    
    def _ensure_router_approval(self, token_address: str, amount: int) -> bool:
        """Ensure token approval for router"""
        return self.wallet.approve_token(
            token_address,
            self.uniswap.network_config.uniswap_v3_router,
            amount
        )
    
    def _ensure_position_approval(self, token_address: str, amount: int) -> bool:
        """Ensure token approval for position manager"""
        return self.wallet.approve_token(
            token_address,
            self.uniswap.network_config.position_manager,
            amount
        )