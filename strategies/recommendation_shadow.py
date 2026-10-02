"""版本化影子筛选；不改变原推荐、跟踪或模拟交易。"""
import math

VERSION = "candidate-v1.2"
MODELS = {"海龟20日突破": "TURTLE_20_BREAKOUT_V1", "RPS强势突破": "RPS_STRONG_BREAKOUT_V1"}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def evaluate_candidate(row, breadth, coverage):
    """只使用推荐日指标；缺失不当作0，不将信号分解释为概率。"""
    strategy = row.get("strategy_name")
    if strategy not in {*MODELS, "均线金叉放量"}:
        return "未纳入优化", "该策略保留原算法"
    day = str(row.get("recommend_date"))[:10]
    if str(row.get("daily_date"))[:10] != day:
        return "数据待核查", "缺少推荐日行情"
    if row.get("data_quality") != "HIGH":
        return "数据待核查", "行情质量不满足要求"
    price, base = number(row.get("close_price")), number(row.get("recommend_price"))
    if price is None or base is None or min(price, base) <= 0:
        return "数据待核查", "推荐价或收盘价无效"
    if abs(price / base - 1) > .01:
        return "数据待核查", "推荐价与日线价偏差超过1%，保留原基准待核查"
    if strategy == "均线金叉放量":
        breadth, coverage = number(breadth), number(coverage)
        if breadth is None or not 0 <= breadth <= 100 or coverage is None or not .8 <= coverage <= 1:
            return "数据待核查", "市场宽度缺失或有效均线覆盖率不足80%"
        return ("候选保留", "市场宽度超过40%") if breadth > 40 else ("规则过滤", "市场宽度不超过40%")
    ma20 = number(row.get("ma20"))
    score = number(row.get("technical_score"))
    if ma20 is None or ma20 <= 0 or score is None or not 0 <= score <= 100:
        return "数据待核查", "均线或技术评分缺失/无效"
    if str(row.get("tech_date"))[:10] != day or row.get("score_model") != MODELS[strategy]:
        return "数据待核查", "评分日期或评分模型不匹配"
    if price / ma20 - 1 > .10:
        return "规则过滤", "距20日均线超过10%，过热"
    threshold = 85 if strategy == "海龟20日突破" else 75
    if score < threshold:
        return "规则过滤", f"技术评分低于{threshold}分（非原推荐分数）"
    if strategy == "RPS强势突破":
        high = number(row.get("high120"))
        count = number(row.get("high120_count"))
        if high is None or high <= 0 or count is None or count < 120:
            return "数据待核查", "不足120个有效市场交易日日线，不能确认高点"
        if number(row.get("adjustment_kinds")) != 1:
            return "数据待核查", "120日窗口存在复权标记混合或缺失"
        if price < high * .98:
            return "规则过滤", "距120日高点超过2%"
    return "候选保留", "满足本策略影子过滤条件；不是买入指令"
