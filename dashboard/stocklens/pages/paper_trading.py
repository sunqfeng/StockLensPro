import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from stocklens.paper_trading import (
    DEFAULT_CONFIG,
    STRATEGY_NAMES,
    create_account,
    get_account,
    load_nav,
    load_positions,
    load_runs,
    load_signals,
    set_account_status,
    update_account_config,
)


def _money(value):
    return f"¥{float(value or 0):,.2f}"


def _pct(value):
    return f"{float(value or 0):+.2f}%"


def _signed_money(value):
    amount = float(value or 0)
    sign = "+" if amount > 0 else "-" if amount < 0 else ""
    return f"{sign}¥{abs(amount):,.2f}"


def _overview_summary(account, positions, closed, nav):
    market_value = float((positions["quantity"] * positions["current_price"]).sum()) if not positions.empty else 0
    total_assets = float(account["cash"]) + market_value
    initial_cash = float(account["initial_cash"])
    realized = float(closed["realized_pnl"].sum()) if not closed.empty else 0
    position_pnl = (
        positions["quantity"] * (positions["current_price"] - positions["entry_price"])
        - positions["entry_fee"]
        if not positions.empty else pd.Series(dtype=float)
    )
    unrealized = float(position_pnl.sum())
    wins = int((closed["realized_pnl"] > 0).sum()) if not closed.empty else 0
    losses = int((closed["realized_pnl"] < 0).sum()) if not closed.empty else 0
    return {
        "initial_cash": initial_cash,
        "market_value": market_value,
        "total_assets": total_assets,
        "total_pnl": total_assets - initial_cash,
        "cumulative": (total_assets / initial_cash - 1) * 100 if initial_cash else 0,
        "realized": realized,
        "unrealized": unrealized,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / (wins + losses) * 100 if wins + losses else 0,
        "open_wins": int((position_pnl > 0).sum()),
        "open_losses": int((position_pnl < 0).sum()),
        "max_drawdown": float(nav["drawdown_pct"].min()) if not nav.empty else 0,
    }


def _setup_form():
    st.subheader("创建前向模拟账户")
    st.info("账户创建后由系统自动买卖；初始金额将锁定，避免历史收益失真。")
    with st.form("paper_account_setup"):
        name = st.text_input("账户名称", value="前向模拟账户")
        initial_cash = st.number_input("初始金额（元）", min_value=10_000.0, value=1_000_000.0, step=10_000.0)
        strategies = st.multiselect(
            "启用策略",
            options=list(STRATEGY_NAMES),
            default=DEFAULT_CONFIG["strategies"],
            format_func=lambda code: STRATEGY_NAMES[code],
        )
        st.markdown("**自动卖出规则**")
        c1, c2, c3 = st.columns(3)
        take_profit = c1.number_input(
            "止盈（%）", min_value=0.1, value=float(DEFAULT_CONFIG["take_profit_pct"])
        )
        stop_loss = c2.number_input(
            "止损（%）", min_value=0.1, value=float(DEFAULT_CONFIG["stop_loss_pct"])
        )
        max_days = c3.number_input(
            "最长持有交易日", min_value=1, value=int(DEFAULT_CONFIG["max_holding_days"])
        )
        if st.form_submit_button("创建并启动", type="primary"):
            try:
                config = dict(
                    DEFAULT_CONFIG,
                    strategies=strategies,
                    take_profit_pct=take_profit,
                    stop_loss_pct=stop_loss,
                    max_holding_days=max_days,
                )
                create_account(name, initial_cash, config)
                st.success("模拟账户已启动。")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _overview(account, positions, closed, nav):
    summary = _overview_summary(account, positions, closed, nav)

    cols = st.columns(4)
    cols[0].metric("总资产", _money(summary["total_assets"]), _pct(summary["cumulative"]))
    cols[1].metric("账户总盈亏", _signed_money(summary["total_pnl"]))
    cols[2].metric("可用现金", _money(account["cash"]))
    cols[3].metric("持仓市值", _money(summary["market_value"]))

    cols = st.columns(4)
    cols[0].metric(
        "已实现盈亏",
        _signed_money(summary["realized"]),
        f"{summary['wins'] + summary['losses']}笔已平仓",
        delta_color="off",
    )
    cols[1].metric(
        "浮动盈亏",
        _signed_money(summary["unrealized"]),
        f"当前持仓：{summary['open_wins']}盈 · {summary['open_losses']}亏",
        delta_color="off",
    )
    cols[2].metric(
        "已平仓胜率",
        f"{summary['win_rate']:.1f}%",
        f"{summary['wins']}胜 · {summary['losses']}负",
        delta_color="off",
    )
    cols[3].metric("最大回撤", f"{summary['max_drawdown']:.2f}%")

    if nav.empty:
        st.info("账户已就绪，完成首次交易日结算后将显示收益曲线。")
        return

    chart_col, pnl_col = st.columns([0.6, 0.4])
    with chart_col:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=nav["trade_date"], y=nav["cumulative_return_pct"],
            mode="lines+markers", name="累计收益率", line={"color": "#ff5f6d", "width": 3},
        ))
        fig.update_layout(
            title="账户累计收益曲线", xaxis_title="交易日", yaxis_title="累计收益率（%）",
            template="plotly_dark", margin={"l": 20, "r": 20, "t": 50, "b": 20}, height=360,
        )
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
    with pnl_col:
        fig = go.Figure(go.Waterfall(
            measure=["absolute", "relative", "relative", "total"],
            x=["初始资金", "已实现盈亏", "浮动盈亏", "当前总资产"],
            y=[summary["initial_cash"], summary["realized"], summary["unrealized"], 0],
            text=[
                _money(summary["initial_cash"]),
                _signed_money(summary["realized"]),
                _signed_money(summary["unrealized"]),
                _money(summary["total_assets"]),
            ],
            textposition="outside",
            increasing={"marker": {"color": "#ff5f6d"}},
            decreasing={"marker": {"color": "#1fbf83"}},
            totals={"marker": {"color": "#3ddcff"}},
            connector={"line": {"color": "#566473"}},
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        ))
        fig.update_layout(
            title="资金变化", template="plotly_dark", showlegend=False,
            xaxis_title=None, yaxis_title="金额（元）", margin={"l": 20, "r": 20, "t": 50, "b": 20}, height=360,
        )
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
        st.caption(f"累计交易费用 {_money(nav.iloc[-1]['total_fees'])}，已包含在上述盈亏中，不重复相加。")


