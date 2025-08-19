import math
from typing import Dict, Optional, Tuple, List
from web3 import Web3
from config.networks import NetworkManager, UNISWAP_V3_POOL_ABI

class UniswapV3Manager:
    """CELO-optimized Uniswap V3 manager with enhanced error handling"""
    
    def __init__(self, wallet_manager, network_manager: NetworkManager):
        self.wallet = wallet_manager
        self.network_manager = network_manager
        self.network_config = network_manager.get_network_config()
        
        # Price history for volatility calculation
        self.price_history = []
        
        # CELO-specific settings
        self.CELO_SLIPPAGE = 0.08  # 8% slippage for CELO
        self.CELO_GAS_MULTIPLIER = 1.8
        
        # Position Manager ABI
        self.position_manager_abi = [
            {
                "inputs": [
                    {"name": "params", "type": "tuple", "components": [
                        {"name": "token0", "type": "address"},
                        {"name": "token1", "type": "address"},
                        {"name": "fee", "type": "uint24"},
                        {"name": "tickLower", "type": "int24"},
                        {"name": "tickUpper", "type": "int24"},
                        {"name": "amount0Desired", "type": "uint256"},
                        {"name": "amount1Desired", "type": "uint256"},
                        {"name": "amount0Min", "type": "uint256"},
                        {"name": "amount1Min", "type": "uint256"},
                        {"name": "recipient", "type": "address"},
                        {"name": "deadline", "type": "uint256"}
                    ]}
                ],
                "name": "mint",
                "outputs": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "liquidity", "type": "uint128"},
                    {"name": "amount0", "type": "uint256"},
                    {"name": "amount1", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "positions",
                "outputs": [
                    {"name": "nonce", "type": "uint96"},
                    {"name": "operator", "type": "address"},
                    {"name": "token0", "type": "address"},
                    {"name": "token1", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "tickLower", "type": "int24"},
                    {"name": "tickUpper", "type": "int24"},
                    {"name": "liquidity", "type": "uint128"},
                    {"name": "feeGrowthInside0LastX128", "type": "uint256"},
                    {"name": "feeGrowthInside1LastX128", "type": "uint256"},
                    {"name": "tokensOwed0", "type": "uint128"},
                    {"name": "tokensOwed1", "type": "uint128"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "params", "type": "tuple", "components": [
                        {"name": "tokenId", "type": "uint256"},
                        {"name": "liquidity", "type": "uint128"},
                        {"name": "amount0Min", "type": "uint256"},
                        {"name": "amount1Min", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"}
                    ]}
                ],
                "name": "decreaseLiquidity",
                "outputs": [
                    {"name": "amount0", "type": "uint256"},
                    {"name": "amount1", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "params", "type": "tuple", "components": [
                        {"name": "tokenId", "type": "uint256"},
                        {"name": "recipient", "type": "address"},
                        {"name": "amount0Max", "type": "uint128"},
                        {"name": "amount1Max", "type": "uint128"}
                    ]}
                ],
                "name": "collect",
                "outputs": [
                    {"name": "amount0", "type": "uint256"},
                    {"name": "amount1", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        
        # Router ABI
        self.router_abi = [
            {
                "inputs": [
                    {"name": "params", "type": "tuple", "components": [
                        {"name": "tokenIn", "type": "address"},
                        {"name": "tokenOut", "type": "address"},
                        {"name": "fee", "type": "uint24"},
                        {"name": "recipient", "type": "address"},
                        {"name": "deadline", "type": "uint256"},
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "amountOutMinimum", "type": "uint256"},
                        {"name": "sqrtPriceLimitX96", "type": "uint160"}
                    ]}
                ],
                "name": "exactInputSingle",
                "outputs": [{"name": "amountOut", "type": "uint256"}],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        
        # Factory ABI
        self.factory_abi = [
            {
                "inputs": [
                    {"name": "tokenA", "type": "address"},
                    {"name": "tokenB", "type": "address"},
                    {"name": "fee", "type": "uint24"}
                ],
                "name": "getPool",
                "outputs": [{"name": "pool", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def get_pool_address(self, token0: str, token1: str, fee: int) -> Optional[str]:
        """Get pool address with proper token ordering"""
        try:
            token0 = Web3.to_checksum_address(token0)
            token1 = Web3.to_checksum_address(token1)
            
            # Ensure proper token ordering
            if int(token0, 16) > int(token1, 16):
                token0, token1 = token1, token0
            
            factory_contract = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.uniswap_v3_factory),
                abi=self.factory_abi
            )
            
            pool_address = factory_contract.functions.getPool(token0, token1, fee).call()
            
            if pool_address == "0x0000000000000000000000000000000000000000":
                print(f"Pool not found for {token0}/{token1} with fee {fee}")
                return None
            
            print(f"Found pool: {pool_address}")
            return pool_address
            
        except Exception as e:
            print(f"Error getting pool address: {e}")
            return None
    
    def get_pool_price(self, pool_address: str) -> Optional[Dict]:
        """Get current pool price with enhanced validation"""
        try:
            if not pool_address:
                return None
            
            pool_contract = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V3_POOL_ABI
            )
            
            slot0 = pool_contract.functions.slot0().call()
            
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]
            
            if sqrt_price_x96 == 0:
                print("Invalid price data: sqrt_price_x96 is 0")
                return None
            
            # Convert sqrtPriceX96 to actual price
            price = (sqrt_price_x96 / (2 ** 96)) ** 2
            
            if price <= 0 or not math.isfinite(price):
                print(f"Invalid calculated price: {price}")
                return None
            
            # Store price for volatility calculation
            import time
            self.price_history.append({
                "price": price,
                "timestamp": time.time(),
                "tick": current_tick
            })
            
            # Keep only recent price history
            if len(self.price_history) > 100:
                self.price_history = self.price_history[-100:]
            
            return {
                "sqrt_price_x96": sqrt_price_x96,
                "current_tick": current_tick,
                "price": price,
                "volatility": self.calculate_price_volatility()
            }
            
        except Exception as e:
            print(f"Error getting pool price: {e}")
            return None
    
    def calculate_price_volatility(self, periods: int = 10) -> float:
        """Calculate price volatility over recent periods"""
        try:
            if len(self.price_history) < periods:
                return 0.0
            
            recent_prices = [entry["price"] for entry in self.price_history[-periods:]]
            
            if len(recent_prices) < 2:
                return 0.0
            
            # Calculate percentage changes
            price_changes = []
            for i in range(1, len(recent_prices)):
                if recent_prices[i-1] > 0:
                    change = abs((recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1])
                    price_changes.append(change)
            
            if not price_changes:
                return 0.0
            
            # Calculate standard deviation
            avg_change = sum(price_changes) / len(price_changes)
            variance = sum((x - avg_change) ** 2 for x in price_changes) / len(price_changes)
            volatility = math.sqrt(variance)
            
            return volatility * 100  # Return as percentage
            
        except Exception as e:
            print(f"Error calculating volatility: {e}")
            return 0.0
    
    def calculate_dynamic_range(self, current_price: float, config) -> float:
        """Calculate dynamic price range with CELO optimizations"""
        try:
            if current_price <= 0 or not math.isfinite(current_price):
                print(f"Invalid current price: {current_price}")
                return config.price_range_percent
            
            base_range = config.price_range_percent
            
            if not config.dynamic_range:
                return base_range
            
            if config.range_calculation_method == "fixed":
                return base_range
            
            elif config.range_calculation_method == "volatility_based":
                volatility = self.calculate_price_volatility()
                
                if volatility > 0:
                    volatility_factor = min(volatility * config.volatility_multiplier, 5.0)
                    adjusted_range = base_range + volatility_factor
                else:
                    adjusted_range = base_range
                
                # Apply constraints
                adjusted_range = max(config.min_price_range_percent, adjusted_range)
                adjusted_range = min(config.max_price_range_percent, adjusted_range)
                
                return adjusted_range
            
            elif config.range_calculation_method == "adaptive":
                volatility = self.calculate_price_volatility()
                
                # Get recent price range
                if len(self.price_history) >= 5:
                    recent_prices = [entry["price"] for entry in self.price_history[-5:]]
                    price_min = min(recent_prices)
                    price_max = max(recent_prices)
                    
                    if price_min > 0:
                        recent_range = ((price_max - price_min) / current_price) * 100
                        adaptive_range = max(base_range, recent_range + config.range_buffer_percent)
                    else:
                        adaptive_range = base_range
                else:
                    adaptive_range = base_range
                
                # Add volatility component
                if volatility > 0:
                    adaptive_range += volatility * config.volatility_multiplier
                
                # Apply constraints
                adaptive_range = max(config.min_price_range_percent, adaptive_range)
                adaptive_range = min(config.max_price_range_percent, adaptive_range)
                
                return adaptive_range
            
            return base_range
            
        except Exception as e:
            print(f"Error calculating dynamic range: {e}")
            return config.price_range_percent
    
    def calculate_tick_range(self, current_price: float, range_percent: float, 
                           tick_spacing: int = 1) -> Tuple[Optional[int], Optional[int]]:
        """CELO-optimized tick range calculation"""
        try:
            if current_price <= 0 or not math.isfinite(current_price):
                print(f"Invalid price for tick calculation: {current_price}")
                return None, None
            
            if range_percent <= 0:
                print(f"Invalid range percent: {range_percent}")
                return None, None
            
            # Convert price to tick
            try:
                current_tick = int(math.log(current_price) / math.log(1.0001))
            except (ValueError, OverflowError) as e:
                print(f"Error converting price to tick: {e}")
                return None, None
            
            # Calculate range in ticks
            price_multiplier = 1 + (range_percent / 100)
            upper_price = current_price * price_multiplier
            lower_price = current_price / price_multiplier
            
            try:
                upper_tick = int(math.log(upper_price) / math.log(1.0001))
                lower_tick = int(math.log(lower_price) / math.log(1.0001))
            except (ValueError, OverflowError) as e:
                print(f"Error calculating tick bounds: {e}")
                return None, None
            
            # Round to valid tick spacing
            upper_tick = ((upper_tick // tick_spacing) + 1) * tick_spacing
            lower_tick = (lower_tick // tick_spacing) * tick_spacing
            
            # CELO-specific: Ensure minimum range for 0.01% pools
            if tick_spacing == 1:
                min_tick_range = 30  # Increased minimum for CELO
                if upper_tick - lower_tick < min_tick_range:
                    current_tick_rounded = (current_tick // tick_spacing) * tick_spacing
                    upper_tick = current_tick_rounded + (min_tick_range // 2)
                    lower_tick = current_tick_rounded - (min_tick_range // 2)
                    
                    # Ensure tick spacing compliance
                    upper_tick = ((upper_tick // tick_spacing) + 1) * tick_spacing
                    lower_tick = (lower_tick // tick_spacing) * tick_spacing
            else:
                # Ensure minimum range for other pools
                if upper_tick - lower_tick < 2 * tick_spacing:
                    current_tick_rounded = (current_tick // tick_spacing) * tick_spacing
                    upper_tick = current_tick_rounded + tick_spacing
                    lower_tick = current_tick_rounded - tick_spacing
            
            # Validate tick bounds
            MIN_TICK = -887272
            MAX_TICK = 887272
            
            if lower_tick < MIN_TICK or upper_tick > MAX_TICK:
                print(f"Tick range out of bounds: {lower_tick} to {upper_tick}")
                return None, None
            
            print(f"CELO tick range calculation:")
            print(f"  Current price: {current_price:.6f}")
            print(f"  Range percent: {range_percent:.2f}%")
            print(f"  Lower tick: {lower_tick} (price: {1.0001**lower_tick:.6f})")
            print(f"  Upper tick: {upper_tick} (price: {1.0001**upper_tick:.6f})")
            print(f"  Current tick: {current_tick}")
            
            return lower_tick, upper_tick
            
        except Exception as e:
            print(f"Error calculating tick range: {e}")
            return None, None
    
    def get_tick_spacing_for_fee(self, fee: int) -> int:
        """Get appropriate tick spacing for fee tier with CELO optimization"""
        tick_spacings = {
            100: 1,     # 0.01% - CELO minimum
            500: 10,    # 0.05%
            3000: 60,   # 0.3%
            10000: 200  # 1%
        }
        return tick_spacings.get(fee, 1)  # Default to 1 for CELO
    
    def create_position_with_config(self, token0: str, token1: str, fee: int,
                                  amount0: int, amount1: int, config) -> Optional[str]:
        """Create position using dynamic range calculation"""
        try:
            # Validate inputs
            if amount0 < 0 or amount1 < 0:
                print("Invalid token amounts")
                return None
            
            if amount0 == 0 and amount1 == 0:
                print("Both token amounts are zero")
                return None
            
            # Get current price
            pool_address = self.get_pool_address(token0, token1, fee)
            if not pool_address:
                print("Could not find pool address")
                return None
            
            price_info = self.get_pool_price(pool_address)
            if not price_info:
                print("Could not get current price")
                return None
            
            current_price = price_info["price"]
            
            # Calculate dynamic range
            range_percent = self.calculate_dynamic_range(current_price, config)
            print(f"Using dynamic range: {range_percent:.4f}%")
            
            # Get appropriate tick spacing
            tick_spacing = self.get_tick_spacing_for_fee(fee)
            
            # Calculate tick range
            tick_lower, tick_upper = self.calculate_tick_range(
                current_price, range_percent, tick_spacing
            )
            
            if tick_lower is None or tick_upper is None:
                print("Failed to calculate tick range")
                return None
            
            # Create position with calculated range
            return self.create_position(
                token0, token1, fee, amount0, amount1, tick_lower, tick_upper
            )
            
        except Exception as e:
            print(f"Error creating position with config: {e}")
            return None
    
    def create_position(self, token0: str, token1: str, fee: int, 
                       amount0: int, amount1: int, 
                       tick_lower: int, tick_upper: int) -> Optional[str]:
        """Create new liquidity position with CELO optimizations"""
        try:
            # Validate inputs
            if not self._validate_position_params(token0, token1, fee, amount0, amount1, tick_lower, tick_upper):
                return None
            
            # CELO optimization: Ensure proper token ordering
            token0_addr = Web3.to_checksum_address(token0)
            token1_addr = Web3.to_checksum_address(token1)
            
            if int(token0_addr, 16) > int(token1_addr, 16):
                token0_addr, token1_addr = token1_addr, token0_addr
                amount0, amount1 = amount1, amount0
            
            position_manager = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.position_manager),
                abi=self.position_manager_abi
            )
            
            # CELO-specific slippage calculation (higher tolerance)
            amount0_min = int(amount0 * (1 - self.CELO_SLIPPAGE))
            amount1_min = int(amount1 * (1 - self.CELO_SLIPPAGE))
            
            # Get deadline (longer for CELO)
            deadline = int(self.wallet.w3.eth.get_block('latest')['timestamp']) + 900  # 15 minutes
            
            # Build mint parameters
            mint_params = (
                token0_addr,
                token1_addr,
                fee,
                tick_lower,
                tick_upper,
                amount0,
                amount1,
                amount0_min,
                amount1_min,
                self.wallet.account.address,
                deadline
            )
            
            print(f"Creating CELO-optimized position:")
            print(f"  Token0: {token0_addr}, Amount: {amount0}")
            print(f"  Token1: {token1_addr}, Amount: {amount1}")
            print(f"  Fee: {fee}, Tick range: {tick_lower} to {tick_upper}")
            print(f"  Min amounts: {amount0_min}, {amount1_min} (CELO slippage: {self.CELO_SLIPPAGE*100}%)")
            
            # CELO-optimized gas calculation
            base_gas = 1200000  # Higher base gas for CELO
            final_gas = int(base_gas * self.CELO_GAS_MULTIPLIER)
            
            # Build transaction
            transaction = position_manager.functions.mint(mint_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': final_gas,
                'gasPrice': self.wallet._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            print(f"CELO gas optimization: {final_gas} gas limit")
            
            # Send transaction
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=600):  # 10 min timeout
                print(f"CELO position created successfully: {tx_hash}")
                
                # Get position token ID from transaction receipt
                token_id = self._get_token_id_from_mint_receipt(tx_hash)
                if token_id:
                    print(f"📝 Position NFT Token ID: {token_id}")
                    print(f"💡 Add to monitoring with: add {token_id}")
                
                return tx_hash
            else:
                print("Failed to create CELO position")
                return None
                
        except Exception as e:
            print(f"Error creating CELO position: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_token_id_from_mint_receipt(self, tx_hash: str) -> Optional[int]:
        """Extract NFT token ID from mint transaction receipt"""
        try:
            receipt = self.wallet.get_transaction_receipt(tx_hash)
            if not receipt:
                return None
            
            # Look for Transfer event from position manager (NFT mint)
            for log in receipt.get('logs', []):
                try:
                    # NFT Transfer event signature
                    transfer_signature = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                    
                    if (log.get('topics', [{}])[0].hex() == transfer_signature and
                        log['address'].lower() == self.network_config.position_manager.lower()):
                        
                        # Token ID is in the third topic
                        token_id_hex = log['topics'][3].hex()
                        token_id = int(token_id_hex, 16)
                        
                        print(f"Found position NFT token ID: {token_id}")
                        return token_id
                        
                except Exception as e:
                    continue
            
            print("Could not extract token ID from transaction receipt")
            return None
            
        except Exception as e:
            print(f"Error extracting token ID: {e}")
            return None
    
    def _validate_position_params(self, token0: str, token1: str, fee: int, 
                                amount0: int, amount1: int, 
                                tick_lower: int, tick_upper: int) -> bool:
        """Validate position creation parameters"""
        try:
            # Validate addresses
            Web3.to_checksum_address(token0)
            Web3.to_checksum_address(token1)
            
            # Validate fee tier
            valid_fees = [100, 500, 3000, 10000]
            if fee not in valid_fees:
                print(f"Invalid fee tier: {fee}. Valid fees: {valid_fees}")
                return False
            
            # Validate amounts
            if amount0 < 0 or amount1 < 0:
                print("Token amounts cannot be negative")
                return False
            
            if amount0 == 0 and amount1 == 0:
                print("At least one token amount must be greater than 0")
                return False
            
            # Validate tick range
            if tick_lower >= tick_upper:
                print("tick_lower must be less than tick_upper")
                return False
            
            MIN_TICK = -887272
            MAX_TICK = 887272
            
            if tick_lower < MIN_TICK or tick_upper > MAX_TICK:
                print(f"Tick range out of bounds: {tick_lower} to {tick_upper}")
                return False
            
            # Validate tick spacing
            tick_spacing = self.get_tick_spacing_for_fee(fee)
            if tick_lower % tick_spacing != 0 or tick_upper % tick_spacing != 0:
                print(f"Ticks must be multiples of {tick_spacing} for fee {fee}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating position parameters: {e}")
            return False
    
    def get_position_info(self, token_id: int) -> Optional[Dict]:
        """Get information about a specific position"""
        try:
            if token_id < 0:
                print("Invalid token ID")
                return None
            
            position_manager = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.position_manager),
                abi=self.position_manager_abi
            )
            
            position_data = position_manager.functions.positions(token_id).call()
            
            return {
                "token_id": token_id,
                "nonce": position_data[0],
                "operator": position_data[1],
                "token0": position_data[2],
                "token1": position_data[3],
                "fee": position_data[4],
                "tick_lower": position_data[5],
                "tick_upper": position_data[6],
                "liquidity": position_data[7],
                "fee_growth_inside0": position_data[8],
                "fee_growth_inside1": position_data[9],
                "tokens_owed0": position_data[10],
                "tokens_owed1": position_data[11]
            }
            
        except Exception as e:
            print(f"Error getting position info: {e}")
            return None
    
    def remove_position(self, token_id: int) -> bool:
        """Remove entire liquidity position"""
        try:
            # Get position info first
            position_info = self.get_position_info(token_id)
            if not position_info:
                print(f"Position {token_id} not found")
                return False
            
            liquidity = position_info["liquidity"]
            if liquidity == 0:
                print("Position already has zero liquidity")
                return True
            
            position_manager = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.position_manager),
                abi=self.position_manager_abi
            )
            
            # Get deadline
            deadline = int(self.wallet.w3.eth.get_block('latest')['timestamp']) + 600  # 10 minutes
            
            # Build decrease liquidity parameters
            decrease_params = (
                token_id,
                liquidity,
                0,  # amount0Min
                0,  # amount1Min
                deadline
            )
            
            print(f"Removing liquidity from position {token_id}")
            print(f"  Liquidity to remove: {liquidity}")
            
            # Build transaction with CELO optimizations
            transaction = position_manager.functions.decreaseLiquidity(decrease_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': int(600000 * self.CELO_GAS_MULTIPLIER),  # Higher gas for CELO
                'gasPrice': self.wallet._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            # Send transaction
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=300):
                print(f"Position removed successfully: {tx_hash}")
                
                # Also collect any owed tokens
                self._collect_position_fees(token_id)
                
                return True
            else:
                print("Failed to remove position")
                return False
                
        except Exception as e:
            print(f"Error removing position: {e}")
            return False
    
    def _collect_position_fees(self, token_id: int) -> bool:
        """Collect accumulated fees from position"""
        try:
            position_manager = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.position_manager),
                abi=self.position_manager_abi
            )
            
            # Collect all available tokens
            collect_params = (
                token_id,
                self.wallet.account.address,
                2**128 - 1,  # amount0Max
                2**128 - 1   # amount1Max
            )
            
            transaction = position_manager.functions.collect(collect_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': int(300000 * self.CELO_GAS_MULTIPLIER),
                'gasPrice': self.wallet._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=180):
                print(f"Fees collected successfully: {tx_hash}")
                return True
            else:
                print("Failed to collect fees")
                return False
                
        except Exception as e:
            print(f"Error collecting fees: {e}")
            return False
    
    def swap_tokens(self, token_in: str, token_out: str, amount_in: int, 
                   fee: int, min_amount_out: int = 0) -> Optional[str]:
        """Execute token swap with CELO optimizations"""
        try:
            # Validate inputs
            if not self._validate_swap_params(token_in, token_out, amount_in, fee):
                return None
            
            router = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(self.network_config.uniswap_v3_router),
                abi=self.router_abi
            )
            
            # Get deadline (longer for CELO)
            deadline = int(self.wallet.w3.eth.get_block('latest')['timestamp']) + 900  # 15 minutes
            
            # CELO optimization: If min_amount_out is 0, calculate with higher slippage
            if min_amount_out == 0:
                celo_slippage = 0.05  # 5% slippage for CELO swaps
                min_amount_out = int(amount_in * (1 - celo_slippage))
            
            # Build swap parameters
            swap_params = (
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                fee,
                self.wallet.account.address,
                deadline,
                amount_in,
                min_amount_out,
                0  # sqrtPriceLimitX96 (no limit)
            )
            
            print(f"CELO-optimized swap:")
            print(f"  Token in: {token_in}, Amount: {amount_in}")
            print(f"  Token out: {token_out}, Min amount: {min_amount_out}")
            print(f"  Fee: {fee}")
            
            # CELO-optimized gas calculation
            base_gas = 400000  # Higher base gas for CELO swaps
            final_gas = int(base_gas * self.CELO_GAS_MULTIPLIER)
            
            # Build transaction
            transaction = router.functions.exactInputSingle(swap_params).build_transaction({
                'from': self.wallet.account.address,
                'gas': final_gas,
                'gasPrice': self.wallet._get_celo_gas_price(),
                'nonce': self.wallet._get_next_nonce()
            })
            
            print(f"CELO gas optimization: {final_gas} gas limit")
            
            # Send transaction
            tx_hash = self.wallet.send_transaction(transaction)
            
            if tx_hash and self.wallet.wait_for_transaction(tx_hash, timeout=300):
                print(f"CELO swap completed successfully: {tx_hash}")
                return tx_hash
            else:
                print("CELO swap failed")
                return None
                
        except Exception as e:
            print(f"Error executing CELO swap: {e}")
            return None
    
    def _validate_swap_params(self, token_in: str, token_out: str, amount_in: int, fee: int) -> bool:
        """Validate swap parameters"""
        try:
            # Validate addresses
            Web3.to_checksum_address(token_in)
            Web3.to_checksum_address(token_out)
            
            # Check if tokens are different
            if token_in.lower() == token_out.lower():
                print("Cannot swap token to itself")
                return False
            
            # Validate amount
            if amount_in <= 0:
                print("Swap amount must be greater than 0")
                return False
            
            # Validate fee
            valid_fees = [100, 500, 3000, 10000]
            if fee not in valid_fees:
                print(f"Invalid fee tier: {fee}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating swap parameters: {e}")
            return False
    
    def is_position_in_range(self, token_id: int) -> Optional[Dict]:
        """Check if position is currently in range"""
        try:
            position_info = self.get_position_info(token_id)
            if not position_info:
                return None
            
            # Get pool address and current tick
            pool_address = self.get_pool_address(
                position_info["token0"], 
                position_info["token1"], 
                position_info["fee"]
            )
            
            if not pool_address:
                return None
            
            pool_price_info = self.get_pool_price(pool_address)
            if not pool_price_info:
                return None
            
            current_tick = pool_price_info["current_tick"]
            tick_lower = position_info["tick_lower"]
            tick_upper = position_info["tick_upper"]
            current_price = pool_price_info["price"]
            
            # Position is in range if current tick is between bounds
            in_range = tick_lower <= current_tick <= tick_upper
            
            # Calculate position metrics
            total_range = tick_upper - tick_lower
            
            if total_range > 0:
                distance_from_lower = current_tick - tick_lower
                distance_from_upper = tick_upper - current_tick
                
                position_ratio = min(distance_from_lower, distance_from_upper) / total_range
                
                # Calculate range utilization
                if in_range:
                    range_utilization = 1.0 - (2 * position_ratio)
                else:
                    range_utilization = 0.0
                
                # Calculate price deviation from range center
                range_center_tick = (tick_lower + tick_upper) / 2
                tick_deviation = abs(current_tick - range_center_tick) / (total_range / 2)
            else:
                position_ratio = 0.0
                range_utilization = 0.0
                tick_deviation = 0.0
            
            return {
                "in_range": in_range,
                "current_tick": current_tick,
                "tick_lower": tick_lower,
                "tick_upper": tick_upper,
                "position_ratio": position_ratio,
                "range_utilization": range_utilization,
                "tick_deviation": tick_deviation,
                "current_price": current_price,
                "lower_price": 1.0001 ** tick_lower,
                "upper_price": 1.0001 ** tick_upper,
                "volatility": pool_price_info.get("volatility", 0.0),
                "liquidity": position_info["liquidity"]
            }
            
        except Exception as e:
            print(f"Error checking position range: {e}")
            return None
    
    def get_pool_info(self, pool_address: str) -> Optional[Dict]:
        """Get comprehensive pool information"""
        try:
            pool_contract = self.wallet.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V3_POOL_ABI
            )
            
            # Get token addresses
            token0 = pool_contract.functions.token0().call()
            token1 = pool_contract.functions.token1().call()
            
            # Get token info
            token0_info = self.wallet.get_token_info(token0)
            token1_info = self.wallet.get_token_info(token1)
            
            # Get current price info
            price_info = self.get_pool_price(pool_address)
            
            return {
                "address": pool_address,
                "token0": token0_info,
                "token1": token1_info,
                "price_info": price_info
            }
            
        except Exception as e:
            print(f"Error getting pool info: {e}")
            return None