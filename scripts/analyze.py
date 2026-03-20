"""
분석 스크립트
- 주가 CSV + 재무 JSON 로드
- 이벤트 전후 수익률 계산 (당일 + 30일, 절대 + KOSPI 대비 초과)
- 4축 분류 (매출비중, 이익비중, 상장유형, 자회사/모회사 시총비율)
- 인사이트 도출
- analysis_result.json 출력
- dashboard/data/ 로 대시보드용 데이터 복사
"""
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pandas as pd
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PRICES_DIR = os.path.join(DATA_DIR, 'stock_prices')
FIN_DIR = os.path.join(DATA_DIR, 'financials')
LONGLIST_PATH = os.path.join(DATA_DIR, 'longlist.json')
OUTPUT_PATH = os.path.join(DATA_DIR, 'analysis_result.json')
DASHBOARD_DATA = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'data')


def load_longlist():
    with open(LONGLIST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_prices(ticker):
    path = os.path.join(PRICES_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def load_financials(case_id):
    path = os.path.join(FIN_DIR, f"{case_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calc_return(df, event_date_str, days, col='종가'):
    """이벤트일 기준 N거래일 후 수익률. days=0이면 전일 대비 당일 수익률."""
    event_date = pd.Timestamp(event_date_str)
    future = df[df.index >= event_date]
    if len(future) == 0:
        return None
    base_idx = future.index[0]
    base_pos = df.index.get_loc(base_idx)

    if days == 0:
        # 당일 수익률: 전일 종가 대비 당일 종가
        if base_pos == 0:
            return None
        prev_price = df.iloc[base_pos - 1][col]
        if prev_price == 0:
            return None
        cur_price = df.loc[base_idx, col]
        return round((cur_price - prev_price) / prev_price, 4)

    base_price = df.loc[base_idx, col]
    if base_price == 0:
        return None
    target_pos = base_pos + days
    if target_pos >= len(df):
        return None
    target_price = df.iloc[target_pos][col]
    return round((target_price - base_price) / base_price, 4)


DART_API_KEY = '359212a47d6222104789f5d610aa3896471f8227'
CORPCODE_PATH = os.path.join(DATA_DIR, 'CORPCODE.xml')
_CORP_CODE_MAP = None


def _load_corp_codes():
    global _CORP_CODE_MAP
    if _CORP_CODE_MAP is not None:
        return _CORP_CODE_MAP
    tree = ET.parse(CORPCODE_PATH)
    root = tree.getroot()
    _CORP_CODE_MAP = {}
    for corp in root.findall('list'):
        sc = corp.findtext('stock_code')
        if sc:
            _CORP_CODE_MAP[sc] = corp.findtext('corp_code')
    return _CORP_CODE_MAP


def get_listed_shares(ticker, year):
    """DART API로 보통주 상장주식수 조회."""
    codes = _load_corp_codes()
    corp_code = codes.get(ticker)
    if not corp_code:
        return None

    url = 'https://opendart.fss.or.kr/api/stockTotqySttus.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011',
    }
    try:
        r = requests.get(url, params=params)
        time.sleep(0.3)
        data = r.json()
        if data.get('status') != '000':
            return None
        for item in data.get('list', []):
            se = item.get('se', '')
            # 보통주, 보통주식, 의결권 있는 주식 등 다양한 표기
            se_clean = se.replace(' ', '')
            if ('보통주' in se_clean or '의결권있는' in se_clean) and '우선' not in se_clean and '합계' not in se_clean:
                shares_str = item.get('istc_totqy', '').replace(',', '').replace('-', '')
                if shares_str.isdigit():
                    return int(shares_str)
    except Exception as e:
        print(f"    Shares error for {ticker}: {e}")
    return None


def calc_market_cap(ticker, date_str, price_df):
    """종가 * 상장주식수로 시가총액 계산 (억원)."""
    event_date = pd.Timestamp(date_str)
    if price_df is None:
        return None

    # 이벤트일에 가장 가까운 거래일 종가
    future = price_df[price_df.index >= event_date]
    past = price_df[price_df.index <= event_date]
    if len(future) > 0:
        close = future.iloc[0]['종가']
    elif len(past) > 0:
        close = past.iloc[-1]['종가']
    else:
        return None

    # 상장주식수: 이벤트 연도부터 역순 + 정순 탐색
    base_year = event_date.year if event_date.month > 3 else event_date.year - 1
    shares = None
    for offset in [0, -1, 1, -2, 2, -3, 3]:
        shares = get_listed_shares(ticker, base_year + offset)
        if shares:
            break
    if not shares:
        return None

    return int(close * shares / 100000000)  # 원 -> 억원


def get_mcap_ratio_group(ratio):
    """자회사/모회사 시총 비율 그룹."""
    if ratio is None:
        return '미분류'
    if ratio >= 0.5:
        return '고비율(50%+)'
    elif ratio >= 0.2:
        return '중비율(20-50%)'
    else:
        return '저비율(<20%)'


def analyze_case(case, kospi_df):
    parent_df = load_prices(case['parent']['ticker'])
    fin = load_financials(case['id'])

    if parent_df is None:
        print(f"  SKIP: No price data for {case['parent']['name']}")
        return None

    # 수익률 계산: 당일(D+0) + 30일
    returns = {}
    for event_key, event_name in [
        ('split_announcement', 'announcement'),
        ('ipo_date', 'ipo')
    ]:
        event_date = case['events'].get(event_key)
        if not event_date:
            continue
        for days in [0, 30]:
            label = f"{event_name}_D0" if days == 0 else f"{event_name}_{days}d"
            ret = calc_return(parent_df, event_date, days)
            returns[label] = ret

            kospi_ret = calc_return(kospi_df, event_date, days)
            if ret is not None and kospi_ret is not None:
                returns[f"excess_{label}"] = round(ret - kospi_ret, 4)
            else:
                returns[f"excess_{label}"] = None

    # 시가총액: 자회사 상장일 당일 기준으로 모회사/자회사 모두 조회
    ipo_date = case['events']['ipo_date']
    print(f"  Getting market caps at IPO date ({ipo_date})...")
    sub_df = load_prices(case['subsidiary']['ticker'])
    parent_mcap = calc_market_cap(case['parent']['ticker'], ipo_date, parent_df)
    sub_mcap = calc_market_cap(case['subsidiary']['ticker'], ipo_date, sub_df)

    mcap_ratio = None
    if parent_mcap and sub_mcap and parent_mcap > 0:
        mcap_ratio = round(sub_mcap / parent_mcap, 4)

    result = {
        'id': case['id'],
        'parent': case['parent'],
        'subsidiary': case['subsidiary'],
        'type': case['type'],
        'events': case['events'],
        'metrics': {
            'parent_market_cap': parent_mcap,
            'subsidiary_market_cap': sub_mcap,
            'mcap_ratio': mcap_ratio,
            'mcap_ratio_group': get_mcap_ratio_group(mcap_ratio),
            'revenue_ratio': fin.get('revenue_ratio') if fin else None,
            'op_income_ratio': fin.get('op_income_ratio') if fin else None,
            'financial_year': fin.get('year') if fin else None,
            'mcap_base_date': ipo_date,
            'returns': returns,
        },
        'stock_prices_file': f"data/{case['parent']['ticker']}.csv",
    }
    return result


def derive_insights(cases):
    insights = []

    # 1. 상장유형별 분석
    for typ in ['물적분할', '기존자회사IPO']:
        group = [c for c in cases if c['type'] == typ]
        if len(group) < 2:
            continue
        for period_key, period_label in [
            ('announcement_D0', '발표 당일'),
            ('announcement_30d', '발표 후 30거래일'),
            ('ipo_D0', '상장 당일'),
            ('ipo_30d', '상장 후 30거래일'),
        ]:
            rets = [c['metrics']['returns'].get(period_key)
                    for c in group if c['metrics']['returns'].get(period_key) is not None]
            if len(rets) >= 2:
                avg = round(sum(rets) / len(rets), 4)
                direction = '하락' if avg < 0 else '상승'
                neg_count = sum(1 for r in rets if r < 0)
                insights.append({
                    'category': f'상장유형_{typ}',
                    'pattern': f'{typ} {len(rets)}건: {period_label} 평균 {avg*100:.1f}% {direction} ({neg_count}/{len(rets)}건 하락)',
                    'supporting_cases': [c['id'] for c in group
                                        if c['metrics']['returns'].get(period_key) is not None],
                    'confidence': 'high' if len(rets) >= 5 else 'medium',
                    'avg_return': avg,
                    'period': period_key,
                })

    # 2. 매출비중별 분석
    cases_with_rev = [c for c in cases if c['metrics'].get('revenue_ratio') is not None]
    if len(cases_with_rev) >= 3:
        high_rev = [c for c in cases_with_rev if c['metrics']['revenue_ratio'] >= 0.10]
        low_rev = [c for c in cases_with_rev if c['metrics']['revenue_ratio'] < 0.10]

        for group, label, desc in [
            (high_rev, '고비중', '매출비중 10% 이상'),
            (low_rev, '저비중', '매출비중 10% 미만'),
        ]:
            if len(group) < 2:
                continue
            for pk, pl in [('ipo_D0', '상장 당일'), ('ipo_30d', '상장 후 30일')]:
                rets = [c['metrics']['returns'].get(pk)
                        for c in group if c['metrics']['returns'].get(pk) is not None]
                if len(rets) >= 2:
                    avg = round(sum(rets) / len(rets), 4)
                    direction = '하락' if avg < 0 else '상승'
                    neg_count = sum(1 for r in rets if r < 0)
                    insights.append({
                        'category': f'매출비중_{label}',
                        'pattern': f'{desc} {len(rets)}건: {pl} 평균 {avg*100:.1f}% {direction} ({neg_count}/{len(rets)}건 하락)',
                        'supporting_cases': [c['id'] for c in group
                                            if c['metrics']['returns'].get(pk) is not None],
                        'confidence': 'high' if len(rets) >= 4 else 'medium',
                        'avg_return': avg,
                        'period': pk,
                    })

    # 3. 시총비율별 분석 (자회사/모회사)
    for group_name in ['고비율(50%+)', '중비율(20-50%)', '저비율(<20%)']:
        group = [c for c in cases if c['metrics'].get('mcap_ratio_group') == group_name]
        if len(group) < 2:
            continue
        for pk, pl in [('ipo_D0', '상장 당일'), ('ipo_30d', '상장 후 30일')]:
            rets = [c['metrics']['returns'].get(pk)
                    for c in group if c['metrics']['returns'].get(pk) is not None]
            if len(rets) >= 2:
                avg = round(sum(rets) / len(rets), 4)
                direction = '하락' if avg < 0 else '상승'
                neg_count = sum(1 for r in rets if r < 0)
                insights.append({
                    'category': f'시총비율_{group_name}',
                    'pattern': f'자/모 시총비율 {group_name} {len(rets)}건: {pl} 평균 {avg*100:.1f}% {direction} ({neg_count}/{len(rets)}건 하락)',
                    'supporting_cases': [c['id'] for c in group
                                        if c['metrics']['returns'].get(pk) is not None],
                    'confidence': 'high' if len(rets) >= 4 else 'medium',
                    'avg_return': avg,
                    'period': pk,
                })

    # 4. 복합: 고비중 + 물적분할
    high_rev_split = [c for c in cases
                      if c['type'] == '물적분할'
                      and (c['metrics'].get('revenue_ratio') or 0) >= 0.10]
    if len(high_rev_split) >= 2:
        rets = [c['metrics']['returns'].get('ipo_30d')
                for c in high_rev_split if c['metrics']['returns'].get('ipo_30d') is not None]
        if len(rets) >= 2:
            avg = round(sum(rets) / len(rets), 4)
            direction = '하락' if avg < 0 else '상승'
            insights.append({
                'category': '복합_고비중_물적분할',
                'pattern': f'매출비중 10%+ 물적분할 {len(rets)}건: 상장 후 30일 평균 {avg*100:.1f}% {direction}',
                'supporting_cases': [c['id'] for c in high_rev_split],
                'confidence': 'medium',
                'avg_return': avg,
                'period': 'ipo_30d',
            })

    return insights


def analyze_withdrawn_case(case, kospi_df):
    """불발 케이스 분석. 발표일 기준 수익률만 계산."""
    parent_df = load_prices(case['parent']['ticker'])
    if parent_df is None:
        print(f"  SKIP: No price data for {case['parent']['name']}")
        return None

    returns = {}
    ann_date = case['events'].get('announcement')
    wd_date = case['events'].get('withdrawal')

    if ann_date:
        for days in [0, 30]:
            label = f"announcement_D0" if days == 0 else f"announcement_{days}d"
            ret = calc_return(parent_df, ann_date, days)
            returns[label] = ret
            kospi_ret = calc_return(kospi_df, ann_date, days)
            if ret is not None and kospi_ret is not None:
                returns[f"excess_{label}"] = round(ret - kospi_ret, 4)
            else:
                returns[f"excess_{label}"] = None

    if wd_date:
        for days in [0, 30]:
            label = f"withdrawal_D0" if days == 0 else f"withdrawal_{days}d"
            ret = calc_return(parent_df, wd_date, days)
            returns[label] = ret
            kospi_ret = calc_return(kospi_df, wd_date, days)
            if ret is not None and kospi_ret is not None:
                returns[f"excess_{label}"] = round(ret - kospi_ret, 4)
            else:
                returns[f"excess_{label}"] = None

    return {
        'id': case['id'],
        'parent': case['parent'],
        'subsidiary': case['subsidiary'],
        'type': case['type'],
        'events': case['events'],
        'withdrawal_reason': case.get('withdrawal_reason', ''),
        'metrics': {
            'returns': returns,
        },
        'stock_prices_file': f"data/{case['parent']['ticker']}.csv",
    }


WITHDRAWN_PATH = os.path.join(DATA_DIR, 'withdrawn_cases.json')
WITHDRAWN_OUTPUT_PATH = os.path.join(DATA_DIR, 'withdrawn_result.json')


def copy_to_dashboard(cases, withdrawn_cases=None):
    os.makedirs(DASHBOARD_DATA, exist_ok=True)
    shutil.copy2(OUTPUT_PATH, os.path.join(DASHBOARD_DATA, 'analysis_result.json'))
    copied = set()
    for case in cases:
        for key in ['parent', 'subsidiary']:
            ticker = case[key]['ticker']
            if ticker not in copied:
                src = os.path.join(PRICES_DIR, f"{ticker}.csv")
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(DASHBOARD_DATA, f"{ticker}.csv"))
                    copied.add(ticker)
    if withdrawn_cases:
        shutil.copy2(WITHDRAWN_OUTPUT_PATH, os.path.join(DASHBOARD_DATA, 'withdrawn_result.json'))
        for case in withdrawn_cases:
            ticker = case['parent']['ticker']
            if ticker not in copied:
                src = os.path.join(PRICES_DIR, f"{ticker}.csv")
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(DASHBOARD_DATA, f"{ticker}.csv"))
                    copied.add(ticker)
    kospi_src = os.path.join(PRICES_DIR, 'KOSPI.csv')
    if os.path.exists(kospi_src):
        shutil.copy2(kospi_src, os.path.join(DASHBOARD_DATA, 'KOSPI.csv'))
    print(f"Copied {len(copied)+1} files to dashboard/data/")


