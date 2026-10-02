import pandas as pd
import streamlit as st


def render_tech_score_page(source_df):
    """
    渲染独立技术评分单页面。
    """
    st.markdown('<div id="tech-score"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">技术评分单</div>', unsafe_allow_html=True)
    st.caption(
        "雪球讨论热度排名来自最近一次全市场 Top 100 快照，仅供查看，"
        "不参与推荐分数、技术评分或筛选排序。"
    )

    tech_df = source_df.copy()

    if tech_df.empty:
        st.info("当前日期范围内没有技术评分数据。")
        return

    tech_filter_col1, tech_filter_col2, tech_filter_col3, tech_filter_col4 = st.columns(4)

    with tech_filter_col1:
        tech_keyword = st.text_input(
            "股票代码/名称",
            value="",
            placeholder="输入代码或名称",
        ).strip()

    if tech_keyword:
        keyword_mask = (
            tech_df["股票代码"].astype(str).str.contains(tech_keyword, case=False, na=False)
            | tech_df["股票名称"].astype(str).str.contains(tech_keyword, case=False, na=False)
        )
        tech_df = tech_df[keyword_mask]

    with tech_filter_col2:
        tech_strategy_list = ["全部"] + sorted(tech_df["推荐策略"].dropna().astype(str).unique().tolist())
        selected_tech_strategy = st.selectbox("推荐策略", tech_strategy_list)

    if selected_tech_strategy != "全部":
        tech_df = tech_df[tech_df["推荐策略"].astype(str) == selected_tech_strategy]

    with tech_filter_col3:
        tech_level_list = ["全部"] + sorted(tech_df["技术等级"].dropna().astype(str).unique().tolist())
        selected_tech_level = st.selectbox("技术等级", tech_level_list)

    if selected_tech_level != "全部":
        tech_df = tech_df[tech_df["技术等级"].astype(str) == selected_tech_level]

    with tech_filter_col4:
        risk_level_list = ["全部"] + sorted(tech_df["风险等级"].dropna().astype(str).unique().tolist())
        selected_risk_level = st.selectbox("风险等级", risk_level_list)

    if selected_risk_level != "全部":
        tech_df = tech_df[tech_df["风险等级"].astype(str) == selected_risk_level]

    score_filter_col1, score_filter_col2, score_filter_col3 = st.columns([1, 1, 2])

    with score_filter_col1:
        min_tech_score = st.number_input(
            "最低技术综合分",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
        )

    with score_filter_col2:
        only_scored = st.checkbox("只看已有评分", value=True)

    if only_scored:
        tech_df = tech_df[tech_df["技术综合分"].notna()]

    tech_df = tech_df[
        tech_df["技术综合分"].isna()
        | (tech_df["技术综合分"] >= min_tech_score)
    ].copy()

    if tech_df.empty:
        st.info("当前评分筛选条件下没有数据。")
        return

    tech_df = tech_df.sort_values(
        by=["技术综合分", "推荐日期"],
        ascending=[False, False],
        na_position="last",
    )

    scored_count = int(tech_df["技术综合分"].notna().sum())
    avg_score = tech_df["技术综合分"].mean()
    top_score = tech_df["技术综合分"].max()

    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    with kpi_col1:
        st.metric("当前展示股票数", len(tech_df))

    with kpi_col2:
        st.metric("已有评分数量", scored_count)

    with kpi_col3:
        st.metric("平均技术综合分", "-" if pd.isna(avg_score) else f"{avg_score:.2f}")

    with kpi_col4:
        st.metric("最高技术综合分", "-" if pd.isna(top_score) else f"{top_score:.2f}")

    tech_main_cols = [
        "推荐批次号",
        "推荐日期",
        "推荐策略",
        "所属行业",
        "股票代码",
        "股票名称",
        "雪球讨论热度排名",
        "雪球热度采集时间",
        "推荐价格",
        "推荐分数",
        "评分交易日",
        "评分收盘价",
        "技术综合分",
        "技术等级",
        "趋势分",
        "位置分",
        "动量分",
        "量能分",
        "风险分",
        "信号标签",
        "风险等级",
        "交易建议",
        "评分原因",
        "风险提示",
    ]
    tech_main_cols = [col for col in tech_main_cols if col in tech_df.columns]

    st.dataframe(
        tech_df[tech_main_cols],
        width="stretch",
        hide_index=True,
    )

    show_full_tech = st.checkbox(
        "查看完整技术指标字段",
        value=False,
        key="tech_show_full_fields",
    )
    if show_full_tech:
        st.dataframe(
            tech_df,
            width="stretch",
            hide_index=True,
        )
