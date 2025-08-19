import time
import threading
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
import requests

@dataclass
class PriceAlert:
    """Price alert configuration"""
    pool_address: str
    token_pair: str
    threshold_type: str  # 'above', 'below', 'range_exit'
    threshold_value: float
    callback: Callable
    active: bool = True

class PriceMonitor:
    """Real-time price monitoring and alert system"""
    
    def __init__(self, uniswap_manager, check_interval: int = 30):
        self.uniswap = uniswap_manager
        self.check_interval = check_interval
        self.price_cache = {}
        self.alerts = []
        self.monitoring = False
        self.monitor_thread = None
        
        # Price feed APIs (fallback sources)
        self.price_apis = [
            "https://api.coingecko.com/api/v3/simple/price",
            "https://api.coinbase.com/v2/exchange-rates",
        ]
    
    def start_monitoring(self):
        """Start price monitoring in background thread"""
        if self.monitoring:
            print("Price monitoring already running")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Price monitoring started")
    
    def stop_monitoring(self):
        """Stop price monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        print("Price monitoring stopped")
    
    def add_price_alert(self, pool_address: str, token_pair: str, 
                       threshold_type: str, threshold_value: float, 
                       callback: Callable):
        """Add new price alert"""
        alert = PriceAlert(
            pool_address=pool_address,
            token_pair=token_pair,
            threshold_type=threshold_type,
            threshold_value=threshold_value,
            callback=callback
        )
        
        self.alerts.append(alert)
        print(f"Price alert added for {token_pair}: {threshold_type} {threshold_value}")
    
    def remove_alert(self, pool_address: str):
        """Remove alert for specific pool"""
        self.alerts = [alert for alert in self.alerts if alert.pool_address != pool_address]
        print(f"Alerts removed for pool {pool_address}")
    
    def get_current_price(self, pool_address: str) -> Optional[Dict]:
        """Get current price for a pool"""
        try:
            price_info = self.uniswap.get_pool_price(pool_address)
            
            if price_info:
                # Cache the price with timestamp
                self.price_cache[pool_address] = {
                    **price_info,
                    "timestamp": time.time()
                }
                
                return price_info
            
            return None
            
        except Exception as e:
            print(f"Error getting current price: {e}")
            return None
    
    def get_price_change(self, pool_address: str, time_window: int = 300) -> Optional[Dict]:
        """Calculate price change over time window (seconds)"""
        try:
            current_price_info = self.get_current_price(pool_address)
            
            if not current_price_info:
                return None
            
            current_price = current_price_info["price"]
            current_time = time.time()
            
            # Look for historical price in cache
            historical_price = None
            for cached_pool, cached_data in self.price_cache.items():
                if (cached_pool == pool_address and 
                    current_time - cached_data["timestamp"] >= time_window):
                    historical_price = cached_data["price"]
                    break
            
            if historical_price is None:
                return {"current_price": current_price, "change_percent": 0.0}
            
            change_percent = ((current_price - historical_price) / historical_price) * 100
            
            return {
                "current_price": current_price,
                "historical_price": historical_price,
                "change_percent": change_percent,
                "time_window": time_window
            }
            
        except Exception as e:
            print(f"Error calculating price change: {e}")
            return None
    
    def check_position_range_status(self, token_id: int) -> Optional[Dict]:
        """Check if position is approaching range boundaries"""
        try:
            range_info = self.uniswap.is_position_in_range(token_id)
            
            if not range_info:
                return None
            
            in_range = range_info["in_range"]
            position_ratio = range_info["position_ratio"]
            
            # Determine status based on position ratio
            if not in_range:
                status = "OUT_OF_RANGE"
                urgency = "HIGH"
            elif position_ratio < 0.1:  # Within 10% of range edge
                status = "APPROACHING_EDGE"
                urgency = "MEDIUM"
            elif position_ratio < 0.2:  # Within 20% of range edge
                status = "NEAR_EDGE"
                urgency = "LOW"
            else:
                status = "SAFE"
                urgency = "NONE"
            
            return {
                "token_id": token_id,
                "status": status,
                "urgency": urgency,
                "in_range": in_range,
                "position_ratio": position_ratio,
                "range_info": range_info
            }
            
        except Exception as e:
            print(f"Error checking position range status: {e}")
            return None
    
    def _monitor_loop(self):
        """Main monitoring loop running in background"""
        while self.monitoring:
            try:
                # Check all price alerts
                for alert in self.alerts:
                    if not alert.active:
                        continue
                    
                    try:
                        self._check_alert(alert)
                    except Exception as e:
                        print(f"Error checking alert for {alert.token_pair}: {e}")
                
                # Clean up old cache entries (older than 1 hour)
                self._cleanup_cache()
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)
    
    def _check_alert(self, alert: PriceAlert):
        """Check individual price alert"""
        current_price_info = self.get_current_price(alert.pool_address)
        
        if not current_price_info:
            return
        
        current_price = current_price_info["price"]
        triggered = False
        
        if alert.threshold_type == "above" and current_price > alert.threshold_value:
            triggered = True
        elif alert.threshold_type == "below" and current_price < alert.threshold_value:
            triggered = True
        elif alert.threshold_type == "range_exit":
            # For range exit alerts, threshold_value is position ratio
            range_info = self.uniswap.is_position_in_range(int(alert.pool_address))
            if range_info and not range_info["in_range"]:
                triggered = True
        
        if triggered:
            try:
                alert.callback(alert, current_price_info)
            except Exception as e:
                print(f"Error executing alert callback: {e}")
    
    def _cleanup_cache(self):
        """Remove old price cache entries"""
        current_time = time.time()
        cache_timeout = 3600  # 1 hour
        
        expired_pools = []
        for pool_address, cached_data in self.price_cache.items():
            if current_time - cached_data["timestamp"] > cache_timeout:
                expired_pools.append(pool_address)
        
        for pool_address in expired_pools:
            del self.price_cache[pool_address]
    
    def get_price_from_external_api(self, token_symbol: str) -> Optional[float]:
        """Get price from external API as fallback"""
        try:
            # Try CoinGecko first
            response = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={token_symbol}&vs_currencies=usd",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if token_symbol in data:
                    return data[token_symbol]["usd"]
            
            return None
            
        except Exception as e:
            print(f"Error getting price from external API: {e}")
            return None
    
    def calculate_volatility(self, pool_address: str, periods: int = 10) -> Optional[float]:
        """Calculate price volatility over recent periods"""
        try:
            # This is a simplified volatility calculation
            # In production, you'd want more sophisticated metrics
            
            if pool_address not in self.price_cache:
                return None
            
            # For now, return a basic volatility estimate based on recent price changes
            recent_change = self.get_price_change(pool_address, 300)  # 5 min change
            
            if recent_change and "change_percent" in recent_change:
                return abs(recent_change["change_percent"])
            
            return 0.0
            
        except Exception as e:
            print(f"Error calculating volatility: {e}")
            return None
    
    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status and statistics"""
        return {
            "monitoring": self.monitoring,
            "check_interval": self.check_interval,
            "active_alerts": len([a for a in self.alerts if a.active]),
            "total_alerts": len(self.alerts),
            "cached_prices": len(self.price_cache),
            "last_check": time.time()
        }