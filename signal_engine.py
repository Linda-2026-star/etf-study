"""
小资金右侧波段策略 · 信号引擎优化版
规则：
- 入场：20日线上穿60日线 + 成交量放大(>1.2倍20日均量)
- 加仓：金叉后首次缩量回踩20日线不破，且出现涨幅>1.5%的确认阳线
- 持仓：试探仓(1-2成) → 主升仓(3-5成)
- 退场：收盘跌破20日线清仓；或跌破10日线减半仓
- 预警：单日涨幅>4%且成交量暴增，提示分批止盈
"""

"""
小资金右侧波段策略 · 信号引擎（支持动态风格参数）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class SignalEngine:
    def __init__(self, params: Optional[Dict] = None):
        """
        params: 策略参数字典，包含 vol_ratio, atr_max, test_ratio, main_ratio
        若不传则使用默认标准参数
        """
        if params is None:
            params = {'vol_ratio': 1.2, 'atr_max': 3.0, 'test_ratio': 0.12, 'main_ratio': 0.45}

        self.vol_ratio_threshold = params.get('vol_ratio', 1.2)
        self.atr_max = params.get('atr_max', 3.0)
        self.test_ratio = params.get('test_ratio', 0.12)
        self.main_ratio = params.get('main_ratio', 0.45)

        # 固定参数
        self.ma_short = 20
        self.ma_long = 60
        self.ma_trailing = 10
        self.pullback_ret_threshold = 0.015
        self.profit_warning_pct = 0.04

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.sort_values('date', inplace=True)
        df.reset_index(drop=True, inplace=True)

        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['ret'] = df['close'].pct_change()

        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift()))
        )
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_pct'] = df['atr'] / df['close'] * 100

        df['trend_bull'] = df['ma20'] > df['ma60']
        df['golden_cross'] = (df['ma20'] > df['ma60']) & (df['ma20'].shift(1) <= df['ma60'].shift(1))
        df['death_cross'] = (df['ma20'] < df['ma60']) & (df['ma20'].shift(1) >= df['ma60'].shift(1))
        df['vol_surge'] = df['vol_ratio'] > self.vol_ratio_threshold
        df['near_ma20'] = (df['close'] / df['ma20'] - 1).abs() < 0.02
        df['vol_shrink'] = df['volume'] < df['vol_ma20']
        df['pullback_confirm'] = (df['ret'] > self.pullback_ret_threshold) & (df['close'] > df['ma20'])
        df['surge_warning'] = (df['ret'] > self.profit_warning_pct) & df['vol_surge']

        position = 0
        positions = []
        golden_cross_date = None

        for i in range(len(df)):
            golden = df.loc[i, 'golden_cross']
            death = df.loc[i, 'death_cross']
            vol_ok = df.loc[i, 'vol_surge']
            near = df.loc[i, 'near_ma20']
            shrink = df.loc[i, 'vol_shrink']
            confirm = df.loc[i, 'pullback_confirm']
            close = df.loc[i, 'close']
            ma20 = df.loc[i, 'ma20']
            ma10 = df.loc[i, 'ma10']
            atr_pct = df.loc[i, 'atr_pct']

            if death:
                position = 0
                golden_cross_date = None
            elif position > 0 and close < ma20:
                position = 0
                golden_cross_date = None
            elif position == 2 and close < ma10:
                position = 1
            else:
                if position == 0 and golden and vol_ok and atr_pct < self.atr_max:
                    position = 1
                    golden_cross_date = df.loc[i, 'date']
                elif position == 1 and golden_cross_date is not None:
                    days_since = (df.loc[i, 'date'] - golden_cross_date).days
                    if days_since >= 2 and near and shrink and confirm:
                        position = 2

            positions.append(position)

        df['position'] = positions
        df['position_label'] = df['position'].map({0: '空仓', 1: '试探仓', 2: '主升仓'})
        df['signal_change'] = df['position'].diff().fillna(0)
        df['action'] = df.apply(lambda row: self._get_action(row), axis=1)
        return df

    def _get_action(self, row) -> str:
        if row['signal_change'] == 1 and row['position'] == 1:
            return '试探建仓'
        elif row['signal_change'] == 1 and row['position'] == 2:
            return '加仓至主升'
        elif row['signal_change'] < 0:
            return '清仓离场' if row['position'] == 0 else '减仓至试探'
        elif row['surge_warning'] and row['position'] > 0:
            return '加速预警·考虑减仓'
        else:
            return '持仓不变'

    def get_signal_summary(self, df: pd.DataFrame, code: str, name: str = '') -> Dict:
        latest = df.iloc[-1]
        return {
            'code': code,
            'name': name,
            'date': str(latest['date']),
            'close': round(latest['close'], 3),
            'ma20': round(latest['ma20'], 3),
            'ma60': round(latest['ma60'], 3),
            'ma10': round(latest['ma10'], 3),
            'vol_ratio': round(latest['vol_ratio'], 2),
            'trend': '多头' if latest['trend_bull'] else '空头',
            'position': int(latest['position']),
            'position_label': latest['position_label'],
            'action': latest['action'],
            'golden_cross': bool(latest['golden_cross']),
            'surge_warning': bool(latest['surge_warning']),
            'ret': f"{latest['ret'] * 100:.2f}%" if not pd.isna(latest['ret']) else '0.00%',
            'atr_pct': round(latest['atr_pct'], 2),
        }

    @staticmethod
    def scan_all_etfs(etf_list: List[tuple], fetcher, params: Dict, days: int = 200) -> List[Dict]:
        candidates = []
        engine = SignalEngine(params=params)
        for code, name, category in etf_list:
            df = fetcher.fetch_history(code, days=days)
            if df is None or df.empty:
                continue
            sig_df = engine.compute(df)
            if sig_df is None or sig_df.empty:
                continue
            latest = sig_df.iloc[-1]
            if (latest['golden_cross'] and
                    latest['vol_ratio'] > engine.vol_ratio_threshold and
                    latest['atr_pct'] < engine.atr_max):
                candidates.append({
                    'code': code, 'name': name, 'category': category,
                    'close': round(latest['close'], 3),
                    'ma20': round(latest['ma20'], 3),
                    'vol_ratio': round(latest['vol_ratio'], 2),
                    'atr_pct': round(latest['atr_pct'], 2),
                    'score': round(latest['vol_ratio'] * (1 - latest['atr_pct'] / 100), 3),
                    'date': str(latest['date'])[:10]
                })
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates