import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 账户持久化 (防止刷新丢失) ---
if 'account' not in st.session_state:
    st.session_state.account = {"cash": 1000000.0, "positions": {}}

# --- 2. 字段自适应的数据获取函数 ---
def get_safe_hist(code, start_d, end_d):
    try:
        # 增加延时防止被封 IP
        time.sleep(0.2) 
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        
        # 自动识别中英文列名
        col_map = {'收盘': 'close', '开盘': 'open', '最高': 'high', '最低': 'low', 'Close': 'close'}
        df.rename(columns=col_map, inplace=True)
        return df
    except Exception as e:
        return None

# --- 3. 手写核心指标 (避开环境兼容性问题) ---
def calc_rsi(df, n=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 4. 主界面设计 ---
st.title("🛡️ A股全向决策中心 (云端稳定版)")

with st.sidebar:
    strategy = st.selectbox("策略逻辑", ["趋势追踪", "极低抄底"])
    sector = st.selectbox("行业板块", ["半导体", "煤炭行业", "汽车零部件", "中药", "酿酒行业"])

tab1, tab2 = st.tabs(["🔍 智能选股", "💼 模拟持仓"])

with tab1:
    if st.button("🚀 启动深度扫描", use_container_width=True):
        results = []
        # 云端建议扫描范围不要太大
        try:
            stocks = ak.stock_board_industry_cons_em(symbol=sector).head(30)
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            
            p_bar = st.progress(0)
            for i, row in stocks.iterrows():
                p_bar.progress((i + 1) / len(stocks))
                hist = get_safe_hist(row['代码'], start_date, end_date)
                
                if hist is not None and len(hist) > 20:
                    hist['ma20'] = hist['close'].rolling(20).mean()
                    last_price = hist['close'].iloc[-1]
                    
                    is_match = False
                    if strategy == "趋势追踪":
                        if last_price > hist['ma20'].iloc[-1] and hist['ma20'].iloc[-1] > hist['ma20'].iloc[-2]:
                            is_match = True
                    else:
                        rsi = calc_rsi(hist).iloc[-1]
                        if not pd.isna(rsi) and rsi < 40: # 稍微放宽阈值
                            is_match = True
                            
                    if is_match:
                        results.append({"code": row['代码'], "name": row['名称'], "price": last_price})
            
            if results:
                for item in results:
                    st.success(f"候选股: {item['name']} ({item['code']}) | 价格: {item['price']}")
                    if st.button(f"模拟买入 {item['name']}", key=item['code']):
                        st.session_state.account['cash'] -= item['price'] * 1000
                        st.session_state.account['positions'][item['code']] = {"name": item['name'], "price": item['price']}
                        st.rerun()
            else:
                st.warning("未发现匹配，可能是该板块目前均处于调整期或接口响应过慢。")
        except Exception as e:
            st.error(f"接口调用超时: 请稍后再试。")

with tab2:
    st.write(f"### 可用资金: ¥{st.session_state.account['cash']:,.2f}")
    # 模拟持仓列表... (同前)
