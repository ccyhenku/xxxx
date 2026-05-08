import streamlit as st
import akshare as ak
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 模拟账户系统初始化 ---
if 'account' not in st.session_state:
    st.session_state.account = {"cash": 1000000.0, "positions": {}}

# --- 2. 页面配置 ---
st.set_page_config(page_title="A股全向决策中心", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #020617; color: #cbd5e1; }
    .neon-text { color: #f43f5e; font-weight: bold; text-shadow: 0 0 10px rgba(244, 63, 94, 0.3); }
    .stock-card { background: #1e293b; padding: 18px; border-radius: 12px; border-left: 5px solid #f43f5e; margin-bottom: 12px; border: 1px solid #334155; }
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .tag-blue { background: #1e3a8a; color: #60a5fa; }
    .tag-purple { background: #4c1d95; color: #c084fc; }
</style>
""", unsafe_allow_html=True)

# --- 3. 手动实现 RSI 指标 (不依赖 pandas_ta) ---
def calc_rsi(df, n=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 4. 增强型数据函数 ---
def get_safe_hist(code, start_d, end_d):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        df.rename(columns={'收盘': 'close', '开盘': 'open', '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        return df
    except: return None

# --- 5. 侧边栏与主逻辑 ---
with st.sidebar:
    st.markdown('<h2 class="neon-text">🧭 投资地图</h2>', unsafe_allow_html=True)
    strategy_type = st.selectbox("核心选股逻辑", ["趋势追踪", "极低抄底 (超跌反弹)"])
    STRATEGY_MAP = {
        "全球科技映射": ["半导体", "通信设备", "软件开发"],
        "避险红利资产": ["煤炭行业", "银行", "电力行业"],
        "大消费复苏": ["酿酒行业", "家电行业", "旅游酒店"]
    }
    choice = st.radio("选择覆盖行业", list(STRATEGY_MAP.keys()))
    current_sectors = STRATEGY_MAP[choice]

tab1, tab2 = st.tabs(["🔍 智能选股", "💼 模拟账户"])

with tab1:
    st.markdown(f'<h1 class="neon-text">📈 决策中心 · {strategy_type}</h1>', unsafe_allow_html=True)
    if st.button("🚀 启动深度扫描", use_container_width=True):
        results = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")
        
        p_bar = st.progress(0)
        for i, sector in enumerate(current_sectors):
            p_bar.progress((i+1)/len(current_sectors))
            try:
                stocks = ak.stock_board_industry_cons_em(symbol=sector).head(10)
                for _, row in stocks.iterrows():
                    hist = get_safe_hist(row['代码'], start_date, end_date)
                    if hist is not None and len(hist) > 30:
                        hist['ma20'] = hist['close'].rolling(20).mean()
                        last = hist.iloc[-1]
                        match = False
                        if strategy_type == "趋势追踪" and last['close'] > last['ma20']:
                            match = True
                        elif strategy_type == "极低抄底 (超跌反弹)":
                            rsi = calc_rsi(hist).iloc[-1]
                            if rsi < 32: match = True
                        
                        if match:
                            results.append({"代码": row['代码'], "名称": row['名称'], "现价": last['close'], "涨幅": row['涨跌幅']})
            except: continue
            
        for item in results:
            with st.container():
                st.markdown(f'<div class="stock-card"><b>{item["名称"]} ({item["代码"]})</b> | 现价: {item["现价"]} | 涨幅: {item["涨幅"]}%</div>', unsafe_allow_html=True)
                if st.button(f"模拟买入 1000股 {item['名称']}", key=item['代码']):
                    st.session_state.account['cash'] -= item['现价'] * 1000
                    st.session_state.account['positions'][item['代码']] = {"name": item['名称'], "price": item['现价'], "qty": 1000}
                    st.success("已存入模拟持仓")

with tab2:
    st.write(f"### 可用资金: ¥{st.session_state.account['cash']:,.2f}")
    for code, info in st.session_state.account['positions'].items():
        col_a, col_b = st.columns([4, 1])
        col_a.info(f"{info['name']} ({code}) | 成本: {info['price']} | 数量: {info['qty']}")
        if col_b.button("清仓", key=f"sell_{code}"):
            st.session_state.account['cash'] += info['price'] * info['qty']
            del st.session_state.account['positions'][code]
            st.rerun()
