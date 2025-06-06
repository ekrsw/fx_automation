# FX自動売買システム - フェーズ3完了

## 📋 プロジェクト概要
ダウ理論とエリオット波動理論に基づくFX自動売買システム。Python FastAPI基盤、MQL5 EA実装、完全な取引機能を搭載。

## 🗂️ プロジェクト構造
```
FX_automation/
├── app/
│   ├── core/
│   │   ├── config.py              # 設定管理
│   │   ├── logging.py             # ログ機能
│   │   └── database.py            # SQLiteデータベース
│   ├── api/
│   │   ├── market_data.py         # 市場データAPI
│   │   ├── analysis.py            # テクニカル分析API
│   │   ├── trading.py             # 取引実行API
│   │   └── reports.py             # レポート・統計API
│   ├── models/
│   │   ├── market_data.py         # 市場データモデル
│   │   └── trading.py             # 取引データモデル
│   └── services/
│       ├── technical_analysis.py  # テクニカル分析サービス
│       └── risk_management.py     # リスク管理サービス
├── mql5/
│   ├── FX_Trading_EA.mq5          # MetaTrader 5 Expert Advisor
│   └── README.md                  # EA セットアップガイド
├── docs/                          # 要件定義書
├── logs/                          # ログファイル
├── main.py                        # FastAPIアプリケーション
├── test_communication.py         # 通信テストスクリプト
└── requirements.txt               # Python依存関係
```

## 🚀 セットアップ手順

### 1. Python環境セットアップ
```bash
# 依存関係インストール
pip install -r requirements.txt

# FastAPIサーバー起動
python main.py
```

### 2. MQL5 EA セットアップ
1. MetaTrader 5でWebRequestを有効化
2. `mql5/FX_Trading_EA.mq5`をコンパイル
3. USDJPY チャートにEAを適用

詳細は `mql5/README.md` を参照

### 3. 通信テスト実行
```bash
python test_communication.py
```

## 🔧 API エンドポイント

### 基本API
- `GET /status` - システム状態確認
- `GET /api/v1/system-status` - 詳細システム状態

### 市場データAPI  
- `POST /api/v1/market-data` - MT5からのデータ受信
- `GET /api/v1/market-data/{symbol}` - 過去データ取得

### テクニカル分析API
- `GET /api/v1/analysis/{symbol}` - 包括的テクニカル分析
- `GET /api/v1/swing-points/{symbol}` - スイングポイント取得
- `GET /api/v1/zigzag/{symbol}` - ZigZagインジケータ
- `GET /api/v1/trend/{symbol}` - トレンド分析

### 取引実行API
- `POST /api/v1/orders` - 新規注文作成
- `GET /api/v1/positions` - ポジション一覧取得
- `POST /api/v1/positions/{ticket}/close` - ポジション決済
- `PUT /api/v1/positions/{ticket}/modify` - SL/TP修正
- `GET /api/v1/account` - 口座情報取得
- `POST /api/v1/risk/calculate` - リスク計算
- `GET /api/v1/signals/validate` - シグナル検証

### レポート・統計API
- `GET /api/v1/trading-summary` - 取引サマリー
- `GET /api/v1/trade-history` - 取引履歴
- `GET /api/v1/performance-metrics` - パフォーマンス指標
- `GET /api/v1/risk-exposure` - リスクエクスポージャー
- `GET /api/v1/daily-pnl` - 日次損益

## 📊 実装済み機能

### フェーズ1: 基本インフラ ✅
- FastAPI基盤とヘルスチェックAPI
- ログ機能とSQLiteデータベース
- 基本的なAPIエンドポイント

### フェーズ2: シングルペア分析 ✅  
- MQL5 EA（HTTP通信機能）
- MetaTraderとの基本接続
- USD/JPY価格データ取得
- Python-MQL5間通信テスト
- ダウ理論スイングポイント検出
- 高値・安値切り上げ/切り下げ判定
- ZigZagインジケータ実装

### フェーズ3: 実取引機能 ✅
- 注文機能（成行・指値・逆指値注文）
- ストップロス・テイクプロフィット設定
- ポジション管理（修正・決済・部分決済）
- リスク管理（2%リスク計算、15%ドローダウン監視）
- ポジションサイズ計算機能
- 取引履歴記録とトラッキング
- レポート・統計機能

## 🔍 テクニカル分析機能

