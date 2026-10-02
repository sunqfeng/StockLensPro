import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from stocklens.charts import apply_tech_layout
from stocklens.data.price_history import load_price_history


def make_price_chart(history, recommend_date, recommend_price):
    fig = go.Figure(go.Scatter(
        x=history["trade_date"].dt.strftime("%Y-%m-%d"), y=history["close_price"],
        mode="lines+markers", name="每日价格", line={"color": "#3DDCFF", "width": 2.5},
        customdata=history[["return_pct", "price_type"]].to_numpy(),
        hovertemplate=("%{x}<br>价格：¥%{y:.2f}<br>推荐后涨跌：%{customdata[0]:+.2f}%"
                       "<br>%{customdata[1]}<extra></extra>"),
    ))
    fig.add_hline(y=float(recommend_price), line_dash="dash", line_color="#A4B1C3",
                  annotation_text=f"推荐价 ¥{float(recommend_price):.2f}", annotation_position="bottom right")
    fig.add_trace(go.Scatter(
        x=[str(recommend_date)[:10]], y=[float(recommend_price)], mode="markers",
        name="推荐日", marker={"symbol": "diamond", "size": 11, "color": "#F0B429"},
        hovertemplate="推荐日 %{x}<br>推荐价 ¥%{y:.2f}<extra></extra>",
    ))
    fig = apply_tech_layout(fig, "", "价格（元）", external_title=True)
    fig.update_xaxes(type="category", title="交易日期", tickangle=0, nticks=8)
    fig.update_yaxes(tickformat=".2f", rangemode="normal")
    low = min(float(history["close_price"].min()), float(recommend_price))
    high = max(float(history["close_price"].max()), float(recommend_price))
    padding = max((high - low) * 0.15, high * 0.01)
    fig.update_yaxes(range=[low - padding, high + padding])
    fig.update_layout(height=420, margin={"l": 56, "r": 24, "t": 48, "b": 60})
    return fig


@st.fragment
def render_stock_history_table(detail_df):
    identities = detail_df[["推荐批次号", "推荐日期", "推荐策略", "股票代码"]].astype(str)
    digest = hashlib.sha256(identities.to_csv(index=False).encode()).hexdigest()[:16]
    st.caption("勾选股票行左侧选择框，在弹窗中查看该次推荐日至今天的每日价格走势。")
    selected = st.dataframe(
        detail_df, width="stretch", hide_index=True,
        on_select="rerun", selection_mode="single-row", key=f"stock_history_{digest}",
    )
    rows = selected.selection.rows
    if not rows or rows[0] >= len(detail_df):
        return
    show_stock_price_dialog(detail_df.iloc[rows[0]])


@st.dialog("推荐后每日价格走势", width="large")
def show_stock_price_dialog(row):
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    with st.spinner("正在加载每日价格…"):
        try:
            history, warning = load_price_history(
                str(row["股票代码"]).zfill(6), row["推荐日期"], float(row["推荐价格"]), today,
            )
        except Exception:
            st.error("价格走势加载失败，请稍后重新选择股票。")
            return
    industry = row.get("所属行业")
    industry = str(industry).strip() if pd.notna(industry) else ""
    score = row.get("推荐分数")
    score_text = f"{float(score):g} 分" if pd.notna(score) else "暂无"
    st.subheader(
        f"{row['股票名称']} · {str(row['股票代码']).zfill(6)} · "
        f"板块：{industry or '未分类'} · 推荐时评分：{score_text}"
    )
    st.caption(f"{row['推荐策略']} · 推荐日 {str(row['推荐日期'])[:10]} · 查询截至 {today}")
    if history.empty:
        st.info("该次推荐尚无可展示的价格数据。")
        return
    last = history.iloc[-1]
    cols = st.columns(3)
    cols[0].metric("推荐价格", f"¥{float(row['推荐价格']):,.2f}")
    cols[1].metric("最后价格", f"¥{last['close_price']:,.2f}")
    cols[2].metric("推荐后累计涨跌", f"{last['return_pct']:+.2f}%")
    st.plotly_chart(make_price_chart(history, row["推荐日期"], row["推荐价格"]),
                    width="stretch", theme=None, config={"displayModeBar": False})
    st.caption(f"最后数据：{last['trade_date']:%Y-%m-%d} · {last['price_type']}。休市和缺失行情日期不补点。")
    if warning:
        st.info(warning)
