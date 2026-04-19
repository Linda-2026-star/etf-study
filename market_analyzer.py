"""
市场环境自动分析器
根据趋势、估值、波动率、流动性、成交量、政策信号综合判断当前应使用的策略风格
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple


class MarketStyleAnalyzer:
    def __init__(self):
        self.cache = {}
        self.cache_time = None
        self.cache_ttl = 3600  # 缓存1小时

    def _is_cache_valid(self) -> bool:
        if self.cache_time is None:
            return False
        return (datetime.now() - self.cache_time).seconds < self.cache_ttl

    def analyze(self, force_refresh: bool = False) -> Dict:
        """
        分析当前市场环境，返回风格建议和参数
        返回格式：
        {
            'style': '保守' | '标准' | '激进',
            'score': {'trend': '标准', 'valuation': '保守', ...},
            'params': {'vol_ratio': 1.5, 'atr_max': 2.5, 'test_ratio': 0.10, 'main_ratio': 0.35},
            'reason': '估值偏贵，触发保护机制，建议保守',
            'valuation_level': 80.5,  # PE分位数
            'vix_level': 18.67,
            'turnover_avg': 2.4,      # 万亿
            'index_trend': 0.4,       # 宽基指数上涨比例
        }
        """
        if self._is_cache_valid() and not force_refresh:
            return self.cache

        # 获取各维度数据
        valuation = self._get_valuation()
        trend = self._get_trend_strength()
        liquidity = self._get_liquidity()
        vix = self._get_vix()
        volume = self._get_volume_heat()
        policy = self._get_policy_signal()

        # 各维度评分
        scores = {
            'trend': self._score_trend(trend),
            'valuation': self._score_valuation(valuation),
            'liquidity': self._score_liquidity(liquidity),
            'vix': self._score_vix(vix),
            'volume': self._score_volume(volume),
            'policy': policy
        }

        # 统计各风格特征数量
        style_counts = {'保守': 0, '标准': 0, '激进': 0}
        for _, style in scores.items():
            style_counts[style] = style_counts.get(style, 0) + 1

        # 极端保守触发条件检查
        extreme_conservative = False
        reasons = []

        # 估值极端贵（>85%分位）
        if valuation > 85:
            extreme_conservative = True
            reasons.append(f"中证全指PE分位数{valuation:.1f}% > 85%，估值过高")

        # VIX恐慌（>80%分位）
        if vix > 80:
            extreme_conservative = True
            reasons.append(f"VIX分位数{vix:.1f}% > 80%，市场恐慌")

        # 宽基指数破位（低于20日线比例>66%）
        if trend < 0.33:
            extreme_conservative = True
            reasons.append(f"宽基指数上涨比例仅{trend * 100:.0f}%，趋势偏弱")

        # 资金收紧（10年国债>3.5%）
        if liquidity == '收紧':
            extreme_conservative = True
            reasons.append("10年国债收益率>3.5%，流动性收紧")

        # 最终决策
        if extreme_conservative:
            final_style = '保守'
            main_reason = '；'.join(reasons[:2]) if reasons else '触发极端保守条件'
        elif style_counts['激进'] >= 3:
            final_style = '激进'
            main_reason = f"多项指标偏积极（激进指标{style_counts['激进']}个）"
        elif style_counts['保守'] >= 2:
            final_style = '保守'
            main_reason = f"偏谨慎指标较多（保守指标{style_counts['保守']}个）"
        else:
            final_style = '标准'
            main_reason = "各维度信号均衡"

        # 估值保护：即使其他维度激进，若估值>80%分位，降级且限制仓位
        if valuation > 80 and final_style == '激进':
            final_style = '标准'
            main_reason = f"估值分位{valuation:.1f}%偏高，降级为标准风格"
        elif valuation > 80 and final_style == '标准':
            final_style = '保守'
            main_reason = f"估值分位{valuation:.1f}%较高，降级为保守风格"

        # 构建参数
        params = self._get_style_params(final_style)

        result = {
            'style': final_style,
            'score': scores,
            'params': params,
            'reason': main_reason,
            'valuation_level': valuation,
            'vix_level': vix,
            'turnover_avg': volume,
            'index_trend': trend,
            'liquidity': liquidity,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.cache = result
        self.cache_time = datetime.now()
        return result

    def _get_style_params(self, style: str) -> Dict:
        """返回指定风格的策略参数"""
        styles = {
            '保守': {'vol_ratio': 1.5, 'atr_max': 2.5, 'test_ratio': 0.10, 'main_ratio': 0.35, 'max_position': 0.70},
            '标准': {'vol_ratio': 1.2, 'atr_max': 3.0, 'test_ratio': 0.12, 'main_ratio': 0.45, 'max_position': 0.80},
            '激进': {'vol_ratio': 1.0, 'atr_max': 4.0, 'test_ratio': 0.15, 'main_ratio': 0.55, 'max_position': 0.90}
        }
        return styles.get(style, styles['标准'])

    def _get_valuation(self) -> float:
        """获取中证全指PE-TTM历史分位数（模拟值，实际需接入数据源）"""
        try:
            # 中证全指代码：000985
            df = ak.stock_zh_index_value_csindex(symbol="000985")
            if df is not None and not df.empty:
                pe = float(df.iloc[-1]['pe'])
                # 简化：直接返回一个模拟分位数（实际应计算历史分位）
                # 这里用固定映射，当前PE约18-20对应70-80%分位
                if pe > 25:
                    return 90.0
                elif pe > 20:
                    return 80.0
                elif pe > 17:
                    return 60.0
                elif pe > 14:
                    return 40.0
                else:
                    return 20.0
        except:
            pass
        # 默认返回偏贵状态（保守倾向）
        return 80.0

    def _get_trend_strength(self) -> float:
        """计算主要宽基指数中，价格在20日均线上方的比例"""
        indices = ['sh000001', 'sz399001', 'sz399006', 'sh000300', 'sh000905']
        count_above = 0
        total = 0
        for idx in indices:
            try:
                df = ak.stock_zh_index_daily(symbol=idx)
                if df is not None and not df.empty:
                    df['ma20'] = df['close'].rolling(20).mean()
                    latest = df.iloc[-1]
                    if latest['close'] > latest['ma20']:
                        count_above += 1
                    total += 1
            except:
                continue
        if total == 0:
            return 0.5
        return count_above / total

    def _get_liquidity(self) -> str:
        """判断流动性环境"""
        try:
            # 获取10年期国债收益率
            df = ak.bond_zh_us_rate()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                y10 = float(latest['中国国债收益率10年'])
                if y10 > 3.5:
                    return '收紧'
                elif y10 < 2.5:
                    return '宽松'
                else:
                    return '中性'
        except:
            pass
        return '宽松'  # 当前实际约1.77%

    def _get_vix(self) -> float:
        """获取VIX恐慌指数历史分位数"""
        try:
            # 上证50ETF期权VIX
            df = ak.option_risk_indicator_sse()
            if df is not None and not df.empty:
                vix = float(df.iloc[-1]['vix'])
                # 计算近一年分位数
                recent = df.tail(250)['vix'].astype(float)
                rank = (recent < vix).sum() / len(recent) * 100
                return rank
        except:
            pass
        return 41.0  # 默认中等偏低

    def _get_volume_heat(self) -> float:
        """获取市场成交热度（日均成交额，万亿）"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            if df is not None and not df.empty:
                recent_volume = df.tail(5)['volume'].mean() / 1e8  # 转为亿
                # 沪深两市总成交约上证2.5倍估算
                total = recent_volume * 2.5 / 10000  # 万亿
                return total
        except:
            pass
        return 2.4  # 默认2.4万亿

    def _get_policy_signal(self) -> str:
        """政策信号判断"""
        # 简化：根据近期央行表态和利率水平判断
        liquidity = self._get_liquidity()
        if liquidity == '宽松':
            return '激进'
        elif liquidity == '收紧':
            return '保守'
        else:
            return '标准'

    def _score_trend(self, trend: float) -> str:
        if trend >= 0.6:
            return '激进'
        elif trend >= 0.3:
            return '标准'
        else:
            return '保守'

    def _score_valuation(self, valuation: float) -> str:
        if valuation <= 40:
            return '激进'
        elif valuation <= 70:
            return '标准'
        else:
            return '保守'

    def _score_liquidity(self, liquidity: str) -> str:
        if liquidity == '宽松':
            return '激进'
        elif liquidity == '中性':
            return '标准'
        else:
            return '保守'

    def _score_vix(self, vix: float) -> str:
        if vix <= 30:
            return '激进'
        elif vix <= 70:
            return '标准'
        else:
            return '保守'

    def _score_volume(self, volume: float) -> str:
        if volume >= 2.0:
            return '激进'
        elif volume >= 1.2:
            return '标准'
        else:
            return '保守'