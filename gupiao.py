import html
import os
import time
from datetime import datetime, timedelta

import akshare as ak
import numpy as np
import pandas as pd
import streamlit as st


APP_TITLE = "A股全维度决策终端"
INITIAL_CASH = 1_000_000.0
DATA_FETCH_ERRORS = []


def prefer_direct_eastmoney():
    """Avoid broken system proxies for Eastmoney data endpoints."""
    no_proxy_hosts = [
        "eastmoney.com",
        ".eastmoney.com",
        "push2.eastmoney.com",
        ".push2.eastmoney.com",
    ]
    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    merged = [item.strip() for item in existing.split(",") if item.strip()]
    for host in no_proxy_hosts:
        if host not in merged:
            merged.append(host)
    os.environ["NO_PROXY"] = ",".join(merged)
    os.environ["no_proxy"] = os.environ["NO_PROXY"]


prefer_direct_eastmoney()

INDUSTRY_GROUPS = {
    "核心科技": ["半导体", "通信设备", "消费电子", "软件开发", "光学光电子"],
    "高端制造": ["机器人", "航天航空", "通用设备", "专用设备", "计算机设备"],
    "能源电力": ["电力行业", "煤炭行业", "电网设备", "光伏设备", "风电设备"],
    "工业与基建": ["汽车零部件", "工程机械", "电机", "仪器仪表", "轨道交通设备"],
    "医药健康": ["中药", "生物制品", "医疗器械", "化学制药", "医疗服务"],
    "消费服务": ["酿酒行业", "家电行业", "装修建材", "旅游酒店", "物流行业"],
    "金融红利": ["银行", "证券", "保险", "公路铁路运输", "港口航运"],
}

HIST_COLUMNS = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_chg",
    "涨跌额": "change",
    "换手率": "turnover",
}


st.set_page_config(page_title=APP_TITLE, layout="wide")


