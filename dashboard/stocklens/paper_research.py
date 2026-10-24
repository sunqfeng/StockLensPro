"""Fixed prospective signal controls; independent of simulated-account decisions."""
import hashlib
import gzip
import json
import math
import os
import tempfile
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


VERSION = 'paper-rps-controls-v1'
SEEDS = (17, 43, 97)
HORIZONS = (1, 5, 10, 20)


def read_snapshot(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def freeze_json(path, payload):
    path = Path(path)
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
    if path.suffix == '.gz':
        encoded = gzip.compress(encoded, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            staged.unlink(missing_ok=True)
            raise
    try:
        os.link(staged, path)
    except FileExistsError:
        pass
    finally:
        staged.unlink(missing_ok=True)
    return read_snapshot(path)


def build_groups(rows, day, seeds=SEEDS):
    if len(rows) != len({r['stock_code'] for r in rows}):
        raise ValueError('duplicate security identity')
    universe = [r for r in rows if r['eligible']]
    candidates = [r for r in universe if r['candidate']]
    groups = {
        'rps_all': sorted(r['stock_code'] for r in candidates),
        'legacy_top3': [],
    }
    unrankable = [r['stock_code'] for r in candidates if r.get('score') is None
                  or not math.isfinite(float(r['score']))]
    if not unrankable:
        groups['legacy_top3'] = [r['stock_code'] for r in sorted(candidates,
            key=lambda r: (-r['score'], r.get('source_order', 10**9), r['stock_code']))[:3]]
    required = Counter(r['stratum'] for r in candidates)
    matching = {}
    for seed in seeds:
        def key(row):
            value = f'{VERSION}|{day}|{seed}|{row["stock_code"]}'
            return hashlib.sha256(value.encode()).hexdigest()
        groups[f'rps_random3_seed{seed}'] = [r['stock_code'] for r in sorted(candidates, key=key)[:3]]
        controls = []
        counts = {}
        for stratum, count in sorted(required.items()):
            pool = sorted((r for r in universe if r['stratum'] == stratum), key=key)
            selected = pool[:count]
            controls.extend(r['stock_code'] for r in selected)
            counts[stratum] = {'required': count, 'available': len(pool), 'selected': len(selected),
                               'shortfall': max(0, count-len(selected))}
        name = f'universe_matched_seed{seed}'
        groups[name] = sorted(controls)
        matching[name] = counts
    return {'groups': groups, 'matching': matching,
            'ranking': {'status': 'unavailable' if unrankable else 'complete', 'missing_score_codes': sorted(unrankable)}}


def net_outcome(entry, bars, expected_dates, config):
    def missing(reason):
        return {'status': reason, 'net_return_pct': None, 'budget_return_pct': None}
    if (len(expected_dates) < 2 or expected_dates != sorted(set(expected_dates))
            or expected_dates[0] != entry['trade_date']):
        return missing('invalid_calendar')
    selected = {str(b['trade_date'])[:10]: b for b in bars if str(b['trade_date'])[:10] in expected_dates}
    if len(selected) != len([b for b in bars if str(b['trade_date'])[:10] in expected_dates]):
        return missing('duplicate_bar')
    if set(selected) != set(expected_dates):
        return missing('missing_bar')
    previous = None
    adjustment = None
    for day in expected_dates:
        bar = selected[day]
        if 'data_quality' in bar and bar['data_quality'] != 'HIGH':
            return missing('close_quality_not_high')
        for field in ('close_price', 'volume'):
            try:
                value = float(bar[field])
            except (TypeError, ValueError, KeyError):
                return missing('invalid_bar')
            if not math.isfinite(value) or value <= 0:
                return missing('suspended_or_invalid_bar')
        marker = bar.get('is_adjusted')
        if marker not in (0, 1):
            return missing('unknown_adjustment')
        if marker != 0:
            return missing('adjusted_bar_against_raw_entry')
        if adjustment is not None and marker != adjustment:
            return missing('mixed_adjustment')
        adjustment = marker
        try:
            reference = float(bar['prev_close'])
        except (KeyError, TypeError, ValueError):
            return missing('unknown_reference_price')
        if not math.isfinite(reference) or reference <= 0:
            return missing('unknown_reference_price')
        if previous is not None:
            if abs(reference-previous) > max(.011, abs(previous)*.0001):
                return missing('corporate_action_or_revision')
        previous = float(bar['close_price'])
    if selected[expected_dates[-1]].get('sell_locked') is not False:
        return missing('exit_unavailable')
    try:
        price = Decimal(str(entry['entry_price']))
        budget = Decimal(str(config['nominal_budget']))
        commission = Decimal(str(config['commission_rate']))
        minimum = Decimal(str(config['min_commission']))
        tax_rate = Decimal(str(config['sell_tax_rate']))
        slip = Decimal(str(config['slippage_bps'])) / 10000
        if (not all(x.is_finite() for x in (price, budget, commission, minimum, tax_rate, slip))
                or min(price, budget) <= 0 or min(commission, minimum, tax_rate, slip) < 0 or slip >= 1):
            return missing('invalid_execution_input')
    except Exception:
        return missing('invalid_execution_input')
    def money(value):
        return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    buy = (price * (1+slip)).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
    quantity = int(budget / buy / 100) * 100
    while quantity > 0:
        gross = money(quantity*buy)
        entry_fee = money(max(gross*commission, minimum))
        if gross+entry_fee <= budget:
            break
        quantity -= 100
    if quantity <= 0:
        return missing('insufficient_lot_budget')
    cost = gross+entry_fee
    sell = (Decimal(str(previous))*(1-slip)).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
    exit_gross = money(quantity*sell)
    exit_fee = money(max(exit_gross*commission, minimum))
    exit_tax = money(exit_gross*tax_rate)
    pnl = exit_gross-exit_fee-exit_tax-cost
    return {'status': 'complete', 'quantity': quantity, 'buy_fill': float(buy), 'sell_fill': float(sell),
            'invested_cost': float(cost), 'net_pnl': float(pnl), 'uninvested_cash': float(budget-cost),
            'total_fees_tax': float(entry_fee+exit_fee+exit_tax),
            'net_return_pct': float(pnl/cost*100), 'budget_return_pct': float(pnl/budget*100)}
