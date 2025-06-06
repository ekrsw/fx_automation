"""
監視サービス
システム状態の監視とアラート生成を管理
"""

import asyncio
import logging
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self):
        self.monitoring_rules = []
        self.last_check_time = {}
        self.system_start_time = datetime.now()
        
    async def get_system_health(self) -> Dict[str, Any]:
        """
        システムヘルス状態を取得
        """
        try:
            # システムリソース情報
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # プロセス情報
            current_process = psutil.Process()
            process_memory = current_process.memory_info()
            
            # ネットワーク統計
            network = psutil.net_io_counters()
            
            # データベース統計
            db_stats = await self._get_database_stats()
            
            # 取引統計
            trading_stats = await self._get_trading_stats()
            
            # 稼働時間
            uptime = datetime.now() - self.system_start_time
            
            health_data = {
                "timestamp": datetime.now(),
                "uptime_seconds": uptime.total_seconds(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used
                    },
                    "disk": {
                        "total": disk.total,
                        "free": disk.free,
                        "used": disk.used,
                        "percent": (disk.used / disk.total) * 100
                    },
                    "network": {
                        "bytes_sent": network.bytes_sent,
                        "bytes_recv": network.bytes_recv,
                        "packets_sent": network.packets_sent,
                        "packets_recv": network.packets_recv
                    }
                },
                "process": {
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "cpu_percent": current_process.cpu_percent(),
                    "num_threads": current_process.num_threads()
                },
                "database": db_stats,
                "trading": trading_stats,
                "health_score": await self._calculate_health_score(cpu_percent, memory.percent, trading_stats)
            }
            
            return health_data
            
        except Exception as e:
            logger.error(f"システムヘルス取得エラー: {str(e)}")
            return {
                "timestamp": datetime.now(),
                "error": f"システムヘルス取得に失敗: {str(e)}",
                "health_score": 0
            }
    
    async def _get_database_stats(self) -> Dict[str, Any]:
        """
        データベース統計を取得
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # テーブルサイズ情報
            tables_info = {}
            table_names = ["market_data", "trades", "alerts", "signals"]
            
            for table in table_names:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                tables_info[table] = {"record_count": count}
            
            # 最新データのタイムスタンプ
            cursor.execute("SELECT MAX(timestamp) FROM market_data")
            latest_data = cursor.fetchone()[0]
            
            # アクティブアラート数
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'active'")
            active_alerts = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "tables": tables_info,
                "latest_market_data": latest_data,
                "active_alerts": active_alerts
            }
            
        except Exception as e:
            logger.error(f"データベース統計取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def _get_trading_stats(self) -> Dict[str, Any]:
        """
        取引統計を取得
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 本日の取引統計
            today = datetime.now().date()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(profit) as total_profit,
                    AVG(profit) as avg_profit
                FROM trades 
                WHERE DATE(open_time) = ?
            """, (today,))
            
            today_stats = cursor.fetchone()
            
            # アクティブポジション
            cursor.execute("SELECT COUNT(*) FROM trades WHERE close_time IS NULL")
            active_positions = cursor.fetchone()[0]
            
            # 最新シグナル
            cursor.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE created_at > datetime('now', '-1 hour')
            """)
            recent_signals = cursor.fetchone()[0]
            
            conn.close()
            
            win_rate = 0
            if today_stats[0] > 0:
                win_rate = (today_stats[1] / today_stats[0]) * 100
            
            return {
                "today": {
                    "total_trades": today_stats[0] or 0,
                    "winning_trades": today_stats[1] or 0,
                    "win_rate": round(win_rate, 2),
                    "total_profit": today_stats[2] or 0,
                    "avg_profit": today_stats[3] or 0
                },
                "active_positions": active_positions,
                "recent_signals_1h": recent_signals
            }
            
        except Exception as e:
            logger.error(f"取引統計取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def _calculate_health_score(self, cpu_percent: float, memory_percent: float, trading_stats: Dict) -> int:
        """
        システムヘルススコアを計算（0-100）
        """
        try:
            score = 100
            
            # CPU使用率によるスコア調整
            if cpu_percent > 80:
                score -= 30
            elif cpu_percent > 60:
                score -= 15
            elif cpu_percent > 40:
                score -= 5
            
            # メモリ使用率によるスコア調整
            if memory_percent > 90:
                score -= 25
            elif memory_percent > 75:
                score -= 10
            elif memory_percent > 60:
                score -= 5
            
            # 取引状況によるスコア調整
            if "error" in trading_stats:
                score -= 20
            else:
                # アクティブポジション数チェック
                active_pos = trading_stats.get("active_positions", 0)
                if active_pos > 5:  # 設定可能
                    score -= 10
                
                # 最新シグナルチェック
                recent_signals = trading_stats.get("recent_signals_1h", 0)
                if recent_signals == 0:
                    score -= 5  # シグナルが全くない場合
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"ヘルススコア計算エラー: {str(e)}")
            return 50  # デフォルトスコア
    
    async def run_all_checks(self):
        """
        すべての監視チェックを実行
        """
        try:
            # システムリソースチェック
            await self._check_system_resources()
            
            # データベースヘルスチェック
            await self._check_database_health()
            
            # 取引システムチェック
            await self._check_trading_system()
            
            # 外部接続チェック
            await self._check_external_connections()
            
            logger.info("すべての監視チェックが完了しました")
            
        except Exception as e:
            logger.error(f"監視チェック実行エラー: {str(e)}")
            await self._create_alert("system", "監視チェックエラー", 
                                   f"監視チェック実行中にエラーが発生: {str(e)}", 8)
    
    async def _check_system_resources(self):
        """
        システムリソースをチェック
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # CPU使用率チェック
            if cpu_percent > 90:
                await self._create_alert("system", "CPU使用率高", 
                                       f"CPU使用率が{cpu_percent}%に達しています", 9)
            elif cpu_percent > 75:
                await self._create_alert("system", "CPU使用率警告", 
                                       f"CPU使用率が{cpu_percent}%です", 6)
            
            # メモリ使用率チェック
            if memory.percent > 95:
                await self._create_alert("system", "メモリ不足", 
                                       f"メモリ使用率が{memory.percent}%に達しています", 9)
            elif memory.percent > 85:
                await self._create_alert("system", "メモリ使用率警告", 
                                       f"メモリ使用率が{memory.percent}%です", 6)
            
            # ディスク容量チェック
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 95:
                await self._create_alert("system", "ディスク容量不足", 
                                       f"ディスク使用率が{disk_percent:.1f}%に達しています", 8)
            elif disk_percent > 85:
                await self._create_alert("system", "ディスク容量警告", 
                                       f"ディスク使用率が{disk_percent:.1f}%です", 5)
            
        except Exception as e:
            logger.error(f"システムリソースチェックエラー: {str(e)}")
    
    async def _check_database_health(self):
        """
        データベースヘルスをチェック
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # データベース接続テスト
            cursor.execute("SELECT 1")
            
            # 最新データチェック
            cursor.execute("SELECT MAX(timestamp) FROM market_data")
            latest_data = cursor.fetchone()[0]
            
            if latest_data:
                latest_time = datetime.fromisoformat(latest_data.replace('Z', '+00:00'))
                time_diff = datetime.now() - latest_time.replace(tzinfo=None)
                
                if time_diff.total_seconds() > 600:  # 10分以上データが古い
                    await self._create_alert("system", "市場データ遅延", 
                                           f"最新データが{time_diff.total_seconds():.0f}秒前です", 7)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"データベースヘルスチェックエラー: {str(e)}")
            await self._create_alert("system", "データベースエラー", 
                                   f"データベース接続に問題があります: {str(e)}", 9)
    
    async def _check_trading_system(self):
        """
        取引システムをチェック
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # アクティブポジション数チェック
            cursor.execute("SELECT COUNT(*) FROM trades WHERE close_time IS NULL")
            active_positions = cursor.fetchone()[0]
            
            if active_positions > 5:  # 設定可能な上限
                await self._create_alert("trade", "ポジション数過多", 
                                       f"アクティブポジション数が{active_positions}に達しています", 6)
            
            # 最近の損失をチェック
            cursor.execute("""
                SELECT SUM(profit) FROM trades 
                WHERE open_time > datetime('now', '-24 hours')
                AND profit < 0
            """)
            daily_loss = cursor.fetchone()[0] or 0
            
            if daily_loss < -1000:  # 設定可能な損失限度額
                await self._create_alert("trade", "大幅損失", 
                                       f"本日の損失が{daily_loss:.2f}に達しています", 8)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"取引システムチェックエラー: {str(e)}")
            await self._create_alert("system", "取引システムエラー", 
                                   f"取引システムチェックでエラー: {str(e)}", 8)
    
    async def _check_external_connections(self):
        """
        外部接続をチェック
        """
        try:
            # MetaTrader接続チェック（過去5分以内のデータ受信チェック）
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM market_data 
                WHERE timestamp > datetime('now', '-5 minutes')
            """)
            recent_data_count = cursor.fetchone()[0]
            
            if recent_data_count == 0:
                await self._create_alert("system", "MT5接続問題", 
                                       "MetaTraderからのデータ受信が停止している可能性があります", 8)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"外部接続チェックエラー: {str(e)}")
    
    async def _create_alert(self, alert_type: str, title: str, message: str, severity: int):
        """
        アラートを作成
        """
        try:
            # クールダウンチェック（同じタイプのアラートを短時間で重複生成しない）
            alert_key = f"{alert_type}_{title}"
            now = datetime.now()
            
            if alert_key in self.last_check_time:
                time_diff = now - self.last_check_time[alert_key]
                if time_diff.total_seconds() < 300:  # 5分間のクールダウン
                    return
            
            self.last_check_time[alert_key] = now
            
            # データベースにアラートを保存
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO alerts (type, title, message, severity, status, created_at)
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (alert_type, title, message, severity, now))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"アラート生成: {title} - {message}")
            
        except Exception as e:
            logger.error(f"アラート作成エラー: {str(e)}")
    
    async def update_alert_statistics(self, alert_id: int, alert_type: str, severity: int):
        """
        アラート統計を更新
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # アラート統計テーブルに記録
            cursor.execute("""
                INSERT OR REPLACE INTO alert_statistics 
                (date, alert_type, count, total_severity)
                VALUES (
                    DATE('now'), 
                    ?,
                    COALESCE((SELECT count FROM alert_statistics 
                             WHERE date = DATE('now') AND alert_type = ?), 0) + 1,
                    COALESCE((SELECT total_severity FROM alert_statistics 
                             WHERE date = DATE('now') AND alert_type = ?), 0) + ?
                )
            """, (alert_type, alert_type, alert_type, severity))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"アラート統計更新エラー: {str(e)}")

    async def start_continuous_monitoring(self, interval_seconds: int = 60):
        """
        継続的な監視を開始
        """
        logger.info(f"継続的監視を開始します（間隔: {interval_seconds}秒）")
        
        while True:
            try:
                await self.run_all_checks()
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"継続的監視エラー: {str(e)}")
                await asyncio.sleep(interval_seconds)  # エラーが発生してもループを継続