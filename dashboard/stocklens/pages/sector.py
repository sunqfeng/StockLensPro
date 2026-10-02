import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from stocklens.charts import CN_DIVERGING_SCALE, TERM_CYAN, TERM_AMBER, apply_tech_layout
from stocklens.data.loaders import load_sector_hot_data, normalize_sector_hot_numeric_columns


def render_sector_page():
    """
    渲染板块信息页面。
    """
    st.markdown('<div id="sector-info"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">板块信息</div>', unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])

    with filter_col1:
        sector_min_count = st.number_input(
            "最小成分股数",
            min_value=3,
            max_value=100,
            value=5,
            step=1,
        )

    with filter_col2:
        top_n = st.number_input(
            "展示 Top N",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
        )

    with filter_col3:
        sector_keyword = st.text_input(
            "板块/行业搜索",
            value="",
            placeholder="输入行业名称关键词",
        ).strip()

    sector_df = load_sector_hot_data(min_stock_count=sector_min_count)
    sector_df = normalize_sector_hot_numeric_columns(sector_df)

    if sector_df.empty:
        st.info("当前没有可用于计算板块热度的数据。")
        return

    if sector_keyword:
        sector_df = sector_df[
            sector_df["板块行业"].astype(str).str.contains(sector_keyword, case=False, na=False)
        ].copy()

    if sector_df.empty:
        st.info("当前板块筛选条件下没有数据。")
        return

    sector_df = sector_df.sort_values("板块热度分", ascending=False).copy()
    top_sector_df = sector_df.head(int(top_n)).copy()
    display_count = len(top_sector_df)
    chart_height = max(440, min(980, 120 + display_count * 24))
    table_height = max(360, min(900, 88 + display_count * 36))

    top_row = top_sector_df.iloc[0]
    avg_hot_score = top_sector_df["板块热度分"].mean()
    avg_5td_change = top_sector_df["近5交易日均涨幅%"].mean()

    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    with kpi_col1:
        st.metric("当前热门板块", str(top_row["板块行业"]))

    with kpi_col2:
        st.metric("最高热度分", f"{top_row['板块热度分']:.2f}")

    with kpi_col3:
        st.metric("Top均热度分", f"{avg_hot_score:.2f}")

    with kpi_col4:
        st.metric("Top近5日均涨幅", f"{avg_5td_change:.2f}%")

    st.markdown(
        """
<div class="small-note">
板块热度分综合了最近 5/10 个交易日平均涨幅、上涨占比、换手活跃度、近 7 日推荐次数和平均技术分。
其中行情数据来自 stock_daily，推荐与评分数据来自 stock_recommend_record、stock_recommend_tech_score。
</div>
""",
        unsafe_allow_html=True,
    )

    fig_hot = px.bar(
        top_sector_df.sort_values("板块热度分", ascending=True),
        x="板块热度分",
        y="板块行业",
        orientation="h",
        color="近5交易日均涨幅%",
        color_continuous_scale=CN_DIVERGING_SCALE,

        color_continuous_midpoint=0,
        hover_data=[
            "成分股数",
            "近5交易日均涨幅%",
            "近10交易日均涨幅%",
            "上涨占比%",
            "近7日推荐次数",
            "平均技术分",
        ],
    )
    fig_hot = apply_tech_layout(fig_hot, f"热门板块热度排行 Top {display_count}", "板块行业")
    fig_hot.update_layout(
        coloraxis_colorbar={"title": "近5日涨跌%"},
        height=chart_height,
        margin={"l": 150, "r": 28, "t": 58, "b": 58},
    )
    st.plotly_chart(fig_hot, width="stretch", theme=None)

    marker_size = (top_sector_df["成分股数"].clip(lower=5, upper=100) * 0.55 + 18).tolist()
    fig_rec = go.Figure()
    fig_rec.add_trace(
        go.Scatter(
            x=top_sector_df["近7日推荐次数"],
            y=top_sector_df["平均技术分"],
            mode="markers+text",
            text=top_sector_df["板块行业"],
            textposition="top center",
            textfont={"color": "#C5D0E0", "size": 11},
            customdata=top_sector_df[
                [
                    "板块行业",
                    "成分股数",
                    "板块热度分",
                    "近5交易日均涨幅%",
                    "近7日推荐次数",
                    "平均技术分",
                ]
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "近7日推荐次数=%{customdata[4]}<br>"
                "平均技术分=%{customdata[5]:.2f}<br>"
                "成分股数=%{customdata[1]}<br>"
                "板块热度分=%{customdata[2]:.2f}<br>"
                "近5日均涨幅=%{customdata[3]:.2f}%"
                "<extra></extra>"
            ),
            marker={
                "size": marker_size,
                "color": TERM_AMBER,
                "opacity": 0.92,
                "line": {"color": TERM_CYAN, "width": 1.5},
                "symbol": "circle",
            },
        )
    )
    fig_rec = apply_tech_layout(fig_rec, f"推荐热度 x 技术评分 Top {display_count}", "平均技术分")
    fig_rec.update_layout(
        height=chart_height,
        plot_bgcolor="rgba(8, 14, 24, 0.55)",
        hoverlabel={
            "bgcolor": "rgba(3, 10, 24, 0.98)",
            "bordercolor": "rgba(61, 220, 255, 0.35)",
            "font": {"color": "#ffffff", "size": 14},
        },
    )
    fig_rec.update_xaxes(
        title_text="近7日推荐次数",
        title_font={"color": "#8FA0B8", "size": 12},
        tickfont={"color": "#8FA0B8", "size": 11},
        gridcolor="rgba(120, 145, 175, 0.10)",
    )
    fig_rec.update_yaxes(
        title_font={"color": "#8FA0B8", "size": 12},
        tickfont={"color": "#8FA0B8", "size": 11},
        gridcolor="rgba(120, 145, 175, 0.10)",
    )
    st.plotly_chart(fig_rec, width="stretch", theme=None)

    st.markdown('<div class="section-title">热门板块明细</div>', unsafe_allow_html=True)
    st.dataframe(
        top_sector_df,
        width="stretch",
        height=table_height,
        hide_index=True,
    )

    # 不用 st.expander 标题（自定义 CSS 下 summary 中文易叠字）
    show_all_sectors = st.checkbox("查看全部板块数据", value=False, key="sector_show_all")
    if show_all_sectors:
        st.dataframe(
            sector_df,
            width="stretch",
            hide_index=True,
            height=min(720, 42 + max(len(sector_df), 1) * 28),
        )
