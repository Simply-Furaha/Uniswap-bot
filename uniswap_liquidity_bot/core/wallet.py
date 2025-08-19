from web3 import Web3
from eth_account import Account
import time
from typing import Optional, Dict, Any
from config.networks import NetworkManager, ERC20_ABI

class WalletManager:
    """Manages wallet connection and transactions with improved error handling"""
    
    def __init__(self, private_key: str, network_manager: NetworkManager):
        self.private_key = private_key
        self.network_manager = network_manager
        self.w3 = None
        self.account = None
        self.connected = False
        self.last_nonce = None  # Track nonce to prevent conflicts
        
        self._connect()
    
    def _connect(self):
        """Establish connection to blockchain network"""
        try:
            network_config = self.network_manager.get_network_config()
            
            # Initialize Web3 connection
            self.w3 = Web3(Web3.HTTPProvider(network_config.rpc_url))
            
            # Setup account from private key
            self.account = Account.from_key(self.private_key)
            
            # Verify connection
            if self.w3.is_connected():
                self.connected = True
                # Reset nonce tracking on connection
                self.last_nonce = None
                print(f"Connected to {network_config.name}")
                print(f"Wallet address: {self.account.address}")
            else:
                raise ConnectionError("Failed to connect to network")
                
        except Exception as e:
            print(f"Wallet connection error: {e}")
            self.connected = False
    
    def get_balance(self, token_address: str = None) -> float:
        """Get balance of native token or ERC20 token"""
        if not self.connected:
            return 0.0
        
        try:
            if token_address is None:
                # Get native token balance (ETH, MATIC, CELO, etc.)
                balance_wei = self.w3.eth.get_balance(self.account.address)
                return self.w3.from_wei(balance_wei, 'ether')
            else:
                # Get ERC20 token balance
                contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                
                balance = contract.functions.balanceOf(self.account.address).call()
                decimals = contract.functions.decimals().call()
                
                return balance / (10 ** decimals)
                
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0
    
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get token information (symbol, decimals)"""
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            name = contract.functions.name().call()
            
            return {
                "address": token_address,
                "symbol": symbol,
                "decimals": decimals,
                "name": name
            }
            
        except Exception as e:
            print(f"Error getting token info: {e}")
            return {"address": token_address, "symbol": "UNKNOWN", "decimals": 18, "name": "Unknown Token"}
    
    def _get_next_nonce(self) -> int:
        """Get next available nonce with conflict resolution"""
        try:
            # Get current nonce from network (pending to include any pending transactions)
            current_nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            
            # If we have a tracked nonce, use the higher value
            if self.last_nonce is not None:
                next_nonce = max(current_nonce, self.last_nonce + 1)
            else:
                next_nonce = current_nonce
            
            # Update our tracked nonce
            self.last_nonce = next_nonce
            
            print(f"Using nonce: {next_nonce} (network: {current_nonce})")
            return next_nonce
            
        except Exception as e:
            print(f"Error getting nonce: {e}")
            # Fallback to basic nonce
            return self.w3.eth.get_transaction_count(self.account.address)
    
    def _send_signed_transaction(self, signed_txn) -> str:
        """Send signed transaction with version compatibility handling"""
        # Handle different Web3.py versions
        # Try different attribute names based on version
        raw_transaction = None
        
        # Method 1: Try rawTransaction (most common in current versions)
        if hasattr(signed_txn, 'rawTransaction'):
            raw_transaction = signed_txn.rawTransaction
        # Method 2: Try raw_transaction (used in some 6.x versions)
        elif hasattr(signed_txn, 'raw_transaction'):
            raw_transaction = signed_txn.raw_transaction
        # Method 3: Try accessing as dict key (fallback)
        elif hasattr(signed_txn, '__getitem__'):
            try:
                raw_transaction = signed_txn['rawTransaction']
            except KeyError:
                try:
                    raw_transaction = signed_txn['raw_transaction']
                except KeyError:
                    pass
        
        if raw_transaction is None:
            # Last resort: try accessing the private attributes
            for attr in ['_raw_transaction', '_rawTransaction', 'transaction']:
                if hasattr(signed_txn, attr):
                    raw_transaction = getattr(signed_txn, attr)
                    break
        
        if raw_transaction is None:
            raise AttributeError(f"Could not find raw transaction data in signed transaction object. Available attributes: {dir(signed_txn)}")
        
        # Send the transaction
        return self.w3.eth.send_raw_transaction(raw_transaction)
    
    def approve_token(self, token_address: str, spender_address: str, amount: int = None) -> bool:
        """Approve token spending for a contract with improved error handling"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            spender_address = Web3.to_checksum_address(spender_address)
            
            contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )
            
            # Check current allowance first
            current_allowance = contract.functions.allowance(
                self.account.address, 
                spender_address
            ).call()
            
            # If allowance is already sufficient, skip approval
            if amount is not None and current_allowance >= amount:
                print(f"Token already approved with sufficient allowance: {current_allowance}")
                return True
            
            # Use maximum allowance if amount not specified
            if amount is None:
                amount = 2**256 - 1
            
            print(f"Approving {amount} tokens for {spender_address}")
            
            # Build transaction with proper nonce handling
            transaction = contract.functions.approve(
                spender_address,
                amount
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'gasPrice': self._get_gas_price(),
                'nonce': self._get_next_nonce()
            })
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            
            # Send transaction with version compatibility
            tx_hash = self._send_signed_transaction(signed_txn)
            
            # Wait for confirmation with timeout
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                print(f"Token approval successful: {tx_hash.hex()}")
                return True
            else:
                print(f"Token approval failed: {tx_hash.hex()}")
                return False
                
        except Exception as e:
            print(f"Error approving token: {e}")
            # Reset nonce tracking on error
            self.last_nonce = None
            return False
    
    def send_transaction(self, transaction_data: Dict) -> Optional[str]:
        """Send a transaction and return transaction hash with improved error handling"""
        try:
            # Ensure from address is set
            if 'from' not in transaction_data:
                transaction_data['from'] = self.account.address
            
            # Add gas and nonce if not provided
            if 'gas' not in transaction_data:
                transaction_data['gas'] = self._estimate_gas(transaction_data)
            
            if 'gasPrice' not in transaction_data:
                transaction_data['gasPrice'] = self._get_gas_price()
            
            if 'nonce' not in transaction_data:
                transaction_data['nonce'] = self._get_next_nonce()
            
            print(f"Sending transaction with gas: {transaction_data['gas']}, gasPrice: {transaction_data['gasPrice']}")
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction_data)
            
            # Send transaction with version compatibility
            tx_hash = self._send_signed_transaction(signed_txn)
            
            print(f"Transaction sent: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            print(f"Error sending transaction: {e}")
            # Reset nonce tracking on error
            self.last_nonce = None
            return None
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> bool:
        """Wait for transaction confirmation with improved error handling"""
        try:
            print(f"Waiting for transaction confirmation: {tx_hash}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt.status == 1:
                print(f"Transaction confirmed: {tx_hash}")
                gas_used = receipt.gasUsed
                print(f"Gas used: {gas_used}")
                return True
            else:
                print(f"Transaction failed: {tx_hash}")
                return False
                
        except Exception as e:
            print(f"Error waiting for transaction: {e}")
            return False
    
    def _get_gas_price(self) -> int:
        """Get current gas price with network-specific optimization"""
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Network-specific adjustments
            network_config = self.network_manager.get_network_config()
            
            if "celo" in network_config.name.lower():
                # CELO has very low gas prices, add smaller buffer
                buffered_price = int(gas_price * 1.05)
            elif "polygon" in network_config.name.lower():
                # Polygon needs higher buffer for faster confirmation
                buffered_price = int(gas_price * 1.2)
            else:
                # Default 10% buffer
                buffered_price = int(gas_price * 1.1)
            
            print(f"Gas price: {self.w3.from_wei(buffered_price, 'gwei'):.2f} gwei")
            return buffered_price
            
        except Exception as e:
            print(f"Error getting gas price: {e}")
            # Return network-specific default gas price
            network_config = self.network_manager.get_network_config()
            if "celo" in network_config.name.lower():
                return self.w3.to_wei(1, 'gwei')  # 1 gwei for CELO
            elif "polygon" in network_config.name.lower():
                return self.w3.to_wei(30, 'gwei')  # 30 gwei for Polygon
            else:
                return self.w3.to_wei(20, 'gwei')  # 20 gwei default
    
    def _estimate_gas(self, transaction_data: Dict) -> int:
        """Estimate gas for transaction with safety buffers"""
        try:
            # Create a copy for estimation (remove nonce for estimation)
            estimate_data = transaction_data.copy()
            if 'nonce' in estimate_data:
                del estimate_data['nonce']
            
            gas_estimate = self.w3.eth.estimate_gas(estimate_data)
            
            # Add safety buffer based on transaction type
            if 'data' in transaction_data and transaction_data['data']:
                # Contract interaction - add 30% buffer
                safety_buffer = int(gas_estimate * 1.3)
            else:
                # Simple transfer - add 20% buffer
                safety_buffer = int(gas_estimate * 1.2)
            
            # Ensure minimum gas limit
            min_gas = 21000
            final_gas = max(safety_buffer, min_gas)
            
            print(f"Gas estimation: {gas_estimate} -> {final_gas} (with buffer)")
            return final_gas
            
        except Exception as e:
            print(f"Error estimating gas: {e}")
            # Return conservative default based on network
            network_config = self.network_manager.get_network_config()
            if "celo" in network_config.name.lower():
                return 300000  # CELO default
            else:
                return 500000  # Other networks default
    
    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction receipt with error handling"""
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return dict(receipt)
        except Exception as e:
            print(f"Error getting transaction receipt: {e}")
            return None
    
    def is_connected(self) -> bool:
        """Check if wallet is connected with improved validation"""
        try:
            return (self.connected and 
                   self.w3 and 
                   self.w3.is_connected() and 
                   self.account is not None)
        except:
            return False
    
    def reconnect(self):
        """Reconnect to network with state reset"""
        print("Reconnecting wallet...")
        self.connected = False
        self.last_nonce = None
        self._connect()
    
    def switch_network(self, network_name: str):
        """Switch to different network with full reset"""
        print(f"Switching to network: {network_name}")
        self.network_manager.set_network(network_name)
        self.reconnect()
    
    def get_current_network(self) -> str:
        """Get current network name"""
        return self.network_manager.current_network
    
    def reset_nonce(self):
        """Reset nonce tracking (useful after errors)"""
        self.last_nonce = None
        print("Nonce tracking reset")
    
    def get_nonce_info(self) -> Dict[str, int]:
        """Get nonce information for debugging"""
        try:
            current_nonce = self.w3.eth.get_transaction_count(self.account.address)
            pending_nonce = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            
            return {
                "current_nonce": current_nonce,
                "pending_nonce": pending_nonce,
                "tracked_nonce": self.last_nonce
            }
        except Exception as e:
            print(f"Error getting nonce info: {e}")
            return {}
    
    def validate_transaction_data(self, transaction_data: Dict) -> bool:
        """Validate transaction data before sending"""
        try:
            required_fields = ['to']
            
            for field in required_fields:
                if field not in transaction_data:
                    print(f"Missing required field: {field}")
                    return False
            
            # Validate addresses
            if 'to' in transaction_data:
                try:
                    Web3.to_checksum_address(transaction_data['to'])
                except:
                    print("Invalid 'to' address")
                    return False
            
            # Validate amounts
            if 'value' in transaction_data and transaction_data['value'] < 0:
                print("Invalid transaction value")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating transaction: {e}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get comprehensive account information"""
        try:
            nonce_info = self.get_nonce_info()
            balance = self.get_balance()
            network_info = self.network_manager.get_network_info()
            
            return {
                "address": self.account.address,
                "balance": balance,
                "network": network_info,
                "nonce_info": nonce_info,
                "connected": self.is_connected()
            }
            
        except Exception as e:
            print(f"Error getting account info: {e}")
            return {}