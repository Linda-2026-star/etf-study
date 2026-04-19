import time
import pandas as pd
import akshare as ak
import yfinance as yf
import baostock as bs
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

class DataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.prefix_map = {'5': 'sh', '1': 'sh', '0': 'sz', '3': 'sz', '2': 'sz'}
        self.bs_login_flag = False

    def fetch_history(self, code: str, days: int = 200) -> Optional[pd.DataFrame]:
        df = self._fetch_from_baostock(code, days)
        if df is not None and not df.empty:
            return df
        time.sleep(0.5)
        df = self._fetch_from_akshare(code, days)
        if df is not None and not df.empty:
            return df
        time.sleep(0.5)
        df = self._fetch_from_yfinance(code, days)
        if df is not None and not df.empty:
            return df
        time.sleep(0.5)
        df = self._fetch_from_efinance(code, days)
        return df

    def _fetch_from_baostock(self, code: str, days: int) -> Optional[pd.DataFrame]:
        try:
            if not self.bs_login_flag:
                lg = bs.login()
                if lg.error_code != '0':
                    return None
                self.bs_login_flag = True
            prefix = 'sz' if code.startswith(('0', '3', '1', '2')) else 'sh'
            bs_code = f"{prefix}.{code}"
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            rs = bs.query_history_k_data_plus(bs_code, "date,open,high,low,close,volume",
                                              start_date=start, end_date=end,
                                              frequency="d", adjustflag="2")
            if rs.error_code != '0':
                return None
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return None
            df = pd.DataFrame(data_list, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.sort_values('date', inplace=True)
            return df[df['volume'] > 0][['date', 'open', 'high', 'low', 'close', 'volume']]
        except:
            return None

    def _fetch_from_akshare(self, code: str, days: int) -> Optional[pd.DataFrame]:
        try:
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq")
            df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                               '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'high', 'low', 'close', 'volume']]
        except:
            return None

    def _fetch_from_yfinance(self, code: str, days: int) -> Optional[pd.DataFrame]:
        try:
            suffix = '.SZ' if code.startswith(('0', '3', '1', '2')) else '.SS'
            ticker = f"{code}{suffix}"
            end = datetime.now()
            start = end - timedelta(days=days)
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty:
                return None
            df = df.reset_index()
            df.columns = [col.lower() for col in df.columns]
            return df[['date', 'open', 'high', 'low', 'close', 'volume']]
        except:
            return None

    def _fetch_from_efinance(self, code: str, days: int) -> Optional[pd.DataFrame]:
        try:
            import efinance as ef
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            df = ef.stock.get_quote_history(code, beg=start_date, end=end_date)
            df = df[df['成交量'] > 0]
            df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                               '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'high', 'low', 'close', 'volume']]
        except:
            return None

    def fetch_realtime(self, codes: list) -> Dict:
        def _code_to_sina_format(code: str) -> str:
            prefix = self.prefix_map.get(code[0], 'sh')
            return f"{prefix}{code}"
        if not codes:
            return {}
        sina_codes = [_code_to_sina_format(c) for c in codes]
        url = f"https://hq.sinajs.cn/rn={int(datetime.now().timestamp()*1000)}&list={','.join(sina_codes)}"
        try:
            resp = self.session.get(url, timeout=2)
            resp.encoding = 'gbk'
            text = resp.text
            result = {}
            for i, raw_code in enumerate(codes):
                sina_code = sina_codes[i]
                if f"hq_str_{sina_code}" not in text:
                    continue
                data_str = text.split(f'hq_str_{sina_code}="')[1].split('";')[0]
                fields = data_str.split(',')
                result[raw_code] = {
                    'name': fields[0], 'open': float(fields[1]), 'lastClose': float(fields[2]),
                    'lastPrice': float(fields[3]), 'high': float(fields[4]), 'low': float(fields[5]),
                    'volume': int(float(fields[8])), 'timestamp': f"{fields[30]} {fields[31]}"
                }
            return result
        except:
            return {}