import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stocklens.charts import CN_DOWN, CN_FLAT, CN_UP, apply_tech_layout
from stocklens.data.hot_stock_loaders import (
    load_hot_stock_dashboard,
    select_heat_change_top,
)


MARKET_LABELS = {
    "CN_SH": "沪市",
    "CN_SZ": "深市",
    "HK": "港股",
    "US": "美股",
    "OTHER": "其他",
}


def _format_capture_time(value):
    if value is None or pd.isna(value):
        return "-"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")


def _format_rank_change(row):
    if pd.isna(row.get("previous_rank")):
        return "新上榜"
    change = int(row.get("rank_change") or 0)
    if change > 0:
        return f"↑{change}"
    if change < 0:
        return f"↓{abs(change)}"
    return "→0"


def _render_heat_change_chart(data):
    comparable = select_heat_change_top(data)
    if comparable.empty:
        st.info("目前只有一个采集批次，下一次自动采集后将显示热度变化图。")
        return

    comparable = comparable.sort_values("heat_change_pct")
    comparable["display_name"] = comparable.apply(
        lambda row: f'#{int(row["rank_no"])} {row["stock_name"]}', axis=1
    )
    colors = comparable["heat_change_pct"].map(
        lambda value: CN_UP if value > 0 else CN_DOWN if value < 0 else CN_FLAT
    )
    labels = comparable["heat_change_pct"].map(lambda value: f"{value:+.2f}%")

    figure = go.Figure(
        go.Bar(
            x=comparable["heat_change_pct"],
            y=comparable["display_name"],
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="outside",
            customdata=comparable[["heat_score", "previous_heat", "rank_change"]],
            hovertemplate=(
                "%{y}<br>本批热度：%{customdata[0]:,.0f}"
                "<br>上批热度：%{customdata[1]:,.0f}"
                "<br>热度变化幅度：%{x:+.2f}%"
                "<br>排名变化：%{customdata[2]:+.0f}<extra></extra>"
            ),
            name="热度变化幅度",
        )
    )
    figure.add_vline(x=0, line_color=CN_FLAT, line_width=1)
    apply_tech_layout(figure, "", "股票")
    figure.update_layout(
        height=max(480, 29 * len(comparable) + 150),
        showlegend=False,
        hovermode="closest",
        margin={"l": 38, "r": 70, "t": 18, "b": 58},
    )
    figure.update_xaxes(title="较上一批热度变化幅度（%）", zeroline=False)
    figure.update_yaxes(title=None, automargin=True)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def render_hot_stocks_page():
    st.title("🔥 股票热榜")
    st.caption("雪球股票讨论热榜 · 每30分钟自动采集 · 红色上升 / 绿色下降")

    try:
        metadata, data = load_hot_stock_dashboard(top_n=50)
    except Exception:
        st.error("热榜数据加载失败，请稍后重试或查看服务日志。")
        return

    if data.empty:
        st.info("暂无热榜数据，自动采集成功后会在这里显示。")
        return

    capture_time = _format_capture_time(metadata.get("capture_slot"))
    previous_time = _format_capture_time(metadata.get("previous_capture_slot"))
    hottest = data.iloc[0]
    up_count = int((data["change_direction"] == "上升").sum())
    down_count = int((data["change_direction"] == "下降").sum())

    metric_cols = st.columns(4)
    metric_cols[0].metric("最新批次", capture_time)
    metric_cols[1].metric(
        "当前榜首",
        hottest["stock_name"],
        f'热度 {hottest["heat_score"]:,.0f}',
    )
    metric_cols[2].metric("热度上升", f"{up_count} 只", help="较上一采集批次热度增加")
    metric_cols[3].metric("热度下降", f"{down_count} 只", help="较上一采集批次热度减少")

    st.markdown("### 热度变化幅度 Top20")
    st.caption(f"对比批次：{previous_time} → {capture_time}；柱长表示相对上一批的热度变化百分比。")
    _render_heat_change_chart(data)

    st.markdown("### 最新热榜 Top50")
    table = data.copy()
    table["排名变化"] = table.apply(_format_rank_change, axis=1)
    table["市场"] = table["market"].map(MARKET_LABELS).fillna(table["market"])
    table["sector_name"] = table["sector_name"].fillna("—")
    table = table.rename(
        columns={
            "rank_no": "排名",
            "stock_name": "股票名称",
            "normalized_code": "股票代码",
            "heat_score": "当前热度",
            "heat_change_pct": "热度变化幅度",
            "quote_change_pct": "股价涨跌幅",
            "latest_price": "最新收盘价",
            "sector_name": "所属板块",
            "topic": "热门话题",
        }
    )
    st.dataframe(
        table[
            [
                "排名",
                "排名变化",
                "股票名称",
                "股票代码",
                "市场",
                "最新收盘价",
                "所属板块",
                "当前热度",
                "热度变化幅度",
                "股价涨跌幅",
                "热门话题",
            ]
        ],
        width="stretch",
        hide_index=True,
        height=720,
        column_config={
            "排名": st.column_config.NumberColumn(format="%d"),
            "当前热度": st.column_config.NumberColumn(format="%.0f"),
            "最新收盘价": st.column_config.NumberColumn(format="%.2f"),
            "热度变化幅度": st.column_config.NumberColumn(format="%+.2f%%"),
            "股价涨跌幅": st.column_config.NumberColumn(format="%.2f%%"),
            "热门话题": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption("最新收盘价与所属板块来自本地A股行情、基础信息库；未覆盖的港股和美股显示为空。")