def _position_tables(positions, closed):
    current, history = st.tabs(["当前持仓", "已完成交易"])
    with current:
        if positions.empty:
            st.info("暂无持仓。")
        else:
            frame = positions.copy()
            frame["持仓市值"] = frame["quantity"] * frame["current_price"]
            frame["浮动盈亏"] = frame["quantity"] * (frame["current_price"] - frame["entry_price"]) - frame["entry_fee"]
            frame["浮动收益率%"] = frame["浮动盈亏"] / (frame["quantity"] * frame["entry_price"] + frame["entry_fee"]) * 100
            frame = frame.rename(columns={
                "stock_code": "股票代码", "stock_name": "股票名称", "strategy_name": "策略",
                "quantity": "数量", "entry_time": "买入时间", "entry_price": "成本价",
                "current_price": "现价", "take_profit_price": "止盈价", "stop_loss_price": "止损价",
            })
            st.dataframe(frame[["股票代码", "股票名称", "策略", "数量", "成本价", "现价", "持仓市值", "浮动盈亏", "浮动收益率%", "止盈价", "止损价", "买入时间"]], width="stretch", hide_index=True)
    with history:
        if closed.empty:
            st.info("暂无已完成交易。")
        else:
            frame = closed.rename(columns={
                "stock_code": "股票代码", "stock_name": "股票名称", "strategy_name": "策略",
                "quantity": "数量", "entry_time": "买入时间", "entry_price": "买入价",
                "exit_time": "卖出时间", "exit_price": "卖出价", "realized_pnl": "净收益",
                "exit_reason": "卖出原因", "config_version": "参数版本",
            })
            st.dataframe(frame[["股票代码", "股票名称", "策略", "数量", "买入时间", "买入价", "卖出时间", "卖出价", "净收益", "卖出原因", "参数版本"]], width="stretch", hide_index=True)


