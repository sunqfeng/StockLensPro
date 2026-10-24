"""Read-only SQL/quote adapters for the independent paper signal observer."""
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from stocklens.db import get_engine
from stocklens.paper_research import VERSION, HORIZONS, SEEDS, build_groups, freeze_json, net_outcome, read_snapshot
from stocklens.paper_trading import DEFAULT_CONFIG, EXECUTION_VERSION, STRATEGY_DIR, _quote_function, fetch_quotes, limit_locked, _trade_dates


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'outputs' / 'paper_signal_research' / VERSION
TZ = ZoneInfo('Asia/Shanghai')
MIN_TURNOVER = 100_000_000


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def board(code):
    if code.startswith(('300', '301')):
        return 'ChiNext'
    if code.startswith(('688', '689')):
        return 'STAR'
    if code.startswith(('4', '8', '92')):
        return 'Beijing'
    return 'Main'


def read_inputs(day):
    with get_engine().connect() as conn:
        conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        conn.exec_driver_sql('SET TRANSACTION READ ONLY')
        conn.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT')
        runs = conn.execute(text("""SELECT * FROM paper_runs WHERE trade_date=:day
            AND run_type='SIGNAL' AND status='SUCCESS' ORDER BY id DESC LIMIT 1"""), {'day': day}).mappings().all()
        if not runs:
            raise ValueError('no successful same-day signal run')
        run = dict(runs[0])
        data_day = str(run['data_date'])[:10]
        if not data_day < day:
            raise ValueError('signal data is not strictly prior to entry date')
        dates = [str(r[0])[:10] for r in conn.execute(text("""SELECT DISTINCT trade_date FROM stock_daily
            WHERE trade_date<=:day ORDER BY trade_date DESC LIMIT 22"""), {'day': data_day})]
        if len(dates) != 22 or dates[0] != data_day:
            raise ValueError('insufficient prior market dates')
        history = pd.read_sql(text("""SELECT stock_code,trade_date,close_price,prev_close,volume,turnover,
            is_adjusted,data_quality FROM stock_daily WHERE trade_date BETWEEN :start AND :end
            ORDER BY stock_code,trade_date"""), conn, params={'start': dates[-1], 'end': data_day})
        info = pd.read_sql(text('SELECT stock_code,stock_name,sub_industry FROM stock_full_info'), conn)
        signals = [dict(r) for r in conn.execute(text("""SELECT id,run_id,data_date,stock_code,stock_name,
            score,reason,status,status_reason,quote_price,quote_time,config_version FROM paper_signals
            WHERE run_id=:run AND strategy_code='RPS_BREAKOUT' ORDER BY id"""), {'run': run['id']}).mappings()]
        account = conn.execute(text('SELECT config_json,config_version FROM paper_accounts WHERE id=:id'),
                               {'id': run['account_id']}).mappings().one()
        versions = [dict(r) for r in conn.execute(text('''SELECT version_no,config_json FROM paper_config_versions
            WHERE account_id=:id ORDER BY version_no'''), {'id': run['account_id']}).mappings()]
    config = {k: v for k, v in json.loads(account['config_json']).items() if k in DEFAULT_CONFIG}
    config['_account_version'] = account['config_version']
    config['_signal_configs'] = {str(r['version_no']): {k: v for k, v in json.loads(r['config_json']).items()
                                if k in DEFAULT_CONFIG} for r in versions}
    return run, dates, history, info, signals, config


def index_quotes():
    import requests
    import sys
    function = _quote_function()
    parser = sys.modules[function.__module__].parse_tencent_line
    response = requests.get('https://qt.gtimg.cn/q=sh000300,sh000001,sz399006', timeout=10,
                            headers={'Referer': 'https://gu.qq.com/'})
    response.raise_for_status()
    response.encoding = 'gbk'
    codes = {'000300': 'sh000300', '000001': 'sh000001', '399006': 'sz399006'}
    return {codes[row['stock_code']]: row for line in response.text.splitlines()
            if (row := parser(line)) and row['stock_code'] in codes}


