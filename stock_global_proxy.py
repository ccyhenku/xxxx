import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 模拟账户初始化 ---
if 'account' not in st.session_state:
    st.session_state.account = {"cash": 1000000.0, "positions": {}}

st.set_page_config(page_title="A股全维度决策终端", layout="wide")

# --- 2. 核心算法 (手写指标避开依赖地雷) ---
def calculate_rsi(df, n=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_safe_hist(code, start_d, end_d):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        df.rename(columns={'收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
        return df
    except: return None

# --- 3. 样式表 ---
st.markdown("""
<style>
    .stApp { background-color: #020617; color: #cbd5e1; }
    .neon-text { color: #f43f5e; font-weight: bold; text-shadow: 0 0 10px rgba(244, 63, 94, 0.3); }
    .stock-card { background: #1e293b; padding: 15px; border-radius: 12px; border-left: 5px solid #f43f5e; margin-bottom: 10px; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# --- 4. 侧边栏：极速扩展的行业矩阵 ---
with st.sidebar:
    st.markdown('<h2 class="neon-text">🧭 行业矩阵</h2>', unsafe_allow_html=True)
    strategy_type = st.selectbox("核心逻辑", ["趋势追踪", "极低抄底 (超跌反弹)"])
    
    # 扩展后的多行业字典
    INDUSTRY_GROUPS = {
        "🔥 核心科技": ["半导体", "通信设备", "消费电子", "软件开发", "光学光电子"],
        "🛸 未来赛道": ["机器人", "航天航空", "通用设备", "专用设备", "计算机设备"],
        "🔋 能源电力": ["电力行业", "煤炭行业", "电网设备", "光伏设备", "风电设备"],
        "🚗 工业制造": ["汽车零部件", "工程机械", "电机", "仪器仪表", "轨道交通设备"],
        "💊 医药健康": ["中药", "生物制品", "医疗器械", "化学制药", "医疗服务"],
        "🏙️ 基建消费": ["酿酒行业", "家电行业", "装修建材", "旅游酒店", "物流行业"],
        "💰 金融红利": ["银行", "证券", "保险", "公路铁路运输", "港口航运"]
    }
    
    group_choice = st.radio("选择扫描领域", list(INDUSTRY_GROUPS.keys()))
    selected_sectors = INDUSTRY_GROUPS[group_choice]

# --- 5. 主界面 ---
tab1, tab2 = st.tabs(["🔍 全行业深度扫描", "💼 模拟实盘持仓"])

with tab1:
    st.markdown(f'<h1 class="neon-text">🚀 决策扫描 · {group_choice}</h1>', unsafe_allow_html=True)
    
    if st.button("🔥 立即执行全量扫描", use_container_width=True):
        results = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")
        
        progress_text = st.empty()
        p_bar = st.progress(0)
        
        for i, sector in enumerate(selected_sectors):
            progress_text.write(f"正在穿透分析：{sector}...")
            p_bar.progress((i + 1) / len(selected_sectors))
            try:
                # 获取行业成分股
                stocks = ak.stock_board_industry_cons_em(symbol=sector).head(15)
                for _, row in stocks.iterrows():
                    hist = get_safe_hist(row['代码'], start_date, end_date)
                    if hist is not None and len(hist) > 30:
                        hist['ma20'] = hist['close'].rolling(20).mean()
                        last_price = hist['close'].iloc[-1]
                        
                        is_match = False
                        if strategy_type == "趋势追踪":
                            # 逻辑：价格在20日线上方，且均线趋势向上
                            if last_price > hist['ma20'].iloc[-1] and hist['ma20'].iloc[-1] >= hist['ma20'].iloc[-2]:
                                is_match = True
                        else:
                            # 抄底逻辑：RSI < 30 或 乖离率严重
                            rsi = calculate_rsi(hist).iloc[-1]
                            bias = (last_price - hist['ma20'].iloc[-1]) / hist['ma20'].iloc[-1] * 100
                            if (not pd.isna(rsi) and rsi < 32) or bias < -10:
                                is_match = True
                        
                        if is_match:
                            results.append({"代码": row['代码'], "名称": row['名称'], "现价": last_price, "涨幅": row['涨跌幅'], "行业": sector})
            except: continue
        
        p_bar.empty()
        progress_text.empty()
        
        if results:
            st.success(f"扫描完成！在 {group_choice} 中发现 {len(results)} 个符合条件的标的")
            for item in results:
                with st.container():
                    st.markdown(f"""
                    <div class="stock-card">
                        <span style="font-size:18px; font-weight:bold;">{item['名称']} ({item['代码']})</span>
                        <span style="float:right; color:#ef4444; font-size:18px;">{item['涨幅']}%</span><br/>
                        <small>行业: {item['行业']} | 现价: {item['现价']}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"🛒 模拟买入 1000股 {item['名称']}", key=f"buy_{item['代码']}"):
                        cost = item['现价'] * 1000
                        if st.session_state.account['cash'] >= cost:
                            st.session_state.account['cash'] -= cost
                            st.session_state.account['positions'][item['代码']] = {"name": item['名称'], "qty": 1000, "price": item['现价']}
                            st.rerun()
                        else:
                            st.error("余额不足")
        else:
            st.warning("当前筛选条件下未发现匹配个股，建议切换行业组或策略逻辑。")

with tab2:
    st.markdown('<h2 class="neon-text">📊 模拟盘状态</h2>', unsafe_allow_html=True)
    cash = st.session_state.account['cash']
    mv = sum([v['qty'] * v['price'] for v in st.session_state.account['positions'].values()])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("可用现金", f"¥{cash:,.2f}")
    col2.metric("持仓市值", f"¥{mv:,.2f}")
    col3.metric("资产总值", f"¥{cash + mv:,.2f}", delta=f"{cash+mv-1000000:,.2f}")
    
    st.divider()
    if st.session_state.account['positions']:
        for code, info in st.session_state.account['positions'].items():
            c_a, c_b = st.columns([4, 1])
            c_a.info(f"**{info['name']} ({code})** | 持有: {info['qty']} | 成本: {info['price']}")
            if c_b.button("一键清仓", key=f"sell_{code}"):
                st.session_state.account['cash'] += info['qty'] * info['price']
                del st.session_state.account['positions'][code]
                st.rerun()
    else:
        st.write("暂无持仓，请先从选股中心扫描买入。")
