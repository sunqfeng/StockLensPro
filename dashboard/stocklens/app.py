import pandas as pd
import streamlit as st

from stocklens.data.loaders import (
    load_batch_list,
    load_date_range,
    load_detail_data,
    load_strategy_stats,
    load_tech_score_data,
    normalize_detail_numeric_columns,
    normalize_numeric_columns,
    normalize_tech_score_numeric_columns,
)
from stocklens.pages.fund_info import render_fund_info_page
from stocklens.data.optimized_recommendations import (
    ALGORITHM_EFFECTIVE_DATE, ALGORITHM_VERSION, load_display_ids,
)
from stocklens.pages.hot_stocks import render_hot_stocks_page
from stocklens.pages.main_dashboard import render_main_dashboard
from stocklens.pages.paper_trading import render_paper_trading_page
from stocklens.pages.sector import render_sector_page
from stocklens.pages.task_center import render_task_center_page
from stocklens.pages.tech_score import render_tech_score_page
from stocklens.styles import apply_styles


def render_header():
    st.markdown(
        """
<div class="tide-top-accent" aria-hidden="true"></div>
<div class="tide-header-v2">
  <div class="tide-header-inner">
    <div class="tide-brand">
      <div class="tide-logo-mark">潮</div>
      <div>
        <div class="tide-title-v2">潮汐 Tide</div>
        <div class="tide-subtitle-v2">股票推荐策略分析看板 · 推荐跟踪 · 成功率验证 · 行业复盘 · 策略进化</div>
      </div>
    </div>
    <div class="tide-header-meta">
      <span class="tide-chip static">CN EQUITY</span>
      <span class="tide-chip rule">红涨绿跌</span>
      <span class="tide-chip live">LIVE</span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_control_panel():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    st.markdown("## 🧭 功能导航")
    page_name = st.radio(
        "页面",
        ["主看板", "模拟交易", "股票热榜", "技术评分单", "板块信息", "基金信息", "任务中心"],
        index=0,
        label_visibility="collapsed",
    )

    if page_name in ["模拟交易", "股票热榜", "基金信息", "任务中心"]:
        st.markdown("---")
        if page_name == "模拟交易":
            st.markdown(
                """
        <div class="small-note">
        虚拟资金自动买卖，不连接真实券商；收益与胜率按实际模拟成交统计。
        </div>
        """,
                unsafe_allow_html=True,
            )
        elif page_name == "任务中心":
            st.markdown(
                """
        <div class="small-note">
        手动执行入口独立于看板筛选条件，适合补跑同步、推荐和评分任务。
        </div>
        """,
                unsafe_allow_html=True,
            )
        elif page_name == "基金信息":
            st.markdown(
                """
        <div class="small-note">
        基金信息独立读取 fund_data_center 入库后的基金数据，默认展示最新完整报告期的基金持仓。
        </div>
        """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
        <div class="small-note">
        雪球股票讨论热榜每30分钟自动采集。红色表示热度上升，绿色表示热度下降。
        </div>
        """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)
        return {"page_name": page_name}

    st.markdown("---")
    st.markdown("## 🔎 筛选条件")

    min_date, max_date = load_date_range()

    if min_date is None:
        st.error("没有查询到推荐数据，请先确认 stock_recommend_record 表是否有数据。")
        st.stop()

    start_date = st.date_input(
        "开始推荐日期",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )

    end_date = st.date_input(
        "结束推荐日期",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

    if start_date > end_date:
        st.error("开始日期不能大于结束日期。")
        st.stop()

    batch_options = ["全部"] + load_batch_list(start_date, end_date)

    selected_batch = st.selectbox(
        "推荐批次号",
        batch_options,
        index=0,
    )

    selected_status = st.selectbox(
        "推荐状态",
        ["全部", "TRACKING", "FINISHED"],
        index=0,
    )

    group_type = st.selectbox(
        "统计维度",
        [
            "按策略",
            "按策略 + 行业",
            "按推荐日期 + 策略",
            "按推荐日期 + 策略 + 行业",
        ],
        index=3,
    )

    min_count = st.number_input(
        "最小推荐总数",
        min_value=1,
        max_value=1000,
        value=1,
        step=1,
    )

    sort_column = st.selectbox(
        "排序指标",
        [
            "5日成功率%",
            "5日平均涨幅%",
            "10日成功率%",
            "10日平均涨幅%",
            "20日成功率%",
            "20日平均涨幅%",
            "20日内平均最大涨幅%",
            "20日内平均最大回撤%",
            "推荐总数",
        ],
        index=0,
    )

    st.markdown("")
    st.button("查询数据")

    st.markdown("---")

    st.markdown(
        """
    <div class="small-note">
    <b>📌 数据说明</b><br>
    成功率：涨幅 &gt; 0 视为成功。<br>
    核心观察：5日成功率、5日平均涨幅、20日内最大涨幅、20日内最大回撤。<br>
    样本太少时结果容易失真，建议数据多后最小推荐总数设为 5、10 或 30。
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    return {
        "page_name": page_name,
        "start_date": start_date,
        "end_date": end_date,
        "selected_batch": selected_batch,
        "selected_status": selected_status,
        "group_type": group_type,
        "min_count": min_count,
        "sort_column": sort_column,
    }


def main():
    st.set_page_config(
        page_title="潮汐 Tide",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_styles()
    render_header()

    control_col, content_col = st.columns([0.18, 0.82], gap="small")

    with control_col:
        filters = render_control_panel()

    page_name = filters["page_name"]

    if page_name == "模拟交易":
        with content_col:
            render_paper_trading_page()
        st.stop()

    if page_name == "股票热榜":
        with content_col:
            render_hot_stocks_page()
        st.stop()

    if page_name == "任务中心":
        with content_col:
            render_task_center_page()
        st.stop()

    if page_name == "基金信息":
        with content_col:
            render_fund_info_page()
        st.stop()

    # 板块页只依赖日线热度数据，避免先查推荐/跟踪/评分三张表
    if page_name == "板块信息":
        with content_col:
            render_sector_page()
        st.stop()

    start_date = filters["start_date"]
    end_date = filters["end_date"]
    selected_batch = filters["selected_batch"]
    selected_status = filters["selected_status"]
    group_type = filters["group_type"]
    min_count = filters["min_count"]
    sort_column = filters["sort_column"]

    # 按页面懒加载：切换界面时不再无条件拉全量三套数据
    if page_name == "技术评分单":
        with st.spinner("加载技术评分数据..."):
            df_tech_score = load_tech_score_data(
                start_date=start_date,
                end_date=end_date,
                selected_batch=selected_batch,
                selected_status=selected_status,
            )
            df_tech_score = normalize_tech_score_numeric_columns(df_tech_score)
        with content_col:
            render_tech_score_page(df_tech_score)
        st.stop()

    recommendation_ids, optimization_info = load_display_ids(start_date,end_date,selected_batch)
    with content_col:
        st.subheader("推荐跟踪")
        st.caption(f"{ALGORITHM_EFFECTIVE_DATE} 起采用 {ALGORITHM_VERSION} 新规则；"
                   "此前的历史推荐全部保留，不重新筛除。模拟交易不变。")
        st.caption("验证新算法成功率时，请按生效日之后的推荐日期或批次筛选；跨期统计包含旧推荐。")
        if optimization_info["issues"]:
            st.warning("部分新规则快照无法读取，已排除；历史推荐不受影响。")
        if optimization_info["replayed"]:
            st.caption("新规则结果包含重放评估，不代表独立样本外验证或实际交易收益。")
        if not recommendation_ids:
            message = ("当前批次已完成新算法筛选，但没有保留的股票。"
                       if optimization_info["evaluated_batches"] else
                       "当前日期或批次没有历史推荐，或尚未完成新算法评估。")
            st.info(message)
            st.stop()
        st.caption(f"本范围历史推荐 {optimization_info['historical_records']} 条，"
                   f"新规则保留 {optimization_info['optimized_records']} 条；统计与明细口径一致。")

    with st.spinner("加载推荐统计与明细..."):
        df_stats = load_strategy_stats(
            start_date=start_date,
            end_date=end_date,
            group_type=group_type,
            selected_batch=selected_batch,
            selected_status=selected_status,
            recommendation_ids=recommendation_ids,
        )
        df_stats = normalize_numeric_columns(df_stats)

        df_detail = load_detail_data(
            start_date=start_date,
            end_date=end_date,
            selected_batch=selected_batch,
            selected_status=selected_status,
            recommendation_ids=recommendation_ids,
        )
        df_detail = normalize_detail_numeric_columns(df_detail)

    if df_stats.empty:
        st.warning("当前筛选条件下没有统计数据。")
        st.stop()

    df_stats = df_stats[df_stats["推荐总数"] >= min_count].copy()

    if df_stats.empty:
        st.warning("当前最小推荐总数过滤后没有数据，可以把左侧的“最小推荐总数”调小。")
        st.stop()

    if sort_column in df_stats.columns:
        df_stats = df_stats.sort_values(
            by=sort_column,
            ascending=False,
            na_position="last",
        )

    with content_col:
        render_main_dashboard(
            df_stats=df_stats,
            df_detail=df_detail,
            start_date=start_date,
            end_date=end_date,
            group_type=group_type,
            selected_batch=selected_batch,
            selected_status=selected_status,
            min_count=min_count,
            recommendation_ids=recommendation_ids,
        )


if __name__ == "__main__":
    main()
