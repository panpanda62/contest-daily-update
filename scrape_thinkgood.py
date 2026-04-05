import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.thinkcontest.com"
START_URL = "https://www.thinkcontest.com/thinkgood/index.do"

OUTPUT_DIR = "docs"
JSON_PATH = os.path.join(OUTPUT_DIR, "latest.json")
HTML_PATH = os.path.join(OUTPUT_DIR, "index.html")
DEBUG_HTML_PATH = "debug_list_page.html"

TARGET_COUNT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> str:
    print(f"[요청] {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"[상태코드] {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_text_by_label(all_text: str, label: str, next_labels=None) -> str:
    if next_labels is None:
        next_labels = [
            "주최", "주관", "응모분야", "접수방법", "접수기간",
            "참가자격", "시상종류", "시상금", "홈페이지",
            "첨부파일", "키워드", "문의", "스크랩"
        ]

    pattern = re.escape(label) + r"\s*(.*?)\s*(?=" + "|".join(map(re.escape, next_labels)) + r"|$)"
    match = re.search(pattern, all_text, re.DOTALL)
    if match:
        return clean_text(match.group(1))
    return ""


def extract_links_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    anchors = soup.select("a[href]")

    results = []
    seen = set()

    for a in anchors:
        href = a.get("href", "").strip()

        if "user/contest/view.do" in href or "contest/view.do" in href:
            full_url = urljoin(BASE_URL, href)

            if full_url in seen:
                continue
            seen.add(full_url)

            title = clean_text(a.get_text(" ", strip=True))
            if not title:
                title = a.get("title", "").strip()
            if not title:
                img = a.find("img")
                if img:
                    title = img.get("alt", "").strip()
            if not title:
                title = "제목 없음"

            results.append({
                "title": title,
                "url": full_url
            })

    if not results:
        found = re.findall(r'(/thinkgood/user/contest/view\.do\?[^"\'>\s]+)', html)
        for href in found:
            full_url = urljoin(BASE_URL, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            results.append({
                "title": "제목 없음",
                "url": full_url
            })

    return results


def collect_detail_links() -> list[dict]:
    html = fetch_html(START_URL)
    print("[목록 HTML 길이]", len(html))

    with open(DEBUG_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[디버그 HTML 저장] {DEBUG_HTML_PATH}")

    results = extract_links_from_html(html)
    print("[메인에서 수집한 링크 수]", len(results))
    return results


def supplement_links_from_detail_pages(items: list[dict], target_count: int = 10) -> list[dict]:
    """
    처음 수집한 링크가 부족하면, 상세 페이지 안의 다른 공모전 링크까지 추가 수집
    """
    merged = []
    seen = set()

    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            merged.append(item)

    if len(merged) >= target_count:
        return merged

    print(f"[보강 시작] 현재 {len(merged)}개 / 목표 {target_count}개")

    base_items = merged[:]
    for item in base_items:
        if len(merged) >= target_count:
            break

        try:
            html = fetch_html(item["url"])
            extra_links = extract_links_from_html(html)
            print(f"[상세 페이지 보강] {item['url']} 에서 {len(extra_links)}개 발견")

            for extra in extra_links:
                if extra["url"] not in seen:
                    seen.add(extra["url"])
                    merged.append(extra)
                    print(f"  + 추가: {extra['url']}")

                if len(merged) >= target_count:
                    break

        except Exception as e:
            print(f"[보강 실패] {item['url']} / {e}")

    print(f"[보강 후 링크 수] {len(merged)}")
    return merged


def parse_detail_page(item: dict) -> dict:
    try:
        html = fetch_html(item["url"])
        soup = BeautifulSoup(html, "lxml")

        text_lines = [clean_text(x) for x in soup.get_text("\n").splitlines()]
        text_lines = [x for x in text_lines if x]
        all_text = "\n".join(text_lines)

        host = extract_text_by_label(
            all_text,
            "주최",
            next_labels=["주관", "응모분야", "접수방법", "접수기간", "참가자격", "시상종류", "홈페이지", "키워드", "문의"]
        )

        period = extract_text_by_label(
            all_text,
            "접수기간",
            next_labels=["참가자격", "시상종류", "홈페이지", "키워드", "문의", "주최", "주관", "응모분야"]
        )

        field = extract_text_by_label(
            all_text,
            "응모분야",
            next_labels=["접수방법", "접수기간", "참가자격", "시상종류", "홈페이지", "키워드", "문의", "주최", "주관"]
        )

        target = extract_text_by_label(
            all_text,
            "참가자격",
            next_labels=["시상종류", "홈페이지", "키워드", "문의", "주최", "주관", "응모분야", "접수방법"]
        )

        keywords = extract_text_by_label(
            all_text,
            "키워드",
            next_labels=["문의", "홈페이지", "스크랩", "공모요강", "팀원모집", "주최", "주관"]
        )

        description = ""
        for line in text_lines:
            if len(line) >= 20 and all(x not in line for x in ["접수기간", "참가자격", "응모분야", "주최", "주관", "키워드"]):
                description = line
                break

        return {
            "title": item["title"],
            "url": item["url"],
            "host": host,
            "period": period,
            "field": field,
            "target": target,
            "keywords": keywords,
            "description": description
        }

    except Exception as e:
        return {
            "title": item["title"],
            "url": item["url"],
            "host": "",
            "period": "",
            "field": "",
            "target": "",
            "keywords": "",
            "description": f"상세 파싱 실패: {e}"
        }


def load_previous() -> list[dict]:
    if not os.path.exists(JSON_PATH):
        return []

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_json(data: list[dict]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def row_html(label: str, value: str) -> str:
    return f'''
    <p class="row">
        <span class="label">{label}:</span>
        <span class="value">{value or "-"}</span>
    </p>
    '''


def build_html(items: list[dict], previous: list[dict]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    prev_urls = {x.get("url", "") for x in previous}
    now_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")

    new_count = 0
    cards = []

    for item in items:
        is_new = item["url"] not in prev_urls
        if is_new:
            new_count += 1

        card = f"""
        <div class="card">
            {row_html("주최", item['host'])}
            {row_html("접수기간", item['period'])}
            {row_html("응모분야", item['field'])}
            {row_html("참가자격", item['target'])}
            {row_html("키워드", item['keywords'])}
            {row_html("설명", item['description'])}
            <p class="row"><a href="{item['url']}" target="_blank">상세보기</a></p>
        </div>
        """
        cards.append(card)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>씽굿 공모전 Daily Update</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
        }}
        .info {{
            text-align: center;
            color: #555;
            margin-bottom: 30px;
            line-height: 1.8;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .row {{
            margin: 10px 0;
            line-height: 1.6;
        }}
        .label {{
            font-size: 18px;
            font-weight: 700;
        }}
        .value {{
            font-size: 14px;
            font-weight: 400;
        }}
        .card a {{
            color: #1565c0;
            text-decoration: none;
            font-size: 18px;
        }}
        .card a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>씽굿 공모전 Daily Update</h1>
    <div class="info">
        마지막 업데이트: {now_str}<br>
        전체 공모전 수: {len(items)}개<br>
        신규 공모전 수: {new_count}개
    </div>

    {''.join(cards) if cards else '<p>표시할 데이터가 없습니다.</p>'}
</body>
</html>
"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_items = collect_detail_links()

    if not raw_items:
        print("[실패] 상세 링크를 하나도 찾지 못했습니다.")
        print(f"[확인 필요] {DEBUG_HTML_PATH} 파일을 열어서 실제 HTML 구조를 확인하세요.")
        return

    raw_items = supplement_links_from_detail_pages(raw_items, TARGET_COUNT)

    unique_items = []
    seen = set()

    for item in raw_items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique_items.append(item)

    # 최소 10개는 확보되도록, 최대는 12개 정도만 사용
    unique_items = unique_items[:12]

    print("[상세 파싱 시작]")
    detailed_items = []
    for item in unique_items:
        parsed = parse_detail_page(item)
        print(" -", parsed["url"])
        detailed_items.append(parsed)

    previous = load_previous()
    build_html(detailed_items, previous)
    save_json(detailed_items)

    print(f"[완료] {len(detailed_items)}개 항목 저장")
    print(f"[생성 파일] {HTML_PATH}")
    print(f"[생성 파일] {JSON_PATH}")


if __name__ == "__main__":
    main()
