from typing import Dict, NamedTuple

class NetworkConfig(NamedTuple):
    """Network configuration structure"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    uniswap_v3_factory: str
    uniswap_v3_router: str
    position_manager: str
    quoter: str
    weth_address: str
    usdc_address: str
    usdt_address: str

# CELO Network Configuration (Primary)
NETWORKS: Dict[str, NetworkConfig] = {
    "celo": NetworkConfig(
        chain_id=42220,
        name="Celo",
        rpc_url="https://forno.celo.org",
        explorer_url="https://celoscan.io",
        uniswap_v3_factory="0xAfE208a311B21f13EF87E33A90049fC17A7acDEc",
        uniswap_v3_router="0x5615CDAb10dc425a742d643d949a7F474C01abc4",
        position_manager="0x3d79EdAaBC0EaB6F08ED885C05Fc0B014290D95A",
        quoter="0x82825d0554fA07f7FC52Ab63c961F330fdEFa8E8",
        weth_address="0x122013fd7dF1C6F636a5bb8f03108E876548b455",  # WETH on Celo
        usdc_address="0xcebA9300f2b948710d2653dD7B07f33A8B32118C",  # USDC on Celo
        usdt_address="0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e"   # USDT on Celo
    ),
    
    # Keep Polygon as backup for testing
    "polygon": NetworkConfig(
        chain_id=137,
        name="Polygon",
        rpc_url="https://polygon-rpc.com/",
        explorer_url="https://polygonscan.com",
        uniswap_v3_factory="0x1F98431c8aD98523631AE4a59f267346ea31F984",
        uniswap_v3_router="0xE592427A0AEce92De3Edee1F18E0157C05861564",
        position_manager="0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
        quoter="0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
        weth_address="0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        usdt_address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
    )
}

class NetworkManager:
    """Manages network configurations and switching"""
    
    def __init__(self, default_network: str = "celo"):
        self.current_network = default_network
    
    def get_network_config(self, network_name: str = None) -> NetworkConfig:
        """Get configuration for specified network"""
        network = network_name or self.current_network
        
        if network not in NETWORKS:
            raise ValueError(f"Network '{network}' not supported")
        
        return NETWORKS[network]
    
    def set_network(self, network_name: str):
        """Set current active network"""
        if network_name not in NETWORKS:
            raise ValueError(f"Network '{network_name}' not supported")
        
        self.current_network = network_name
    
    def get_supported_networks(self) -> list:
        """Get list of supported network names"""
        return list(NETWORKS.keys())
    
    def is_network_supported(self, network_name: str) -> bool:
        """Check if network is supported"""
        return network_name in NETWORKS
    
    def get_network_info(self, network_name: str = None) -> dict:
        """Get human-readable network information"""
        config = self.get_network_config(network_name)
        
        return {
            "name": config.name,
            "chain_id": config.chain_id,
            "explorer": config.explorer_url,
            "native_token": "CELO" if "celo" in config.name.lower() else "MATIC" if "polygon" in config.name.lower() else "ETH"
        }
    
    def get_tick_spacing_for_fee(self, fee: int) -> int:
        """Get appropriate tick spacing for fee tier - CELO specific"""
        tick_spacings = {
            100: 1,     # 0.01% - MINIMUM SPACING (Client's requirement)
            500: 10,    # 0.05%
            3000: 60,   # 0.3%
            10000: 200  # 1%
        }
        return tick_spacings.get(fee, 1)  # Default to 1 for CELO 0.01% pools

# Contract ABIs for Uniswap V3 (simplified versions)
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "observationIndex", "type": "uint16"},
            {"name": "observationCardinality", "type": "uint16"},
            {"name": "observationCardinalityNext", "type": "uint16"},
            {"name": "feeProtocol", "type": "uint8"},
            {"name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Complete ERC20 ABI with all required functions
ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]