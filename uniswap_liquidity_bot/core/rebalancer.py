import time
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3

@dataclass
class RebalanceAction:
    """Represents a rebalancing action to be executed"""
    action_type: str  # 'close_position', 'swap_tokens', 'create_position', 'auto_balance'
    token_id: Optional[int] = None
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    amount: Optional[int] = None
    new_range: Optional[Tuple[int, int]] = None
    reason: str = ""
    priority: int = 1  # 1 = high, 2 = medium, 3 = low

class PositionRebalancer:
    """CELO-optimized position rebalancing system with automatic portfolio balancing"""
    
    def __init__(self, wallet_manager, uniswap_manager, price_monitor, config):
        self.wallet = wallet_manager
        self.uniswap = uniswap_manager
        self.price_monitor = price_monitor
        self.config = config
        
        # CELO-optimized parameters
        self.CELO_SLIPPAGE = 4.0  # Higher slippage for CELO stability
        self.CELO_GAS_MULTIPLIER = 1.8
        self.MAX_RETRIES = 3
        
        # Rebalancing parameters
        self.rebalance_threshold = config.rebalance_threshold / 100
        self.max_slippage = max(config.max_slippage / 100, self.CELO_SLIPPAGE / 100)
        self.price_range_percent = config.price_range_percent / 100
        
        # Track active positions
        self.active_positions = {}
        self.rebalance_history = []
        
        # Performance tracking
        self.position_metrics = {}
    
    def auto_balance_portfolio(self, target_ratio: float = 0.5) -> bool:
        """CELO-optimized portfolio balancing with enhanced error handling"""
        try:
            print("\n=== CELO-OPTIMIZED AUTO-BALANCING ===")
            
            # Get current balances
            token0_balance = self.wallet.get_balance(self.config.token0_address)
            token1_balance = self.wallet.get_balance(self.config.token1_address)
            gas_balance = self.wallet.get_balance()
            
            # Get token info
            token0_info = self.wallet.get_token_info(self.config.token0_address)
            token1_info = self.wallet.get_token_info(self.config.token1_address)
            
            print(f"Current balances:")
            print(f"  {token0_info['symbol']}: {token0_balance:.6f}")
            print(f"  {token1_info['symbol']}: {token1_balance:.6f}")
            print(f"  Gas: {gas_balance:.6f}")
            
            # Check gas balance
            if gas_balance < self.config.min_gas_balance:
                print(f"❌ Insufficient gas balance: {gas_balance} < {self.config.min_gas_balance}")
                return False
            
            # Get current price
            pool_address = self.uniswap.get_pool_address(
                self.config.token0_address,
                self.config.token1_address,
                self.config.pool_fee
            )
            
            if not pool_address:
                print("❌ Could not find pool for token pair")
                return False
            
            price_info = self.price_monitor.get_current_price(pool_address)
            if not price_info:
                print("❌ Could not get current price")
                return False
            
            current_price = price_info["price"]
            print(f"Current price: {current_price:.6f} {token0_info['symbol']}/{token1_info['symbol']}")
            
            # Calculate total portfolio value
            total_value_token1 = token1_balance + (token0_balance * current_price)
            
            if total_value_token1 == 0:
                print("❌ No token balances found")
                return False
            
            print(f"Total portfolio value: {total_value_token1:.6f} {token1_info['symbol']}")
            
            # Calculate target amounts
            target_token1_value = total_value_token1 * target_ratio
            target_token0_value = total_value_token1 * (1 - target_ratio)
            target_token0_amount = target_token0_value / current_price
            
            print(f"Target balances:")
            print(f"  {token0_info['symbol']}: {target_token0_amount:.6f}")
            print(f"  {token1_info['symbol']}: {target_token1_value:.6f}")
            
            # Calculate swap needed
            token0_diff = target_token0_amount - token0_balance
            token1_diff = target_token1_value - token1_balance
            
            print(f"Difference needed:")
            print(f"  {token0_info['symbol']}: {token0_diff:.6f}")
            print(f"  {token1_info['symbol']}: {token1_diff:.6f}")
            
            # Check if balancing is needed
            swap_threshold = 0.01  # Minimum $0.01 worth to swap
            
            if abs(token0_diff) < swap_threshold and abs(token1_diff) < swap_threshold:
                print("✅ Portfolio already balanced")
                return True
            
            # Execute CELO-optimized swap
            if token0_diff > 0:
                # Need more token0, swap token1 → token0
                swap_amount = abs(token1_diff) * 0.80  # Use 80% to account for higher slippage
                print(f"🔄 CELO-optimized swap: {swap_amount:.6f} {token1_info['symbol']} → {token0_info['symbol']}")
                
                return self._execute_celo_optimized_swap(
                    self.config.token1_address,
                    self.config.token0_address,
                    swap_amount,
                    f"Balance portfolio: swap {swap_amount:.6f} {token1_info['symbol']} to {token0_info['symbol']}"
                )
            else:
                # Need more token1, swap token0 → token1
                swap_amount = abs(token0_diff) * 0.80  # Use 80% to account for higher slippage
                print(f"🔄 CELO-optimized swap: {swap_amount:.6f} {token0_info['symbol']} → {token1_info['symbol']}")
                
                return self._execute_celo_optimized_swap(
                    self.config.token0_address,
                    self.config.token1_address,
                    swap_amount,
                    f"Balance portfolio: swap {swap_amount:.6f} {token0_info['symbol']} to {token1_info['symbol']}"
                )
                
        except Exception as e:
            print(f"❌ Error in CELO auto-balancing: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _execute_celo_optimized_swap(self, token_in: str, token_out: str, amount: float, reason: str) -> bool:
        """Execute CELO-optimized swap with multiple retries and progressive slippage"""
        try:
            print(f"\n🔧 CELO-OPTIMIZED SWAP EXECUTION")
            print(f"Reason: {reason}")
            
            # Get token info
            token_in_info = self.wallet.get_token_info(token_in)
            token_out_info = self.wallet.get_token_info(token_out)
            
            # Convert to wei
            amount_with_decimals = int(amount * (10 ** token_in_info["decimals"]))
            
            # Check balance
            current_balance = self.wallet.get_balance(token_in)
            if current_balance < amount:
                print(f"❌ Insufficient balance: {current_balance} < {amount}")
                return False
            
            print(f"Swapping: {amount:.6f} {token_in_info['symbol']} → {token_out_info['symbol']}")
            print(f"Amount in wei: {amount_with_decimals}")
            
            # Ensure approval with extra buffer
            if not self._ensure_router_approval(token_in, amount_with_decimals * 2):
                print(f"❌ Failed to approve {token_in_info['symbol']}")
                return False
            
            # Retry with progressive slippage
            for attempt in range(self.MAX_RETRIES):
                # Increase slippage with each attempt
                attempt_slippage = self.CELO_SLIPPAGE + (attempt * 2.0)  # +2% per attempt
                
                print(f"\nAttempt {attempt + 1}/{self.MAX_RETRIES} (Slippage: {attempt_slippage}%)")
                
                success = self._execute_swap_with_slippage(
                    token_in, token_out, amount_with_decimals, attempt_slippage, attempt
                )
                
                if success:
                    print(f"✅ CELO swap successful on attempt {attempt + 1}")
                    
                    # Wait for balance to update
                    time.sleep(5)
                    
                    # Show updated balances
                    new_token0_balance = self.wallet.get_balance(self.config.token0_address)
                    new_token1_balance = self.wallet.get_balance(self.config.token1_address)
                    
                    print(f"Updated balances:")
                    print(f"  USDC: {new_token0_balance:.6f}")
                    print(f"  USDT: {new_token1_balance:.6f}")
                    
                    return True
                else:
                    print(f"❌ Attempt {attempt + 1} failed")
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = 10 + (attempt * 5)  # Progressive wait time
                        print(f"⏳ Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
            
            print(f"❌ All {self.MAX_RETRIES} swap attempts failed")
            return False
            
        except Exception as e:
            print(f"❌ Error in CELO optimized swap: {e}")
            return False
    
    def _execute_swap_with_slippage(self, token_in: str, token_out: str, amount_wei: int, 
                                   slippage_percent: float, attempt: int) -> bool:
        """Execute single swap attempt with specified slippage"""
        try:
            # Calculate minimum amount out
            min_amount_out = int(amount_wei * (100 - slippage_percent) / 100)
            
            print(f"  Amount in: {amount_wei}")
            print(f"  Min amount out: {min_amount_out}")
            print(f"  Slippage: {slippage_percent}%")
            
            # Use the enhanced Uniswap manager for CELO-optimized swaps
            tx_hash = self.uniswap.swap_tokens(
                token_in,
                token_out,
                amount_wei,
                self.config.pool_fee,
                min_amount_out
            )
            
            if tx_hash:
                print(f"  ✅ Swap transaction successful: {tx_hash}")
                return True
            else:
                print(f"  ❌ Swap transaction failed")
                return False
                
        except Exception as e:
            print(f"  ❌ Swap execution error: {e}")
            return False
    
    def _ensure_router_approval(self, token_address: str, amount: int) -> bool:
        """Ensure token approval for router"""
        try:
            return self.wallet.approve_token(
                token_address,
                self.uniswap.network_config.uniswap_v3_router,
                amount
            )
        except Exception as e:
            print(f"Error ensuring router approval: {e}")
            return False
    
    def analyze_position_health(self, token_id: int) -> Optional[Dict]:
        """Analyze position health with enhanced metrics"""
        try:
            # Get position range status
            range_status = self.price_monitor.check_position_range_status(token_id)
            
            if not range_status:
                return None
            
            position_info = self.uniswap.get_position_info(token_id)
            if not position_info:
                return None
            
            # Calculate position value and efficiency
            liquidity = position_info["liquidity"]
            
            # Get current token balances
            token0_balance = self.wallet.get_balance(position_info["token0"])
            token1_balance = self.wallet.get_balance(position_info["token1"])
            
            # Enhanced rebalancing logic
            needs_rebalance = False
            rebalance_reason = ""
            rebalance_urgency = "LOW"
            
            if not range_status["in_range"]:
                needs_rebalance = True
                rebalance_reason = "Position completely out of range"
                rebalance_urgency = "HIGH"
            elif range_status["position_ratio"] < self.rebalance_threshold:
                needs_rebalance = True
                rebalance_reason = f"Position too close to edge (ratio: {range_status['position_ratio']:.2f})"
                rebalance_urgency = "MEDIUM"
            elif liquidity == 0:
                needs_rebalance = True
                rebalance_reason = "Position has zero liquidity"
                rebalance_urgency = "HIGH"
            elif range_status.get("range_utilization", 1.0) < 0.3:
                needs_rebalance = True
                rebalance_reason = "Range too wide, low fee efficiency"
                rebalance_urgency = "LOW"
            elif range_status.get("volatility", 0.0) > 5.0 and range_status["position_ratio"] < 0.3:
                needs_rebalance = True
                rebalance_reason = "High volatility detected, preemptive rebalancing"
                rebalance_urgency = "MEDIUM"
            
            # Calculate comprehensive health score
            health_score = self._calculate_enhanced_health_score(range_status, liquidity)
            
            # Track position metrics
            self.position_metrics[token_id] = {
                "last_health_score": health_score,
                "last_check_time": time.time(),
                "in_range_time": self.position_metrics.get(token_id, {}).get("in_range_time", 0),
                "total_rebalances": self.position_metrics.get(token_id, {}).get("total_rebalances", 0)
            }
            
            # Update in-range time
            if range_status["in_range"]:
                self.position_metrics[token_id]["in_range_time"] += self.config.check_interval
            
            return {
                "token_id": token_id,
                "needs_rebalance": needs_rebalance,
                "reason": rebalance_reason,
                "urgency": rebalance_urgency,
                "range_status": range_status,
                "position_info": position_info,
                "token0_balance": token0_balance,
                "token1_balance": token1_balance,
                "health_score": health_score,
                "position_metrics": self.position_metrics[token_id]
            }
            
        except Exception as e:
            print(f"Error analyzing position health: {e}")
            return None
    
    def create_rebalance_plan(self, position_analysis: Dict) -> List[RebalanceAction]:
        """Create a comprehensive rebalancing plan with auto-balancing"""
        actions = []
        
        try:
            token_id = position_analysis["token_id"]
            position_info = position_analysis["position_info"]
            range_status = position_analysis["range_status"]
            urgency = position_analysis["urgency"]
            
            # Determine priority based on urgency
            priority = 1 if urgency == "HIGH" else 2 if urgency == "MEDIUM" else 3
            
            # Step 1: Close existing position if it has liquidity
            if position_info["liquidity"] > 0:
                actions.append(RebalanceAction(
                    action_type="close_position",
                    token_id=token_id,
                    reason="Remove liquidity for rebalancing",
                    priority=priority
                ))
            
            # Step 2: Auto-balance portfolio before creating new position
            actions.append(RebalanceAction(
                action_type="auto_balance",
                reason="Auto-balance portfolio for optimal position creation",
                priority=priority
            ))
            
            # Step 3: Get current market conditions
            pool_address = self.uniswap.get_pool_address(
                position_info["token0"], 
                position_info["token1"], 
                position_info["fee"]
            )
            
            if not pool_address:
                return actions
            
            current_price_info = self.price_monitor.get_current_price(pool_address)
            if not current_price_info:
                return actions
            
            current_price = current_price_info["price"]
            
            # Step 4: Calculate new optimal range with CELO optimization
            new_range_percent = self.uniswap.calculate_dynamic_range(current_price, self.config)
            
            # Get appropriate tick spacing
            tick_spacing = self.uniswap.get_tick_spacing_for_fee(position_info["fee"])
            
            # Use CELO-optimized tick range calculation
            new_tick_lower, new_tick_upper = self.uniswap.calculate_tick_range(
                current_price, new_range_percent, tick_spacing
            )
            
            if new_tick_lower is None or new_tick_upper is None:
                return actions
            
            # Step 5: Create new position with optimal range
            actions.append(RebalanceAction(
                action_type="create_position",
                new_range=(new_tick_lower, new_tick_upper),
                reason=f"Create new CELO-optimized position with range {new_range_percent:.2f}% (ticks: {new_tick_lower} to {new_tick_upper})",
                priority=priority
            ))
            
            return actions
            
        except Exception as e:
            print(f"Error creating rebalance plan: {e}")
            return []
    
    def execute_rebalance_plan(self, actions: List[RebalanceAction]) -> bool:
        """Execute the rebalancing plan with CELO optimizations"""
        try:
            # Sort actions by priority
            actions.sort(key=lambda x: x.priority)
            
            print(f"\n=== EXECUTING CELO-OPTIMIZED REBALANCE PLAN ===")
            print(f"Total actions: {len(actions)}")
            
            for i, action in enumerate(actions):
                print(f"\nStep {i+1}/{len(actions)} (Priority {action.priority}): {action.action_type}")
                print(f"  Reason: {action.reason}")
                
                success = self._execute_single_action(action)
                
                if not success:
                    print(f"❌ Failed to execute action: {action.action_type}")
                    if action.priority == 1:  # High priority - stop on failure
                        return False
                    else:
                        print("⚠️ Continuing with remaining actions...")
                        continue
                
                # Wait between actions for transaction confirmation
                if i < len(actions) - 1:
                    print("⏳ Waiting for transaction confirmation...")
                    time.sleep(20)  # Longer wait for CELO
            
            print("✅ CELO-optimized rebalance plan executed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error executing rebalance plan: {e}")
            return False
    
    def _execute_single_action(self, action: RebalanceAction) -> bool:
        """Execute a single rebalancing action with CELO optimizations"""
        try:
            if action.action_type == "close_position":
                return self.uniswap.remove_position(action.token_id)
            
            elif action.action_type == "auto_balance":
                return self.auto_balance_portfolio(target_ratio=0.5)  # 50/50 balance
            
            elif action.action_type == "swap_tokens":
                # Check gas balance first
                gas_balance = self.wallet.get_balance()
                if gas_balance < self.config.min_gas_balance:
                    print(f"❌ Insufficient gas balance: {gas_balance} < {self.config.min_gas_balance}")
                    return False
                
                return self._execute_celo_optimized_swap(
                    action.token_in,
                    action.token_out,
                    action.amount,
                    action.reason
                )
            
            elif action.action_type == "create_position":
                return self._create_celo_optimized_position(action.new_range)
            
            return False
            
        except Exception as e:
            print(f"❌ Error executing single action: {e}")
            return False
    
    def _create_celo_optimized_position(self, tick_range: Tuple[int, int]) -> bool:
        """Create new position using current token balances with CELO optimizations"""
        try:
            tick_lower, tick_upper = tick_range
            
            print(f"\n🔧 CREATING CELO-OPTIMIZED POSITION")
            print(f"Tick range: {tick_lower} to {tick_upper}")
            
            # Check gas balance
            gas_balance = self.wallet.get_balance()
            if gas_balance < self.config.min_gas_balance:
                print(f"❌ Insufficient gas balance for position creation: {gas_balance}")
                return False
            
            # Get current balances
            token0_balance = self.wallet.get_balance(self.config.token0_address)
            token1_balance = self.wallet.get_balance(self.config.token1_address)
            
            if token0_balance == 0 and token1_balance == 0:
                print("❌ No token balances available for position creation")
                return False
            
            # Get token info for decimal conversion
            token0_info = self.wallet.get_token_info(self.config.token0_address)
            token1_info = self.wallet.get_token_info(self.config.token1_address)
            
            # Use 80% of available balances for CELO (more conservative)
            amount0 = int(token0_balance * 0.80 * (10 ** token0_info["decimals"]))
            amount1 = int(token1_balance * 0.80 * (10 ** token1_info["decimals"]))
            
            print(f"Creating position with:")
            print(f"  {token0_info['symbol']}: {token0_balance * 0.80:.6f}")
            print(f"  {token1_info['symbol']}: {token1_balance * 0.80:.6f}")
            
            # Ensure token approvals for position manager
            if amount0 > 0 and not self._ensure_position_approval(self.config.token0_address, amount0 * 2):
                return False
            if amount1 > 0 and not self._ensure_position_approval(self.config.token1_address, amount1 * 2):
                return False
            
            # Use the enhanced Uniswap manager for CELO-optimized position creation
            tx_hash = self.uniswap.create_position(
                self.config.token0_address,
                self.config.token1_address,
                self.config.pool_fee,
                amount0,
                amount1,
                tick_lower,
                tick_upper
            )
            
            if tx_hash:
                print(f"✅ CELO position created successfully: {tx_hash}")
                return True
            else:
                print(f"❌ CELO position creation failed")
                return False
            
        except Exception as e:
            print(f"❌ Error creating CELO optimized position: {e}")
            return False
    
    def _ensure_position_approval(self, token_address: str, amount: int) -> bool:
        """Ensure token is approved for position manager"""
        try:
            return self.wallet.approve_token(
                token_address,
                self.uniswap.network_config.position_manager,
                amount
            )
        except Exception as e:
            print(f"Error ensuring position approval: {e}")
            return False
    
    def _calculate_enhanced_health_score(self, range_status: Dict, liquidity: int) -> float:
        """Calculate enhanced position health score (0-100)"""
        try:
            if not range_status["in_range"]:
                return 0.0
            
            if liquidity == 0:
                return 0.0
            
            # Base score from position ratio
            position_ratio = range_status["position_ratio"]
            base_score = position_ratio * 100
            
            # Adjust for range utilization
            range_utilization = range_status.get("range_utilization", 0.5)
            utilization_bonus = range_utilization * 20
            
            # Adjust for volatility
            volatility = range_status.get("volatility", 0.0)
            if volatility > 3.0:
                volatility_penalty = min(volatility - 3.0, 10.0)
            else:
                volatility_penalty = 0
            
            # Final score
            final_score = base_score + utilization_bonus - volatility_penalty
            return max(0.0, min(100.0, final_score))
            
        except Exception as e:
            print(f"Error calculating health score: {e}")
            return 50.0
    
    def monitor_and_rebalance_position(self, token_id: int) -> bool:
        """Monitor position and execute rebalancing if needed"""
        try:
            # Analyze position health
            analysis = self.analyze_position_health(token_id)
            
            if not analysis:
                print(f"Could not analyze position {token_id}")
                return False
            
            health_score = analysis['health_score']
            urgency = analysis['urgency']
            
            print(f"Position {token_id} health: {health_score:.1f}/100 (Urgency: {urgency})")
            
            if not analysis["needs_rebalance"]:
                print(f"Position {token_id} is healthy, no rebalancing needed")
                return True
            
            print(f"Rebalancing needed for position {token_id}: {analysis['reason']}")
            
            # Create rebalancing plan
            plan = self.create_rebalance_plan(analysis)
            
            if not plan:
                print("Could not create rebalancing plan")
                return False
            
            # Execute plan with CELO optimizations
            success = self.execute_rebalance_plan(plan)
            
            # Update metrics
            if token_id in self.position_metrics:
                self.position_metrics[token_id]["total_rebalances"] += 1
            
            # Record rebalancing action
            self.rebalance_history.append({
                "timestamp": time.time(),
                "token_id": token_id,
                "reason": analysis["reason"],
                "urgency": urgency,
                "health_score_before": health_score,
                "success": success,
                "actions_count": len(plan)
            })
            
            # Keep only recent history (last 50 entries)
            if len(self.rebalance_history) > 50:
                self.rebalance_history = self.rebalance_history[-50:]
            
            return success
            
        except Exception as e:
            print(f"Error in monitor and rebalance: {e}")
            return False
    
    def get_rebalance_statistics(self) -> Dict:
        """Get comprehensive rebalancing statistics"""
        total_rebalances = len(self.rebalance_history)
        successful_rebalances = sum(1 for r in self.rebalance_history if r["success"])
        
        # Calculate average time between rebalances
        if len(self.rebalance_history) > 1:
            time_diffs = []
            for i in range(1, len(self.rebalance_history)):
                diff = self.rebalance_history[i]["timestamp"] - self.rebalance_history[i-1]["timestamp"]
                time_diffs.append(diff)
            avg_time_between = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        else:
            avg_time_between = 0
        
        # Calculate urgency distribution
        urgency_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in self.rebalance_history:
            urgency_counts[r.get("urgency", "LOW")] += 1
        
        return {
            "total_rebalances": total_rebalances,
            "successful_rebalances": successful_rebalances,
            "success_rate": successful_rebalances / total_rebalances if total_rebalances > 0 else 0,
            "avg_time_between_rebalances": avg_time_between,
            "urgency_distribution": urgency_counts,
            "recent_history": self.rebalance_history[-10:],
            "active_positions": len(self.active_positions),
            "position_metrics": self.position_metrics
        }
    
    def add_position_to_monitor(self, token_id: int):
        """Add position to monitoring list"""
        self.active_positions[token_id] = {
            "added_timestamp": time.time(),
            "last_check": 0,
            "rebalance_count": 0
        }
        
        # Initialize position metrics
        self.position_metrics[token_id] = {
            "last_health_score": 100.0,
            "last_check_time": time.time(),
            "in_range_time": 0,
            "total_rebalances": 0
        }
        
        print(f"Position {token_id} added to CELO-optimized monitoring")
    
    def remove_position_from_monitor(self, token_id: int):
        """Remove position from monitoring list"""
        if token_id in self.active_positions:
            del self.active_positions[token_id]
        
        if token_id in self.position_metrics:
            del self.position_metrics[token_id]
            
        print(f"Position {token_id} removed from monitoring")
    
    def get_position_performance(self, token_id: int) -> Dict:
        """Get detailed performance metrics for a position"""
        if token_id not in self.position_metrics:
            return {}
        
        metrics = self.position_metrics[token_id]
        total_time = time.time() - self.active_positions.get(token_id, {}).get("added_timestamp", time.time())
        
        return {
            "token_id": token_id,
            "total_monitoring_time": total_time,
            "in_range_time": metrics["in_range_time"],
            "in_range_percentage": metrics["in_range_time"] / total_time if total_time > 0 else 0,
            "total_rebalances": metrics["total_rebalances"],
            "last_health_score": metrics["last_health_score"],
            "rebalance_frequency": metrics["total_rebalances"] / (total_time / 3600) if total_time > 0 else 0
        }