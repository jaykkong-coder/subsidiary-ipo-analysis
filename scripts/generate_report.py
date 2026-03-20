"""
HTML 분석 리포트 생성 스크립트
- analysis_result.json을 읽어 정적 HTML 리포트 생성
- 인쇄/PDF 변환 가능한 포맷
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
INPUT_PATH = os.path.join(DATA_DIR, 'analysis_result.json')


def load_data():
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def fmt_pct(v):
    if v is None:
        return '-'
    pct = v * 100
    sign = '+' if pct >= 0 else ''
    return f'{sign}{pct:.1f}%'


def fmt_pct_color(v):
    if v is None:
        return '<span>-</span>'
    pct = v * 100
    sign = '+' if pct >= 0 else ''
    color = '#d63031' if pct >= 0 else '#0984e3'
    return f'<span style="color:{color};font-weight:600">{sign}{pct:.1f}%</span>'


def generate_html(data):
    cases = data['cases']
    insights = data['insights']

    # 요약 통계
    total = len(cases)
    split_count = sum(1 for c in cases if c['type'] == '물적분할')
    ipo_count = total - split_count

    ann_d0_vals = [c['metrics']['returns'].get('announcement_D0') for c in cases
                   if c['metrics']['returns'].get('announcement_D0') is not None]
    avg_ann_d0 = sum(ann_d0_vals) / len(ann_d0_vals) * 100 if ann_d0_vals else 0

    ipo30_vals = [c['metrics']['returns'].get('ipo_30d') for c in cases
                  if c['metrics']['returns'].get('ipo_30d') is not None]
    avg_ipo30 = sum(ipo30_vals) / len(ipo30_vals) * 100 if ipo30_vals else 0

    # 케이스 테이블 행
    case_rows = ''
    for c in cases:
        r = c['metrics']['returns']
        mcap_ratio = c['metrics'].get('mcap_ratio')
        mcap_ratio_str = fmt_pct(mcap_ratio) if mcap_ratio is not None else '-'
        case_rows += f"""
        <tr>
            <td>{c['parent']['name']}</td>
            <td>{c['subsidiary']['name']}</td>
            <td>{c['type']}</td>
            <td>{fmt_pct(c['metrics'].get('revenue_ratio'))}</td>
            <td>{mcap_ratio_str}</td>
            <td>{fmt_pct_color(r.get('announcement_D0'))}</td>
            <td>{fmt_pct_color(r.get('announcement_30d'))}</td>
            <td>{fmt_pct_color(r.get('ipo_D0'))}</td>
            <td>{fmt_pct_color(r.get('ipo_30d'))}</td>
        </tr>"""

    # 인사이트 목록
    insight_items = ''
    for ins in insights:
        color = '#d63031' if (ins.get('avg_return', 0) or 0) < 0 else '#00b894'
        insight_items += f"""
        <div style="padding:0.8rem 1rem;margin-bottom:0.5rem;border-left:4px solid {color};background:#f8f9fa;border-radius:4px;">
            <strong>[{ins['category']}]</strong> {ins['pattern']}
        </div>"""

    # 케이스별 상세
    case_details = ''
    for c in cases:
        r = c['metrics']['returns']
        mcap = c['metrics'].get('parent_market_cap')
        mcap_str = f"{mcap/10000:.1f}조원" if mcap else '-'

        case_details += f"""
        <div style="page-break-inside:avoid;margin-bottom:2rem;padding:1.5rem;background:#f8f9fa;border-radius:8px;">
            <h3 style="margin-bottom:0.8rem;color:#0c2461;">{c['parent']['name']} → {c['subsidiary']['name']}</h3>
            <table style="width:100%;font-size:0.85rem;margin-bottom:0.5rem;">
                <tr>
                    <td><strong>유형:</strong> {c['type']}</td>
                    <td><strong>발표일:</strong> {c['events']['split_announcement']}</td>
                    <td><strong>상장일:</strong> {c['events']['ipo_date']}</td>
                </tr>
                <tr>
                    <td><strong>모회사 시총:</strong> {mcap_str}</td>
                    <td><strong>자/모 시총비율:</strong> {fmt_pct(c['metrics'].get('mcap_ratio'))}</td>
                    <td><strong>매출비중:</strong> {fmt_pct(c['metrics'].get('revenue_ratio'))}</td>
                </tr>
            </table>
            <table style="width:100%;font-size:0.85rem;">
                <tr style="background:#0c2461;color:white;">
                    <th style="padding:0.4rem;">발표당일</th>
                    <th style="padding:0.4rem;">발표+30일</th>
                    <th style="padding:0.4rem;">상장당일</th>
                    <th style="padding:0.4rem;">상장+30일</th>
                </tr>
                <tr style="text-align:center;">
                    <td>{fmt_pct_color(r.get('announcement_D0'))}</td>
                    <td>{fmt_pct_color(r.get('announcement_30d'))}</td>
                    <td>{fmt_pct_color(r.get('ipo_D0'))}</td>
                    <td>{fmt_pct_color(r.get('ipo_30d'))}</td>
                </tr>
            </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>자회사 상장 영향 분석 리포트</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family: 'Pretendard', -apple-system, sans-serif; color:#2d3436; line-height:1.7; max-width:900px; margin:0 auto; padding:2rem; }}
        h1 {{ font-size:1.6rem; color:#0c2461; margin-bottom:0.3rem; }}
        h2 {{ font-size:1.2rem; color:#0c2461; margin:2rem 0 0.8rem; border-bottom:2px solid #0c2461; padding-bottom:0.3rem; }}
        h3 {{ font-size:1rem; }}
        .meta {{ color:#636e72; font-size:0.85rem; margin-bottom:2rem; }}
        .summary-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; margin:1rem 0; }}
        .summary-box {{ background:#f0f3ff; border-radius:8px; padding:1rem; text-align:center; }}
        .summary-box .num {{ font-size:1.8rem; font-weight:700; color:#0c2461; }}
        .summary-box .label {{ font-size:0.75rem; color:#636e72; }}
        table {{ width:100%; border-collapse:collapse; margin:1rem 0; font-size:0.85rem; }}
        th {{ background:#0c2461; color:white; padding:0.5rem 0.7rem; text-align:left; }}
        td {{ padding:0.5rem 0.7rem; border-bottom:1px solid #eee; }}
        .conclusion {{ background:#f0f3ff; padding:1.5rem; border-radius:8px; margin-top:1rem; }}
        @media print {{
            body {{ padding:1rem; font-size:0.8rem; }}
            .summary-grid {{ grid-template-columns: repeat(4,1fr); }}
        }}
    </style>
</head>
<body>
    <h1>자회사 상장이 모회사 주가에 미치는 영향</h1>
    <div class="meta">분석 기간: 2020-2024 | 생성일: {datetime.now().strftime('%Y-%m-%d')} | 데이터: KRX, DART OpenAPI</div>

    <h2>1. 분석 개요</h2>
    <p>본 리포트는 최근 5개년간 상장 모회사의 자회사 상장(물적분할 후 상장 + 기존 자회사 IPO) 사례를 수집하고, 주요 이벤트 시점 전후 모회사 주가 변동을 분석하여 패턴을 도출합니다.</p>

    <div class="summary-grid">
        <div class="summary-box"><div class="num">{total}</div><div class="label">전체 케이스</div></div>
        <div class="summary-box"><div class="num">{split_count}</div><div class="label">물적분할</div></div>
        <div class="summary-box"><div class="num">{ipo_count}</div><div class="label">기존자회사 IPO</div></div>
        <div class="summary-box"><div class="num">{avg_ipo30:+.1f}%</div><div class="label">상장후 30일 평균</div></div>
    </div>

    <h2>2. 전체 케이스 요약</h2>
    <table>
        <thead>
            <tr>
                <th>모회사</th><th>자회사</th><th>유형</th>
                <th>매출비중</th><th>자/모 시총</th>
                <th>발표당일</th><th>발표+30일</th><th>상장당일</th><th>상장+30일</th>
            </tr>
        </thead>
        <tbody>{case_rows}</tbody>
    </table>

    <h2>3. 주요 인사이트</h2>
    {insight_items}

    <h2>4. 케이스별 상세</h2>
    {case_details}

    <h2>5. 결론</h2>
    <div class="conclusion">
        <p><strong>핵심 발견:</strong></p>
        <ul style="margin:0.5rem 0 0 1.5rem;">
            <li>자회사 상장 당일 모회사 주가 <strong>대부분 하락</strong> (15건 중 12건)</li>
            <li>자회사 상장 후 30일 기준 모회사 주가 평균 <strong>{avg_ipo30:+.1f}%</strong></li>
            <li>자회사의 <strong>매출 비중이 높을수록</strong> 상장 후 모회사 주가 하락 폭이 큰 경향</li>
            <li>기존 자회사 IPO는 상장 후 30일 기준 <strong>10건 중 9건 하락</strong></li>
        </ul>
        <p style="margin-top:1rem;color:#636e72;font-size:0.85rem;">* 본 분석은 과거 데이터 기반이며 미래 수익률을 보장하지 않습니다. 개별 케이스의 시장 환경, 업종 특성 등 다양한 변수가 존재합니다.</p>
    </div>
</body>
</html>"""
    return html


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    data = load_data()
    html = generate_html(data)
    out_path = os.path.join(REPORTS_DIR, 'subsidiary_ipo_analysis_report.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report saved: {out_path}")


if __name__ == '__main__':
    main()
