import html

import pandas as pd
import plotly.express as px
import streamlit as st

from stocklens.charts import apply_tech_layout
from stocklens.data.fund_loaders import (
    choose_latest_complete_report,
    load_fund_basic_summary,
    load_fund_holding_industry_weights,
    load_fund_holdings_detail,
    load_fund_industry_ranking,
    load_fund_report_overview,
    load_fund_return_ranking,
    load_fund_sector_options,
    load_fund_stock_ranking,
    load_stock_fund_holders,
)


def _format_number(value):
    if pd.isna(value):
        return "-"
    return f"{value:,.0f}"


def _format_pct(value):
    if pd.isna(value):
        return "-"
    return f"{value:.2f}%"


def _render_paginated_dataframe(
    df,
    *,
    key,
    page_size_options=(10, 20, 50, 100),
    default_page_size=20,
    column_config=None,
):
    """Render a dataframe with explicit pagination controls."""
    if df.empty:
        st.info("当前筛选条件下没有数据。")
        return

    total_rows = len(df)
    size_key = f"{key}_page_size"
    page_key = f"{key}_page"

    if size_key not in st.session_state:
        st.session_state[size_key] = default_page_size
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    page_size = st.session_state[size_key]
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    st.session_state[page_key] = min(max(1, st.session_state[page_key]), total_pages)

    current_page = st.session_state[page_key]
    start = (current_page - 1) * page_size
    end = min(start + page_size, total_rows)
    page_df = df.iloc[start:end].copy()
    table_height = min(760, max(260, 38 * (len(page_df) + 1)))

    st.dataframe(
        page_df,
        width="stretch",
        hide_index=True,
        height=table_height,
        column_config=column_config,
    )

    st.caption(f"第 {current_page} / {total_pages} 页，共 {total_rows:,} 条记录，当前显示 {start + 1:,}-{end:,} 条")
    control_col1, control_col2, control_col3, control_col4 = st.columns([1.1, 1, 1, 1.2])
    with control_col1:
        selected_page_size = st.selectbox(
            "每页条数",
            page_size_options,
            index=page_size_options.index(page_size) if page_size in page_size_options else 1,
            key=size_key,
        )
    if selected_page_size != page_size:
        st.session_state[page_key] = 1
        st.rerun()

    with control_col2:
        if st.button("上一页", key=f"{key}_prev", disabled=current_page <= 1):
            st.session_state[page_key] -= 1
            st.rerun()

    with control_col3:
        if st.button("下一页", key=f"{key}_next", disabled=current_page >= total_pages):
            st.session_state[page_key] += 1
            st.rerun()

    with control_col4:
        page = st.number_input(
            "页码",
            min_value=1,
            max_value=total_pages,
            value=current_page,
            step=1,
            key=f"{key}_page_input",
        )
        if page != current_page:
            st.session_state[page_key] = int(page)
            st.rerun()