def main():
    data = load_longlist()
    kospi_df = load_prices('KOSPI')

    # 상장 완료 케이스
    analyzed = []
    for case in data['cases']:
        print(f"Analyzing: {case['parent']['name']} -> {case['subsidiary']['name']}")
        result = analyze_case(case, kospi_df)
        if result:
            analyzed.append(result)

    insights = derive_insights(analyzed)

    output = {
        'generated_at': datetime.now().isoformat(),
        'total_cases': len(analyzed),
        'cases': analyzed,
        'insights': insights,
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Cases: {len(analyzed)}, Insights: {len(insights)}")
    print("\n=== Insights ===")
    for ins in insights:
        print(f"  [{ins['category']}] {ins['pattern']}")

    # 불발 케이스
    withdrawn_analyzed = []
    if os.path.exists(WITHDRAWN_PATH):
        with open(WITHDRAWN_PATH, 'r', encoding='utf-8') as f:
            wd_data = json.load(f)
        print("\n=== Withdrawn Cases ===")
        for case in wd_data['cases']:
            print(f"Analyzing withdrawn: {case['parent']['name']} -> {case['subsidiary']['name']}")
            result = analyze_withdrawn_case(case, kospi_df)
            if result:
                withdrawn_analyzed.append(result)

        wd_output = {
            'generated_at': datetime.now().isoformat(),
            'total_cases': len(withdrawn_analyzed),
            'cases': withdrawn_analyzed,
        }
        with open(WITHDRAWN_OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(wd_output, f, ensure_ascii=False, indent=2)
        print(f"Saved: {WITHDRAWN_OUTPUT_PATH} ({len(withdrawn_analyzed)} cases)")

    copy_to_dashboard(analyzed, withdrawn_analyzed)


if __name__ == '__main__':
    main()
