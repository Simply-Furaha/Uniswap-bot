import time
import signal
import sys
import threading
from typing import Dict, List
import json
import os

# Import our modules
from config.settings import ConfigManager, BotConfig
from config.networks import NetworkManager
from core.wallet import WalletManager
from core.uniswap import UniswapV3Manager
from core.price_monitor import PriceMonitor
from core.rebalancer import PositionRebalancer
from utils.logger import setup_logger

class UniswapLiquidityBot:
    """Main bot controller with enhanced auto-swap functionality"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = None
        self.network_manager = None
        self.wallet_manager = None
        self.uniswap_manager = None
        self.price_monitor = None
        self.rebalancer = None
        
        self.running = False
        self.positions_file = "data/positions.json"
        self.active_positions = []
        
        # Setup logging
        self.logger = setup_logger()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self) -> bool:
        """Initialize all bot components"""
        try:
            print("Initializing Uniswap Liquidity Bot...")
            
            # Load configuration
            self.config = self.config_manager.load_config()
            
            if not self.config_manager.validate_config():
                print("Configuration validation failed!")
                self._show_setup_instructions()
                return False
            
            # Initialize network manager
            self.network_manager = NetworkManager(self.config.network)
            network_info = self.network_manager.get_network_info()
            print(f"Network: {network_info['name']} (Chain ID: {network_info['chain_id']})")
            
            # Initialize wallet manager
            self.wallet_manager = WalletManager(
                self.config.private_key,
                self.network_manager
            )
            
            if not self.wallet_manager.is_connected():
                print("Failed to connect wallet!")
                return False
            
            # Initialize Uniswap manager
            self.uniswap_manager = UniswapV3Manager(
                self.wallet_manager,
                self.network_manager
            )
            
            # Initialize price monitor
            self.price_monitor = PriceMonitor(
                self.uniswap_manager,
                self.config.check_interval
            )
            
            # Initialize rebalancer with auto-swap capability
            self.rebalancer = PositionRebalancer(
                self.wallet_manager,
                self.uniswap_manager,
                self.price_monitor,
                self.config
            )
            
            # Load existing positions
            self._load_positions()
            
            # Show configuration summary
            self._show_config_summary()
            
            print("Bot initialized successfully!")
            return True
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start(self):
        """Start the bot"""
        if not self.running:
            self.running = True
            print("Starting Uniswap Liquidity Bot...")
            
            # Start price monitoring
            self.price_monitor.start_monitoring()
            
            # Start main bot loop
            bot_thread = threading.Thread(target=self._main_loop, daemon=True)
            bot_thread.start()
            
            # Start user interface
            self._start_user_interface()
    
    def stop(self):
        """Stop the bot gracefully"""
        print("Stopping bot...")
        self.running = False
        
        if self.price_monitor:
            self.price_monitor.stop_monitoring()
        
        self._save_positions()
        print("Bot stopped successfully!")
    
    def _main_loop(self):
        """Main bot execution loop with enhanced monitoring"""
        while self.running:
            try:
                # Check all monitored positions
                for position_data in self.active_positions:
                    token_id = position_data["token_id"]
                    
                    try:
                        # Monitor and rebalance if needed (includes auto-swapping)
                        success = self.rebalancer.monitor_and_rebalance_position(token_id)
                        
                        # Update position data
                        position_data["last_check"] = time.time()
                        if success:
                            position_data["last_rebalance"] = time.time()
                            position_data["rebalance_count"] = position_data.get("rebalance_count", 0) + 1
                        
                    except Exception as e:
                        print(f"Error monitoring position {token_id}: {e}")
                
                # Save positions periodically
                self._save_positions()
                
                # Show periodic status update
                if len(self.active_positions) > 0:
                    self._show_monitoring_update()
                
                # Wait before next cycle
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(self.config.check_interval)
    
    def create_initial_position(self) -> bool:
        """Create initial liquidity position with automatic token balancing and NFT ID capture"""
        try:
            print("\n" + "="*60)
            print("CREATING INITIAL LIQUIDITY POSITION WITH AUTO-SWAP")
            print("="*60)
            
            # Check token balances
            token0_balance = self.wallet_manager.get_balance(self.config.token0_address)
            token1_balance = self.wallet_manager.get_balance(self.config.token1_address)
            gas_balance = self.wallet_manager.get_balance()
            
            # Get token info
            token0_info = self.wallet_manager.get_token_info(self.config.token0_address)
            token1_info = self.wallet_manager.get_token_info(self.config.token1_address)
            
            print(f"Current balances:")
            print(f"  Gas: {gas_balance:.4f}")
            print(f"  {token0_info['symbol']}: {token0_balance:.6f}")
            print(f"  {token1_info['symbol']}: {token1_balance:.6f}")
            
            if gas_balance < self.config.min_gas_balance:
                print(f"❌ Insufficient gas balance! Need at least {self.config.min_gas_balance}")
                return False
            
            # Check if we have any tokens at all
            if token0_balance == 0 and token1_balance == 0:
                print("❌ No token balances found. Please fund your wallet first.")
                return False
            
            # Auto-balance portfolio if we have uneven distribution
            print(f"\n🔄 STEP 1: AUTO-BALANCING PORTFOLIO")
            balance_success = self.rebalancer.auto_balance_portfolio(target_ratio=0.5)
            
            if not balance_success:
                print("⚠️ Auto-balancing failed, proceeding with current balances...")
            else:
                print("✅ Portfolio auto-balanced successfully!")
                
                # Refresh balances after auto-balancing
                token0_balance = self.wallet_manager.get_balance(self.config.token0_address)
                token1_balance = self.wallet_manager.get_balance(self.config.token1_address)
                
                print(f"Updated balances after auto-balancing:")
                print(f"  {token0_info['symbol']}: {token0_balance:.6f}")
                print(f"  {token1_info['symbol']}: {token1_balance:.6f}")
            
            print(f"\n📊 STEP 2: CALCULATING OPTIMAL RANGE")
            
            # Get current price for range calculation
            pool_address = self.uniswap_manager.get_pool_address(
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
            volatility = price_info.get("volatility", 0.0)
            print(f"Current price: {current_price:.6f}")
            print(f"Market volatility: {volatility:.2f}%")
            
            # Calculate dynamic range
            range_percent = self.uniswap_manager.calculate_dynamic_range(current_price, self.config)
            print(f"Using range: {range_percent:.4f}% (optimized for CELO 0.01% fee tier)")
            
            # Get appropriate tick spacing for CELO
            tick_spacing = self.uniswap_manager.get_tick_spacing_for_fee(self.config.pool_fee)
            
            # Calculate tick range with CELO-specific handling
            tick_lower, tick_upper = self.uniswap_manager.calculate_tick_range(
                current_price, range_percent, tick_spacing
            )
            
            if tick_lower is None or tick_upper is None:
                print("❌ Failed to calculate tick range")
                return False
            
            print(f"\n🎯 STEP 3: CREATING POSITION")
            
            # Use available balances (with 90% buffer for gas and slippage)
            amount0 = int(token0_balance * 0.90 * (10 ** token0_info["decimals"]))
            amount1 = int(token1_balance * 0.90 * (10 ** token1_info["decimals"]))
            
            print(f"Position details:")
            print(f"  {token0_info['symbol']} amount: {token0_balance * 0.90:.6f}")
            print(f"  {token1_info['symbol']} amount: {token1_balance * 0.90:.6f}")
            print(f"  Price range: {1.0001**tick_lower:.6f} - {1.0001**tick_upper:.6f}")
            print(f"  Tick range: {tick_lower} to {tick_upper}")
            print(f"  Fee tier: {self.config.pool_fee/10000}%")
            print(f"  Tick spacing: {tick_spacing} (CELO optimized)")
            
            # Approve tokens for position manager
            print(f"\n🔐 STEP 4: APPROVING TOKENS")
            if amount0 > 0:
                print(f"Approving {token0_info['symbol']}...")
                if not self.wallet_manager.approve_token(
                    self.config.token0_address,
                    self.network_manager.get_network_config().position_manager,
                    amount0
                ):
                    print(f"❌ Failed to approve {token0_info['symbol']}")
                    return False
            
            if amount1 > 0:
                print(f"Approving {token1_info['symbol']}...")
                if not self.wallet_manager.approve_token(
                    self.config.token1_address,
                    self.network_manager.get_network_config().position_manager,
                    amount1
                ):
                    print(f"❌ Failed to approve {token1_info['symbol']}")
                    return False
            
            # Create position
            print(f"\n🚀 STEP 5: MINTING POSITION")
            tx_hash = self.uniswap_manager.create_position(
                self.config.token0_address,
                self.config.token1_address,
                self.config.pool_fee,
                amount0,
                amount1,
                tick_lower,
                tick_upper
            )
            
            if tx_hash:
                print(f"\n✅ POSITION CREATED SUCCESSFULLY!")
                print(f"📝 Transaction hash: {tx_hash}")
                print(f"🔗 View on explorer: {self.network_manager.get_network_config().explorer_url}/tx/{tx_hash}")
                
                # ENHANCED: Try to get token ID from transaction receipt
                print(f"\n🔍 STEP 6: RETRIEVING POSITION NFT TOKEN ID")
                time.sleep(5)  # Wait for transaction to be processed
                
                token_id = self.uniswap_manager._get_token_id_from_mint_receipt(tx_hash)
                
                if token_id:
                    print(f"🎯 Position NFT Token ID: {token_id}")
                    print(f"📋 AUTOMATICALLY ADDING TO MONITORING...")
                    
                    # Automatically add to monitoring
                    success = self.add_position(token_id)
                    if success:
                        print(f"✅ Position {token_id} automatically added to monitoring!")
                    else:
                        print(f"⚠️ Failed to add position to monitoring. Add manually: add {token_id}")
                else:
                    print(f"⚠️ Could not extract token ID from transaction")
                    print(f"📋 Please check the transaction and add manually: add <token_id>")
                
                print(f"\n📋 NEXT STEPS:")
                print(f"1. Monitor your position with: status")
                print(f"2. Check position health regularly")
                print(f"3. The bot will auto-rebalance when needed")
                print("="*60)
                return True
            else:
                print("❌ Failed to create position")
                return False
                
        except Exception as e:
            print(f"❌ Error creating initial position: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def balance_portfolio(self) -> bool:
        """Manual portfolio balancing command"""
        try:
            print("\n" + "="*50)
            print("MANUAL PORTFOLIO BALANCING")
            print("="*50)
            
            success = self.rebalancer.auto_balance_portfolio(target_ratio=0.5)
            
            if success:
                print("✅ Portfolio balanced successfully!")
            else:
                print("❌ Portfolio balancing failed")
            
            print("="*50)
            return success
            
        except Exception as e:
            print(f"❌ Error in manual balancing: {e}")
            return False
    
    def add_position(self, token_id: int) -> bool:
        """Add existing position to monitoring"""
        try:
            # Verify position exists
            position_info = self.uniswap_manager.get_position_info(token_id)
            
            if not position_info:
                print(f"❌ Position {token_id} not found or not owned by this wallet")
                return False
            
            # Check if already monitoring
            for pos in self.active_positions:
                if pos["token_id"] == token_id:
                    print(f"⚠️ Position {token_id} is already being monitored")
                    return True
            
            # Get position details
            token0_info = self.wallet_manager.get_token_info(position_info["token0"])
            token1_info = self.wallet_manager.get_token_info(position_info["token1"])
            
            print(f"✅ Position {token_id} details:")
            print(f"  Token pair: {token0_info['symbol']}/{token1_info['symbol']}")
            print(f"  Fee tier: {position_info['fee']/10000}%")
            print(f"  Tick range: {position_info['tick_lower']} to {position_info['tick_upper']}")
            print(f"  Liquidity: {position_info['liquidity']}")
            
            # Add to monitoring
            position_data = {
                "token_id": token_id,
                "added_timestamp": time.time(),
                "last_check": 0,
                "last_rebalance": 0,
                "rebalance_count": 0,
                "token0_symbol": token0_info['symbol'],
                "token1_symbol": token1_info['symbol']
            }
            
            self.active_positions.append(position_data)
            self.rebalancer.add_position_to_monitor(token_id)
            
            # Check initial health
            analysis = self.rebalancer.analyze_position_health(token_id)
            if analysis:
                print(f"📊 Initial health score: {analysis['health_score']:.1f}/100")
                if analysis['needs_rebalance']:
                    print(f"⚠️ Warning: Position needs rebalancing - {analysis['reason']}")
            
            print(f"🎯 Position {token_id} added to monitoring with auto-rebalancing")
            self._save_positions()
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding position: {e}")
            return False
    
    def remove_position(self, token_id: int) -> bool:
        """Remove position from monitoring"""
        try:
            self.active_positions = [
                pos for pos in self.active_positions 
                if pos["token_id"] != token_id
            ]
            
            self.rebalancer.remove_position_from_monitor(token_id)
            self._save_positions()
            
            print(f"✅ Position {token_id} removed from monitoring")
            return True
            
        except Exception as e:
            print(f"❌ Error removing position: {e}")
            return False
    
    def show_status(self):
        """Display comprehensive bot status with auto-swap info"""
        print("\n" + "="*70)
        print("🤖 UNISWAP LIQUIDITY BOT STATUS (CELO + AUTO-SWAP)")
        print("="*70)
        
        # Network and wallet info
        network_info = self.network_manager.get_network_info()
        print(f"🌐 Network: {network_info['name']} (Chain ID: {network_info['chain_id']})")
        print(f"👛 Wallet: {self.wallet_manager.account.address}")
        
        # Balances
        gas_balance = self.wallet_manager.get_balance()
        token0_balance = self.wallet_manager.get_balance(self.config.token0_address)
        token1_balance = self.wallet_manager.get_balance(self.config.token1_address)
        
        token0_info = self.wallet_manager.get_token_info(self.config.token0_address)
        token1_info = self.wallet_manager.get_token_info(self.config.token1_address)
        
        print(f"\n💰 WALLET BALANCES:")
        print(f"Gas: {gas_balance:.6f} {network_info.get('native_token', 'CELO')}")
        print(f"{token0_info['symbol']}: {token0_balance:.6f}")
        print(f"{token1_info['symbol']}: {token1_balance:.6f}")
        
        # Calculate portfolio balance
        if token0_balance > 0 or token1_balance > 0:
            try:
                pool_address = self.uniswap_manager.get_pool_address(
                    self.config.token0_address,
                    self.config.token1_address,
                    self.config.pool_fee
                )
                price_info = self.price_monitor.get_current_price(pool_address)
                if price_info:
                    current_price = price_info["price"]
                    total_value = token1_balance + (token0_balance * current_price)
                    token0_percent = (token0_balance * current_price) / total_value * 100 if total_value > 0 else 0
                    token1_percent = token1_balance / total_value * 100 if total_value > 0 else 0
                    
                    print(f"\n📊 PORTFOLIO DISTRIBUTION:")
                    print(f"{token0_info['symbol']}: {token0_percent:.1f}% (${token0_balance * current_price:.2f})")
                    print(f"{token1_info['symbol']}: {token1_percent:.1f}% (${token1_balance:.2f})")
                    print(f"Total Value: ${total_value:.2f}")
                    
                    # Show balance recommendation
                    if abs(token0_percent - 50) > 20:
                        print(f"💡 Portfolio unbalanced! Use 'balance' command to auto-balance")
            except:
                pass
        
        if gas_balance < self.config.min_gas_balance:
            print(f"⚠️  Warning: Low gas balance! Minimum required: {self.config.min_gas_balance}")
        
        # Configuration info with CELO specifics
        range_info = self.config_manager.get_range_info()
        print(f"\n⚙️ RANGE CONFIGURATION (CELO OPTIMIZED):")
        print(f"Method: {range_info['calculation_method']}")
        print(f"Base range: {range_info['current_range_percent']:.4f}%")
        print(f"Min/Max range: {range_info['min_range_percent']:.4f}% - {range_info['max_range_percent']:.1f}%")
        print(f"Dynamic range: {'Enabled' if range_info['dynamic_range_enabled'] else 'Disabled'}")
        print(f"Fee tier: {self.config.pool_fee/10000}% (Ultra-low for CELO)")
        print(f"Tick spacing: {self.uniswap_manager.get_tick_spacing_for_fee(self.config.pool_fee)}")
        
        # Monitored positions
        print(f"\n📍 MONITORED POSITIONS: {len(self.active_positions)}")
        if len(self.active_positions) == 0:
            print("  No positions being monitored")
            print("  💡 Use 'create' to create a new position with auto-balancing")
        else:
            for pos in self.active_positions:
                token_id = pos["token_id"]
                analysis = self.rebalancer.analyze_position_health(token_id)
                
                if analysis:
                    status = "HEALTHY" if not analysis["needs_rebalance"] else f"NEEDS REBALANCE ({analysis['urgency']})"
                    health_score = analysis["health_score"]
                    range_status = analysis["range_status"]
                    
                    print(f"  📌 Position {token_id} ({pos.get('token0_symbol', '?')}/{pos.get('token1_symbol', '?')}):")
                    print(f"    Status: {status}")
                    print(f"    Health: {health_score:.1f}/100")
                    print(f"    In range: {'Yes' if range_status['in_range'] else 'No'}")
                    if not range_status['in_range']:
                        print(f"    Current price: {range_status['current_price']:.6f}")
                        print(f"    Range: {range_status['lower_price']:.6f} - {range_status['upper_price']:.6f}")
                    
                    # Show performance metrics
                    performance = self.rebalancer.get_position_performance(token_id)
                    if performance:
                        print(f"    In-range time: {performance['in_range_percentage']:.1%}")
                        print(f"    Total rebalances: {performance['total_rebalances']}")
                else:
                    print(f"  📌 Position {token_id}: ERROR - Could not analyze")
        
        # Rebalancing statistics
        stats = self.rebalancer.get_rebalance_statistics()
        print(f"\n📈 REBALANCING STATISTICS:")
        print(f"Total rebalances: {stats['total_rebalances']}")
        print(f"Success rate: {stats['success_rate']:.1%}")
        if stats['avg_time_between_rebalances'] > 0:
            print(f"Avg time between rebalances: {stats['avg_time_between_rebalances']/3600:.1f} hours")
        
        urgency_dist = stats['urgency_distribution']
        print(f"Urgency distribution: High: {urgency_dist['HIGH']}, Medium: {urgency_dist['MEDIUM']}, Low: {urgency_dist['LOW']}")
        
        # Bot status
        monitor_status = self.price_monitor.get_monitoring_status()
        print(f"\n🤖 BOT STATUS:")
        print(f"Running: {self.running}")
        print(f"Price monitoring: {monitor_status['monitoring']}")
        print(f"Check interval: {self.config.check_interval}s")
        print(f"Active alerts: {monitor_status['active_alerts']}")
        print(f"Auto-swap: Enabled ✅")
        print(f"CELO Network: Optimized ✅")
        
        print("="*70)
    
    def _start_user_interface(self):
        """Enhanced command-line interface with auto-swap commands"""
        print("\nBot is running! Available commands:")
        print("status - Show comprehensive bot status")
        print("create - Create initial position (with auto-balancing)")
        print("balance - Manually balance portfolio (50/50)")
        print("add <token_id> - Add position to monitoring")
        print("remove <token_id> - Remove position from monitoring")
        print("range - Show range configuration")
        print("set_range <percent> - Set base range percentage")
        print("set_method <method> - Set range calculation method")
        print("stats - Show rebalancing statistics")
        print("stop - Stop the bot")
        print("help - Show this help")
        
        while self.running:
            try:
                command = input("\n> ").strip().lower()
                
                if command == "status":
                    self.show_status()
                elif command == "create":
                    self.create_initial_position()
                elif command == "balance":
                    self.balance_portfolio()
                elif command.startswith("add "):
                    try:
                        token_id = int(command.split()[1])
                        self.add_position(token_id)
                    except (IndexError, ValueError):
                        print("Usage: add <token_id>")
                elif command.startswith("remove "):
                    try:
                        token_id = int(command.split()[1])
                        self.remove_position(token_id)
                    except (IndexError, ValueError):
                        print("Usage: remove <token_id>")
                elif command == "range":
                    self.show_range_config()
                elif command.startswith("set_range "):
                    try:
                        percent = float(command.split()[1])
                        self.update_range_config(price_range_percent=percent)
                    except (IndexError, ValueError):
                        print("Usage: set_range <percent>")
                elif command.startswith("set_method "):
                    try:
                        method = command.split()[1]
                        if method in ["fixed", "adaptive", "volatility_based"]:
                            self.update_range_config(range_calculation_method=method)
                        else:
                            print("Valid methods: fixed, adaptive, volatility_based")
                    except IndexError:
                        print("Usage: set_method <method>")
                elif command == "stats":
                    stats = self.rebalancer.get_rebalance_statistics()
                    print(f"\nRebalancing Statistics:")
                    print(json.dumps(stats, indent=2, default=str))
                elif command == "stop":
                    self.stop()
                    break
                elif command == "help":
                    print("Available commands:")
                    print("status - Show comprehensive bot status")
                    print("create - Create initial position (with auto-balancing)")
                    print("balance - Manually balance portfolio (50/50)")
                    print("add <token_id> - Add position to monitoring")
                    print("remove <token_id> - Remove position from monitoring")
                    print("range - Show range configuration")
                    print("set_range <percent> - Set base range percentage")
                    print("set_method <method> - Set calculation method")
                    print("stats - Show rebalancing statistics")
                    print("stop - Stop the bot")
                elif command:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                print(f"Error processing command: {e}")
    
    def show_range_config(self):
        """Show current range configuration"""
        range_info = self.config_manager.get_range_info()
        
        print("\n" + "="*50)
        print("RANGE CONFIGURATION")
        print("="*50)
        print(f"Calculation method: {range_info['calculation_method']}")
        print(f"Base range: {range_info['current_range_percent']:.4f}%")
        print(f"Minimum range: {range_info['min_range_percent']:.4f}%")
        print(f"Maximum range: {range_info['max_range_percent']:.1f}%")
        print(f"Dynamic range: {'Enabled' if range_info['dynamic_range_enabled'] else 'Disabled'}")
        print(f"Volatility multiplier: {range_info['volatility_multiplier']:.1f}x")
        print(f"Range buffer: {range_info['range_buffer']}%")
        print(f"Rebalance threshold: {self.config.rebalance_threshold}%")
        print("="*50)
    
    def update_range_config(self, **kwargs):
        """Update range configuration"""
        valid_params = {
            'price_range_percent', 'min_price_range_percent', 'max_price_range_percent',
            'dynamic_range', 'volatility_multiplier', 'range_calculation_method',
            'range_buffer_percent', 'rebalance_threshold'
        }
        
        updates = {k: v for k, v in kwargs.items() if k in valid_params}
        
        if updates:
            self.config_manager.update_config(updates)
            self.config = self.config_manager.load_config()
            print(f"✅ Updated configuration: {updates}")
        else:
            print("❌ No valid parameters to update")
    
    def _show_config_summary(self):
        """Show configuration summary"""
        print(f"\nConfiguration Summary:")
        print(f"  Budget: ${self.config.budget_usd}")
        print(f"  Range method: {self.config.range_calculation_method}")
        print(f"  Base range: {self.config.price_range_percent}%")
        print(f"  Rebalance threshold: {self.config.rebalance_threshold}%")
        print(f"  Check interval: {self.config.check_interval}s")
        print(f"  Max slippage: {self.config.max_slippage}%")
        print(f"  Auto-swap: Enabled ✅")
        print(f"  CELO Network: Optimized for ultra-low fees ✅")
    
    def _show_monitoring_update(self):
        """Show brief monitoring update"""
        healthy_positions = 0
        needs_attention = 0
        
        for pos in self.active_positions:
            analysis = self.rebalancer.analyze_position_health(pos["token_id"])
            if analysis:
                if not analysis["needs_rebalance"]:
                    healthy_positions += 1
                else:
                    needs_attention += 1
        
        if needs_attention > 0:
            print(f"📊 Monitor update: {healthy_positions} healthy, {needs_attention} need attention")
    
    def _load_positions(self):
        """Load positions from file"""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, 'r') as f:
                    self.active_positions = json.load(f)
                
                print(f"Loaded {len(self.active_positions)} positions from file")
                
                # Add positions to rebalancer monitoring
                for pos in self.active_positions:
                    self.rebalancer.add_position_to_monitor(pos["token_id"])
            
        except Exception as e:
            print(f"Error loading positions: {e}")
            self.active_positions = []
    
    def _save_positions(self):
        """Save positions to file"""
        try:
            os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
            
            with open(self.positions_file, 'w') as f:
                json.dump(self.active_positions, f, indent=2)
                
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def _show_setup_instructions(self):
        """Show setup instructions for first-time users"""
        print("\n" + "="*60)
        print("SETUP REQUIRED")
        print("="*60)
        print("Please configure the bot by editing data/config.json")
        print("\nRequired fields:")
        print("- rpc_url: Your RPC endpoint URL")
        print("- private_key: Your wallet private key")
        print("- token0_address: First token address")
        print("- token1_address: Second token address")
        print("\nExample configuration:")
        
        sample_config = self.config_manager.get_sample_config()
        print(json.dumps(sample_config, indent=2))
        
        print("\n⚠️  SECURITY WARNING:")
        print("   Never share your private key!")
        print("   Use a dedicated wallet for testing!")
        print("="*60)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

def main():
    """Main entry point"""
    bot = UniswapLiquidityBot()
    
    if bot.initialize():
        bot.start()
    else:
        print("Failed to initialize bot")
        sys.exit(1)

if __name__ == "__main__":
    main()