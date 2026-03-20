"""
재무 데이터 수집 스크립트
- DART OpenAPI로 연결/별도 재무제표 조회
- 매출액, 영업이익 추출
- 자회사/모회사 비중 계산
"""
import json
import os
import time
import zipfile
import io
import xml.etree.ElementTree as ET

import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FIN_DIR = os.path.join(DATA_DIR, 'financials')
LONGLIST_PATH = os.path.join(DATA_DIR, 'longlist.json')

DART_API_KEY = '359212a47d6222104789f5d610aa3896471f8227'
DART_BASE = 'https://opendart.fss.or.kr/api'

_corp_code_cache = None


def load_longlist():
    with open(LONGLIST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_corp_codes():
    global _corp_code_cache
    if _corp_code_cache is not None:
        return _corp_code_cache

    corpcode_path = os.path.join(DATA_DIR, 'CORPCODE.xml')
    if not os.path.exists(corpcode_path):
        print("Downloading CORPCODE.xml...")
        url = f'{DART_BASE}/corpCode.xml'
        params = {'crtfc_key': DART_API_KEY}
        r = requests.get(url, params=params)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(DATA_DIR)

    tree = ET.parse(corpcode_path)
    root = tree.getroot()
    mapping = {}
    for corp in root.findall('list'):
        sc = corp.findtext('stock_code', '').strip()
        if sc:
            mapping[sc] = corp.findtext('corp_code')
    _corp_code_cache = mapping
    return mapping


def get_corp_code(stock_code):
    codes = load_corp_codes()
    return codes.get(stock_code)


def get_financials(corp_code, year, report_code='11011', fs_div='CFS'):
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': report_code,
        'fs_div': fs_div,
    }
    r = requests.get(url, params=params)
    time.sleep(0.5)
    data = r.json()
    if data.get('status') != '000':
        return None
    return data.get('list', [])


def extract_metrics(fin_list):
    revenue = None
    op_income = None
    for item in fin_list:
        acnt = item.get('account_nm', '')
        amount_str = item.get('thstrm_amount', '').replace(',', '')
        if not amount_str:
            continue
        try:
            amount = int(amount_str)
        except ValueError:
            continue

        # 매출액 or 영업수익(은행/금융) or 수익(보험)
        if revenue is None:
            if ('매출' in acnt and '원가' not in acnt and '총' not in acnt) or \
               acnt in ('영업수익', '이자수익', '순이자이익'):
                revenue = amount
        if op_income is None:
            if '영업이익' in acnt and '손실' not in acnt:
                op_income = amount

    return {'revenue': revenue, 'op_income': op_income}


def find_sub_financials(sub_corp, ipo_year, current_year=2025):
    """자회사 재무데이터를 찾는다. IPO 이후 최근 사업연도부터 역순 탐색."""
    for year in range(current_year, ipo_year - 2, -1):
        fin = get_financials(sub_corp, year, fs_div='OFS')
        if fin:
            metrics = extract_metrics(fin)
            if metrics.get('revenue') is not None:
                return year, metrics
    return None, {'revenue': None, 'op_income': None}


def find_parent_financials(parent_corp, target_year):
    """모회사 연결재무데이터. target_year 먼저, 없으면 인접 연도."""
    for year in [target_year, target_year - 1, target_year + 1]:
        fin = get_financials(parent_corp, year, fs_div='CFS')
        if fin:
            metrics = extract_metrics(fin)
            if metrics.get('revenue') is not None:
                return year, metrics
    return None, {'revenue': None, 'op_income': None}


def process_case(case):
    announce_date = case['events']['split_announcement']
    ipo_date = case['events']['ipo_date']
    pre_year = int(announce_date[:4]) - 1
    ipo_year = int(ipo_date[:4])

    parent_ticker = case['parent']['ticker']
    sub_ticker = case['subsidiary']['ticker']

    parent_corp = get_corp_code(parent_ticker)
    if not parent_corp:
        print(f"    WARN: Corp code not found for {parent_ticker}")
        return None

    sub_corp = get_corp_code(sub_ticker)

    # 1차: 발표 직전 연도로 시도
    print(f"  Trying pre-announcement year ({pre_year})...")
    parent_fin = get_financials(parent_corp, pre_year, fs_div='CFS')
    parent_metrics = extract_metrics(parent_fin) if parent_fin else {'revenue': None, 'op_income': None}

    sub_metrics = {'revenue': None, 'op_income': None}
    used_year = pre_year

    if sub_corp:
        sub_fin = get_financials(sub_corp, pre_year, fs_div='OFS')
        if sub_fin:
            sub_metrics = extract_metrics(sub_fin)

        # 2차: 자회사 데이터 없으면 IPO 이후 최근 연도로 폴백
        if sub_metrics.get('revenue') is None:
            print(f"    Sub data missing for {pre_year}, searching post-IPO years...")
            found_year, sub_metrics = find_sub_financials(sub_corp, ipo_year)
            if found_year:
                print(f"    Found sub data for year {found_year}")
                used_year = found_year
                # 동일 연도의 모회사 연결재무도 다시 가져옴 (비율 일관성)
                p_year, p_metrics = find_parent_financials(parent_corp, found_year)
                if p_year:
                    parent_metrics = p_metrics
                    print(f"    Updated parent data to year {p_year}")

    result = {
        'case_id': case['id'],
        'year': used_year,
        'parent': parent_metrics,
        'subsidiary': sub_metrics,
        'revenue_ratio': None,
        'op_income_ratio': None,
    }

    if parent_metrics.get('revenue') and sub_metrics.get('revenue'):
        result['revenue_ratio'] = round(sub_metrics['revenue'] / parent_metrics['revenue'], 4)
    if parent_metrics.get('op_income') and sub_metrics.get('op_income'):
        if parent_metrics['op_income'] != 0:
            result['op_income_ratio'] = round(sub_metrics['op_income'] / parent_metrics['op_income'], 4)

    return result


def main():
    os.makedirs(FIN_DIR, exist_ok=True)
    data = load_longlist()

    for case in data['cases']:
        print(f"Processing: {case['parent']['name']} -> {case['subsidiary']['name']}")
        result = process_case(case)
        if result:
            path = os.path.join(FIN_DIR, f"{case['id']}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  Saved: {path}")
        print()

    print("Done!")


if __name__ == '__main__':
    main()