def make_rows(day, data_day, history, info, signals, quotes, preview=False):
    if info['stock_code'].duplicated().any() or history.duplicated(['stock_code', 'trade_date']).any():
        raise ValueError('duplicate source security/date')
    names = {str(r['stock_code']).zfill(6): r for r in info.to_dict('records')}
    by_signal = {str(r['stock_code']).zfill(6): r for r in signals}
    source_order = {str(r['stock_code']).zfill(6): i for i, r in enumerate(signals)}
    if len(by_signal) != len(signals):
        raise ValueError('duplicate RPS candidate')
    daily = {str(code).zfill(6): frame for code, frame in history.groupby('stock_code')}
    rows = []
    for code in sorted(set(names) | set(by_signal) | set(daily)):
        if not code.startswith(('00', '30', '60', '68', '4', '8', '92')):
            continue
        quote = quotes.get(code, {})
        name = quote.get('stock_name') or names.get(code, {}).get('stock_name') or by_signal.get(code, {}).get('stock_name') or ''
        row = {'stock_code': code, 'stock_name': name, 'industry': names.get(code, {}).get('sub_industry'),
               'board': board(code), 'candidate': code in by_signal, 'eligible': False, 'exclusions': [],
               'entry_price': number(quote.get('close_price')), 'quote_time': str(quote.get('quote_time') or ''),
               'score': number(by_signal.get(code, {}).get('score')),
               'source_order': source_order.get(code),
               'signal_id': by_signal.get(code, {}).get('id'),
               'signal_config_version': by_signal.get(code, {}).get('config_version'),
               'prior_turnover': None, 'volatility20': None,
               'quote_volume': number(quote.get('volume')), 'raw_rps': None, 'rps_high120': None}
        frame = daily.get(code)
        if frame is None or len(frame) < 22 or str(frame.iloc[-1]['trade_date'])[:10] != data_day:
            row['exclusions'].append('missing_prior_history')
        else:
            row['prior_turnover'] = number(frame.iloc[-1]['turnover'])
            prices = [(number(r['close_price']), number(r['prev_close']), number(r['volume']))
                      for r in frame.tail(20).to_dict('records')]
            returns = [close/reference-1 for close, reference, volume in prices
                       if all(v is not None and v > 0 for v in (close, reference, volume))]
            if len(returns) == 20:
                row['volatility20'] = statistics.stdev(returns)
            else:
                row['exclusions'].append('missing_volatility_history')
            if row['prior_turnover'] is None or row['prior_turnover'] < MIN_TURNOVER:
                row['exclusions'].append('prior_turnover_below_100m')
            if frame['is_adjusted'].isna().any() or frame['is_adjusted'].nunique() != 1:
                row['exclusions'].append('mixed_or_missing_adjustment')
            if frame.iloc[-1]['data_quality'] != 'HIGH':
                row['exclusions'].append('prior_quality_not_high')
        if 'ST' in name.upper():
            row['exclusions'].append('ST')
        stamp = pd.to_datetime(row['quote_time'], errors='coerce')
        if (row['entry_price'] is None or row['entry_price'] <= 0 or pd.isna(stamp)
                or str(stamp.date()) != day or row['quote_volume'] is None or row['quote_volume'] <= 0):
            row['exclusions'].append('missing_invalid_or_suspended_quote')
        elif not preview and not time(14, 44) <= stamp.time() <= time(14, 50):
            row['exclusions'].append('quote_outside_capture_window')
        elif limit_locked(quote, 'BUY') or limit_locked(quote, 'SELL'):
            row['exclusions'].append('upper_or_lower_locked')
        if code in by_signal:
            source = by_signal[code]
            row['source_signal'] = {k: str(v) if k in ('data_date', 'quote_time', 'score', 'quote_price') and v is not None else v
                                    for k, v in source.items()}
            reason = by_signal[code].get('reason') or ''
            raw = re.search(r'RPS\s+([0-9.]+)', reason)
            high = re.search(r'高点\s*([0-9.]+)', reason)
            row['raw_rps'] = number(raw.group(1)) if raw else None
            row['rps_high120'] = number(high.group(1)) if high else None
            # Keep the original candidate flag; add a separate experiment flag, never delete the original.
            row['live_proximity_pass'] = (row['entry_price'] >= .9*row['rps_high120']
                                           if row['entry_price'] and row['rps_high120'] else None)
        rows.append(row)
    clean = [r for r in rows if not r['exclusions']]
    for key in ('prior_turnover', 'volatility20'):
        values = sorted(r[key] for r in clean if r[key] is not None)
        boundaries = [values[int((len(values)-1)*q)] for q in (1/3, 2/3)] if values else []
        for row in rows:
            row[key+'_bucket'] = sum(row[key] > b for b in boundaries) if row[key] is not None else -1
    for row in rows:
        row['eligible'] = not row['exclusions']
        row['stratum'] = f"{row['board']}:{row['prior_turnover_bucket']}:{row['volatility20_bucket']}"
    return rows


