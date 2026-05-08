import streamlit as st
import akshare as ak
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import time

# --- 1. 页面配置与模拟账户初始化 ---
st.set_page_config(page_title="A股全向决策中心", layout="wide")

# 初始化模拟账户数据
if 'account' not in st.session_state:
    st.session_state.account = {
        "cash": 1000000.0,       # 初始资金 100万
        "positions": {},         # 持仓字典 {代码: {名称, 数量, 成本价}}
        "history": []            # 交易历史
    }

st.markdown("""
<style>
    .stApp { background-color: #020617; color: #cbd5e1; }
    .neon-text { color: #f43f5e; font-weight: bold; text-shadow: 0 0 10px rgba(244, 63, 94, 0.3); }
    .stock-card { background: #1e293b; padding: 18px; border-radius: 12px; border-left: 5px solid #f43f5e; margin-bottom: 12px; border: 1px solid #334155; }
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .tag-blue { background: #1e3a8a; color: #60a5fa; }
    .tag-green { background: #064e3b; color: #34d399; }
    .tag-gold { background: #451a03; color: #fbbf24; }
    .tag-purple { background: #4c1d95; color: #c084fc; }
    .account-box { background: #0f172a; padding: 20px; border-radius: 10px; border: 1px dashed #334155; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 2. 核心数据函数 ---
def get_safe_hist(code, start_d, end_d):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        col_map = {'收盘': 'close', '开盘': 'open', '最高': 'high', '最低': 'low', 'Close': 'close', '成交量': 'volume'}
        df.rename(columns=col_map, inplace=True)
        return df
    except: return None

# --- 3. 模拟交易逻辑函数 ---
def execute_trade(code, name, price, action="买入"):
    qty = 1000  # 设定每次模拟买入/卖出 1000 股
    cost = price * qty
    
    if action == "买入":
        if st.session_state.account['cash'] >= cost:
            st.session_state.account['cash'] -= cost
            if code in st.session_state.account['positions']:
                p = st.session_state.account['positions'][code]
                new_qty = p['qty'] + qty
                new_price = (p['price'] * p['qty'] + cost) / new_qty
                st.session_state.account['positions'][code] = {"name": name, "qty": new_qty, "price": new_price}
            else:
                st.session_state.account['positions'][code] = {"name": name, "qty": qty, "price": price}
            st.toast(f"✅ 成功买入 {name} 1000股")
        else:
            st.error("资金不足，无法买入！")
            
    elif action == "卖出":
        if code in st.session_state.account['positions']:
            st.session_state.account['cash'] += cost
            del st.session_state.account['positions'][code]
            st.toast(f"💰 成功清仓 {name}")

def main_engine(sectors, mode_name, strategy_type="趋势追踪"):
    recommend_list = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")
    
    msg = st.empty()
    bar = st.progress(0)
    
    for i, sector in enumerate(sectors):
        msg.write(f"正在扫描【{sector}】板块中的{strategy_type}机会...")
        bar.progress((i + 1) / len(sectors))
        try:
            stocks = ak.stock_board_industry_cons_em(symbol=sector)
            if stocks is None or stocks.empty: continue
            
            for _, row in stocks.head(20).iterrows():
                code, name = row['代码'], row['名称']
                hist = get_safe_hist(code, start_date, end_date)
                
                if hist is not None and len(hist) >= 30:
                    hist['ma20'] = hist['close'].rolling(20).mean()
                    last = hist.iloc[-1]
                    
                    if strategy_type == "趋势追踪":
                        prev_ma20 = hist['ma20'].iloc[-2]
                        if last['close'] > last['ma20'] and last['ma20'] >= prev_ma20:
                            recommend_list.append({
                                "代码": code, "名称": name, "现价": round(last['close'], 2),
                                "当日涨幅": row['涨跌幅'], "所属板块": sector, "形态": "上升通道"
                            })
                    
                    elif strategy_type == "极低抄底 (超跌反弹)":
                        hist['rsi'] = ta.rsi(hist['close'], length=14)
                        bias = (last['close'] - last['ma20']) / last['ma20'] * 100
                        rsi_val = hist['rsi'].iloc[-1]
                        
                        if rsi_val < 35 or bias < -8:
                            recommend_list.append({
                                "代码": code, "名称": name, "现价": round(last['close'], 2),
                                "当日涨幅": row['涨跌幅'], "所属板块": sector, 
                                "形态": f"超跌 (RSI:{int(rsi_val)}/Bias:{int(bias)}%)"
                            })
                time.sleep(0.01)
        except: continue
    msg.empty()
    bar.empty()
    return pd.DataFrame(recommend_list)

# --- 4. 侧边栏策略配置 ---
with st.sidebar:
    st.markdown('<h2 class="neon-text">🧭 投资地图</h2>', unsafe_allow_html=True)
    strategy_type = st.selectbox("核心选股逻辑", ["趋势追踪", "极低抄底 (超跌反弹)"])
    
    STRATEGY_MAP = {
        "全球科技映射": {"tag": "tag-blue", "sectors": ["半导体", "通信设备", "软件开发", "互联网服务"]},
        "国内政策风口": {"tag": "tag-green", "sectors": ["航天航空", "通用设备", "汽车零部件", "电机"]},
        "避险红利资产": {"tag": "tag-gold", "sectors": ["煤炭行业", "银行", "电力行业", "石油行业", "公路铁路运输"]},
        "大消费复苏": {"tag": "tag-purple", "sectors": ["酿酒行业", "家电行业", "食品饮料", "旅游酒店"]}
    }
    
    choice = st.radio("选择覆盖行业", list(STRATEGY_MAP.keys()))
    current_sectors = STRATEGY_MAP[choice]["sectors"]
    current_tag = STRATEGY_MAP[choice]["tag"] if strategy_type == "趋势追踪" else "tag-purple"

# --- 5. 主界面布局 ---
tab1, tab2 = st.tabs(["🔍 智能选股", "💼 模拟账户"])

with tab1:
    st.markdown(f'<h1 class="neon-text">📈 A股决策中心 · {strategy_type}</h1>', unsafe_allow_html=True)

    if st.button("🚀 启动深度扫描", use_container_width=True):
        with st.spinner(f"正在分析市场数据，寻找{strategy_type}机会..."):
            df_res = main_engine(current_sectors, choice, strategy_type)
            
            if not df_res.empty:
                st.success(f"扫描完毕！找到 {len(df_res)} 只符合【{strategy_type}】特征的个股。")
                df_res = df_res.sort_values("当日涨幅", ascending=False)
                
                for _, row in df_res.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="stock-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:20px; font-weight:bold;">{row['名称']} <small style="color:#64748b;">{row['代码']}</small></span>
                                <span style="color:#ef4444; font-size:22px; font-weight:bold;">{row['当日涨幅']}%</span>
                            </div>
                            <div style="margin-top:10px; font-size:14px;">
                                <span class="tag {current_tag}">{strategy_type}</span>
                                <span style="margin-left:10px; color:#94a3b8;">板块: {row['所属板块']} | 现价: {row['现价']}</span>
                                <span style="float:right; color:#4ade80;">特征: {row['形态']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        # 新增：买入按钮
                        if st.button(f"🛒 模拟买入 1000股 {row['名称']}", key=f"buy_{row['代码']}"):
                            execute_trade(row['代码'], row['名称'], row['现价'], "买入")

                with st.expander("📊 查看完整统计表"):
                    st.dataframe(df_res, use_container_width=True)
            else:
                st.warning(f"⚠️ 暂未发现符合{strategy_type}条件的个股。")

with tab2:
    st.markdown('<h2 class="neon-text">💼 我的模拟实盘</h2>', unsafe_allow_html=True)
    
    # 账户资金卡片
    cash = st.session_state.account['cash']
    mv = sum([v['qty'] * v['price'] for v in st.session_state.account['positions'].values()])
    total = cash + mv
    
    c1, c2, c3 = st.columns(3)
    c1.metric("可用现金", f"¥{cash:,.2f}")
    c2.metric("持仓市值", f"¥{mv:,.2f}")
    c3.metric("总资产", f"¥{total:,.2f}", delta=f"{total-1000000:,.2f}")
    
    st.divider()
    
    # 持仓列表
    if st.session_state.account['positions']:
        st.write("### 📝 当前持仓明细")
        for code, info in st.session_state.account['positions'].items():
            col_pos1, col_pos2 = st.columns([4, 1])
            with col_pos1:
                st.info(f"**{info['name']} ({code})** | 持有: {info['qty']}股 | 成本价: {info['price']:.2f}")
            with col_pos2:
                if st.button(f"一键清仓", key=f"sell_{code}"):
                    execute_trade(code, info['name'], info['price'], "卖出")
                    st.rerun()
    else:
        st.write("目前暂无持仓，快去选股中心扫描并买入吧！")

    if st.button("🔄 重置账户"):
        st.session_state.account = {"cash": 1000000.0, "positions": {}, "history": []}
        st.rerun()

st.divider()
st.info("💡 **操作提示**：扫描出股票后，直接点击卡片下方的‘模拟买入’即可建仓。账户数据存放在浏览器会话中，刷新页面不会丢失，但关闭标签页可能会重置。")
