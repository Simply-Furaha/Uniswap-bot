import os
import json
import subprocess
import sys

def install_requirements():
    """Install required Python packages"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["data", "logs"]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created directory: {directory}")

def create_sample_config():
    """Create sample configuration file"""
    config_path = "data/config.json"
    
    if os.path.exists(config_path):
        print(f"✓ Configuration file already exists: {config_path}")
        return
    
    sample_config = {
        "network": "ethereum",
        "rpc_url": "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
        "private_key": "YOUR_PRIVATE_KEY_HERE",
        "wallet_address": "YOUR_WALLET_ADDRESS",
        "budget_usd": 100.0,
        "price_range_percent": 5.0,
        "rebalance_threshold": 80.0,
        "token0_address": "0xA0b86a33E6C741c4C1C8E62EE8B4B9c8D5c8E1a0",
        "token1_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "pool_fee": 3000,
        "max_slippage": 0.5,
        "gas_price_gwei": None,
        "check_interval": 30,
        "auto_compound": True,
        "log_level": "INFO"
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(sample_config, f, indent=2)
        print(f"✓ Sample configuration created: {config_path}")
        print("⚠️  Please edit the configuration file with your actual values!")
    except Exception as e:
        print(f"✗ Failed to create configuration: {e}")

def create_init_files():
    """Create __init__.py files for Python packages"""
    packages = ["config", "core", "utils"]
    
    for package in packages:
        init_file = os.path.join(package, "__init__.py")
        os.makedirs(package, exist_ok=True)
        
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write(f'"""Uniswap Liquidity Bot - {package.title()} Package"""\n')
            print(f"✓ Created {init_file}")

def show_next_steps():
    """Show instructions for next steps"""
    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print("Next steps:")
    print("1. Edit data/config.json with your:")
    print("   - RPC endpoint URL")
    print("   - Wallet private key")
    print("   - Token addresses")
    print("   - Trading parameters")
    print()
    print("2. Run the bot:")
    print("   python main.py")
    print()
    print("3. Available commands in the bot:")
    print("   - status: Show bot status")
    print("   - create: Create initial position")
    print("   - add <token_id>: Monitor existing position")
    print("   - remove <token_id>: Stop monitoring position")
    print("   - stop: Stop the bot")
    print()
    print("⚠️  SECURITY WARNING:")
    print("   Never share your private key!")
    print("   Use a dedicated wallet for testing!")
    print("="*60)

def main():
    """Main setup function"""
    print("Uniswap Liquidity Bot Setup")
    print("="*30)
    
    # Install requirements
    if not install_requirements():
        print("Setup failed during package installation")
        return
    
    # Create directories
    create_directories()
    
    # Create package init files
    create_init_files()
    
    # Create sample configuration
    create_sample_config()
    
    # Show next steps
    show_next_steps()

if __name__ == "__main__":
    main()