def collect(day=None, preview=False, output=OUTPUT):
    now = datetime.now(TZ)
    day = day or str(now.date())
    if day > str(now.date()):
        raise ValueError('future preview date')
    if not preview and (day != str(now.date()) or now.weekday() >= 5 or day not in _trade_dates(now.date())
                        or not time(14, 45) <= now.time() <= time(14, 50)):
        return {'event': 'capture_skipped', 'reason': 'outside_real_trading_window', 'day': day}
    target = Path(output) / ('previews' if preview else 'cohorts') / f'{day}.json.gz'
    if target.exists():
        old = read_snapshot(target)
        return {'event': 'capture_already_frozen', 'day': day, 'members': len(old['rows'])}
    run, dates, history, info, signals, config = read_inputs(day)
    codes = sorted(set(history['stock_code'].astype(str).str.zfill(6)))
    if preview:
        with get_engine().connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            records = [dict(r) for r in conn.execute(text("""SELECT stock_code,close_price,prev_close,volume
                FROM stock_daily WHERE trade_date=:day"""), {'day': day}).mappings()]
        quotes = {r['stock_code']: dict(r, quote_time=f'{day} 15:00:00', stock_name='') for r in records}
    else:
        quotes = fetch_quotes(codes)
    rows = make_rows(day, str(run['data_date'])[:10], history, info, signals, quotes, preview)
    finished = datetime.now(TZ)
    if not preview and (finished.date() != now.date() or finished.time() > time(14, 50)):
        return {'event': 'capture_failed', 'reason': 'capture_deadline_exceeded', 'day': day}
    benchmarks = {}
    benchmark_error = None
    if not preview:
        try:
            benchmarks = index_quotes()
            benchmarks = {k: v for k, v in benchmarks.items()
                          if not pd.isna(stamp := pd.to_datetime(v.get('quote_time'), errors='coerce')) and str(stamp.date()) == day
                          and time(14, 44) <= stamp.time() <= time(14, 50)}
        except Exception as exc:
            benchmark_error = type(exc).__name__
    groups = build_groups(rows, day)
    # Revalidation is its own arm; it never changes the frozen original candidate population.
    groups['groups']['rps_live_proximity'] = sorted(r['stock_code'] for r in rows
        if r['eligible'] and r['candidate'] and r.get('live_proximity_pass') is True)
    costs = {key: float(config[key]) for key in ('commission_rate', 'min_commission', 'sell_tax_rate', 'slippage_bps')}
    costs['nominal_budget'] = 100000.0
    for name, codes in groups['groups'].items():
        if name.startswith('universe_matched_'):
            groups['matching'][name]['RPS_overlap_n'] = len(set(codes) & set(groups['groups']['rps_all']))
    payload = {'version': VERSION, 'execution_version': EXECUTION_VERSION,
               'mode': 'historical_close_preview' if preview else 'prospective_1445', 'trade_date': day,
               'capture_started_at': now.isoformat(), 'capture_finished_at': datetime.now(TZ).isoformat(),
               'data_date': str(run['data_date'])[:10], 'source_run_id': run['id'],
               'account_config_version_at_capture': config['_account_version'],
               'signal_config_history': config['_signal_configs'],
               'source_code_version': run['code_version'], 'costs': costs, 'seeds': list(SEEDS),
               'horizons': list(HORIZONS), 'rules': {'min_prior_turnover': MIN_TURNOVER,
               'matching': 'board + prior turnover tercile + prior20 volatility tercile',
               'random_universe_may_include_RPS': True, 'preview_uses_current_metadata': preview},
               'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    (Path(__file__), ROOT/'stocklens/paper_research.py', ROOT/'stocklens/paper_trading.py',
                     STRATEGY_DIR/'strategies/rps_breakout.py', STRATEGY_DIR/'config.py')},
               'rows': rows, **groups,
               'benchmarks': {k: {'entry_price': number(v.get('close_price')), 'quote_time': str(v.get('quote_time'))}
                              for k, v in benchmarks.items()}, 'benchmark_error': benchmark_error}
    freeze_json(target, payload)
    return {'event': 'capture_frozen', 'mode': payload['mode'], 'day': day, 'universe': len(rows),
            'eligible': sum(r['eligible'] for r in rows), 'RPS_candidates': sum(r['candidate'] for r in rows),
            'groups': {k: len(v) for k, v in groups['groups'].items()},
            'exclusions': dict(Counter(reason for r in rows for reason in r['exclusions']))}


