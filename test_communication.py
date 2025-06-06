#!/usr/bin/env python3
"""
Python-MQL5間通信テストスクリプト
FastAPIサーバーとMQL5 EAの通信をテストする
"""

import asyncio
import json
import requests
import time
from datetime import datetime
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class CommunicationTester:
    def __init__(self):
        self.base_url = f"http://{settings.HOST}:{settings.PORT}"
        self.test_results = []
    
    def test_server_status(self):
        """サーバー状態テスト"""
        print("=== Server Status Test ===")
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Server Status: {data['status']}")
                print(f"   Service: {data['service']}")
                print(f"   Version: {data['version']}")
                self.test_results.append(("Server Status", True))
                return True
            else:
                print(f"❌ Server Status Failed: HTTP {response.status_code}")
                self.test_results.append(("Server Status", False))
                return False
        except Exception as e:
            print(f"❌ Server Status Error: {str(e)}")
            self.test_results.append(("Server Status", False))
            return False
    
    def test_market_data_endpoint(self):
        """市場データエンドポイントテスト"""
        print("\n=== Market Data Endpoint Test ===")
        
        # テストデータ作成
        test_data = {
            "symbol": "USDJPY",
            "data": [
                {
                    "symbol": "USDJPY",
                    "timestamp": datetime.now().isoformat(),
                    "open": 150.123,
                    "high": 150.456,
                    "low": 149.789,
                    "close": 150.234,
                    "volume": 1000
                },
                {
                    "symbol": "USDJPY", 
                    "timestamp": datetime.now().isoformat(),
                    "open": 150.234,
                    "high": 150.567,
                    "low": 149.890,
                    "close": 150.345,
                    "volume": 1200
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/market-data",
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Market Data POST: {result['status']}")
                print(f"   Records Processed: {result['records_processed']}")
                self.test_results.append(("Market Data POST", True))
                return True
            else:
                print(f"❌ Market Data POST Failed: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                self.test_results.append(("Market Data POST", False))
                return False
                
        except Exception as e:
            print(f"❌ Market Data POST Error: {str(e)}")
            self.test_results.append(("Market Data POST", False))
            return False
    
    def test_market_data_retrieval(self):
        """市場データ取得テスト"""
        print("\n=== Market Data Retrieval Test ===")
        
        try:
            response = requests.get(f"{self.base_url}/api/v1/market-data/USDJPY", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Market Data GET: Success")
                print(f"   Symbol: {data['symbol']}")
                print(f"   Records Count: {data['count']}")
                if data['count'] > 0:
                    latest = data['data'][0]
                    print(f"   Latest Close: {latest['close']}")
                    print(f"   Latest Time: {latest['timestamp']}")
                self.test_results.append(("Market Data GET", True))
                return True
            else:
                print(f"❌ Market Data GET Failed: HTTP {response.status_code}")
                self.test_results.append(("Market Data GET", False))
                return False
                
        except Exception as e:
            print(f"❌ Market Data GET Error: {str(e)}")
            self.test_results.append(("Market Data GET", False))
            return False
    
    def test_signals_endpoint(self):
        """シグナルエンドポイントテスト"""
        print("\n=== Signals Endpoint Test ===")
        
        try:
            response = requests.get(f"{self.base_url}/api/v1/signals", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Signals GET: Success")
                print(f"   Total Count: {data['total_count']}")
                print(f"   Timestamp: {data['timestamp']}")
                self.test_results.append(("Signals GET", True))
                return True
            else:
                print(f"❌ Signals GET Failed: HTTP {response.status_code}")
                self.test_results.append(("Signals GET", False))
                return False
                
        except Exception as e:
            print(f"❌ Signals GET Error: {str(e)}")
            self.test_results.append(("Signals GET", False))
            return False
    
    def test_system_status(self):
        """システム状態詳細テスト"""
        print("\n=== System Status Test ===")
        
        try:
            response = requests.get(f"{self.base_url}/api/v1/system-status", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ System Status: {data['status']}")
                print(f"   Active Trades: {data['active_trades']}")
                print(f"   Monitored Pairs: {', '.join(data['monitored_pairs'])}")
                print(f"   Last Update: {data['last_update']}")
                self.test_results.append(("System Status", True))
                return True
            else:
                print(f"❌ System Status Failed: HTTP {response.status_code}")
                self.test_results.append(("System Status", False))
                return False
                
        except Exception as e:
            print(f"❌ System Status Error: {str(e)}")
            self.test_results.append(("System Status", False))
            return False
    
    def monitor_mql5_communication(self, duration=60):
        """MQL5通信監視テスト"""
        print(f"\n=== MQL5 Communication Monitor (for {duration} seconds) ===")
        print("Waiting for MQL5 EA to send data...")
        print("Please start the EA in MetaTrader 5 now.")
        
        start_time = time.time()
        last_count = 0
        
        while time.time() - start_time < duration:
            try:
                response = requests.get(f"{self.base_url}/api/v1/market-data/USDJPY", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    current_count = data['count']
                    
                    if current_count > last_count:
                        print(f"📊 New data received! Total records: {current_count}")
                        if data['data']:
                            latest = data['data'][0]
                            print(f"   Latest: {latest['close']} at {latest['timestamp']}")
                        last_count = current_count
                
                time.sleep(5)  # 5秒間隔でチェック
                
            except Exception as e:
                print(f"⚠️  Monitor error: {str(e)}")
                time.sleep(5)
        
        if last_count > 0:
            print(f"✅ MQL5 Communication: Success (received {last_count} records)")
            self.test_results.append(("MQL5 Communication", True))
        else:
            print("❌ MQL5 Communication: No data received")
            self.test_results.append(("MQL5 Communication", False))
    
    def print_summary(self):
        """テスト結果サマリー"""
        print("\n" + "="*50)
        print("COMMUNICATION TEST SUMMARY")
        print("="*50)
        
        passed = 0
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:<25} {status}")
            if result:
                passed += 1
        
        print("-"*50)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "0%")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! Communication is working correctly.")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Please check the issues above.")

def main():
    """メイン実行関数"""
    print("FX Trading System - Communication Test")
    print("="*50)
    
    tester = CommunicationTester()
    
    # 基本テスト実行
    tester.test_server_status()
    tester.test_market_data_endpoint()
    tester.test_market_data_retrieval()
    tester.test_signals_endpoint()
    tester.test_system_status()
    
    # MQL5通信監視（オプション）
    print(f"\nDo you want to monitor MQL5 communication? (y/n): ", end="")
    if input().lower().startswith('y'):
        print("Enter monitoring duration in seconds (default 60): ", end="")
        try:
            duration = int(input()) or 60
        except ValueError:
            duration = 60
        tester.monitor_mql5_communication(duration)
    
    # 結果表示
    tester.print_summary()

if __name__ == "__main__":
    main()