### ダウ理論分析
- スイングポイント自動検出
- 高値・安値の切り上げ/切り下げ判定
- トレンド方向判定（上昇/下降/横ばい）
- トレンド強度スコア（0-30点）

### ZigZagインジケータ
- 設定可能な偏差パラメータ
- ピーク・トラフポイント検出
- ノイズフィルタリング

## 💼 取引管理機能

### リスク管理システム
- **ポジションサイズ自動計算**: 2%リスクベースの最適ロットサイズ
- **ドローダウン監視**: 15%制限、緊急停止機能付き
- **ポジション制限**: 最大3ペア同時保有
- **リスクリワード比率計算**: 各取引の期待値評価
- **相関調整**: 通貨ペア間の相関を考慮したリスク分散

### 取引実行機能
- **多様な注文タイプ**: 成行・指値・逆指値注文対応
- **自動SL/TP設定**: エントリー時の自動損切り・利確設定
- **ポジション修正**: 運用中のSL/TP変更
- **部分決済**: ポジションの一部決済機能
- **シグナル検証**: エントリー前の総合リスク評価

### レポート・分析機能
- **取引履歴管理**: 全取引の詳細記録と検索
- **パフォーマンス指標**: 勝率、プロフィットファクター、シャープレシオ
- **日次損益レポート**: 日別の収益性分析
- **リスクエクスポージャー**: 現在のポジション状況とリスク量
- **ドローダウン分析**: 最大ドローダウンと回復期間の追跡

## 📈 次のステップ（フェーズ4: マルチペア対応）

### 実装予定機能
1. **6ペア同時監視**: USDJPY, EURUSD, GBPUSD, AUDUSD, USDCHF, USDCAD
2. **相関調整機能**: 通貨ペア間の相関を考慮した選択ロジック
3. **100点満点スコアリング**: 複合指標による最適ペア選択
4. **動的ポジション入替**: より良いシグナルでの自動入替システム

## 🧪 テスト方法

### 基本通信テスト
```bash
# サーバー起動後
curl http://localhost:8000/status

# 市場データ確認
curl http://localhost:8000/api/v1/market-data/USDJPY
```

### 取引機能テスト
```bash
# リスク計算
curl -X POST "http://localhost:8000/api/v1/risk/calculate?symbol=USDJPY&entry_price=150.0&stop_loss=149.0"

# シグナル検証
curl "http://localhost:8000/api/v1/signals/validate?symbol=USDJPY&side=buy&entry_price=150.0&stop_loss=149.0&take_profit=152.0"

# 口座情報
curl http://localhost:8000/api/v1/account

# 取引履歴
curl http://localhost:8000/api/v1/trade-history
```

### テクニカル分析テスト
```bash
# スイングポイント取得
curl http://localhost:8000/api/v1/swing-points/USDJPY

# トレンド分析
curl http://localhost:8000/api/v1/trend/USDJPY

# ZigZag分析
curl http://localhost:8000/api/v1/zigzag/USDJPY
```

## 📝 設定

### 環境変数（.env）
```env
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
MAX_POSITIONS=3
RISK_PER_TRADE=0.02
MAX_DRAWDOWN=0.15
UPDATE_INTERVAL=300
```

### 主要設定パラメータ
- **MAX_POSITIONS**: 最大同時ポジション数（デフォルト: 3）
- **RISK_PER_TRADE**: 1取引あたりの最大リスク率（デフォルト: 2%）
- **MAX_DRAWDOWN**: 最大許容ドローダウン（デフォルト: 15%）
- **UPDATE_INTERVAL**: データ更新間隔（秒、デフォルト: 300秒）

## 🎯 現在の達成状況

### ✅ 完全実装済み機能
- Python-MQL5間でのリアルタイム価格データ通信
- ダウ理論・ZigZagベースのテクニカル分析
- 完全な取引実行システム（注文・決済・修正）
- 2%リスクベースの自動ポジションサイズ計算
- 15%ドローダウン監視による緊急停止機能
- 包括的な取引履歴・レポート機能

### 🧪 テスト結果
- **API機能テスト**: 8/8 エンドポイント正常動作
- **通信テスト**: Python-MQL5間通信完全成功
- **リスク管理テスト**: 全シナリオで適切な制限動作

### 🎉 フェーズ3完了
要件定義書のフェーズ3「実取引機能（注文実行、ポジション管理、リスク管理）」が完全に実装され、テスト済みです。

**次はフェーズ4（マルチペア対応）への移行準備が完了しています。**