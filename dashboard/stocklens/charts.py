# ==========================================================
# Chart theme helpers (UI only)
# A-share convention: 红涨绿跌 (red up / green down)
# ==========================================================

CN_UP = "#F6465D"
CN_DOWN = "#0ECB81"
CN_FLAT = "#8B9BB4"

TERM_CYAN = "#3DDCFF"
TERM_BLUE = "#4C8DFF"
TERM_AMBER = "#F0B429"
TERM_VIOLET = "#8B7CFF"
TERM_TEAL = "#2DD4BF"
TERM_ORANGE = "#FB923C"
TERM_SLATE = "#94A3B8"

TERM_SERIES = [
    TERM_CYAN,
    TERM_BLUE,
    TERM_AMBER,
    TERM_VIOLET,
    TERM_ORANGE,
]

TERM_PIE_SEQUENCE = [
    "#F6465D",
    "#F0B429",
    "#3DDCFF",
    "#4C8DFF",
    "#8B7CFF",
    "#FB923C",
    "#2DD4BF",
    "#94A3B8",
    "#E879F9",
]

CN_DIVERGING_SCALE = [
    (0.0, "#0ECB81"),
    (0.45, "#1A2740"),
    (0.5, "#8B9BB4"),
    (0.55, "#1A2740"),
    (1.0, "#F6465D"),
]

FONT_UI = (
    "Microsoft YaHei, PingFang SC, Noto Sans SC, "
    "Source Han Sans SC, Segoe UI, sans-serif"
)
FONT_NUM = FONT_UI


def chart_subtitle_html(text: str) -> str:
    """图表小标题：渲染在 Plotly 外部，避免与 legend 抢同一坐标系。"""
    safe = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<div class="chart-subtitle">{safe}</div>'


def _configure_bar_value_labels(fig, value_title_hint: str = ""):
    """给所有柱状图增加常驻数值，并关闭柱体悬浮数据框。"""
    bar_traces = [trace for trace in fig.data if getattr(trace, "type", "") == "bar"]
    if not bar_traces:
        return

    percent_keywords = ("%", "率", "涨幅", "跌幅", "回撤", "占比")
    integer_keywords = ("数量", "次数", "家数", "总数", "基金数", "股票数", "成分股数")

    orientations = set()
    axis_values = []
    for trace in bar_traces:
        orientation = getattr(trace, "orientation", None) or "v"
        orientations.add(orientation)
        metric_name = f"{value_title_hint} {getattr(trace, 'name', '')}"

        if any(keyword in metric_name for keyword in percent_keywords):
            value_format = ".1f"
            suffix = "%"
        elif any(keyword in metric_name for keyword in integer_keywords):
            value_format = ",.0f"
            suffix = ""
        else:
            value_format = ".2f"
            suffix = ""

        value_token = "x" if orientation == "h" else "y"
        trace.update(
            texttemplate=f"%{{{value_token}:{value_format}}}{suffix}",
            textposition="outside",
            cliponaxis=False,
            textfont={"family": FONT_UI, "color": "#E8EEF7", "size": 10},
            hoverinfo="skip",
            hovertemplate=None,
        )

        values = trace.x if orientation == "h" else trace.y
        for value in values if values is not None else []:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if numeric_value == numeric_value:  # 排除 NaN
                axis_values.append(numeric_value)

    # 为柱外文字留出空间，避免最大值或负值标签被坐标轴裁切。
    if axis_values and len(orientations) == 1:
        minimum = min(axis_values)
        maximum = max(axis_values)
        if minimum >= 0:
            axis_range = [0, max(1.0, maximum * 1.16)]
        elif maximum <= 0:
            axis_range = [min(-1.0, minimum * 1.16), 0]
        else:
            span = maximum - minimum
            axis_range = [minimum - span * 0.12, maximum + span * 0.12]

        if "h" in orientations:
            fig.update_xaxes(range=axis_range)
        else:
            fig.update_yaxes(range=axis_range)