def _signal_table():
    signals = load_signals()
    if signals.empty:
        st.info("尚未产生14:10推荐信号。")
        return
    frame = signals.rename(columns={
        "signal_time": "信号时间", "data_date": "日线截止日", "stock_code": "股票代码",
        "stock_name": "股票名称", "strategy_name": "策略", "score": "评分",
        "quote_price": "信号后报价", "status": "处理状态", "status_reason": "说明",
        "config_version": "参数版本",
        "jev_status": "Jev状态", "jev_quality_probability": "Jev信号质量%",
        "jev_risk_probability": "Jev风险概率%", "jev_setup_score": "Jev形态分(0-3)",
        "jev_setup_confidence": "Jev置信度%", "jev_latency_ms": "Jev耗时ms",
    })
    frame["Jev状态"] = frame["Jev状态"].map({
        "SUCCESS": "影子评估成功", "ERROR": "评估失败", "DISABLED": "未启用",
    }).fillna("尚未评估")
    for column in ("Jev信号质量%", "Jev风险概率%", "Jev置信度%"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").mul(100).round(1)
    frame["Jev形态分(0-3)"] = pd.to_numeric(frame["Jev形态分(0-3)"], errors="coerce").round(2)
    st.caption("Jev当前为影子模式：只记录判断，不改变模拟买入结果。")
    st.dataframe(frame[[
        "信号时间", "日线截止日", "股票代码", "股票名称", "策略", "评分", "信号后报价",
        "处理状态", "说明", "Jev状态", "Jev信号质量%", "Jev风险概率%",
        "Jev形态分(0-3)", "Jev置信度%", "Jev耗时ms", "参数版本",
    ]], width="stretch", hide_index=True)


def _strategy_stats(closed):
    if closed.empty:
        st.info("完成交易后将按策略和参数版本统计收益与胜率。")
        return
    grouped = closed.groupby(["strategy_name", "config_version"], as_index=False).agg(
        交易数=("id", "count"),
        净收益=("realized_pnl", "sum"),
        平均收益=("realized_pnl", "mean"),
        盈利数=("realized_pnl", lambda values: int((values > 0).sum())),
    )
    grouped["胜率%"] = grouped["盈利数"] / grouped["交易数"] * 100
    grouped = grouped.rename(columns={"strategy_name": "策略", "config_version": "参数版本"})
    st.dataframe(grouped, width="stretch", hide_index=True)
    fig = px.bar(grouped, x="策略", y="净收益", color="参数版本", barmode="group")
    fig.update_layout(template="plotly_dark", xaxis_title=None, yaxis_title="净收益（元）", height=360)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def _settings(account):
    config = account["config"]
    st.caption(f"当前参数版本 v{account['config_version']}；修改只影响之后的新仓位。初始金额 {_money(account['initial_cash'])} 已锁定。")
    with st.form("paper_settings"):
        strategies = st.multiselect(
            "启用策略", list(STRATEGY_NAMES), default=config["strategies"],
            format_func=lambda code: STRATEGY_NAMES[code],
        )
        c1, c2, c3 = st.columns(3)
        position_pct = c1.number_input("单只仓位（%）", min_value=1.0, max_value=100.0, value=float(config["position_pct"]))
        max_positions = c2.number_input("最大持仓数", min_value=1, value=int(config["max_positions"]))
        max_daily_buys = c3.number_input("每日最多买入", min_value=1, value=int(config["max_daily_buys"]))
        c1, c2, c3 = st.columns(3)
        take_profit = c1.number_input("止盈（%）", min_value=0.1, value=float(config["take_profit_pct"]))
        stop_loss = c2.number_input("止损（%）", min_value=0.1, value=float(config["stop_loss_pct"]))
        max_days = c3.number_input("最长持有交易日", min_value=1, value=int(config["max_holding_days"]))
        c1, c2, c3 = st.columns(3)
        min_score = c1.number_input("最低推荐评分", min_value=0.0, value=float(config["min_score"]))
        commission = c2.number_input("佣金率", min_value=0.0, value=float(config["commission_rate"]), format="%.6f")
        slippage = c3.number_input("滑点（基点）", min_value=0.0, value=float(config["slippage_bps"]))
        if st.form_submit_button("保存新参数版本", type="primary"):
            try:
                new_config = dict(config, strategies=strategies, position_pct=position_pct,
                                  max_positions=max_positions, max_daily_buys=max_daily_buys,
                                  take_profit_pct=take_profit, stop_loss_pct=stop_loss,
                                  max_holding_days=max_days, min_score=min_score,
                                  commission_rate=commission, slippage_bps=slippage)
                update_account_config(account["id"], new_config)
                st.success("新参数已保存，下一个信号周期生效。")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    label = "暂停新开仓" if account["status"] == "ACTIVE" else "恢复新开仓"
    target = "PAUSED" if account["status"] == "ACTIVE" else "ACTIVE"
    if st.button(label):
        set_account_status(account["id"], target)
        st.rerun()


def _logs():
    runs = load_runs()
    if runs.empty:
        st.info("暂无运行记录。")
        return
    frame = runs.rename(columns={
        "run_type": "类型", "trade_date": "交易日", "data_date": "日线截止日",
        "status": "状态", "message": "结果", "code_version": "算法代码版本",
        "started_at": "开始时间", "finished_at": "结束时间",
    })
    st.dataframe(frame[["开始时间", "结束时间", "类型", "交易日", "日线截止日", "状态", "结果", "算法代码版本"]], width="stretch", hide_index=True)


def render_paper_trading_page():
    st.markdown("## 🧪 自动模拟交易")
    account = get_account()
    if not account:
        _setup_form()
        return

    status_text = "自动运行中" if account["status"] == "ACTIVE" else "已暂停"
    st.caption(f"{account['name']} · {status_text} · 每个交易日14:10自动产生信号并模拟买入")
    positions = load_positions("OPEN")
    closed = load_positions("CLOSED")
    nav = load_nav()

    overview, trades, signals, versions, settings, logs = st.tabs([
        "收益总览", "持仓与交易", "今日信号", "算法版本", "参数设置", "运行日志",
    ])
    with overview:
        _overview(account, positions, closed, nav)
    with trades:
        _position_tables(positions, closed)
    with signals:
        _signal_table()
    with versions:
        _strategy_stats(closed)
    with settings:
        _settings(account)
    with logs:
        _logs()