def init_state():
    defaults = {
        "account": {"cash": INITIAL_CASH, "positions": {}},
        "scan_results": [],
        "elite_results": [],
        "elite_has_run": False,
        "watchlist": {},
        "trade_log": [],
        "last_analysis": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


st.markdown(
    """
<style>
    :root {
        --bg: #0b1120;
        --panel: #111827;
        --panel-soft: #0f172a;
        --line: #243244;
        --text: #e5edf8;
        --muted: #91a4bd;
        --blue: #38bdf8;
        --green: #22c55e;
        --amber: #f59e0b;
        --red: #ef4444;
    }
    .stApp { background: var(--bg); color: var(--text); }
    .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }
    [data-testid="stSidebar"] { background: #0a1020; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] h2 { font-size: 19px; }
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(17,24,39,.96), rgba(15,23,42,.96));
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 16px 40px rgba(0,0,0,.18);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--text); font-weight: 800; }
    .stButton > button, .stDownloadButton > button {
        border-radius: 6px;
        border: 1px solid #2d405a;
        background: #142033;
        color: var(--text);
        font-weight: 700;
        min-height: 40px;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: var(--blue);
        color: #ffffff;
        background: #172b45;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0369a1, #0f766e);
        border-color: rgba(56,189,248,.45);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
        background: var(--panel);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid var(--line);
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        padding: 0 18px;
        border-radius: 6px 6px 0 0;
        color: var(--muted);
        font-weight: 700;
    }
    .stTabs [aria-selected="true"] {
        background: #111827;
        color: #f8fafc;
        border: 1px solid var(--line);
        border-bottom-color: #111827;
    }
    .terminal-hero {
        background:
            linear-gradient(135deg, rgba(14,165,233,.18), rgba(34,197,94,.10)),
            #0f172a;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 22px 24px;
        margin-bottom: 18px;
        box-shadow: 0 18px 48px rgba(0,0,0,.26);
    }
    .terminal-hero-top {
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap:18px;
        flex-wrap:wrap;
    }
    .main-title {
        color:#f8fafc;
        font-weight:900;
        letter-spacing:0;
        font-size:34px;
        line-height:1.18;
        margin:0;
    }
    .hero-subtitle { color: var(--muted); margin-top: 8px; font-size: 14px; }
    .status-pill {
        display:inline-flex;
        align-items:center;
        gap:8px;
        border:1px solid rgba(56,189,248,.35);
        background: rgba(8,47,73,.55);
        color:#bae6fd;
        padding:8px 11px;
        border-radius:999px;
        font-size:12px;
        font-weight:800;
        white-space:nowrap;
    }
    .hero-grid {
        display:grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap:10px;
        margin-top:18px;
    }
    .hero-stat {
        background: rgba(15,23,42,.72);
        border:1px solid rgba(148,163,184,.18);
        border-radius:8px;
        padding:12px 14px;
    }
    .hero-stat span { display:block; color:var(--muted); font-size:12px; }
    .hero-stat strong { display:block; color:#f8fafc; font-size:20px; margin-top:4px; }
    .main-title-small { color:#f8fafc; font-weight:800; letter-spacing:0; }
    .accent { color:var(--blue); font-weight:700; }
    .muted { color:var(--muted); }
    .stock-card, .elite-card {
        background: linear-gradient(180deg, rgba(17,24,39,.98), rgba(15,23,42,.98));
        padding:16px;
        border-radius:8px;
        border:1px solid var(--line);
        margin-bottom:12px;
        box-shadow: 0 12px 28px rgba(0,0,0,.18);
    }
    .stock-card { border-left:4px solid var(--blue); }
    .elite-card { border-left:4px solid var(--amber); }
    .badge {
        display:inline-block; padding:3px 9px; border-radius:999px;
        font-size:12px; font-weight:700;
    }
    .score-line {
        height:8px; background:#1e293b; border-radius:999px;
        overflow:hidden; margin:5px 0 3px 0;
    }
    .score-fill { height:8px; border-radius:999px; }
    .dim-row {
        display:flex; justify-content:space-between; gap:12px;
        font-size:12px; color:#cbd5e1;
    }
    @media (max-width: 900px) {
        .hero-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .main-title { font-size: 28px; }
    }
    @media (max-width: 560px) {
        .hero-grid { grid-template-columns: 1fr; }
    }
</style>
""",
    unsafe_allow_html=True,
)


def safe_text(value):
    return html.escape(str(value))


def to_float(value, default=np.nan):
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return default


def _fetch_with_retry(fn, label="", retries=3, base_delay=1.5):
    """
    通用重试包装器。
    - 最多重试 retries 次
    - 每次等待时间指数递增：1.5s → 3s → 6s
    - 返回 (result, error_msg_or_None)
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            result = fn()
            return result, None
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = base_delay * (2 ** (attempt - 1))
                time.sleep(wait)
    err_type = type(last_exc).__name__
    err_msg = str(last_exc)
    # 给出更友好的原因判断
    if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
        reason = "请求超时"
    elif "connection" in err_msg.lower() or "remote" in err_msg.lower():
        reason = "网络连接失败"
    elif "proxy" in err_msg.lower():
        reason = "代理配置异常"
    elif "429" in err_msg or "rate" in err_msg.lower():
        reason = "接口限流(429)"
    elif "ssl" in err_msg.lower():
        reason = "SSL证书错误"
    else:
        reason = err_type
    return None, f"[{label}] {reason} — {err_msg[:120]}"


@st.cache_data(ttl=60 * 60 * 4, show_spinner=False)
def get_industry_stocks(sector):
    result, err = _fetch_with_retry(
        lambda: ak.stock_board_industry_cons_em(symbol=sector),
        label=f"行业成分·{sector}",
    )
    if err is not None:
        DATA_FETCH_ERRORS.append(err)
        return pd.DataFrame()
    if result is None or result.empty:
        return pd.DataFrame()
    return result.copy()


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_safe_hist(code, start_d, end_d):
    result, err = _fetch_with_retry(
        lambda: ak.stock_zh_a_hist(
            symbol=str(code),
            period="daily",
            start_date=start_d,
            end_date=end_d,
            adjust="qfq",
        ),
        label=f"历史行情·{code}",
    )
    if err is not None:
        # 个股行情失败不记录到全局（数量太多），静默跳过
        return pd.DataFrame()

    df = result
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns=HIST_COLUMNS)
    required = {"date", "open", "close", "high", "low", "volume", "pct_chg"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df = df[list(required)].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "close", "high", "low", "volume", "pct_chg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "close", "high", "low"]).sort_values("date")
    return df.reset_index(drop=True)


def calculate_rsi(df, n=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def add_indicators(df):
    if df.empty:
        return df
    out = df.copy()
    out["ma5"] = out["close"].rolling(5).mean()
    out["ma10"] = out["close"].rolling(10).mean()
    out["ma20"] = out["close"].rolling(20).mean()
    out["ma60"] = out["close"].rolling(60).mean()
    out["rsi"] = calculate_rsi(out)
    out["dif"], out["dea"], out["macd"] = calculate_macd(out)
    out["vol_ma5"] = out["volume"].rolling(5).mean()
    out["vol_ma20"] = out["volume"].rolling(20).mean()
    return out


def compute_elite_score(df):
    if df is None or len(df) < 30:
        return 0, {}

    data = add_indicators(df)
    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]
    last = close.iloc[-1]
    scores = {}
    reasons = {}

    trend_score = 0
    if data["ma5"].iloc[-1] > data["ma10"].iloc[-1] > data["ma20"].iloc[-1] > data["ma60"].iloc[-1]:
        trend_score += 15
        reasons["趋势"] = "均线多头排列"
    elif data["ma5"].iloc[-1] > data["ma20"].iloc[-1] > data["ma60"].iloc[-1]:
        trend_score += 10
        reasons["趋势"] = "中期结构偏强"
    else:
        reasons["趋势"] = "均线结构一般"

    ma20_prev = data["ma20"].iloc[-5]
    slope = (data["ma20"].iloc[-1] - ma20_prev) / ma20_prev * 100 if ma20_prev else 0
    trend_score += min(10, max(0, slope * 20))
    scores["趋势强度"] = round(min(25, trend_score), 1)

    momentum_score = 0
    rsi = data["rsi"].iloc[-1]
    if 50 <= rsi <= 68:
        momentum_score += 12
        reasons["动量"] = f"RSI={rsi:.1f}，处于健康强势区"
    elif 40 <= rsi < 50:
        momentum_score += 6
        reasons["动量"] = f"RSI={rsi:.1f}，蓄势待确认"
    elif rsi > 68:
        momentum_score += 4
        reasons["动量"] = f"RSI={rsi:.1f}，短线偏热"
    else:
        momentum_score += 2
        reasons["动量"] = f"RSI={rsi:.1f}，动量偏弱"

    ret_5d = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100
    if 0 < ret_5d <= 8:
        momentum_score += 8
    elif 8 < ret_5d <= 15:
        momentum_score += 4
    elif ret_5d > 15:
        momentum_score += 1
    scores["动量质量"] = round(min(20, momentum_score), 1)

    vol_score = 0
    vol_ma20 = data["vol_ma20"].iloc[-1]
    vol_ratio = data["vol_ma5"].iloc[-1] / vol_ma20 if vol_ma20 and vol_ma20 > 0 else 1
    if 1.2 <= vol_ratio <= 2.5:
        vol_score += 12
        reasons["量价"] = f"温和放量 {vol_ratio:.1f}x"
    elif vol_ratio > 2.5:
        vol_score += 6
        reasons["量价"] = f"放量过大 {vol_ratio:.1f}x"
    else:
        vol_score += 3
        reasons["量价"] = f"量能不足 {vol_ratio:.1f}x"

    up_days_with_vol = sum(
        1
        for i in range(-5, 0)
        if close.iloc[i] > close.iloc[i - 1] and volume.iloc[i] > volume.iloc[i - 1]
    )
    vol_score += up_days_with_vol * 1.6
    scores["量价配合"] = round(min(20, vol_score), 1)

    risk_score = 0
    roll_max = close.rolling(60).max()
    drawdown = ((close - roll_max) / roll_max * 100).iloc[-1]
    if drawdown > -8:
        risk_score += 12
        reasons["风控"] = f"60日回撤 {drawdown:.1f}%，走势稳健"
    elif drawdown > -15:
        risk_score += 6
        reasons["风控"] = f"60日回撤 {drawdown:.1f}%，风险可控"
    else:
        reasons["风控"] = f"60日回撤 {drawdown:.1f}%，波动偏大"

    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_ratio = true_range.rolling(14).mean().iloc[-1] / last * 100
    if atr_ratio < 3:
        risk_score += 8
    elif atr_ratio < 5:
        risk_score += 5
    else:
        risk_score += 2
    scores["波动风控"] = round(min(20, risk_score), 1)

    signal_score = 0
    dif = data["dif"]
    dea = data["dea"]
    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
        signal_score += 8
        reasons["信号"] = "MACD金叉"
    elif dif.iloc[-1] > dea.iloc[-1]:
        signal_score += 4
        reasons["信号"] = "MACD多头延续"
    else:
        reasons["信号"] = "MACD尚未转强"

    high_20 = high.iloc[-21:-1].max()
    if last > high_20 * 0.995:
        signal_score += 7
        reasons["信号"] += "，接近或突破20日高点"
    scores["突破信号"] = round(min(15, signal_score), 1)

    total = round(sum(scores.values()), 1)
    scores["综合得分"] = total
    scores["_reasons"] = reasons
    scores["_extras"] = {
        "RSI": round(rsi, 1),
        "5日涨幅": round(ret_5d, 2),
        "量比": round(vol_ratio, 2),
        "60日回撤": round(drawdown, 2),
        "ATR波动率": round(atr_ratio, 2),
        "止损参考": round(last * 0.92, 2),
        "止盈参考": round(last * 1.16, 2),
    }
    return total, scores


def get_signal_badge(score):
    if score >= 80:
        return "强烈关注", "#fee2e2", "#ef4444"
    if score >= 70:
        return "重点跟踪", "#ffedd5", "#f97316"
    if score >= 60:
        return "值得观察", "#fef9c3", "#ca8a04"
    return "谨慎观察", "#e2e8f0", "#64748b"


def trade_buy(item, qty):
    price = float(item["现价"])
    cost = price * qty
    if qty <= 0:
        st.error("买入数量必须大于 0")
        return
    if st.session_state.account["cash"] < cost:
        st.error("现金余额不足")
        return

    code = str(item["代码"])
    pos = st.session_state.account["positions"].get(code)
    if pos:
        total_qty = pos["qty"] + qty
        pos["price"] = (pos["price"] * pos["qty"] + cost) / total_qty
        pos["qty"] = total_qty
        pos["last_price"] = price
    else:
        st.session_state.account["positions"][code] = {
            "name": item["名称"],
            "qty": qty,
            "price": price,
            "last_price": price,
        }

    st.session_state.account["cash"] -= cost
    st.session_state.trade_log.append(
        {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "方向": "买入",
            "代码": code,
            "名称": item["名称"],
            "数量": qty,
            "价格": price,
            "金额": round(cost, 2),
        }
    )
    st.success(f"已模拟买入 {item['名称']} {qty} 股")


def trade_sell(code, qty, price):
    positions = st.session_state.account["positions"]
    if code not in positions:
        st.error("未持有该股票")
        return
    pos = positions[code]
    qty = min(qty, pos["qty"])
    if qty <= 0:
        st.error("卖出数量必须大于 0")
        return

    amount = qty * price
    st.session_state.account["cash"] += amount
    pos["qty"] -= qty
    pos["last_price"] = price
    st.session_state.trade_log.append(
        {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "方向": "卖出",
            "代码": code,
            "名称": pos["name"],
            "数量": qty,
            "价格": price,
            "金额": round(amount, 2),
        }
    )
    if pos["qty"] <= 0:
        del positions[code]
    st.success("已完成模拟卖出")


def render_stock_card(item, key_prefix):
    name = safe_text(item["名称"])
    code = safe_text(item["代码"])
    pct = to_float(item.get("涨幅"), 0)
    pct_color = "#ef4444" if pct >= 0 else "#22c55e"

    st.markdown(
        f"""
        <div class="stock-card">
            <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start;">
                <div>
                    <div style="font-size:18px; font-weight:800; color:#f8fafc;">{name} <span class="muted">({code})</span></div>
                    <div class="muted">行业：{safe_text(item.get("行业", "-"))} ｜ 现价：{float(item["现价"]):.2f}</div>
                </div>
                <div style="color:{pct_color}; font-size:18px; font-weight:800;">{pct:.2f}%</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    qty = c1.number_input("数量", min_value=100, step=100, value=1000, key=f"{key_prefix}_qty_{code}")
    if c2.button("模拟买入", key=f"{key_prefix}_buy_{code}"):
        trade_buy(item, int(qty))
    if c3.button("加入自选", key=f"{key_prefix}_watch_{code}"):
        st.session_state.watchlist[str(item["代码"])] = {
            "名称": item["名称"],
            "行业": item.get("行业", "-"),
            "加入价": float(item["现价"]),
        }
        st.success("已加入自选股")


def portfolio_market_value():
    total = 0.0
    rows = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")

    for code, pos in st.session_state.account["positions"].items():
        hist = get_safe_hist(code, start_date, end_date)
        last_price = pos.get("last_price", pos["price"])
        if not hist.empty:
            last_price = float(hist["close"].iloc[-1])
            pos["last_price"] = last_price
        market_value = pos["qty"] * last_price
        cost = pos["qty"] * pos["price"]
        pnl = market_value - cost
        total += market_value
        rows.append(
            {
                "代码": code,
                "名称": pos["name"],
                "持仓": pos["qty"],
                "成本价": round(pos["price"], 2),
                "现价": round(last_price, 2),
                "市值": round(market_value, 2),
                "盈亏": round(pnl, 2),
                "盈亏率": round(pnl / cost * 100, 2) if cost else 0,
            }
        )
    return total, pd.DataFrame(rows)


with st.sidebar:
    st.markdown('<h2 class="main-title-small">行业矩阵</h2>', unsafe_allow_html=True)
    strategy_type = st.selectbox("策略逻辑", ["趋势追踪", "超跌反弹", "放量突破"])
    group_choice = st.radio("扫描领域", list(INDUSTRY_GROUPS.keys()))
    selected_sectors = st.multiselect(
        "细分行业",
        INDUSTRY_GROUPS[group_choice],
        default=INDUSTRY_GROUPS[group_choice],
    )
    max_stocks_per_sector = st.slider("每个行业最多扫描", 5, 50, 30, step=5)
    min_turnover_filter = st.checkbox("过滤低成交量股票", value=False)
    st.caption("数据来自 AkShare。扫描速度取决于网络和接口响应。")


position_count = len(st.session_state.account["positions"])
watch_count = len(st.session_state.watchlist)
scan_count = len(st.session_state.scan_results)
elite_count = len(st.session_state.elite_results)
cash_now = st.session_state.account["cash"]
st.markdown(
    f"""
    <section class="terminal-hero">
        <div class="terminal-hero-top">
            <div>
                <h1 class="main-title">{APP_TITLE}</h1>
                <div class="hero-subtitle">行业扫描、量化评分、模拟持仓与自选跟踪的一体化研究工作台。仅用于研究和模拟，不构成投资建议。</div>
            </div>
            <div class="status-pill">数据源：AkShare / 东方财富</div>
        </div>
        <div class="hero-grid">
            <div class="hero-stat"><span>候选标的</span><strong>{scan_count}</strong></div>
            <div class="hero-stat"><span>精选入榜</span><strong>{elite_count}</strong></div>
            <div class="hero-stat"><span>持仓数量</span><strong>{position_count}</strong></div>
            <div class="hero-stat"><span>可用现金</span><strong>¥{cash_now:,.0f}</strong></div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs(["行业扫描", "智能精选", "模拟持仓", "个股分析"])


with tab1:
    st.subheader("行业深度扫描")
    st.write("先用策略条件做初筛，再到“智能精选”里进行多维评分。")

    if st.button("执行扫描", type="primary", use_container_width=True):
        results = []
        DATA_FETCH_ERRORS.clear()
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
        progress = st.progress(0)
        status = st.empty()

        sectors = selected_sectors or INDUSTRY_GROUPS[group_choice]
        total_steps = max(len(sectors), 1)
        for i, sector in enumerate(sectors, 1):
            status.write(f"正在分析：{sector}")
            progress.progress(i / total_steps)
            stocks = get_industry_stocks(sector).head(max_stocks_per_sector)
            if stocks.empty:
                continue

            for _, row in stocks.iterrows():
                code = str(row.get("代码", "")).zfill(6)
                hist = get_safe_hist(code, start_date, end_date)
                if len(hist) < 30:
                    continue

                data = add_indicators(hist)
                last_price = float(data["close"].iloc[-1])
                ma20 = data["ma20"].iloc[-1]
                rsi = data["rsi"].iloc[-1]
                vol_ma20 = data["vol_ma20"].iloc[-1]
                vol_ratio = data["vol_ma5"].iloc[-1] / vol_ma20 if vol_ma20 and vol_ma20 > 0 else 1
                pct_chg = to_float(row.get("涨跌幅", data["pct_chg"].iloc[-1]), 0)

                if min_turnover_filter and data["volume"].tail(20).mean() < 5_000:
                    continue

                is_match = False
                if strategy_type == "趋势追踪":
                    ma20_slope = data["ma20"].iloc[-1] - data["ma20"].iloc[max(-4, -len(data))]
                    is_match = last_price > ma20 and ma20_slope >= 0
                elif strategy_type == "超跌反弹":
                    bias = (last_price - ma20) / ma20 * 100 if ma20 else 0
                    is_match = rsi < 40 or bias < -8
                elif strategy_type == "放量突破":
                    high_20 = data["high"].iloc[-21:-1].max()
                    is_match = last_price >= high_20 * 0.995 and 1.2 <= vol_ratio <= 3.5

                if is_match:
                    results.append(
                        {
                            "代码": code,
                            "名称": row.get("名称", ""),
                            "现价": round(last_price, 2),
                            "涨幅": round(pct_chg, 2),
                            "行业": sector,
                            "RSI": round(rsi, 1),
                            "量比": round(vol_ratio, 2),
                        }
                    )

        progress.empty()
        status.empty()
        st.session_state.scan_results = results
        st.session_state.scan_strategy = strategy_type
        st.session_state.scan_group = group_choice
        st.session_state.elite_results = []
        st.session_state.elite_has_run = False

        failed_count = len([e for e in DATA_FETCH_ERRORS if "行业成分" in e])
        if DATA_FETCH_ERRORS:
            with st.expander(f"⚠️ {failed_count} 个行业接口请求失败（已自动重试3次）", expanded=True):
                st.markdown("""
**常见原因及解决方法：**
- 🌐 **网络不稳定 / 超时**：稍等片刻后点执行扫描重试
- 🔒 **代理异常**：检查系统代理，或在无代理网络下运行
- 🚦 **接口限流 (429)**：等待 1~2 分钟后重试
- 📡 **东方财富服务器波动**：通常几分钟内自行恢复
""")
                st.caption("失败详情（每次已自动等待重试，仍失败则记录如下）：")
                for message in DATA_FETCH_ERRORS[:30]:
                    st.code(message, language="text")
                if st.button("🔄 清除缓存并重试", key="retry_failed"):
                    st.cache_data.clear()
                    DATA_FETCH_ERRORS.clear()
                    st.rerun()

        if results:
            extra = f"（{failed_count} 个行业因网络失败已跳过）" if DATA_FETCH_ERRORS else ""
            st.success(f"扫描完成：发现 {len(results)} 只候选股票{extra}")
        else:
            st.warning("当前条件下没有发现候选股票，可以切换行业、策略或提高扫描数量。")

    if st.session_state.scan_results:
        result_df = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        st.download_button(
            "导出扫描结果 CSV",
            result_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"scan_results_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
        )
        st.divider()
        for item in st.session_state.scan_results:
            render_stock_card(item, "scan")


with tab2:
    st.subheader("智能精选榜")
    with st.expander("评分模型说明"):
        st.markdown(
            """
评分由五部分组成：趋势强度 25 分、动量质量 20 分、量价配合 20 分、
波动风控 20 分、突破信号 15 分。分数越高代表当前技术面越符合强势或稳健特征。
"""
        )

    if not st.session_state.scan_results:
        st.info("请先在“行业扫描”执行扫描。")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("初筛数量", len(st.session_state.scan_results))
        c2.metric("扫描领域", st.session_state.get("scan_group", "-"))
        c3.metric("策略逻辑", st.session_state.get("scan_strategy", "-"))

        col_a, col_b = st.columns(2)
        result_count = len(st.session_state.scan_results)
        min_top_n = 1 if result_count < 3 else 3
        top_n = col_a.slider("展示数量", min_top_n, min(20, result_count), min(8, result_count))
        min_score = col_b.slider("最低评分", 0, 90, 55, step=5)

        if st.button("开始深度评分", type="primary", use_container_width=True):
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=240)).strftime("%Y%m%d")
            elite_results = []
            progress = st.progress(0)
            status = st.empty()

            candidates = st.session_state.scan_results
            for i, item in enumerate(candidates, 1):
                status.write(f"深度分析 [{i}/{len(candidates)}]：{item['名称']} ({item['代码']})")
                progress.progress(i / len(candidates))
                hist = get_safe_hist(item["代码"], start_date, end_date)
                score, detail = compute_elite_score(hist)
                if score >= min_score:
                    elite_results.append({**item, "得分": score, "评分详情": detail})

            elite_results.sort(key=lambda x: x["得分"], reverse=True)
            st.session_state.elite_results = elite_results[:top_n]
            st.session_state.elite_has_run = True
            progress.empty()
            status.empty()

        if st.session_state.elite_results:
            export_rows = []
            for rank, item in enumerate(st.session_state.elite_results, 1):
                detail = item["评分详情"]
                reasons = detail.get("_reasons", {})
                extras = detail.get("_extras", {})
                label, bg, fg = get_signal_badge(item["得分"])
                export_rows.append(
                    {
                        "排名": rank,
                        "代码": item["代码"],
                        "名称": item["名称"],
                        "得分": item["得分"],
                        **{k: v for k, v in detail.items() if not k.startswith("_")},
                        **extras,
                    }
                )

                st.markdown(
                    f"""
                    <div class="elite-card">
                        <div style="display:flex; justify-content:space-between; gap:16px; align-items:flex-start;">
                            <div>
                                <div style="font-size:22px; color:#f8fafc; font-weight:800;">#{rank} {safe_text(item["名称"])} <span class="muted">({item["代码"]})</span></div>
                                <div class="muted">行业：{safe_text(item["行业"])} ｜ 现价：{float(item["现价"]):.2f} ｜ 今日涨幅：{float(item["涨幅"]):.2f}%</div>
                                <div style="margin-top:8px;"><span class="badge" style="background:{bg}; color:{fg};">{label}</span></div>
                            </div>
                            <div style="text-align:right;">
                                <div class="muted">综合得分</div>
                                <div style="font-size:42px; font-weight:900; color:#fbbf24;">{item["得分"]}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                dim_max = {"趋势强度": 25, "动量质量": 20, "量价配合": 20, "波动风控": 20, "突破信号": 15}
                reason_map = {"趋势强度": "趋势", "动量质量": "动量", "量价配合": "量价", "波动风控": "风控", "突破信号": "信号"}
                for dim, max_score in dim_max.items():
                    score = detail.get(dim, 0)
                    pct = min(100, score / max_score * 100)
                    color = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 45 else "#64748b"
                    st.markdown(
                        f"""
                        <div class="dim-row"><span>{dim}：{safe_text(reasons.get(reason_map[dim], ""))}</span><span>{score}/{max_score}</span></div>
                        <div class="score-line"><div class="score-fill" style="width:{pct}%; background:{color};"></div></div>
                        """,
                        unsafe_allow_html=True,
                    )

                e1, e2, e3, e4 = st.columns(4)
                e1.metric("RSI", extras.get("RSI", "-"))
                e2.metric("5日涨幅", f"{extras.get('5日涨幅', 0)}%")
                e3.metric("止损参考", extras.get("止损参考", "-"))
                e4.metric("止盈参考", extras.get("止盈参考", "-"))

                b1, b2 = st.columns([1, 3])
                qty = b1.number_input("买入数量", min_value=100, step=100, value=1000, key=f"elite_qty_{item['代码']}_{rank}")
                if b2.button("模拟买入", key=f"elite_buy_{item['代码']}_{rank}"):
                    trade_buy(item, int(qty))
                st.divider()

            export_df = pd.DataFrame(export_rows)
            st.download_button(
                "导出精选榜 CSV",
                export_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"elite_results_{datetime.now():%Y%m%d_%H%M}.csv",
                mime="text/csv",
            )
        elif st.session_state.elite_has_run:
            st.warning("暂无符合评分门槛的结果。")


with tab3:
    st.subheader("模拟持仓")
    market_value, portfolio_df = portfolio_market_value()
    cash = st.session_state.account["cash"]
    total_assets = cash + market_value

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("可用现金", f"¥{cash:,.2f}")
    c2.metric("持仓市值", f"¥{market_value:,.2f}")
    c3.metric("总资产", f"¥{total_assets:,.2f}", delta=f"{total_assets - INITIAL_CASH:,.2f}")
    c4.metric("收益率", f"{(total_assets / INITIAL_CASH - 1) * 100:.2f}%")

    if not portfolio_df.empty:
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
        for _, row in portfolio_df.iterrows():
            s1, s2, s3 = st.columns([3, 1, 1])
            s1.write(f"**{row['名称']} ({row['代码']})** 现价 {row['现价']}")
            sell_qty = s2.number_input("卖出数量", min_value=100, max_value=int(row["持仓"]), step=100, value=int(row["持仓"]), key=f"sell_qty_{row['代码']}")
            if s3.button("卖出", key=f"sell_btn_{row['代码']}"):
                trade_sell(row["代码"], int(sell_qty), float(row["现价"]))
                st.rerun()
    else:
        st.info("暂无持仓，可以从扫描结果或精选榜模拟买入。")

    if st.session_state.trade_log:
        st.divider()
        st.subheader("交易记录")
        trade_df = pd.DataFrame(st.session_state.trade_log)
        st.dataframe(trade_df, use_container_width=True, hide_index=True)
        st.download_button(
            "导出交易记录 CSV",
            trade_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"trade_log_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
        )

    if st.button("重置模拟账户"):
        st.session_state.account = {"cash": INITIAL_CASH, "positions": {}}
        st.session_state.trade_log = []
        st.rerun()


with tab4:
    st.subheader("个股分析与自选股")
    code_input = st.text_input("输入 6 位股票代码", value="")
    analyze_col, watch_col = st.columns([1, 1])
    if analyze_col.button("查看技术面", use_container_width=True):
        code = code_input.strip()
        if len(code) != 6 or not code.isdigit():
            st.session_state.last_analysis = None
            st.error("请输入正确的 6 位股票代码")
        else:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=240)).strftime("%Y%m%d")
            hist = get_safe_hist(code, start_date, end_date)
            if hist.empty:
                st.session_state.last_analysis = None
                st.error("未获取到历史行情")
            else:
                data = add_indicators(hist)
                score, detail = compute_elite_score(hist)
                latest = data.iloc[-1]
                chart_df = data.set_index("date")[["close", "ma5", "ma20", "ma60"]].rename(
                    columns={"close": "收盘", "ma5": "MA5", "ma20": "MA20", "ma60": "MA60"}
                )
                st.session_state.last_analysis = {
                    "代码": code,
                    "最新收盘": float(latest["close"]),
                    "RSI": float(latest["rsi"]),
                    "综合评分": score,
                    "涨跌幅": float(latest["pct_chg"]),
                    "图表": chart_df,
                    "评分": {k: v for k, v in detail.items() if not k.startswith("_")},
                }

    analysis = st.session_state.last_analysis
    if analysis:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("最新收盘", f"{analysis['最新收盘']:.2f}")
        a2.metric("RSI", f"{analysis['RSI']:.1f}")
        a3.metric("综合评分", analysis["综合评分"])
        a4.metric("涨跌幅", f"{analysis['涨跌幅']:.2f}%")
        st.line_chart(analysis["图表"], use_container_width=True)
        st.json(analysis["评分"])
        if watch_col.button("加入自选", use_container_width=True):
            st.session_state.watchlist[analysis["代码"]] = {
                "名称": analysis["代码"],
                "行业": "手动添加",
                "加入价": analysis["最新收盘"],
            }
            st.success("已加入自选股")

    if st.session_state.watchlist:
        st.divider()
        st.subheader("自选股")
        rows = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        for code, item in st.session_state.watchlist.items():
            hist = get_safe_hist(code, start_date, end_date)
            current = item["加入价"]
            if not hist.empty:
                current = float(hist["close"].iloc[-1])
            rows.append(
                {
                    "代码": code,
                    "名称": item["名称"],
                    "行业": item["行业"],
                    "加入价": round(item["加入价"], 2),
                    "现价": round(current, 2),
                    "跟踪收益率": round((current / item["加入价"] - 1) * 100, 2) if item["加入价"] else 0,
                }
            )
        watch_df = pd.DataFrame(rows)
        st.dataframe(watch_df, use_container_width=True, hide_index=True)
        remove_code = st.selectbox("移除自选", [""] + list(st.session_state.watchlist.keys()))
        if remove_code and st.button("确认移除"):
            del st.session_state.watchlist[remove_code]
            st.rerun()