def capture_close(day, output):
    target = Path(output) / 'market_closes' / f'{day}.json.gz'
    if target.exists():
        return read_snapshot(target)
    with get_engine().connect() as conn:
        conn.exec_driver_sql('SET TRANSACTION READ ONLY')
        records = [dict(r) for r in conn.execute(text("""SELECT stock_code,trade_date,close_price,prev_close,
            volume,is_adjusted,data_quality FROM stock_daily WHERE trade_date=:day"""), {'day': day}).mappings()]
    if len(records) < 1000 or len(records) != len({r['stock_code'] for r in records}):
        raise ValueError('missing or duplicated market close partition')
    stocks = {}
    for r in records:
        quote = {'stock_code': r['stock_code'], 'close_price': number(r['close_price']),
                 'prev_close': number(r['prev_close']), 'quote_time': f'{day} 15:00:00'}
        stocks[r['stock_code']] = {'trade_date': day, 'close_price': quote['close_price'],
            'prev_close': quote['prev_close'], 'volume': number(r['volume']),
            'is_adjusted': r['is_adjusted'], 'data_quality': r['data_quality'],
            'sell_locked': limit_locked(quote, 'SELL')}
    indices = {}
    errors = {}
    import akshare as ak
    for symbol in ('sh000300', 'sh000001', 'sz399006'):
        try:
            frame = ak.stock_zh_index_daily_em(symbol=symbol, start_date=day.replace('-', ''), end_date=day.replace('-', ''))
            selected = frame[frame['date'].astype(str).str[:10] == day]
            if len(selected) != 1:
                raise ValueError('missing index target day')
            indices[symbol] = number(selected.iloc[0]['close'])
        except Exception as exc:
            errors[symbol] = type(exc).__name__
    payload = {'trade_date': day, 'captured_at': datetime.now(TZ).isoformat(), 'stocks': stocks,
               'indices': indices, 'index_source': 'AKShare stock_zh_index_daily_em / Eastmoney', 'index_errors': errors}
    return freeze_json(target, payload)


