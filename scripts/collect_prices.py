"""
주가 데이터 수집 스크립트
- longlist.json에서 종목코드 추출
- pykrx로 5년 일봉 수집
- KOSPI 지수도 수집
- CSV로 저장
"""
import json
import os
import time
from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PRICES_DIR = os.path.join(DATA_DIR, 'stock_prices')
LONGLIST_PATH = os.path.join(DATA_DIR, 'longlist.json')

END_DATE = datetime.now().strftime('%Y%m%d')


def load_longlist():
    with open(LONGLIST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def calc_start_date(cases):
    """발표일 3개월 전 vs 오늘-5년 중 더 이른 날짜 반환."""
    earliest_announcement = None
    for case in cases:
        ann = case['events'].get('split_announcement')
        if ann:
            d = datetime.strptime(ann, '%Y-%m-%d')
            if earliest_announcement is None or d < earliest_announcement:
                earliest_announcement = d

    five_years_ago = datetime.now() - timedelta(days=365 * 5)
    ann_minus_3m = (earliest_announcement - timedelta(days=90)) if earliest_announcement else five_years_ago

    return min(five_years_ago, ann_minus_3m).strftime('%Y%m%d')


def collect_stock(ticker, start, end=END_DATE):
    df = stock.get_market_ohlcv_by_date(start, end, ticker)
    time.sleep(1)
    return df


def collect_kospi(start, end=END_DATE):
    """KOSPI 지수 수집. pykrx index API 호환성 이슈 대비 fallback."""
    try:
        df = stock.get_index_ohlcv_by_date(start, end, "1001")
        time.sleep(1)
        return df
    except (KeyError, Exception):
        print("  KOSPI index API failed, using KODEX 200 ETF as proxy...")
        df = stock.get_market_ohlcv_by_date(start, end, "069500")
        time.sleep(1)
        return df


def save_csv(df, filename):
    path = os.path.join(PRICES_DIR, filename)
    df.to_csv(path, encoding='utf-8-sig')
    print(f"  Saved: {path} ({len(df)} rows)")


def main():
    os.makedirs(PRICES_DIR, exist_ok=True)
    data = load_longlist()
    start_date = calc_start_date(data['cases'])
    print(f"Collection range: {start_date} ~ {END_DATE}")

    tickers = set()
    for case in data['cases']:
        tickers.add((case['parent']['ticker'], case['parent']['name']))
        tickers.add((case['subsidiary']['ticker'], case['subsidiary']['name']))

    for ticker, name in sorted(tickers):
        print(f"Collecting {name} ({ticker})...")
        try:
            df = collect_stock(ticker, start_date)
            if len(df) > 0:
                save_csv(df, f"{ticker}.csv")
            else:
                print(f"  WARNING: No data for {ticker}")
        except Exception as e:
            print(f"  ERROR: {ticker} - {e}")

    print("Collecting KOSPI index...")
    df = collect_kospi(start_date)
    save_csv(df, "KOSPI.csv")

    print("Done!")


if __name__ == '__main__':
    main()
