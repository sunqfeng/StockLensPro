import pandas as pd
import plotly.express as px
import streamlit as st

from stocklens.charts import (
    CN_DOWN,
    CN_UP,
    TERM_PIE_SEQUENCE,
    TERM_SERIES,
    apply_tech_layout,
    apply_tech_pie_layout,
    chart_subtitle_html,
)
from stocklens.data.loaders import load_strategy_stats, normalize_numeric_columns
from stocklens.pages.stock_price_history import render_stock_history_table


def render_main_dashboard(
    *,
    df_stats,
    df_detail,
    start_date,
    end_date,
    group_type,
    selected_batch,
    selected_status,
    min_count,
    recommendation_ids=None,
):
    # ==========================================================
    # 13. KPI 卡片
    # ==========================================================
    st.markdown('<div id="overview"></div>', unsafe_allow_html=True)

    def calc_weighted_success_rate(df, success_col, valid_col):
        """
        计算加权成功率：总上涨数量 / 总有效样本数量。

        注意：
        不能直接对每个策略的成功率求 mean，否则样本数很少的策略会被过度放大。
        """
        if success_col not in df.columns or valid_col not in df.columns:
            return float("nan")

        valid_sum = pd.to_numeric(df[valid_col], errors="coerce").fillna(0).sum()
        if valid_sum <= 0:
            return float("nan")

        success_sum = pd.to_numeric(df[success_col], errors="coerce").fillna(0).sum()
        return success_sum / valid_sum * 100


    kpi_df = df_stats
    selected_kpi_strategy = st.session_state.get("strategy_win_selected_strategy")
    kpi_filter_applied = False
    if (
        selected_kpi_strategy
        and "推荐策略" in df_stats.columns
        and selected_kpi_strategy in set(df_stats["推荐策略"].dropna().astype(str))
    ):
        kpi_df = df_stats[df_stats["推荐策略"].astype(str) == selected_kpi_strategy].copy()
        kpi_filter_applied = True

    kpi_scope_label = selected_kpi_strategy if kpi_filter_applied else "全部策略"
    total_recommend = int(kpi_df["推荐总数"].sum())
    avg_1d_success = calc_weighted_success_rate(kpi_df, "1日上涨数量", "已有1日数据数量")
    avg_5d_success = calc_weighted_success_rate(kpi_df, "5日上涨数量", "已有5日数据数量")
    avg_20d_success = calc_weighted_success_rate(kpi_df, "20日上涨数量", "已有20日数据数量")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
    <div class="kpi-card">
        <div class="kpi-icon">📋</div>
        <div class="kpi-title">推荐总数</div>
        <div class="kpi-value">{total_recommend}</div>
        <div class="kpi-sub">{kpi_scope_label}</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col2:
        value = "-" if pd.isna(avg_1d_success) else f"{avg_1d_success:.2f}%"
        st.markdown(
            f"""
    <div class="kpi-card">
        <div class="kpi-icon">🎯</div>
        <div class="kpi-title">加权1日成功率</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">总上涨数 / 总有效数</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col3:
        value = "-" if pd.isna(avg_5d_success) else f"{avg_5d_success:.2f}%"
        st.markdown(
            f"""
    <div class="kpi-card purple">
        <div class="kpi-icon">📊</div>
        <div class="kpi-title">加权5日成功率</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">总上涨数 / 总有效数</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col4:
        value = "-" if pd.isna(avg_20d_success) else f"{avg_20d_success:.2f}%"
        st.markdown(
            f"""
    <div class="kpi-card up">
        <div class="kpi-icon">⏱️</div>
        <div class="kpi-title">加权20日成功率</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">总上涨数 / 总有效数</div>
    </div>
    """,
            unsafe_allow_html=True,
        )


    # ==========================================================
    # 13.1 策略胜率圆饼图
    # ==========================================================
    st.markdown('<div id="strategy-win"></div>', unsafe_allow_html=True)

    # 这里固定用“按策略”重新统计一次，不受左侧“统计维度”影响。
    # 右侧展示 Top 8 策略上涨数量占比；左侧可以手动选择任意策略查看“成功 / 未成功”占比。
    strategy_win_df = load_strategy_stats(
        start_date=start_date,
        end_date=end_date,
        group_type="按策略",
        selected_batch=selected_batch,
        selected_status=selected_status,
        recommendation_ids=recommendation_ids,
    )
    strategy_win_df = normalize_numeric_columns(strategy_win_df)

    st.markdown(
        '<div class="section-title strategy-win-title">🏆 策略胜率圆饼图</div>',
        unsafe_allow_html=True,
    )

    pie_metric_options = {
        "1日": {
            "valid_col": "已有1日数据数量",
            "success_col": "1日上涨数量",
            "fail_col": "1日未上涨数量",
            "rate_col": "1日成功率%",
            "avg_col": "1日平均涨幅%",
        },
        "3日": {
            "valid_col": "已有3日数据数量",
            "success_col": "3日上涨数量",
            "fail_col": "3日未上涨数量",
            "rate_col": "3日成功率%",
            "avg_col": "3日平均涨幅%",
        },
        "5日": {
            "valid_col": "已有5日数据数量",
            "success_col": "5日上涨数量",
            "fail_col": "5日未上涨数量",
            "rate_col": "5日成功率%",
            "avg_col": "5日平均涨幅%",
        },
        "10日": {
            "valid_col": "已有10日数据数量",
            "success_col": "10日上涨数量",
            "fail_col": "10日未上涨数量",
            "rate_col": "10日成功率%",
            "avg_col": "10日平均涨幅%",
        },
    }

    pie_filter_col1, pie_filter_col2 = st.columns([1, 2])

    with pie_filter_col1:
        pie_period = st.selectbox(
            "圆饼图统计周期",
            ["1日", "3日", "5日", "10日"],
            index=2,
            help="选择圆饼图按推荐后第几日的涨幅来计算胜率。涨幅 > 0 视为成功。",
        )

    pie_cols = pie_metric_options[pie_period]
    valid_col = pie_cols["valid_col"]
    success_col = pie_cols["success_col"]
    fail_col = pie_cols["fail_col"]
    rate_col = pie_cols["rate_col"]
    avg_col = pie_cols["avg_col"]

    strategy_win_df = strategy_win_df[
        (strategy_win_df["推荐总数"] >= min_count)
        & (strategy_win_df[valid_col] > 0)
    ].copy()

    if not strategy_win_df.empty:
        strategy_win_df = strategy_win_df.sort_values(
            by=[rate_col, avg_col, "推荐总数"],
            ascending=[False, False, False],
            na_position="last",
        )

        # 排序后的第 1 名仍然是当前周期胜率最高策略。
        top_strategy_name = strategy_win_df.iloc[0]["推荐策略"]

        # 这里新增“展示策略”下拉框：默认展示最高胜率策略，但你可以切换查看其他策略。
        strategy_options = strategy_win_df["推荐策略"].dropna().astype(str).tolist()
        if st.session_state.get("strategy_win_selected_strategy") not in strategy_options:
            st.session_state["strategy_win_selected_strategy"] = strategy_options[0]

        with pie_filter_col2:
            selected_pie_strategy = st.selectbox(
                "圆饼图展示策略",
                strategy_options,
                index=0,
                key="strategy_win_selected_strategy",
                help="默认第一个是当前周期胜率最高策略，也可以手动选择其他策略查看成功/未成功占比。",
            )

        selected_strategy_row = strategy_win_df[
            strategy_win_df["推荐策略"].astype(str) == selected_pie_strategy
        ].iloc[0]

        def safe_int(value):
            if pd.isna(value):
                return 0
            return int(value)

        def safe_float(value):
            if pd.isna(value):
                return 0.0
            return float(value)

        selected_success_count = safe_int(selected_strategy_row[success_col])
        selected_fail_count = safe_int(selected_strategy_row[fail_col])
        selected_valid_count = safe_int(selected_strategy_row[valid_col])
        selected_success_rate = safe_float(selected_strategy_row[rate_col])
        selected_avg_pct = safe_float(selected_strategy_row[avg_col])

        st.markdown(
            f"""
    <div class="small-note strategy-win-note">
    当前按 <b>{rate_col}</b> 排序，胜率最高策略是：
    <b style="color:#3DDCFF; font-size:18px;">{top_strategy_name}</b>。<br>
    左侧圆饼图当前展示：
    <b style="color:#F0B429; font-size:18px;">{selected_pie_strategy}</b>。
    {rate_col}：<b>{selected_success_rate:.2f}%</b>，
    {avg_col}：<b>{selected_avg_pct:.2f}%</b>，
    有效样本数：<b>{selected_valid_count}</b>。
    </div>
    """,
            unsafe_allow_html=True,
        )

        pie_col1, pie_col2 = st.columns(2)

        with pie_col1:
            st.markdown(
                chart_subtitle_html(
                    f"{selected_pie_strategy}：{pie_period}成功 / 未成功占比"
                ),
                unsafe_allow_html=True,
            )
            selected_pie_df = pd.DataFrame(
                {
                    "结果": ["上涨成功", "未上涨"],
                    "数量": [selected_success_count, selected_fail_count],
                }
            )

            fig_selected_pie = px.pie(
                selected_pie_df,
                names="结果",
                values="数量",
                hole=0.55,
                color="结果",
                color_discrete_map={
                    "上涨成功": CN_UP,   # A股：红涨
                    "未上涨": CN_DOWN,  # A股：绿跌/未涨
                },
            )

            fig_selected_pie = apply_tech_pie_layout(fig_selected_pie, "")
            st.plotly_chart(fig_selected_pie, width="stretch", theme=None)

        with pie_col2:
            st.markdown(
                chart_subtitle_html(f"Top 8 策略：{pie_period}上涨数量占比"),
                unsafe_allow_html=True,
            )
            top_strategy_df = strategy_win_df.head(8).copy()
            top_strategy_df["成功率标签"] = top_strategy_df[rate_col].map(
                lambda x: "-" if pd.isna(x) else f"{x:.2f}%"
            )

            fig_rank_pie = px.pie(
                top_strategy_df,
                names="推荐策略",
                values=success_col,
                hover_data=[rate_col, valid_col, avg_col],
                hole=0.45,
                color_discrete_sequence=TERM_PIE_SEQUENCE,
            )

            fig_rank_pie = apply_tech_pie_layout(fig_rank_pie, "")
            fig_rank_pie.update_traces(
                textinfo="label+percent",
                hovertemplate=(
                    "策略：%{label}<br>"
                    "上涨数量：%{value}<br>"
                    f"{rate_col}：%{{customdata[0]:.2f}}%<br>"
                    f"{valid_col}：%{{customdata[1]}}<br>"
                    f"{avg_col}：%{{customdata[2]:.2f}}%"
                    "<extra></extra>"
                ),
            )
            st.plotly_chart(fig_rank_pie, width="stretch", theme=None)
    else:
        st.info(f"当前筛选条件下，没有可用于计算 {pie_period} 胜率的策略数据。")


    # ==========================================================
    # 14. 展示名称
    # ==========================================================
    df_stats["展示名称"] = df_stats["推荐策略"].astype(str)

    if "所属行业" in df_stats.columns:
        df_stats["展示名称"] = df_stats["展示名称"] + " / " + df_stats["所属行业"].astype(str)

    if "推荐日期" in df_stats.columns:
        df_stats["展示名称"] = df_stats["推荐日期"].astype(str) + " / " + df_stats["展示名称"]

    # 策略对比图固定按“策略”聚合，避免“日期 + 策略 + 行业”这类细粒度分组
    # 出现大量 1/1 = 100% 的小样本误导。
    chart_stats = load_strategy_stats(
        start_date=start_date,
        end_date=end_date,
        group_type="按策略",
        selected_batch=selected_batch,
        selected_status=selected_status,
    )
    chart_stats = normalize_numeric_columns(chart_stats)
    chart_min_count = max(min_count, 10)
    chart_stats = chart_stats[chart_stats["推荐总数"] >= chart_min_count].copy()

    if "5日成功率%" in chart_stats.columns:
        chart_stats = chart_stats.sort_values(
            by=["5日成功率%", "5日平均涨幅%", "推荐总数"],
            ascending=[False, False, False],
            na_position="last",
        )

    chart_stats["展示名称"] = chart_stats["推荐策略"].astype(str)
    df_top = chart_stats.head(30).copy()


    # ==========================================================
    # 15. 成功率对比图
    # ==========================================================
    st.markdown('<div id="chart-analysis"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">一、策略成功率对比</div>', unsafe_allow_html=True)
    # 小标题放在 Plotly 外，与图例彻底隔离
    st.markdown(
        chart_subtitle_html("1日、3日、5日、10日、20日成功率对比"),
        unsafe_allow_html=True,
    )

    success_cols = [
        "1日成功率%",
        "3日成功率%",
        "5日成功率%",
        "10日成功率%",
        "20日成功率%",
    ]

    fig_success = px.bar(
        df_top,
        x="展示名称",
        y=success_cols,
        barmode="group",
        color_discrete_sequence=TERM_SERIES,
    )
    fig_success = apply_tech_layout(fig_success, "", "成功率%", external_title=True)
    st.plotly_chart(
        fig_success,
        width="stretch",
        config={"displayModeBar": False},
        theme=None,
    )


    # ==========================================================
    # 16. 平均涨幅对比图
    # ==========================================================
    st.markdown('<div class="section-title">二、平均涨幅对比</div>', unsafe_allow_html=True)
    st.markdown(
        chart_subtitle_html("1日、3日、5日、10日、20日平均涨幅对比"),
        unsafe_allow_html=True,
    )

    pct_cols = [
        "1日平均涨幅%",
        "3日平均涨幅%",
        "5日平均涨幅%",
        "10日平均涨幅%",
        "20日平均涨幅%",
    ]

    fig_pct = px.bar(
        df_top,
        x="展示名称",
        y=pct_cols,
        barmode="group",
        color_discrete_sequence=TERM_SERIES,
    )
    fig_pct = apply_tech_layout(fig_pct, "", "平均涨幅%", external_title=True)
    st.plotly_chart(
        fig_pct,
        width="stretch",
        config={"displayModeBar": False},
        theme=None,
    )


    # ==========================================================
    # 17. 20日风险收益对比图
    # ==========================================================
    st.markdown('<div class="section-title">三、20日风险收益对比</div>', unsafe_allow_html=True)
    st.markdown(
        chart_subtitle_html("20日内最大涨幅与最大回撤对比"),
        unsafe_allow_html=True,
    )

    risk_cols = [
        "20日内平均最大涨幅%",
        "20日内平均最大回撤%",
    ]

    fig_risk = px.bar(
        df_top,
        x="展示名称",
        y=risk_cols,
        barmode="group",
        color_discrete_sequence=[
            CN_UP,    # 最大涨幅：红
            CN_DOWN,  # 最大回撤：绿
        ],
    )
    fig_risk = apply_tech_layout(fig_risk, "", "涨跌幅%", external_title=True)
    st.plotly_chart(
        fig_risk,
        width="stretch",
        config={"displayModeBar": False},
        theme=None,
    )


    # ==========================================================
    # 18. 统计结果明细表
    # ==========================================================
    st.markdown('<div id="stats-table"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">四、统计结果明细</div>', unsafe_allow_html=True)

    show_cols = [col for col in df_stats.columns if col != "展示名称"]

    st.markdown('<div class="table-card">', unsafe_allow_html=True)
    st.dataframe(
        df_stats[show_cols],
        width="stretch",
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


    # ==========================================================
    # 19. 单只股票明细
    # ==========================================================
    st.markdown('<div id="stock-detail"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">五、单只股票推荐后表现明细</div>', unsafe_allow_html=True)

    detail_df = df_detail.copy()

    if not detail_df.empty:
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            strategy_list = ["全部"] + sorted(detail_df["推荐策略"].dropna().unique().tolist())
            selected_strategy = st.selectbox("明细筛选：推荐策略", strategy_list)

        if selected_strategy != "全部":
            detail_df = detail_df[detail_df["推荐策略"] == selected_strategy]

        with filter_col2:
            industry_list = ["全部"] + sorted(detail_df["所属行业"].dropna().unique().tolist())
            selected_industry = st.selectbox("明细筛选：所属行业", industry_list)

        if selected_industry != "全部":
            detail_df = detail_df[detail_df["所属行业"] == selected_industry]

        with filter_col3:
            success_list = ["全部"] + sorted(detail_df["是否成功"].dropna().unique().tolist())
            selected_success = st.selectbox("明细筛选：是否成功", success_list)

        if selected_success != "全部":
            detail_df = detail_df[detail_df["是否成功"] == selected_success]

        st.caption(
            "雪球讨论热度排名来自最近一次全市场 Top 100 快照，仅供查看，"
            "不参与推荐分数或任何策略统计。"
        )
        st.markdown('<div class="table-card">', unsafe_allow_html=True)
        render_stock_history_table(detail_df)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("当前日期范围内没有股票明细数据。")

    st.markdown("---")
    st.markdown(
        """
    <div class="small-note">
    <b>看板使用建议：</b><br>
    1. 优先看 <b>5日成功率%</b> 和 <b>5日平均涨幅%</b>，这是判断策略短线有效性的核心指标。<br>
    2. 如果 <b>10日、20日平均涨幅</b> 高于 5日平均涨幅，说明策略可能适合多拿几天。<br>
    3. <b>20日内平均最大涨幅%</b> 代表策略爆发力；<b>20日内平均最大回撤%</b> 代表风险。<br>
    4. 如果某个策略在某个行业长期表现好，可以反向提高该行业在推荐算法中的权重。<br>
    5. 推荐总数太少时不要轻易下结论，建议样本量至少达到 30 后再判断策略是否稳定。
    </div>
    """,
        unsafe_allow_html=True,
    )