def settle(output=OUTPUT):
    now = datetime.now(TZ)
    day = str(now.date())
    if now.weekday() >= 5 or now.time() < time(16, 5) or day not in _trade_dates(now.date()):
        return {'event': 'settlement_skipped', 'reason': 'outside_trading_close', 'day': day}
    output = Path(output)
    paths = sorted((output/'cohorts').glob('*.json.gz'))
    if not paths:
        return {'event': 'settlement_skipped', 'reason': 'no_forward_cohorts', 'day': day}
    capture_close(day, output)
    dates = sorted(_trade_dates(now.date()))
    close_cache = {}
    completed = 0
    pending = 0
    for path in paths:
        cohort = read_snapshot(path)
        if cohort['mode'] != 'prospective_1445':
            continue
        entry_day = cohort['trade_date']
        if entry_day not in dates:
            raise ValueError('entry day missing from exchange calendar')
        entry_index = dates.index(entry_day)
        members = sorted({code for codes in cohort['groups'].values() for code in codes})
        rows = {r['stock_code']: r for r in cohort['rows']}
        for horizon in HORIZONS:
            target = output/'outcomes'/entry_day/f'{horizon:02d}d.json'
            if target.exists():
                continue
            if entry_index+horizon >= len(dates) or dates[entry_index+horizon] > day:
                pending += 1
                continue
            expected = dates[entry_index:entry_index+horizon+1]
            missing_days = []
            sources = {}
            for trading_day in expected:
                close_file = output/'market_closes'/f'{trading_day}.json.gz'
                if not close_file.exists():
                    missing_days.append(trading_day)
                else:
                    if trading_day not in close_cache:
                        close_cache[trading_day] = read_snapshot(close_file)
                    sources[trading_day] = hashlib.sha256(close_file.read_bytes()).hexdigest()
            outcomes = {}
            for code in members:
                bars = [close_cache[d]['stocks'][code] for d in expected
                        if d in sources and code in close_cache[d]['stocks']]
                outcomes[code] = net_outcome(dict(rows[code], trade_date=entry_day), bars, expected, cohort['costs'])
            groups = {}
            for name, codes in cohort['groups'].items():
                available = [outcomes[c] for c in codes if outcomes[c]['status'] == 'complete']
                observed = statistics.mean(r['net_return_pct'] for r in available) if available else None
                groups[name] = {'expected_n': len(codes), 'complete_n': len(available),
                    'coverage': len(available)/len(codes) if codes else None,
                    'mean_net_return_pct': observed if available and len(available) == len(codes) else None,
                    'observed_mean_net_return_pct': observed,
                    'observed_budget_return_pct': statistics.mean(r['budget_return_pct'] for r in available) if available else None,
                    'unavailable': dict(Counter(outcomes[c]['status'] for c in codes if outcomes[c]['status'] != 'complete'))}
            benchmark_returns = {}
            for symbol, entry in cohort['benchmarks'].items():
                close = close_cache.get(expected[-1], {}).get('indices', {}).get(symbol)
                price = entry.get('entry_price')
                benchmark_returns[symbol] = (close/price-1)*100 if close and price and price > 0 else None
            comparisons = {}
            original = groups['rps_all']['mean_net_return_pct']
            top3 = groups['legacy_top3']['mean_net_return_pct']
            for seed in SEEDS:
                random_all = groups[f'universe_matched_seed{seed}']['mean_net_return_pct']
                random_three = groups[f'rps_random3_seed{seed}']['mean_net_return_pct']
                comparisons[f'rps_minus_matched_seed{seed}'] = original-random_all if original is not None and random_all is not None else None
                comparisons[f'top3_minus_random3_seed{seed}'] = top3-random_three if top3 is not None and random_three is not None else None
            comparisons.update({f'rps_net_minus_{symbol}_price_return': original-value if original is not None and value is not None else None
                                for symbol, value in benchmark_returns.items()})
            freeze_json(target, {'version': VERSION, 'trade_date': entry_day, 'horizon': horizon,
                'target_date': expected[-1], 'evaluated_at': now.isoformat(), 'market_calendar': expected,
                'missing_market_snapshots': missing_days, 'source_close_hashes': sources,
                'cohort_hash': hashlib.sha256(path.read_bytes()).hexdigest(), 'groups': groups,
                'comparisons_percentage_points': comparisons, 'benchmark_price_returns_pct': benchmark_returns,
                'outcomes': outcomes, 'caveat': 'Fixed-horizon price-return diagnostic, not live account performance. '
                'Observed-only means can be selected by missingness; full-coverage means are null when incomplete. '
                'Cash distributions, overlapping cohorts and residual style differences preclude an alpha claim.'})
            completed += 1
    status = {'event': 'settlement_checked', 'day': day, 'new_horizons': completed, 'pending_horizons': pending}
    freeze_json(output/'checks'/f'{day}.json', status)
    return status