def _render_industry_weight_bars(weight_df, meta):
    if weight_df.empty:
        st.info("当前基金没有查询到持仓行业占比。")
        return

    st.markdown(
        """
<style>
/* Align the primary content in the two-column ranking section.
   Streamlit renders the selection hint before the card; visual order keeps
   the table and industry card on one top baseline without changing logic. */
[data-testid="stHorizontalBlock"]:has(.fund-industry-card)
> [data-testid="stColumn"] {
    align-self: flex-start !important;
}
[data-testid="stHorizontalBlock"]:has(.fund-industry-card)
> [data-testid="stColumn"]:nth-child(2)
> [data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
}
[data-testid="stHorizontalBlock"]:has(.fund-industry-card)
> [data-testid="stColumn"]:nth-child(2)
[data-testid="stElementContainer"]:has(.fund-industry-card) {
    order: 1 !important;
    margin: -14px 0 0 !important;
}
[data-testid="stHorizontalBlock"]:has(.fund-industry-card)
> [data-testid="stColumn"]:nth-child(2)
[data-testid="stElementContainer"]:has(.small-note) {
    order: 2 !important;
    display: none !important;
}
.fund-industry-card {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid rgba(30, 70, 140, 0.08);
    border-radius: 8px;
    padding: 18px 20px 6px 20px;
    height: 402px;
    box-sizing: border-box;
    color: #1d2433 !important;
    text-shadow: none !important;
}
.fund-industry-card * {
    color: inherit;
    text-shadow: none !important;
}
.fund-industry-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(20, 30, 50, 0.08);
}
.fund-industry-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 22px;
    font-weight: 700;
    color: #111827 !important;
    text-shadow: none !important;
}
.fund-industry-title::before {
    content: "";
    width: 5px;
    height: 22px;
    border-radius: 4px;
    background: #4778ff;
}
.fund-industry-meta {
    color: #4b5563 !important;
    font-size: 13px;
    white-space: nowrap;
    text-shadow: none !important;
}
.fund-industry-row {
    display: grid;
    grid-template-columns: minmax(78px, 128px) 1fr minmax(68px, max-content);
    align-items: center;
    gap: 14px;
    min-height: 58px;
    border-bottom: 1px solid rgba(20, 30, 50, 0.06);
}
.fund-industry-name {
    color: #1f2937 !important;
    font-size: 18px;
    overflow-wrap: anywhere;
    text-shadow: none !important;
}
.fund-industry-track {
    height: 22px;
    border-radius: 4px;
    background: rgba(76, 120, 255, 0.10);
    overflow: hidden;
}
.fund-industry-bar {
    height: 100%;
    min-width: 5px;
    border-radius: 4px;
    background: linear-gradient(90deg, #72a7ff 0%, #3f63f0 100%);
}
.fund-industry-pct {
    color: #111827 !important;
    font-size: 18px;
    text-align: right;
    text-shadow: none !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    fund_name = html.escape(str(meta.get("基金名称", "-")))
    report_date = html.escape(str(meta.get("报告期", "-")))
    basis = html.escape(str(meta.get("权重口径", "-")))
    rows_html = []
    for _, row in weight_df.iterrows():
        industry = html.escape(str(row["板块/行业"]))
        pct = float(row["占比%"] or 0)
        bar_width = max(1.5, min(pct, 100))
        rows_html.append(
            f"""
<div class="fund-industry-row">
  <div class="fund-industry-name">{industry}</div>
  <div class="fund-industry-track"><div class="fund-industry-bar" style="width:{bar_width:.2f}%"></div></div>
  <div class="fund-industry-pct">{pct:.2f}%</div>
</div>
"""
        )

    st.markdown(
        f"""
<div class="fund-industry-card">
  <div class="fund-industry-header">
    <div class="fund-industry-title">行业分布</div>
    <div class="fund-industry-meta">{fund_name} | {report_date} | {basis}</div>
  </div>
  {''.join(rows_html)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_fund_info_page():
    """渲染基金信息页面。"""
    st.markdown('<div id="fund-info"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">基金信息</div>', unsafe_allow_html=True)

    report_df = load_fund_report_overview()
    basic_summary = load_fund_basic_summary()

    if report_df.empty:
        st.info("当前没有基金持仓明细数据，请先确认 fund_stock_holdings 是否已同步。")
        return

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1, 1])

    with filter_col1:
        min_complete_funds = st.number_input(
            "完整报告期基金数门槛",
            min_value=100,
            max_value=20000,
            value=3000,
            step=500,
        )

    latest_complete_report = choose_latest_complete_report(report_df, min_complete_funds)
    report_options = report_df["报告期"].astype(str).tolist()
    default_index = report_options.index(str(latest_complete_report)) if str(latest_complete_report) in report_options else 0

    with filter_col2:
        selected_report = st.selectbox("报告期", report_options, index=default_index)

    with filter_col3:
        top_n = st.number_input("展示 Top N", min_value=20, max_value=1000, value=200, step=50)

    with filter_col4:
        min_fund_count = st.number_input("最少持有基金数", min_value=1, max_value=1000, value=10, step=5)

    keyword_col1, keyword_col2, keyword_col3 = st.columns([1.2, 1.2, 1])
    with keyword_col1:
        stock_keyword = st.text_input("股票代码/名称搜索", value="", placeholder="例如 300750 或 宁德时代").strip()
    with keyword_col2:
        stock_code_for_detail = st.text_input("查看股票持有基金", value="", placeholder="输入股票代码，如 300750").strip()
    with keyword_col3:
        fund_code_for_detail = st.text_input("查看基金持仓", value="", placeholder="输入基金代码，如 001480").strip()

    report_row = report_df[report_df["报告期"].astype(str) == str(selected_report)].iloc[0]
    latest_mark = "最新完整报告期" if str(selected_report) == str(latest_complete_report) else "历史/未完整报告期"

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.metric("当前报告期", str(selected_report), latest_mark)
    with metric_col2:
        st.metric("覆盖基金数", _format_number(report_row["覆盖基金数"]))
    with metric_col3:
        st.metric("覆盖股票数", _format_number(report_row["覆盖股票数"]))
    with metric_col4:
        st.metric("持仓明细数", _format_number(report_row["持仓明细数"]))

    if not basic_summary.empty:
        item = basic_summary.iloc[0]
        st.markdown(
            f"""
<div class="small-note">
基金基础库：基金总数 {int(item['基金总数']):,}，场外基金 {int(item['场外基金数']):,}，场内基金 {int(item['场内基金数']):,}。
当前页面默认以“最新完整报告期”为主，避免误用刚开始披露但尚不完整的新报告期。
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">基金收益排行</div>', unsafe_allow_html=True)
    sector_options_df = load_fund_sector_options()
    sector_options = ["全部板块"]
    if not sector_options_df.empty:
        sector_options.extend(sector_options_df["板块"].astype(str).tolist())

    rank_filter_col1, rank_filter_col2, rank_filter_col3, rank_filter_col4, rank_filter_col5 = st.columns(
        [1, 1.15, 1.2, 0.9, 0.85]
    )
    with rank_filter_col1:
        return_period = st.radio("收益周期", ["近1周", "近1月", "近1年"], horizontal=True)
    with rank_filter_col2:
        return_keyword = st.text_input("基金代码/名称搜索", value="", placeholder="例如 001480 或 财通").strip()
    with rank_filter_col3:
        selected_sector = st.selectbox("持仓板块", sector_options, index=0)
    with rank_filter_col4:
        min_sector_nav_ratio = st.number_input(
            "板块最低占比%",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=5.0,
        )
    with rank_filter_col5:
        return_rank_limit = st.number_input("收益排行 Top N", min_value=20, max_value=300, value=100, step=20)

    sector_filter = "" if selected_sector == "全部板块" else selected_sector
    return_rank_df, return_rank_error = load_fund_return_ranking(
        period_col=return_period,
        keyword=return_keyword,
        limit=return_rank_limit,
        report_date=selected_report,
        sector_name=sector_filter,
        min_sector_nav_ratio=min_sector_nav_ratio if sector_filter else 0.0,
    )

    selected_return_fund_code = ""
    selected_return_fund_name = ""
    if return_rank_error:
        st.warning(f"基金收益排行获取失败：{return_rank_error}")
    elif return_rank_df.empty:
        st.info("当前筛选条件下没有基金收益排行数据。")
    else:
        if sector_filter:
            st.markdown(
                f"""
<div class="small-note">
当前收益榜已按“{sector_filter}”过滤：只展示在 {selected_report} 报告期该板块净值占比不低于 {min_sector_nav_ratio:.2f}% 的基金，并按 {return_period} 排序。
</div>
""",
                unsafe_allow_html=True,
            )
        rank_col, industry_weight_col = st.columns([1.35, 1])
        with rank_col:
            column_config = {
                return_period: st.column_config.NumberColumn(return_period, format="%.2f%%"),
                "日增长率": st.column_config.NumberColumn("日增长率", format="%.2f%%"),
                "单位净值": st.column_config.NumberColumn("单位净值", format="%.4f"),
                "累计净值": st.column_config.NumberColumn("累计净值", format="%.4f"),
            }
            if "板块持仓股票数" in return_rank_df.columns:
                column_config.update({
                    "板块持仓股票数": st.column_config.NumberColumn("板块持仓股票数", format="%d"),
                    "板块持仓市值": st.column_config.NumberColumn("板块持仓市值", format="%.2f"),
                    "板块净值占比%": st.column_config.NumberColumn("板块净值占比%", format="%.2f%%"),
                })
            rank_event = st.dataframe(
                return_rank_df,
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"fund_return_rank_{return_period}_{selected_sector}",
                column_config=column_config,
            )

            selected_rows = []
            if hasattr(rank_event, "selection"):
                selected_rows = rank_event.selection.rows
            if selected_rows:
                selected_row = return_rank_df.iloc[selected_rows[0]]
                st.session_state["fund_return_selected_code"] = str(selected_row["基金代码"]).zfill(6)
                st.session_state["fund_return_selected_name"] = str(selected_row["基金简称"])
            else:
                selected_code = st.session_state.get("fund_return_selected_code", "")
                available_codes = set(return_rank_df["基金代码"].astype(str).str.zfill(6))
                if selected_code not in available_codes:
                    first_row = return_rank_df.iloc[0]
                    st.session_state["fund_return_selected_code"] = str(first_row["基金代码"]).zfill(6)
                    st.session_state["fund_return_selected_name"] = str(first_row["基金简称"])

            if "fund_return_selected_code" not in st.session_state and not return_rank_df.empty:
                first_row = return_rank_df.iloc[0]
                st.session_state["fund_return_selected_code"] = str(first_row["基金代码"]).zfill(6)
                st.session_state["fund_return_selected_name"] = str(first_row["基金简称"])

        selected_return_fund_code = st.session_state.get("fund_return_selected_code", "")
        selected_return_fund_name = st.session_state.get("fund_return_selected_name", "")

        with industry_weight_col:
            if selected_return_fund_code:
                st.markdown(
                    f"""
<div class="small-note">
当前选择：{selected_return_fund_name}（{selected_return_fund_code}）。点击左侧排行表中的其他基金可切换行业占比。
</div>
""",
                    unsafe_allow_html=True,
                )
                weight_df, weight_meta = load_fund_holding_industry_weights(
                    selected_report,
                    selected_return_fund_code,
                    top_n=4,
                )
                _render_industry_weight_bars(weight_df, weight_meta)
            else:
                st.info("点击左侧收益排行中的基金后，这里会显示它的持仓行业占比。")

    ranking_df = load_fund_stock_ranking(
        report_date=selected_report,
        keyword=stock_keyword,
        min_fund_count=min_fund_count,
        min_hold_value=0,
        limit=top_n,
    )

    if ranking_df.empty:
        st.info("当前筛选条件下没有基金持仓股票排行数据。")
    else:
        st.markdown('<div class="section-title">基金持仓股票排行</div>', unsafe_allow_html=True)
        chart_df = ranking_df.head(min(30, len(ranking_df))).sort_values("持有基金数", ascending=True)
        fig = px.bar(
            chart_df,
            x="持有基金数",
            y="股票名称",
            orientation="h",
            color="合计持仓市值",
            color_continuous_scale=["#3478ff", "#00eaff", "#23f2a6"],
            hover_data=["股票代码", "合计持仓市值", "合计持股数", "持股变化", "持股变动比例%"],
        )
        fig = apply_tech_layout(fig, "基金持有家数 Top 股票", "股票名称")
        st.plotly_chart(fig, width="stretch", theme=None)
        _render_paginated_dataframe(
            ranking_df,
            key="fund_stock_ranking",
            default_page_size=20,
        )

    industry_df = load_fund_industry_ranking(
        report_date=selected_report,
        min_fund_count=min_fund_count,
        min_hold_value=0,
        limit=top_n,
    )

    if industry_df.empty:
        st.info("当前筛选条件下没有基金持仓板块/行业统计数据。")
    else:
        st.markdown('<div class="section-title">基金持仓板块/行业分布</div>', unsafe_allow_html=True)
        industry_chart_df = industry_df.head(min(30, len(industry_df))).sort_values("基金持仓次数", ascending=True)
        industry_fig = px.bar(
            industry_chart_df,
            x="基金持仓次数",
            y="板块/行业",
            orientation="h",
            color="合计持仓市值",
            color_continuous_scale=["#3478ff", "#00eaff", "#23f2a6"],
            hover_data=["覆盖股票数", "合计持仓市值", "合计持股数", "单股平均持有基金数"],
        )
        industry_fig = apply_tech_layout(industry_fig, "基金持仓次数 Top 板块/行业", "板块/行业")
        st.plotly_chart(industry_fig, width="stretch", theme=None)
        _render_paginated_dataframe(
            industry_df,
            key="fund_industry_ranking",
            default_page_size=20,
        )

    if stock_code_for_detail:
        st.markdown('<div class="section-title">单只股票被哪些基金持有</div>', unsafe_allow_html=True)
        holders_df = load_stock_fund_holders(selected_report, stock_code_for_detail)
        if holders_df.empty:
            st.info("当前报告期没有查询到该股票的基金持仓。")
        else:
            _render_paginated_dataframe(
                holders_df,
                key=f"stock_fund_holders_{stock_code_for_detail}",
                default_page_size=20,
            )

    if fund_code_for_detail:
        st.markdown('<div class="section-title">单只基金股票持仓明细</div>', unsafe_allow_html=True)
        fund_df = load_fund_holdings_detail(selected_report, fund_code_for_detail)
        if fund_df.empty:
            st.info("当前报告期没有查询到该基金的股票持仓。")
        else:
            _render_paginated_dataframe(
                fund_df,
                key=f"fund_holdings_detail_{fund_code_for_detail}",
                default_page_size=20,
            )

    # 不用 st.expander 标题（自定义 CSS 下 summary 中文易叠字）
    show_report_coverage = st.checkbox(
        "查看报告期覆盖情况",
        value=False,
        key="fund_show_report_coverage",
    )
    if show_report_coverage:
        _render_paginated_dataframe(
            report_df,
            key="fund_report_overview",
            default_page_size=20,
        )
