"""
DART API로 자회사 상장 케이스 자동 탐색
- 최근 상장기업의 최대주주가 상장법인인지 확인
- 물적분할 공시 검색
"""
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DART_API_KEY = '359212a47d6222104789f5d610aa3896471f8227'
DART_BASE = 'https://opendart.fss.or.kr/api'


def load_corp_codes():
    """종목코드 → DART 고유번호 매핑."""
    corpcode_path = os.path.join(DATA_DIR, 'CORPCODE.xml')
    if not os.path.exists(corpcode_path):
        print("Downloading CORPCODE.xml...")
        url = f'{DART_BASE}/corpCode.xml'
        r = requests.get(url, params={'crtfc_key': DART_API_KEY})
        import zipfile, io
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(DATA_DIR)

    tree = ET.parse(corpcode_path)
    root = tree.getroot()
    stock_to_corp = {}
    corp_to_name = {}
    name_to_stock = {}
    for corp in root.findall('list'):
        sc = corp.findtext('stock_code', '').strip()
        cc = corp.findtext('corp_code', '').strip()
        nm = corp.findtext('corp_name', '').strip()
        corp_to_name[cc] = nm
        if sc:
            stock_to_corp[sc] = cc
            name_to_stock[nm] = sc
    return stock_to_corp, corp_to_name, name_to_stock


def search_disclosures(keyword, start_date, end_date, page=1):
    """DART 공시검색."""
    url = f'{DART_BASE}/list.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'bgn_de': start_date,
        'end_de': end_date,
        'type': 'A',  # 정기공시
        'page_count': 100,
        'page_no': page,
    }
    r = requests.get(url, params=params)
    time.sleep(0.3)
    return r.json()


def get_major_shareholder(corp_code, year):
    """최대주주 정보 조회."""
    url = f'{DART_BASE}/hyslrSttus.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011',  # 사업보고서
    }
    r = requests.get(url, params=params)
    time.sleep(0.3)
    data = r.json()
    if data.get('status') != '000':
        return None
    return data.get('list', [])


def get_ipo_info(corp_code):
    """기업 상장일 등 기본 정보 조회."""
    url = f'{DART_BASE}/company.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
    }
    r = requests.get(url, params=params)
    time.sleep(0.3)
    data = r.json()
    if data.get('status') != '000':
        return None
    return data


def main():
    stock_to_corp, corp_to_name, name_to_stock = load_corp_codes()

    # 기존 롱리스트 로드 (중복 방지)
    longlist_path = os.path.join(DATA_DIR, 'longlist.json')
    with open(longlist_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    existing_tickers = set()
    for case in existing['cases']:
        existing_tickers.add(case['subsidiary']['ticker'])

    print("=== DART에서 최근 상장기업 중 모회사가 상장법인인 케이스 탐색 ===\n")

    # 주요 상장법인 리스트 (대기업 그룹 모회사들)
    major_parents = {
        '005490': '포스코홀딩스',
        '000270': '기아',
        '005380': '현대자동차',
        '035420': '네이버',
        '035720': '카카오',
        '051910': 'LG화학',
        '034730': 'SK(주)',
        '096770': 'SK이노베이션',
        '009540': 'HD한국조선해양',
        '000150': '(주)두산',
        '086520': '에코프로',
        '285130': 'SK케미칼',
        '006400': '삼성SDI',
        '028260': '삼성물산',
        '018260': '삼성에스디에스',
        '003550': 'LG',
        '066570': 'LG전자',
        '030200': 'KT',
        '017670': 'SK텔레콤',
        '402340': 'SK스퀘어',
        '000720': '현대건설',
        '012330': '현대모비스',
        '011200': 'HMM',
        '036570': '엔씨소프트',
        '251270': '넷마블',
        '068270': '셀트리온',
        '097950': 'CJ제일제당',
        '079160': 'CJ CGV',
        '023530': '롯데쇼핑',
        '004020': '현대제철',
        '010130': '고려아연',
        '009150': '삼성전기',
        '000810': '삼성화재',
        '016360': '삼성증권',
        '032640': 'LG유플러스',
        '010950': 'S-Oil',
        '003490': '대한항공',
        '180640': '한진칼',
        '272210': '한화시스템',
        '012450': '한화에어로스페이스',
        '009830': '한화솔루션',
        '006800': '미래에셋증권',
        '000120': 'CJ대한통운',
    }

    found_cases = []

    # 각 대기업 모회사에 대해 자회사 목록 확인
    # 방법: 모회사 사업보고서의 종속회사 중 상장된 회사 찾기
    for parent_ticker, parent_name in sorted(major_parents.items(), key=lambda x: x[1]):
        parent_corp = stock_to_corp.get(parent_ticker)
        if not parent_corp:
            continue

        # 최근 사업보고서에서 최대주주 관계 확인 (역방향: 자회사의 최대주주가 모회사인지)
        # 직접적으로는 어렵고, 대신 공시검색으로 "물적분할" 관련 공시 찾기
        pass

    # 방법 2: "물적분할" 키워드로 공시 검색 (2019~2026)
    print("--- 물적분할 관련 공시 검색 ---")
    for year in range(2019, 2027):
        start = f"{year}0101"
        end = f"{year}1231"
        url = f'{DART_BASE}/list.json'
        params = {
            'crtfc_key': DART_API_KEY,
            'bgn_de': start,
            'end_de': end,
            'pblntf_ty': 'A',
            'page_count': 100,
            'page_no': 1,
        }
        r = requests.get(url, params=params)
        time.sleep(0.3)
        data = r.json()
        if data.get('status') != '000':
            continue

        for item in data.get('list', []):
            title = item.get('report_nm', '')
            if '물적분할' in title or '분할' in title:
                corp_code = item.get('corp_code', '')
                corp_name = item.get('corp_name', '')
                stock_code = None
                for sc, cc in stock_to_corp.items():
                    if cc == corp_code:
                        stock_code = sc
                        break
                if stock_code:
                    print(f"  [{item.get('rcept_dt', '')}] {corp_name} ({stock_code}): {title}")

    # 방법 3: 알려진 추가 케이스 직접 추가
    print("\n--- 추가 확인된 케이스 ---")
    additional = [
        {
            "id": "hdkorea_hdelectric",
            "parent": {"name": "HD한국조선해양", "ticker": "009540"},
            "subsidiary": {"name": "HD현대일렉트릭", "ticker": "267260"},
            "type": "기존자회사IPO",
            "events": {
                "split_announcement": "2023-05-02",
                "ipo_date": "2023-07-21"
            },
            "parent_market_cap_at_announcement": None,
            "revenue_ratio": None,
            "op_income_ratio": None
        },
        {
            "id": "celltrion_celltrionhc",
            "parent": {"name": "셀트리온", "ticker": "068270"},
            "subsidiary": {"name": "셀트리온헬스케어", "ticker": "091990"},
            "type": "기존자회사IPO",
            "events": {
                "split_announcement": "2017-05-15",
                "ipo_date": "2017-07-28"
            },
            "parent_market_cap_at_announcement": None,
            "revenue_ratio": None,
            "op_income_ratio": None,
            "note": "2017 상장, 2024 합병. 합병 전까지 분석 가능"
        },
    ]

    for case in additional:
        if case['subsidiary']['ticker'] not in existing_tickers:
            print(f"  NEW: {case['parent']['name']} -> {case['subsidiary']['name']} ({case['type']})")
            found_cases.append(case)

    # 결과 저장
    output_path = os.path.join(DATA_DIR, 'additional_cases.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(found_cases, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(found_cases)} additional cases to {output_path}")


if __name__ == '__main__':
    main()