def apply_tech_layout(fig, title, y_title, *, external_title: bool = True):
    """
    柱状/折线主题。

    默认 external_title=True：
      - Plotly 内不画 title（避免与 legend 重叠）
      - 调用方用 chart_subtitle_html + st.markdown 在图上方显示标题
      - legend 放在绘图区顶部内侧上方外侧（y>1），只占 top margin

    external_title=False 时：
      - title 画在图内顶部
      - legend 强制放右侧，永不与标题同带
    """
    # px.bar 在进入公共主题前仍保留真实数值轴标题，横向柱状图需要它来
    # 区分百分比、整数计数和普通小数的显示格式。
    original_x_title = getattr(getattr(fig.layout, "xaxis", None), "title", None)
    original_x_title = getattr(original_x_title, "text", "") or ""
    original_y_title = getattr(getattr(fig.layout, "yaxis", None), "title", None)
    original_y_title = getattr(original_y_title, "text", "") or ""

    fig.update_layout(template="plotly_dark")

    if external_title:
        # —— 标题在 HTML；图内无 title —— #
        fig.update_layout(
            title=None,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(8, 14, 24, 0.55)",
            font={"color": "#C5D0E0", "size": 12, "family": FONT_UI},
            legend={
                "bgcolor": "rgba(8, 14, 24, 0.55)",
                "bordercolor": "rgba(90, 120, 160, 0.16)",
                "borderwidth": 1,
                "font": {"color": "#E8EEF7", "size": 11, "family": FONT_UI},
                "orientation": "h",
                "x": 0.0,
                "xanchor": "left",
                "y": 1.12,
                "yanchor": "bottom",
                "itemclick": "toggleothers",
                "itemdoubleclick": "toggle",
                "tracegroupgap": 8,
                "itemsizing": "constant",
                "itemwidth": 30,
            },
            # top 只给图例一行；不再给内部 title 留位
            margin={"l": 56, "r": 20, "t": 48, "b": 96},
            height=460,
            hovermode="x unified",
            bargap=0.18,
            bargroupgap=0.06,
            hoverlabel={
                "bgcolor": "rgba(10, 18, 32, 0.96)",
                "bordercolor": "rgba(61, 220, 255, 0.35)",
                "font": {"color": "#F3F7FC", "size": 12, "family": FONT_UI},
            },
            dragmode="pan",
            colorway=TERM_SERIES,
            showlegend=True,
            autosize=True,
        )
        # 显式清空 title，防止 template/px 残留
        fig.layout.title = None
        fig.layout.legend.orientation = "h"
        fig.layout.legend.y = 1.12
        fig.layout.legend.yanchor = "bottom"
        fig.layout.margin.t = 48
        fig.layout.margin.b = 96
    else:
        # —— 内部 title + 右侧 legend —— #
        fig.update_layout(
            title={
                "text": title or "",
                "font": {"size": 14, "color": "#E8EEF7", "family": FONT_UI},
                "x": 0.0,
                "xanchor": "left",
                "y": 0.98,
                "yanchor": "top",
                "pad": {"t": 0, "b": 16, "l": 0, "r": 0},
            },
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(8, 14, 24, 0.55)",
            font={"color": "#C5D0E0", "size": 12, "family": FONT_UI},
            legend={
                "bgcolor": "rgba(8, 14, 24, 0.55)",
                "bordercolor": "rgba(90, 120, 160, 0.16)",
                "borderwidth": 1,
                "font": {"color": "#E8EEF7", "size": 11, "family": FONT_UI},
                "orientation": "v",
                "x": 1.02,
                "xanchor": "left",
                "y": 1.0,
                "yanchor": "top",
                "itemclick": "toggleothers",
                "itemdoubleclick": "toggle",
                "tracegroupgap": 6,
            },
            margin={"l": 56, "r": 150, "t": 64, "b": 96},
            height=460,
            hovermode="x unified",
            bargap=0.18,
            bargroupgap=0.06,
            hoverlabel={
                "bgcolor": "rgba(10, 18, 32, 0.96)",
                "bordercolor": "rgba(61, 220, 255, 0.35)",
                "font": {"color": "#F3F7FC", "size": 12, "family": FONT_UI},
            },
            dragmode="pan",
            colorway=TERM_SERIES,
            showlegend=True,
            autosize=True,
        )

    fig.update_xaxes(
        title_text="",
        showgrid=True,
        gridcolor="rgba(120, 145, 175, 0.08)",
        gridwidth=1,
        zeroline=True,
        zerolinecolor="rgba(120, 145, 175, 0.16)",
        zerolinewidth=1,
        tickfont={"color": "#A8B3C4", "size": 11, "family": FONT_UI},
        linecolor="rgba(120, 145, 175, 0.14)",
        automargin=True,
        tickangle=-28,
        showspikes=True,
        spikecolor="rgba(61, 220, 255, 0.35)",
        spikethickness=1,
        spikedash="dot",
    )

    fig.update_yaxes(
        title_text=y_title or "",
        showgrid=True,
        gridcolor="rgba(120, 145, 175, 0.08)",
        gridwidth=1,
        zeroline=True,
        zerolinecolor="rgba(120, 145, 175, 0.18)",
        zerolinewidth=1,
        title_font={"color": "#A8B3C4", "size": 12, "family": FONT_UI},
        tickfont={"color": "#A8B3C4", "size": 11, "family": FONT_UI},
        linecolor="rgba(120, 145, 175, 0.14)",
        automargin=True,
        showspikes=True,
        spikecolor="rgba(61, 220, 255, 0.28)",
        spikethickness=1,
        spikedash="dot",
    )

    fig.update_traces(
        textfont={"family": FONT_UI, "color": "#E8EEF7", "size": 11},
        selector=dict(type="bar"),
    )
    fig.update_traces(
        textfont={"family": FONT_UI, "color": "#E8EEF7", "size": 11},
        selector=dict(type="scatter"),
    )

    bar_traces = [trace for trace in fig.data if getattr(trace, "type", "") == "bar"]
    if bar_traces:
        first_orientation = getattr(bar_traces[0], "orientation", None) or "v"
        value_title_hint = original_x_title if first_orientation == "h" else original_y_title
        _configure_bar_value_labels(fig, value_title_hint or y_title or "")

    return fig


