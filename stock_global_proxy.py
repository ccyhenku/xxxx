import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 模拟账户系统初始化 ---
if 'account' not in st.session_state:
    st.session_state.account = {"cash": 1000000.0, "positions": {}}

# --- 2. 页面配置 ---
st.set_page_config(page_title="A股决策与模拟实盘", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #020617; color: #cbd5e1; }
    .neon-text { color: #f43f5e; font-weight: bold; text-shadow: 0 0 10px rgba(244, 63, 94, 0.3); }
    .stock-card { background: #1e293b; padding: 18px; border-radius: 12px; border-left: 5px solid #f43f5e; margin-bottom: 12px; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# --- 3. 手动实现 RSI 指标 (替代 pandas_ta) ---
def calculate_rsi(df, periods=14):
    close_delta = df['close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.rolling(window=periods).mean()
    ma_down = down.rolling(window=periods).mean()
    rsi = ma_up / ma_down
    rsi = 100 - (100 / (1 + rsi))
    return rsi

# --- 4. 数据获取函数 ---
def get_safe_hist(code, start_d, end_d):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        df = df.rename(columns={'收盘': 'close', '开盘': 'open', '最高': 'high', '最低': 'low', '成交量': 'volume'})
        return df
    except: return None

# --- 5. 侧边栏 ---
with st.sidebar:
    st.markdown('<h2 class="neon-text">🧭 策略导航</h2>', unsafe_allow_html=True)
    strategy_type = st.selectbox("核心逻辑", ["趋势追踪", "极低抄底 (超跌反弹)"])
    sector_list = ["半导体", "银行", "煤炭行业", "酿酒行业", "汽车零部件"]
    choice = st.selectbox("选择行业", sector_list)

# --- 6. 主界面 ---
st.markdown(f'<h1 class="neon-text">📈 A股决策中心 · {strategy_type}</h1>', unsafe_allow_html=True)

# 账户摘要显示
c1, c2, c3 = st.columns(3)
c1.metric("可用现金", f"¥{st.session_state.account['cash']:,.2f}")
c2.metric("持仓个股", len(st.session_state.account['positions']))
total_value = st.session_state.account['cash'] + sum([p['qty'] * p['last_price'] for p in st.session_state.account['positions'].values()])
c3.metric("总资产", f"¥{total_value:,.2f}")

if st.button("🚀 启动深度扫描", use_container_width=True):
    results = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    
    with st.status(f"正在扫描 {choice} 板块...", expanded=True) as status:
        stocks = ak.stock_board_industry_cons_em(symbol=choice).head(15)
        for _, row in stocks.iterrows():
            hist = get_safe_hist(row['代码'], start_date, end_date)
            if hist is not None and len(hist) > 30:
                hist['ma20'] = hist['close'].rolling(20).mean()
                last_price = hist['close'].iloc[-1]
                
                is_match = False
                desc = ""
                
                if strategy_type == "趋势追踪":
                    if last_price > hist['ma20'].iloc[-1] and hist['ma20'].iloc[-1] > hist['ma20'].iloc[-2]:
                        is_match = True
                        desc = "均线多头"
                else:
                    rsi_series = calculate_rsi(hist)
                    last_rsi = rsi_series.iloc[-1]
                    if not pd.isna(last_rsi) and last_rsi < 32:
                        is_match = True
                        desc = f"超跌 (RSI:{int(last_rsi)})"
                
                if is_match:
                    results.append({"代码": row['代码'], "名称": row['名称'], "价格": last_price, "特征": desc})
        status.update(label="扫描完成！", state="complete")

    if results:
        for item in results:
            with st.container():
                st.markdown(f'<div class="stock-card"><b>{item["名称"]} ({item["代码"]})</b> | 价格: {item["价格"]} | {item["特征"]}</div>', unsafe_allow_html=True)
                if st.button(f"模拟买入 1000股 {item['名称']}", key=item['代码']):
                    cost = item['价格'] * 1000
                    if st.session_state.account['cash'] >= cost:
                        st.session_state.account['cash'] -= cost
                        st.session_state.account['positions'][item['代码']] = {"name": item['名称'], "qty": 1000, "last_price": item['价格']}
                        st.rerun()
                    else:
                        st.error("余额不足")
    else:
        st.info("暂无符合策略条件的股票。")

# --- 持仓管理 ---
if st.session_state.account['positions']:
    st.divider()
    st.subheader("💼 当前模拟持仓")
    for code, info in st.session_state.account['positions'].items():
        col_a, col_b = st.columns([4, 1])
        col_a.write(f"**{info['name']} ({code})** | 数量: {info['qty']} | 成本价: {info['last_price']}")
        if col_b.button("卖出平仓", key=f"sell_{code}"):
            st.session_state.account['cash'] += info['qty'] * info['last_price']
            del st.session_state.account['positions'][code]
            st.rerun()