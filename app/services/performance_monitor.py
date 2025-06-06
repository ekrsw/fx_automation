"""
パフォーマンス監視サービス
詳細なシステムパフォーマンスと取引成績の監視・分析
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
import psutil

from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        ダッシュボード用の総合パフォーマンスデータを取得
        """
        try:
            # 基本取引統計
            trading_stats = await self.get_trading_metrics(30)
            
            # システム状態
            system_stats = await self.get_system_metrics()
            
            # 直近のパフォーマンス
            recent_performance = await self._get_recent_performance()
            
            # アクティブポジション
            active_positions = await self._get_active_positions_summary()
            
            # アラート状況
            alert_summary = await self.get_alerts_summary()
            
            return {
                "timestamp": datetime.now(),
                "trading_stats": trading_stats,
                "system_stats": system_stats,
                "recent_performance": recent_performance,
                "active_positions": active_positions,
                "alert_summary": alert_summary,
                "system_uptime": (datetime.now() - self.start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"ダッシュボードデータ取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_trading_metrics(self, period_days: int, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        取引パフォーマンス指標を取得
        """
        try:
            conn = get_db_connection()
            
            # 期間設定
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            # クエリ構築
            where_clause = "WHERE entry_time >= ?"
            params = [start_date]
            
            if symbol:
                where_clause += " AND symbol = ?"
                params.append(symbol)
            
            # 基本統計取得
            query = f"""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(profit_loss) as total_profit,
                    AVG(profit_loss) as avg_profit,
                    MAX(profit_loss) as best_trade,
                    MIN(profit_loss) as worst_trade,
                    AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_win,
                    AVG(CASE WHEN profit_loss < 0 THEN profit_loss END) as avg_loss
                FROM trades 
                {where_clause} AND status = 'closed'
            """
            
            df_stats = pd.read_sql_query(query, conn, params=params)
            
            if df_stats.empty or df_stats.iloc[0]['total_trades'] == 0:
                return self._empty_trading_metrics()
            
            stats = df_stats.iloc[0]
            
            # 勝率計算
            win_rate = stats['winning_trades'] / stats['total_trades'] if stats['total_trades'] > 0 else 0
            
            # プロフィットファクター計算
            gross_profit = abs(stats['avg_win'] * stats['winning_trades']) if stats['avg_win'] else 0
            gross_loss = abs(stats['avg_loss'] * stats['losing_trades']) if stats['avg_loss'] else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # 詳細な取引データを取得してリスク指標を計算
            trades_query = f"""
                SELECT profit_loss, entry_time, exit_time 
                FROM trades 
                {where_clause} AND status = 'closed'
                ORDER BY entry_time
            """
            
            df_trades = pd.read_sql_query(trades_query, conn, params=params)
            
            # シャープレシオ等の計算
            risk_metrics = self._calculate_risk_metrics(df_trades)
            
            conn.close()
            
            return {
                "period_days": period_days,
                "symbol": symbol or "ALL",
                "total_trades": int(stats['total_trades']),
                "winning_trades": int(stats['winning_trades']),
                "losing_trades": int(stats['losing_trades']),
                "win_rate": round(win_rate * 100, 2),
                "total_profit": round(float(stats['total_profit']), 2),
                "avg_profit": round(float(stats['avg_profit']), 2),
                "best_trade": round(float(stats['best_trade']), 2),
                "worst_trade": round(float(stats['worst_trade']), 2),
                "avg_win": round(float(stats['avg_win'] or 0), 2),
                "avg_loss": round(float(stats['avg_loss'] or 0), 2),
                "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
                "risk_metrics": risk_metrics
            }
            
        except Exception as e:
            logger.error(f"取引指標取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        システムパフォーマンス指標を取得
        """
        try:
            # CPU・メモリ使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # ネットワーク統計
            network = psutil.net_io_counters()
            
            # プロセス情報
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # データベース統計
            db_stats = await self._get_database_performance()
            
            return {
                "timestamp": datetime.now(),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "used": disk.used,
                    "usage_percent": round((disk.used / disk.total) * 100, 2)
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "memory_mb": round(process_memory.rss / 1024 / 1024, 2),
                    "cpu_percent": process.cpu_percent(),
                    "threads": process.num_threads()
                },
                "database": db_stats
            }
            
        except Exception as e:
            logger.error(f"システム指標取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_equity_curve(self, period_days: int, interval: str = "daily") -> Dict[str, Any]:
        """
        エクイティカーブを取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            # 取引履歴を取得
            query = """
                SELECT exit_time, profit_loss
                FROM trades 
                WHERE exit_time >= ? AND status = 'closed'
                ORDER BY exit_time
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"equity_curve": [], "summary": {"total_return": 0, "max_drawdown": 0}}
            
            # 日時インデックスに変換
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df = df.set_index('exit_time')
            
            # 期間別集計
            if interval == "hourly":
                df_grouped = df.resample('H').sum()
            elif interval == "daily":
                df_grouped = df.resample('D').sum()
            elif interval == "weekly":
                df_grouped = df.resample('W').sum()
            else:
                df_grouped = df.resample('D').sum()
            
            # 累積利益を計算
            df_grouped['cumulative_pnl'] = df_grouped['profit_loss'].cumsum()
            
            # データポイント作成
            equity_points = []
            for timestamp, row in df_grouped.iterrows():
                equity_points.append({
                    "timestamp": timestamp.isoformat(),
                    "profit_loss": round(row['profit_loss'], 2),
                    "cumulative_pnl": round(row['cumulative_pnl'], 2)
                })
            
            # 最大ドローダウン計算
            max_drawdown = self._calculate_max_drawdown_from_series(df_grouped['cumulative_pnl'])
            
            return {
                "period_days": period_days,
                "interval": interval,
                "equity_curve": equity_points,
                "summary": {
                    "total_return": round(df_grouped['cumulative_pnl'].iloc[-1], 2) if not df_grouped.empty else 0,
                    "max_drawdown": round(max_drawdown, 2),
                    "data_points": len(equity_points)
                }
            }
            
        except Exception as e:
            logger.error(f"エクイティカーブ取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_drawdown_analysis(self, period_days: int) -> Dict[str, Any]:
        """
        ドローダウン分析を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            query = """
                SELECT exit_time, profit_loss
                FROM trades 
                WHERE exit_time >= ? AND status = 'closed'
                ORDER BY exit_time
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"max_drawdown": 0, "drawdown_periods": [], "recovery_times": []}
            
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df = df.set_index('exit_time')
            df['cumulative_pnl'] = df['profit_loss'].cumsum()
            
            # ドローダウン計算
            df['peak'] = df['cumulative_pnl'].expanding().max()
            df['drawdown'] = df['cumulative_pnl'] - df['peak']
            df['drawdown_pct'] = (df['drawdown'] / df['peak'] * 100).fillna(0)
            
            # 最大ドローダウン
            max_drawdown = df['drawdown'].min()
            max_drawdown_pct = df['drawdown_pct'].min()
            
            # ドローダウン期間の検出
            drawdown_periods = self._identify_drawdown_periods(df)
            
            return {
                "period_days": period_days,
                "max_drawdown": round(max_drawdown, 2),
                "max_drawdown_percent": round(max_drawdown_pct, 2),
                "drawdown_periods": drawdown_periods,
                "current_drawdown": round(df['drawdown'].iloc[-1], 2) if not df.empty else 0,
                "recovery_factor": self._calculate_recovery_factor(df)
            }
            
        except Exception as e:
            logger.error(f"ドローダウン分析エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_risk_metrics(self, period_days: int) -> Dict[str, Any]:
        """
        リスク指標を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            query = """
                SELECT profit_loss, entry_time, exit_time, quantity, symbol
                FROM trades 
                WHERE entry_time >= ? AND status = 'closed'
                ORDER BY entry_time
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return self._empty_risk_metrics()
            
            # リスク指標を計算
            risk_metrics = self._calculate_comprehensive_risk_metrics(df)
            
            return {
                "period_days": period_days,
                **risk_metrics
            }
            
        except Exception as e:
            logger.error(f"リスク指標取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_symbol_analysis(self, period_days: int) -> Dict[str, Any]:
        """
        通貨ペア別分析を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            query = """
                SELECT symbol, COUNT(*) as trades, SUM(profit_loss) as total_pnl,
                       AVG(profit_loss) as avg_pnl,
                       SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
                FROM trades 
                WHERE entry_time >= ? AND status = 'closed'
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"symbols": [], "summary": {}}
            
            # 通貨ペア別統計
            symbol_stats = []
            for _, row in df.iterrows():
                win_rate = (row['wins'] / row['trades']) * 100 if row['trades'] > 0 else 0
                
                symbol_stats.append({
                    "symbol": row['symbol'],
                    "trades": int(row['trades']),
                    "total_pnl": round(row['total_pnl'], 2),
                    "avg_pnl": round(row['avg_pnl'], 2),
                    "win_rate": round(win_rate, 2),
                    "wins": int(row['wins']),
                    "losses": int(row['trades'] - row['wins'])
                })
            
            # 要約統計
            summary = {
                "total_symbols": len(symbol_stats),
                "best_symbol": symbol_stats[0]['symbol'] if symbol_stats else None,
                "worst_symbol": symbol_stats[-1]['symbol'] if symbol_stats else None,
                "total_pnl": round(df['total_pnl'].sum(), 2),
                "avg_trades_per_symbol": round(df['trades'].mean(), 1)
            }
            
            return {
                "period_days": period_days,
                "symbols": symbol_stats,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"通貨ペア別分析エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_time_analysis(self, period_days: int) -> Dict[str, Any]:
        """
        時間帯別分析を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            query = """
                SELECT entry_time, profit_loss
                FROM trades 
                WHERE entry_time >= ? AND status = 'closed'
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"hourly_analysis": [], "daily_analysis": [], "summary": {}}
            
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['hour'] = df['entry_time'].dt.hour
            df['day_of_week'] = df['entry_time'].dt.day_name()
            
            # 時間別分析
            hourly_stats = df.groupby('hour').agg({
                'profit_loss': ['count', 'sum', 'mean']
            }).round(2)
            
            hourly_analysis = []
            for hour in range(24):
                if hour in hourly_stats.index:
                    stats = hourly_stats.loc[hour]
                    hourly_analysis.append({
                        "hour": hour,
                        "trades": int(stats[('profit_loss', 'count')]),
                        "total_pnl": float(stats[('profit_loss', 'sum')]),
                        "avg_pnl": float(stats[('profit_loss', 'mean')])
                    })
                else:
                    hourly_analysis.append({
                        "hour": hour,
                        "trades": 0,
                        "total_pnl": 0,
                        "avg_pnl": 0
                    })
            
            # 曜日別分析
            daily_stats = df.groupby('day_of_week').agg({
                'profit_loss': ['count', 'sum', 'mean']
            }).round(2)
            
            daily_analysis = []
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                if day in daily_stats.index:
                    stats = daily_stats.loc[day]
                    daily_analysis.append({
                        "day": day,
                        "trades": int(stats[('profit_loss', 'count')]),
                        "total_pnl": float(stats[('profit_loss', 'sum')]),
                        "avg_pnl": float(stats[('profit_loss', 'mean')])
                    })
                else:
                    daily_analysis.append({
                        "day": day,
                        "trades": 0,
                        "total_pnl": 0,
                        "avg_pnl": 0
                    })
            
            # 最適時間帯
            best_hour = max(hourly_analysis, key=lambda x: x['avg_pnl'])
            best_day = max(daily_analysis, key=lambda x: x['avg_pnl'])
            
            return {
                "period_days": period_days,
                "hourly_analysis": hourly_analysis,
                "daily_analysis": daily_analysis,
                "summary": {
                    "best_hour": best_hour['hour'],
                    "best_day": best_day['day'],
                    "most_active_hour": max(hourly_analysis, key=lambda x: x['trades'])['hour'],
                    "most_active_day": max(daily_analysis, key=lambda x: x['trades'])['day']
                }
            }
            
        except Exception as e:
            logger.error(f"時間帯別分析エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_signal_analysis(self, period_days: int) -> Dict[str, Any]:
        """
        シグナル分析を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            # シグナル統計を取得
            signal_query = """
                SELECT signal_type, score, COUNT(*) as count,
                       AVG(score) as avg_score
                FROM signals 
                WHERE timestamp >= ?
                GROUP BY signal_type
                ORDER BY count DESC
            """
            
            df_signals = pd.read_sql_query(signal_query, conn, params=[start_date])
            
            # 取引との関連性分析（簡易版）
            trade_query = """
                SELECT symbol, side, profit_loss
                FROM trades 
                WHERE entry_time >= ? AND status = 'closed'
            """
            
            df_trades = pd.read_sql_query(trade_query, conn, params=[start_date])
            conn.close()
            
            signal_stats = []
            for _, row in df_signals.iterrows():
                signal_stats.append({
                    "signal_type": row['signal_type'],
                    "count": int(row['count']),
                    "avg_score": round(row['avg_score'], 2)
                })
            
            # 取引方向別統計
            trade_direction_stats = []
            if not df_trades.empty:
                direction_stats = df_trades.groupby('side').agg({
                    'profit_loss': ['count', 'sum', 'mean']
                }).round(2)
                
                for direction in direction_stats.index:
                    stats = direction_stats.loc[direction]
                    trade_direction_stats.append({
                        "direction": direction,
                        "trades": int(stats[('profit_loss', 'count')]),
                        "total_pnl": float(stats[('profit_loss', 'sum')]),
                        "avg_pnl": float(stats[('profit_loss', 'mean')])
                    })
            
            return {
                "period_days": period_days,
                "signal_stats": signal_stats,
                "trade_direction_stats": trade_direction_stats,
                "summary": {
                    "total_signals": df_signals['count'].sum() if not df_signals.empty else 0,
                    "most_frequent_signal": signal_stats[0]['signal_type'] if signal_stats else None
                }
            }
            
        except Exception as e:
            logger.error(f"シグナル分析エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_correlation_analysis(self, period_days: int) -> Dict[str, Any]:
        """
        通貨ペア間相関分析を取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            # 通貨ペア別の日次収益を取得
            query = """
                SELECT DATE(exit_time) as date, symbol, SUM(profit_loss) as daily_pnl
                FROM trades 
                WHERE exit_time >= ? AND status = 'closed'
                GROUP BY DATE(exit_time), symbol
                ORDER BY date, symbol
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"correlation_matrix": [], "summary": {}}
            
            # ピボットテーブル作成
            pivot_df = df.pivot(index='date', columns='symbol', values='daily_pnl').fillna(0)
            
            if pivot_df.shape[1] < 2:
                return {"correlation_matrix": [], "summary": {"message": "相関分析には2つ以上の通貨ペアが必要です"}}
            
            # 相関行列計算
            correlation_matrix = pivot_df.corr()
            
            # 相関データを配列形式に変換
            correlation_data = []
            symbols = correlation_matrix.columns.tolist()
            
            for i, symbol1 in enumerate(symbols):
                for j, symbol2 in enumerate(symbols):
                    correlation_data.append({
                        "symbol1": symbol1,
                        "symbol2": symbol2,
                        "correlation": round(correlation_matrix.iloc[i, j], 3)
                    })
            
            # 最高・最低相関の特定
            correlations = []
            for i in range(len(symbols)):
                for j in range(i + 1, len(symbols)):
                    corr_value = correlation_matrix.iloc[i, j]
                    correlations.append({
                        "pair": f"{symbols[i]}-{symbols[j]}",
                        "correlation": corr_value
                    })
            
            correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
            
            return {
                "period_days": period_days,
                "correlation_matrix": correlation_data,
                "symbols": symbols,
                "summary": {
                    "symbol_count": len(symbols),
                    "highest_correlation": correlations[0] if correlations else None,
                    "lowest_correlation": correlations[-1] if correlations else None,
                    "avg_correlation": round(np.mean([abs(c['correlation']) for c in correlations]), 3) if correlations else 0
                }
            }
            
        except Exception as e:
            logger.error(f"相関分析エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_monthly_summary(self, months: int) -> Dict[str, Any]:
        """
        月次サマリーを取得
        """
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=months * 30)).isoformat()
            
            query = """
                SELECT 
                    strftime('%Y-%m', exit_time) as month,
                    COUNT(*) as trades,
                    SUM(profit_loss) as total_pnl,
                    AVG(profit_loss) as avg_pnl,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
                FROM trades 
                WHERE exit_time >= ? AND status = 'closed'
                GROUP BY strftime('%Y-%m', exit_time)
                ORDER BY month
            """
            
            df = pd.read_sql_query(query, conn, params=[start_date])
            conn.close()
            
            if df.empty:
                return {"monthly_data": [], "summary": {}}
            
            monthly_data = []
            for _, row in df.iterrows():
                win_rate = (row['wins'] / row['trades']) * 100 if row['trades'] > 0 else 0
                
                monthly_data.append({
                    "month": row['month'],
                    "trades": int(row['trades']),
                    "total_pnl": round(row['total_pnl'], 2),
                    "avg_pnl": round(row['avg_pnl'], 2),
                    "win_rate": round(win_rate, 2),
                    "wins": int(row['wins']),
                    "losses": int(row['trades'] - row['wins'])
                })
            
            # サマリー統計
            best_month = max(monthly_data, key=lambda x: x['total_pnl']) if monthly_data else None
            worst_month = min(monthly_data, key=lambda x: x['total_pnl']) if monthly_data else None
            
            return {
                "months": months,
                "monthly_data": monthly_data,
                "summary": {
                    "total_months": len(monthly_data),
                    "best_month": best_month,
                    "worst_month": worst_month,
                    "avg_monthly_pnl": round(df['total_pnl'].mean(), 2) if not df.empty else 0,
                    "total_pnl": round(df['total_pnl'].sum(), 2) if not df.empty else 0
                }
            }
            
        except Exception as e:
            logger.error(f"月次サマリー取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_live_metrics(self) -> Dict[str, Any]:
        """
        リアルタイムパフォーマンス指標を取得
        """
        try:
            # 本日の統計
            today_stats = await self.get_trading_metrics(1)
            
            # アクティブポジション
            active_positions = await self._get_active_positions_summary()
            
            # 最新の取引
            recent_trades = await self._get_recent_trades(5)
            
            # システム状態
            system_health = await self._get_system_health_score()
            
            return {
                "timestamp": datetime.now(),
                "today_stats": today_stats,
                "active_positions": active_positions,
                "recent_trades": recent_trades,
                "system_health": system_health
            }
            
        except Exception as e:
            logger.error(f"ライブ指標取得エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_benchmark_comparison(self, period_days: int, benchmark: str) -> Dict[str, Any]:
        """
        ベンチマーク比較を取得
        """
        try:
            # 取引パフォーマンス
            trading_performance = await self.get_trading_metrics(period_days)
            
            # ベンチマーク（単純な通貨ペア価格変動）の取得
            benchmark_performance = await self._get_benchmark_performance(benchmark, period_days)
            
            # 比較分析
            comparison = self._compare_with_benchmark(trading_performance, benchmark_performance)
            
            return {
                "period_days": period_days,
                "benchmark": benchmark,
                "trading_performance": trading_performance,
                "benchmark_performance": benchmark_performance,
                "comparison": comparison
            }
            
        except Exception as e:
            logger.error(f"ベンチマーク比較エラー: {str(e)}")
            return {"error": str(e)}
    
    async def generate_performance_report(self, period_days: int, report_type: str) -> Dict[str, Any]:
        """
        パフォーマンスレポートを生成
        """
        try:
            report = {
                "id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": report_type,
                "period_days": period_days,
                "generated_at": datetime.now(),
                "sections": {}
            }
            
            if report_type == "comprehensive":
                # 包括的レポート
                report["sections"]["trading_metrics"] = await self.get_trading_metrics(period_days)
                report["sections"]["risk_metrics"] = await self.get_risk_metrics(period_days)
                report["sections"]["symbol_analysis"] = await self.get_symbol_analysis(period_days)
                report["sections"]["time_analysis"] = await self.get_time_analysis(period_days)
                report["sections"]["drawdown_analysis"] = await self.get_drawdown_analysis(period_days)
                
            elif report_type == "summary":
                # サマリーレポート
                report["sections"]["trading_metrics"] = await self.get_trading_metrics(period_days)
                report["sections"]["monthly_summary"] = await self.get_monthly_summary(3)
                
            elif report_type == "risk":
                # リスクレポート
                report["sections"]["risk_metrics"] = await self.get_risk_metrics(period_days)
                report["sections"]["drawdown_analysis"] = await self.get_drawdown_analysis(period_days)
                report["sections"]["correlation_analysis"] = await self.get_correlation_analysis(period_days)
            
            return report
            
        except Exception as e:
            logger.error(f"レポート生成エラー: {str(e)}")
            return {"error": str(e)}
    
    async def get_alerts_summary(self) -> Dict[str, Any]:
        """
        アラート要約を取得
        """
        try:
            conn = get_db_connection()
            
            # アクティブアラート数
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'active'")
            active_alerts = cursor.fetchone()[0]
            
            # 重要度別アラート数
            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM alerts 
                WHERE status = 'active'
                GROUP BY severity
                ORDER BY severity DESC
            """)
            
            severity_counts = {}
            for row in cursor.fetchall():
                severity_counts[row[0]] = row[1]
            
            # 今日のアラート数
            cursor.execute("""
                SELECT COUNT(*) FROM alerts 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_alerts = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "active_alerts": active_alerts,
                "today_alerts": today_alerts,
                "severity_breakdown": severity_counts,
                "has_critical_alerts": any(severity >= 8 for severity in severity_counts.keys())
            }
            
        except Exception as e:
            logger.error(f"アラート要約取得エラー: {str(e)}")
            return {"error": str(e)}
    
    # 内部ヘルパーメソッド
    async def _get_recent_performance(self) -> Dict[str, Any]:
        """直近のパフォーマンスを取得"""
        try:
            recent_1d = await self.get_trading_metrics(1)
            recent_7d = await self.get_trading_metrics(7)
            
            return {
                "last_24h": recent_1d,
                "last_7d": recent_7d
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_active_positions_summary(self) -> Dict[str, Any]:
        """アクティブポジションサマリーを取得"""
        try:
            conn = get_db_connection()
            
            query = """
                SELECT symbol, side, COUNT(*) as count, SUM(quantity) as total_quantity
                FROM trades 
                WHERE status = 'open'
                GROUP BY symbol, side
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            positions = []
            for _, row in df.iterrows():
                positions.append({
                    "symbol": row['symbol'],
                    "side": row['side'],
                    "count": int(row['count']),
                    "total_quantity": row['total_quantity']
                })
            
            return {
                "total_positions": len(positions),
                "positions": positions
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_recent_trades(self, limit: int) -> List[Dict[str, Any]]:
        """最新の取引を取得"""
        try:
            conn = get_db_connection()
            
            query = """
                SELECT symbol, side, profit_loss, exit_time
                FROM trades 
                WHERE status = 'closed'
                ORDER BY exit_time DESC
                LIMIT ?
            """
            
            df = pd.read_sql_query(query, conn, params=[limit])
            conn.close()
            
            trades = []
            for _, row in df.iterrows():
                trades.append({
                    "symbol": row['symbol'],
                    "side": row['side'],
                    "profit_loss": round(row['profit_loss'], 2),
                    "exit_time": row['exit_time']
                })
            
            return trades
            
        except Exception as e:
            return []
    
    def _calculate_risk_metrics(self, df_trades: pd.DataFrame) -> Dict[str, Any]:
        """リスク指標を計算"""
        if df_trades.empty:
            return {}
        
        returns = df_trades['profit_loss'].values
        
        # 基本統計
        volatility = np.std(returns)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)
        
        # VaR計算（95%信頼区間）
        var_95 = np.percentile(returns, 5)
        
        # シャープレシオ（簡易版）
        sharpe_ratio = np.mean(returns) / volatility if volatility > 0 else 0
        
        return {
            "volatility": round(volatility, 4),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurtosis, 4),
            "var_95": round(var_95, 2),
            "sharpe_ratio": round(sharpe_ratio, 4)
        }
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """歪度を計算"""
        if len(data) < 3:
            return 0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0
        
        skewness = np.mean(((data - mean) / std) ** 3)
        return skewness
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """尖度を計算"""
        if len(data) < 4:
            return 0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0
        
        kurtosis = np.mean(((data - mean) / std) ** 4) - 3
        return kurtosis
    
    def _empty_trading_metrics(self) -> Dict[str, Any]:
        """空の取引指標を返す"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_profit": 0,
            "avg_profit": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": None,
            "risk_metrics": {}
        }
    
    def _empty_risk_metrics(self) -> Dict[str, Any]:
        """空のリスク指標を返す"""
        return {
            "volatility": 0,
            "sharpe_ratio": 0,
            "var_95": 0,
            "max_drawdown": 0,
            "skewness": 0,
            "kurtosis": 0
        }
    
    async def _get_database_performance(self) -> Dict[str, Any]:
        """データベースパフォーマンス統計を取得"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # テーブルサイズ
            tables = ["market_data", "trades", "signals", "alerts"]
            table_stats = {}
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_stats[table] = count
            
            conn.close()
            
            return {
                "table_sizes": table_stats,
                "total_records": sum(table_stats.values())
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_max_drawdown_from_series(self, cumulative_pnl: pd.Series) -> float:
        """系列から最大ドローダウンを計算"""
        if cumulative_pnl.empty:
            return 0
        
        peak = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - peak
        return abs(drawdown.min())
    
    def _identify_drawdown_periods(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """ドローダウン期間を特定"""
        periods = []
        in_drawdown = False
        start_date = None
        
        for date, row in df.iterrows():
            if row['drawdown'] < 0 and not in_drawdown:
                # ドローダウン開始
                in_drawdown = True
                start_date = date
            elif row['drawdown'] >= 0 and in_drawdown:
                # ドローダウン終了
                in_drawdown = False
                if start_date:
                    periods.append({
                        "start_date": start_date.isoformat(),
                        "end_date": date.isoformat(),
                        "duration_days": (date - start_date).days,
                        "max_drawdown": round(df.loc[start_date:date, 'drawdown'].min(), 2)
                    })
        
        return periods
    
    def _calculate_recovery_factor(self, df: pd.DataFrame) -> float:
        """回復ファクターを計算"""
        if df.empty:
            return 0
        
        total_return = df['cumulative_pnl'].iloc[-1] - df['cumulative_pnl'].iloc[0]
        max_drawdown = abs(df['drawdown'].min())
        
        if max_drawdown == 0:
            return float('inf')
        
        return total_return / max_drawdown
    
    def _calculate_comprehensive_risk_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """包括的リスク指標を計算"""
        if df.empty:
            return self._empty_risk_metrics()
        
        returns = df['profit_loss'].values
        
        # 基本リスク指標
        volatility = np.std(returns)
        mean_return = np.mean(returns)
        sharpe_ratio = mean_return / volatility if volatility > 0 else 0
        
        # VaR・CVaR
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = np.mean(returns[returns <= var_95]) if len(returns[returns <= var_95]) > 0 else var_95
        
        # その他指標
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)
        
        # 最大連続損失
        max_consecutive_losses = self._calculate_max_consecutive_losses(returns)
        
        return {
            "volatility": round(volatility, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "cvar_95": round(cvar_95, 2),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurtosis, 4),
            "max_consecutive_losses": max_consecutive_losses
        }
    
    def _calculate_max_consecutive_losses(self, returns: np.ndarray) -> int:
        """最大連続損失回数を計算"""
        max_consecutive = 0
        current_consecutive = 0
        
        for ret in returns:
            if ret < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    async def _get_system_health_score(self) -> Dict[str, Any]:
        """システムヘルススコアを取得"""
        try:
            # CPU・メモリ使用率
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            # ヘルススコア計算
            score = 100
            if cpu_percent > 80:
                score -= 30
            elif cpu_percent > 60:
                score -= 15
            
            if memory_percent > 85:
                score -= 25
            elif memory_percent > 70:
                score -= 10
            
            status = "healthy"
            if score < 50:
                status = "critical"
            elif score < 70:
                status = "warning"
            
            return {
                "score": max(0, score),
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent
            }
            
        except Exception as e:
            return {
                "score": 0,
                "status": "error",
                "error": str(e)
            }
    
    async def _get_benchmark_performance(self, symbol: str, period_days: int) -> Dict[str, Any]:
        """ベンチマークパフォーマンスを取得"""
        try:
            conn = get_db_connection()
            start_date = (datetime.now() - timedelta(days=period_days)).isoformat()
            
            query = """
                SELECT open, close, timestamp
                FROM market_data 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp
                LIMIT 1
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (symbol, start_date))
            first_row = cursor.fetchone()
            
            query = """
                SELECT open, close, timestamp
                FROM market_data 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            
            cursor.execute(query, (symbol, start_date))
            last_row = cursor.fetchone()
            conn.close()
            
            if not first_row or not last_row:
                return {"error": f"ベンチマークデータが不足: {symbol}"}
            
            # 価格変動計算
            start_price = first_row[1]  # close price
            end_price = last_row[1]
            price_change = end_price - start_price
            price_change_percent = (price_change / start_price) * 100 if start_price > 0 else 0
            
            return {
                "symbol": symbol,
                "start_price": start_price,
                "end_price": end_price,
                "price_change": round(price_change, 5),
                "price_change_percent": round(price_change_percent, 2),
                "period_days": period_days
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _compare_with_benchmark(self, trading_perf: Dict[str, Any], benchmark_perf: Dict[str, Any]) -> Dict[str, Any]:
        """ベンチマークとの比較分析"""
        if "error" in trading_perf or "error" in benchmark_perf:
            return {"error": "比較データが不完全です"}
        
        trading_return = trading_perf.get("total_profit", 0)
        benchmark_return = benchmark_perf.get("price_change_percent", 0)
        
        outperformance = trading_return - benchmark_return
        
        return {
            "trading_return": trading_return,
            "benchmark_return": benchmark_return,
            "outperformance": round(outperformance, 2),
            "outperformed": outperformance > 0,
            "analysis": {
                "better_than_benchmark": outperformance > 0,
                "outperformance_ratio": round(trading_return / benchmark_return, 2) if benchmark_return != 0 else None
            }
        }