def apply_tech_pie_layout(fig, title):
    """饼图：标题在上（HTML 外置更佳），图例在右。"""
    fig.update_layout(template="plotly_dark")
    fig.update_layout(
        # 饼图也默认清空内部 title，由外部 HTML 控制；若传入 title 则放右侧不挡
        title=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#C5D0E0", "size": 12, "family": FONT_UI},
        legend={
            "bgcolor": "rgba(8, 14, 24, 0.40)",
            "bordercolor": "rgba(90, 120, 160, 0.15)",
            "borderwidth": 1,
            "font": {"color": "#E8EEF7", "size": 11, "family": FONT_UI},
            "orientation": "v",
            "yanchor": "middle",
            "y": 0.5,
            "xanchor": "left",
            "x": 1.02,
            "itemclick": "toggleothers",
            "itemdoubleclick": "toggle",
            "tracegroupgap": 6,
        },
        margin={"l": 16, "r": 150, "t": 24, "b": 20},
        height=400,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        hoverlabel={
            "bgcolor": "rgba(10, 18, 32, 0.96)",
            "bordercolor": "rgba(61, 220, 255, 0.35)",
            "font": {"color": "#F3F7FC", "size": 12, "family": FONT_UI},
        },
        showlegend=True,
        autosize=True,
    )
    fig.layout.title = None

    fig.update_traces(
        textposition="inside",
        textinfo="label+percent",
        hovertemplate="%{label}<br>数量/数值：%{value}<br>占比：%{percent}<extra></extra>",
        textfont={"color": "#F3F7FC", "size": 11, "family": FONT_UI},
        insidetextfont={"color": "#F3F7FC", "size": 11, "family": FONT_UI},
        outsidetextfont={"color": "#E8EEF7", "size": 11, "family": FONT_UI},
        marker={"line": {"color": "rgba(8, 14, 24, 0.85)", "width": 1.5}},
        pull=0,
    )
    return fig
