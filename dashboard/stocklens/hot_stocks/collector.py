import json
import math
import re
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urlparse


XUEQIU_HOT_STOCK_URL = "https://xueqiu.com/hot/stock"
ALLOWED_HOSTS = frozenset({"xueqiu.com", "www.xueqiu.com"})
MAX_HTML_BYTES = 5_000_000
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]{1,32}$")


class HotStockValidationError(ValueError):
    """雪球响应不符合热点股票数据契约。"""


@dataclass(frozen=True)
class HotStockRecord:
    rank_no: int
    external_symbol: str
    normalized_code: str | None
    stock_name: str
    market: str
    heat_score: Decimal
    quote_change_pct: Decimal | None
    topic: str | None
    raw_payload: dict


class _InitialStoreParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._inside_store = False
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attributes = dict(attrs)
        self._inside_store = attributes.get("id") == "initStore"

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._inside_store = False

    def handle_data(self, data):
        if self._inside_store:
            self._parts.append(data)

    @property
    def initial_store_text(self):
        return "".join(self._parts)


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise HotStockValidationError("雪球请求跳转到了非白名单地址")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_hot_stock_html(*, timeout=10):
    """从固定白名单地址获取雪球热股HTML，不接受调用方传入URL。"""
    request = urllib.request.Request(
        XUEQIU_HOT_STOCK_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 StockLensPro/1.0",
        },
    )
    opener = urllib.request.build_opener(_AllowlistedRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise HotStockValidationError("雪球响应不是HTML页面")
        payload = response.read(MAX_HTML_BYTES + 1)

    if len(payload) > MAX_HTML_BYTES:
        raise HotStockValidationError("雪球响应超过允许的最大大小")
    return payload.decode("utf-8", errors="strict")


def parse_hot_stock_html(html, *, limit=100):
    """解析雪球页面内嵌状态，并返回经过边界校验的股票记录。"""
    if not 1 <= limit <= 100:
        raise ValueError("limit必须在1到100之间")
    if not isinstance(html, str) or not html:
        raise HotStockValidationError("雪球HTML内容为空")

    store = _load_initial_store(html)
    items = _find_stock_items(store)
    records = [_parse_item(item, rank) for rank, item in enumerate(items, 1)]

    symbols = [record.external_symbol for record in records]
    if len(symbols) != len(set(symbols)):
        raise HotStockValidationError("雪球榜单包含重复股票代码")
    return records[:limit]


def _load_initial_store(html):
    parser = _InitialStoreParser()
    parser.feed(html)
    script = parser.initial_store_text.strip()
    if not script:
        raise HotStockValidationError("雪球页面缺少初始状态")

    match = re.match(r"window\.__INITIAL_STORE__\s*=\s*(.+?)\s*;?\s*$", script, re.S)
    if not match:
        raise HotStockValidationError("雪球初始状态格式无法识别")
    try:
        return json.loads(_replace_javascript_undefined(match.group(1)))
    except json.JSONDecodeError as exc:
        raise HotStockValidationError("雪球初始状态不是有效JSON") from exc


def _replace_javascript_undefined(payload):
    """只替换JSON字符串外部的JavaScript undefined字面量。"""
    result = []
    index = 0
    inside_string = False
    escaped = False

    while index < len(payload):
        character = payload[index]
        if inside_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                inside_string = False
            index += 1
            continue

        if character == '"':
            inside_string = True
            result.append(character)
            index += 1
            continue

        if payload.startswith("undefined", index):
            before = payload[index - 1] if index else ""
            after_index = index + len("undefined")
            after = payload[after_index] if after_index < len(payload) else ""
            if not (before.isalnum() or before in "_$") and not (
                after.isalnum() or after in "_$"
            ):
                result.append("null")
                index = after_index
                continue

        result.append(character)
        index += 1

    return "".join(result)


def _find_stock_items(value):
    candidates = []

    def visit(node):
        if isinstance(node, list):
            stock_items = [item for item in node if _looks_like_stock(item)]
            if stock_items:
                candidates.append(stock_items)
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for child in node.values():
                visit(child)

    visit(value)
    if not candidates:
        raise HotStockValidationError("雪球初始状态中没有热点股票列表")
    return max(candidates, key=len)


def _looks_like_stock(item):
    return (
        isinstance(item, dict)
        and "symbol" in item
        and "name" in item
        and "value" in item
    )


def _parse_item(item, rank_no):
    symbol = str(item.get("symbol") or "").strip().upper()
    name = str(item.get("name") or "").strip()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise HotStockValidationError(f"第{rank_no}名股票代码无效")
    if not name or len(name) > 100:
        raise HotStockValidationError(f"第{rank_no}名股票名称无效")

    heat = _to_decimal(item.get("value"), field_name="热度", rank_no=rank_no)
    if heat < 0:
        raise HotStockValidationError(f"第{rank_no}名热度不能为负数")

    percent_value = item.get("percent")
    percent = (
        None
        if percent_value is None
        else _to_decimal(percent_value, field_name="涨跌幅", rank_no=rank_no)
    )
    market, normalized_code = _normalize_symbol(symbol, item.get("exchange"))

    hot = item.get("hot")
    topic = hot.get("tag") if isinstance(hot, dict) else None
    if topic is not None:
        topic = str(topic).strip()[:500] or None

    return HotStockRecord(
        rank_no=rank_no,
        external_symbol=symbol,
        normalized_code=normalized_code,
        stock_name=name,
        market=market,
        heat_score=heat,
        quote_change_pct=percent,
        topic=topic,
        raw_payload=item,
    )


def _to_decimal(value, *, field_name, rank_no):
    if isinstance(value, bool):
        raise HotStockValidationError(f"第{rank_no}名{field_name}无效")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HotStockValidationError(f"第{rank_no}名{field_name}无效") from exc
    if not math.isfinite(float(result)):
        raise HotStockValidationError(f"第{rank_no}名{field_name}无效")
    return result


def _normalize_symbol(symbol, exchange):
    if re.fullmatch(r"SH\d{6}", symbol):
        return "CN_SH", symbol[2:]
    if re.fullmatch(r"SZ\d{6}", symbol):
        return "CN_SZ", symbol[2:]

    exchange_name = str(exchange or "").upper()
    if exchange_name == "HK" or re.fullmatch(r"\d{5}", symbol):
        return "HK", None
    if exchange_name in {"NASDAQ", "NYSE", "AMEX"}:
        return "US", None
    return "OTHER", None
