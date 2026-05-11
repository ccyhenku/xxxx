import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 页面配置 (完全保留您的原始样式) ---
st.set_page_config(page_title="A股全向决策中心", layout="wide")

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
</style>
""", unsafe_allow_html=True)

# --- 2. 核心算法函数 (云端稳定性增强) ---

def get_safe_hist(code, start_d, end_d):
    """
    云端数据抓取核心：增加延迟防封，增加列名强制映射
    """
    try:
        # 云端必须延迟，否则IP会被东方财富拦截
        time.sleep(0.3) 
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, end_date=end_d, adjust="qfq")
        if df is None or df.empty: return None
        
        # 强制标准化列名，防止云端环境出现中文乱码或字段名变动
        df.columns = df.columns.str.replace(' ', '')
        col_map = {'收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'}
        df.rename(columns=col_map, inplace=True)
        
        # 确保收盘价为浮点数
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        return df.dropna(subset=['close'])
    except:
        return None

def calculate_rsi(prices, period=14):
    """
    手动实现 RSI 算法，彻底摆脱 pandas_ta 导致的云端环境崩溃
    """
    if len(prices) < period: return np.zeros(len(prices))
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / (down + 1e-10)
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)
    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        if delta > 0: upval, downval = delta, 0.
        else: upval, downval = 0., -delta
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / (down + 1e-10)
        rsi[i] = 100. - 100. / (1. + rs)
    return rsi

def main_engine(sectors, strategy_type):
    recommend_list = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    
    msg = st.empty()
    bar = st.progress(0)
    
    for i, sector in enumerate(sectors):
        msg.write(f"正在深度穿透：【{sector}】板块...")
        bar.progress((i + 1) / len(sectors))
        try:
            # 云端建议扫描深度限制在20只，保证稳定性和速度平衡
            stocks = ak.stock_board_industry_cons_em(symbol=sector).head(20)
            
            for _, row in stocks.iterrows():
                hist = get_safe_hist(row['代码'], start_date, end_date)
                
                if hist is not None and len(hist) >= 30:
                    prices = hist['close'].values
                    ma20 = hist['close'].rolling(20).mean().values
                    
                    is_match = False
                    status_desc = ""
                    
                    if strategy_type == "趋势追踪":
                        # 核心逻辑：价格在20日线上方，且20日线近期没有下跌趋势
                        if prices[-1] > ma20[-1] and ma20[-1] >= ma20[-3]:
                            is_match = True
                            status_desc = "上升通道"
                            
                    elif strategy_type == "极低抄底 (超跌反弹)":
                        # 计算指标：RSI 和 乖离率 (Bias)
                        rsi_vals = calculate_rsi(prices)
                        bias = (prices[-1] - ma20[-1]) / ma20[-1] * 100
                        # 云端环境建议放宽到 RSI < 38 或 乖离率 < -7%，以便能看到结果
                        if rsi_vals[-1] < 38 or bias < -7:
                            is_match = True
                            status_desc = f"超跌(RSI:{int(rsi_vals[-1])}/偏离:{int(bias)}%)"
                    
                    if is_match:
                        recommend_list.append({
                            "代码": row['代码'], "名称": row['名称'], "现价": round(prices[-1], 2),
                            "当日涨幅": row['涨跌幅'], "所属板块": sector, "形态": status_desc
                        })
        except:
            continue
            
    msg.empty()
    bar.empty()
    return pd.DataFrame(recommend_list)

# --- 3. 侧边栏策略配置 (完全保留您的分类) ---
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

# --- 4. 主界面 ---
st.markdown(f'<h1 class="neon-text">📈 A股决策中心 · {strategy_type}</h1>', unsafe_allow_html=True)

if st.button("🚀 启动深度扫描", use_container_width=True):
    with st.spinner("正在抓取实时云端行情..."):
        df_res = main_engine(current_sectors, strategy_type)
        
        if not df_res.empty:
            st.success(f"扫描完毕！发现 {len(df_res)} 只符合特征的个股。")
            df_res = df_res.sort_values("当日涨幅", ascending=False)
            
            for _, row in df_res.iterrows():
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
        else:
            st.warning("⚠️ 云端请求受限或暂无符合条件的个股。如果是抄底模式，说明目前市场整体不处于超跌状态。")

st.divider()
st.info("💡 **云端提示**：为防止IP被封，云端扫描增加了延迟。如果扫描结果为空，请尝试切换至‘避险红利’或‘大消费’板块再试。")
