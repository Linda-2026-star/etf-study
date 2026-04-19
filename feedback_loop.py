"""
反馈自迭代优化机制
- 记录每笔交易信号及结果
- 定期评估策略绩效
- 自动搜索更优参数
- 版本化管理策略配置
"""

import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import itertools


@dataclass
class TradeRecord:
    """单笔交易记录"""
    symbol: str
    entry_date: str
    entry_price: float
    entry_signal: str  # 试探建仓 / 加仓至主升
    shares: int
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 止损 / 止盈 / 信号离场
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    max_profit_pct: Optional[float] = None  # 持仓期间最大浮盈
    max_loss_pct: Optional[float] = None  # 持仓期间最大浮亏


class TradeLogger:
    """交易日志记录器（SQLite）"""

    def __init__(self, db_path: str = "trades.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS trades
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              symbol
                              TEXT
                              NOT
                              NULL,
                              entry_date
                              TEXT
                              NOT
                              NULL,
                              entry_price
                              REAL
                              NOT
                              NULL,
                              entry_signal
                              TEXT
                              NOT
                              NULL,
                              shares
                              INTEGER
                              NOT
                              NULL,
                              exit_date
                              TEXT,
                              exit_price
                              REAL,
                              exit_reason
                              TEXT,
                              pnl
                              REAL,
                              pnl_pct
                              REAL,
                              max_profit_pct
                              REAL,
                              max_loss_pct
                              REAL,
                              status
                              TEXT
                              DEFAULT
                              'OPEN'
                          )
                          """)
        self.conn.commit()

    def log_entry(self, record: TradeRecord):
        """记录开仓"""
        self.conn.execute("""
                          INSERT INTO trades (symbol, entry_date, entry_price, entry_signal, shares, status)
                          VALUES (?, ?, ?, ?, ?, 'OPEN')
                          """, (record.symbol, record.entry_date, record.entry_price,
                                record.entry_signal, record.shares))
        self.conn.commit()

    def log_exit(self, symbol: str, exit_date: str, exit_price: float,
                 exit_reason: str, max_profit: float, max_loss: float):
        """记录平仓（更新最近一笔该标的的开仓记录）"""
        # 找到该标的最新的未平仓记录
        cursor = self.conn.execute("""
                                   SELECT id, entry_price, shares
                                   FROM trades
                                   WHERE symbol = ?
                                     AND status = 'OPEN'
                                   ORDER BY entry_date DESC LIMIT 1
                                   """, (symbol,))
        row = cursor.fetchone()
        if row:
            trade_id, entry_price, shares = row
            pnl = (exit_price - entry_price) * shares
            pnl_pct = (exit_price / entry_price - 1) * 100
            self.conn.execute("""
                              UPDATE trades
                              SET exit_date      = ?,
                                  exit_price     = ?,
                                  exit_reason    = ?,
                                  pnl            = ?,
                                  pnl_pct        = ?,
                                  max_profit_pct = ?,
                                  max_loss_pct   = ?,
                                  status         = 'CLOSED'
                              WHERE id = ?
                              """, (exit_date, exit_price, exit_reason, pnl, pnl_pct,
                                    max_profit, max_loss, trade_id))
            self.conn.commit()

    def get_closed_trades(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """获取已平仓交易记录"""
        query = "SELECT * FROM trades WHERE status = 'CLOSED'"
        if symbol:
            query += f" AND symbol = '{symbol}'"
        return pd.read_sql_query(query, self.conn)

    def get_all_trades(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM trades", self.conn)


class PerformanceEvaluator:
    """绩效评估器"""

    @staticmethod
    def calculate_metrics(trades_df: pd.DataFrame, capital: float = 100000) -> Dict:
        """
        计算核心绩效指标
        - 总收益率、年化收益率
        - 夏普比率
        - 最大回撤
        - 胜率、盈亏比
        - 单笔最大盈利/亏损
        """
        if trades_df.empty:
            return {"error": "无交易记录"}

        # 按时间排序
        trades_df = trades_df.sort_values('entry_date')

        # 计算累计收益曲线
        pnl_series = trades_df['pnl'].fillna(0).values
        cumulative_pnl = np.cumsum(pnl_series)
        equity_curve = capital + cumulative_pnl

        # 总收益率
        total_return = (equity_curve[-1] / capital - 1) * 100

        # 年化收益率（假设交易跨度）
        first_date = pd.to_datetime(trades_df['entry_date'].min())
        last_date = pd.to_datetime(trades_df['exit_date'].max() if 'exit_date' in trades_df else datetime.now())
        years = (last_date - first_date).days / 365.25
        annual_return = ((1 + total_return / 100) ** (1 / max(years, 0.1)) - 1) * 100 if years > 0 else 0

        # 最大回撤
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak * 100
        max_drawdown = drawdown.min()

        # 胜率
        win_trades = trades_df[trades_df['pnl'] > 0]
        win_rate = len(win_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0

        # 盈亏比
        avg_win = win_trades['pnl'].mean() if len(win_trades) > 0 else 0
        loss_trades = trades_df[trades_df['pnl'] < 0]
        avg_loss = abs(loss_trades['pnl'].mean()) if len(loss_trades) > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # 夏普比率（简化版，假设无风险利率为0）
        daily_returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 1 else 0

        # 综合评分（用于参数比较）
        score = (total_return * 0.3 +
                 (100 + max_drawdown) * 0.3 +  # 回撤越小越好
                 win_rate * 0.2 +
                 min(profit_factor, 3) * 10 * 0.2)

        return {
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trade_count": len(trades_df),
            "score": round(score, 2),
            "first_date": first_date.strftime('%Y-%m-%d'),
            "last_date": last_date.strftime('%Y-%m-%d'),
        }


class ParameterOptimizer:
    """参数优化引擎"""

    def __init__(self, data_fetcher, etf_pool, eval_days: int = 180):
        self.fetcher = data_fetcher
        self.etf_pool = etf_pool
        self.eval_days = eval_days

    def grid_search(self, param_ranges: Dict) -> List[Dict]:
        results = []
        keys = list(param_ranges.keys())
        values = list(param_ranges.values())

        total_combinations = np.prod([len(v) for v in values])
        print(f"开始网格搜索，共 {total_combinations} 组参数...")

        for i, combo in enumerate(itertools.product(*values)):
            params = dict(zip(keys, combo))
            params['main_ratio'] = params['test_ratio'] * 3.5
            params['max_position'] = 0.8

            metrics = self._backtest_params(params)
            if metrics:
                metrics['params'] = params
                results.append(metrics)
            else:
                print(f"参数组 {params} 回测无有效交易记录，跳过")

            if (i + 1) % 10 == 0:
                print(f"进度: {i + 1}/{total_combinations}")

        print(f"网格搜索完成，有效结果 {len(results)} 组")
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return results

    def _backtest_params(self, params: Dict) -> Optional[Dict]:
        from signal_engine import SignalEngine
        engine = SignalEngine(params=params)

        all_trades = []
        tested_count = 0
        for code, name, category in self.etf_pool[:10]:
            df = self.fetcher.fetch_history(code, days=self.eval_days)
            if df is None or df.empty:
                print(f"  ⚠️ {code} 数据获取失败")
                continue

            sig_df = engine.compute(df)
            trades = self._simulate_trades(sig_df, code, params)
            if trades:
                all_trades.extend(trades)
            tested_count += 1

        print(f"回测参数 {params}：测试了 {tested_count} 只ETF，共 {len(all_trades)} 笔交易")

        if not all_trades:
            return None

        trades_df = pd.DataFrame(all_trades)
        evaluator = PerformanceEvaluator()
        return evaluator.calculate_metrics(trades_df)

    def _simulate_trades(self, sig_df: pd.DataFrame, code: str, params: Dict) -> List[Dict]:
        """模拟交易记录"""
        trades = []
        position = 0
        entry_price = 0
        entry_date = None
        max_price = 0
        min_price = float('inf')

        for i, row in sig_df.iterrows():
            close = row['close']
            action = row['action']

            if position == 0 and action == '试探建仓':
                position = int(100000 * params['test_ratio'] / close // 100) * 100
                entry_price = close
                entry_date = row['date']
                max_price = close
                min_price = close

            elif position > 0:
                max_price = max(max_price, close)
                min_price = min(min_price, close)

                # 离场条件：清仓离场 或 跌破20日线
                if action == '清仓离场' or close < row['ma20']:
                    pnl = (close - entry_price) * position
                    trades.append({
                        'symbol': code,
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': row['date'],
                        'exit_price': close,
                        'pnl': pnl,
                        'max_profit': (max_price / entry_price - 1) * 100,
                        'max_loss': (min_price / entry_price - 1) * 100,
                    })
                    position = 0

        return trades


class StrategyVersionManager:
    """策略版本管理器"""

    def __init__(self, config_path: str = "strategy_versions.json"):
        self.config_path = config_path
        self.versions = self._load()

    def _load(self) -> List[Dict]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_version(self, params: Dict, metrics: Dict, notes: str = ""):
        """保存新版本"""
        version = {
            "version_id": len(self.versions) + 1,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "params": params,
            "metrics": metrics,
            "notes": notes,
            "is_active": False
        }
        self.versions.append(version)
        self._save()
        return version['version_id']

    def set_active(self, version_id: int):
        """激活指定版本"""
        for v in self.versions:
            v['is_active'] = (v['version_id'] == version_id)
        self._save()

    def get_active(self) -> Optional[Dict]:
        for v in self.versions:
            if v.get('is_active'):
                return v
        return None

    def _save(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.versions, f, ensure_ascii=False, indent=2)

    def get_best_version(self, metric: str = 'score') -> Optional[Dict]:
        """获取历史最佳版本"""
        if not self.versions:
            return None
        return max(self.versions, key=lambda x: x['metrics'].get(metric, 0))