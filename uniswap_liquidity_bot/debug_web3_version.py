#!/usr/bin/env python3
"""
Web3.py Version and Compatibility Debug Script
Run this to check your Web3.py version and test transaction signing
"""

import sys
from web3 import Web3
from eth_account import Account

def check_web3_version():
    """Check Web3.py version and capabilities"""
    print("="*60)
    print("WEB3.PY VERSION AND COMPATIBILITY CHECK")
    print("="*60)
    
    # Check Web3.py version
    try:
        import web3
        print(f"Web3.py version: {web3.__version__}")
    except AttributeError:
        print("Web3.py version: Unknown (no __version__ attribute)")
    
    # Check eth-account version
    try:
        import eth_account
        print(f"eth-account version: {eth_account.__version__}")
    except (ImportError, AttributeError):
        print("eth-account version: Unknown")
    
    print(f"Python version: {sys.version}")
    
    # Test transaction signing
    print("\n" + "="*40)
    print("TESTING TRANSACTION SIGNING")
    print("="*40)
    
    # Create a test account
    test_account = Account.create()
    print(f"Test account: {test_account.address}")
    
    # Create a dummy transaction
    transaction = {
        'to': '0x0000000000000000000000000000000000000000',
        'value': 0,
        'gas': 21000,
        'gasPrice': 20000000000,  # 20 gwei
        'nonce': 0,
    }
    
    # Sign the transaction
    try:
        signed_txn = test_account.sign_transaction(transaction)
        print("✅ Transaction signing successful!")
        
        # Check available attributes
        attributes = [attr for attr in dir(signed_txn) if not attr.startswith('_')]
        print(f"Available attributes: {attributes}")
        
        # Test different raw transaction access methods
        raw_transaction = None
        method_used = None
        
        # Method 1: rawTransaction (camelCase)
        if hasattr(signed_txn, 'rawTransaction'):
            raw_transaction = signed_txn.rawTransaction
            method_used = "rawTransaction (camelCase)"
        
        # Method 2: raw_transaction (snake_case)
        elif hasattr(signed_txn, 'raw_transaction'):
            raw_transaction = signed_txn.raw_transaction
            method_used = "raw_transaction (snake_case)"
        
        if raw_transaction:
            print(f"✅ Raw transaction access: {method_used}")
            print(f"Raw transaction type: {type(raw_transaction)}")
            print(f"Raw transaction length: {len(raw_transaction)} bytes")
        else:
            print("❌ Could not access raw transaction data")
            print("Available methods to try:")
            for attr in dir(signed_txn):
                if 'transaction' in attr.lower() or 'raw' in attr.lower():
                    print(f"  - {attr}: {type(getattr(signed_txn, attr, None))}")
        
    except Exception as e:
        print(f"❌ Transaction signing failed: {e}")
        import traceback
        traceback.print_exc()

def test_web3_connection():
    """Test Web3 connection capabilities"""
    print("\n" + "="*40)
    print("TESTING WEB3 CONNECTION")
    print("="*40)
    
    # Test connection to CELO
    try:
        w3 = Web3(Web3.HTTPProvider("https://forno.celo.org"))
        
        if w3.is_connected():
            print("✅ CELO connection successful!")
            
            # Get chain ID
            chain_id = w3.eth.chain_id
            print(f"Chain ID: {chain_id}")
            
            # Get latest block
            latest_block = w3.eth.block_number
            print(f"Latest block: {latest_block}")
            
            # Test gas price
            gas_price = w3.eth.gas_price
            print(f"Current gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
            
        else:
            print("❌ CELO connection failed")
            
    except Exception as e:
        print(f"❌ CELO connection error: {e}")

def main():
    """Main debug function"""
    check_web3_version()
    test_web3_connection()
    
    print("\n" + "="*60)
    print("DEBUG COMPLETE")
    print("="*60)
    print("If you see errors above, please:")
    print("1. Update Web3.py: pip install --upgrade web3")
    print("2. Update eth-account: pip install --upgrade eth-account")
    print("3. Check your Python version (3.8+ recommended)")
    print("4. Report the output to get specific help")

if __name__ == "__main__":
    main()