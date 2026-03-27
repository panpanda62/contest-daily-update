import json
import re
from datetime import datetime, date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.wevity.com/"
LIST_URL = "https://www.wevity.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
}


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return BeautifulSoup(response.text, "html.parser")


def extract_detail_links() -> list[str]:
    soup = get_soup(LIST_URL)
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "c=find" in href and "gbn=view" in href:
            full_url = urljoin(BASE_URL, href)
            links.append(full_url)

    unique_links = []
    seen = set()

    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_title(soup: BeautifulSoup) -> str:
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])
        if title:
            return title

    for tag in soup.find_all(["h1", "h2", "h3", "strong"]):
        candidate = clean_text(tag.get_text(" ", strip=True))
        if len(candidate) >= 5:
            return candidate

    return "제목 없음"


def extract_period(text: str, lines: list[str]) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1).replace(" ", "")

    match = re.search(r"(\d{4}\.\d{2}\.\d{2}\s*~\s*\d{4}\.\d{2}\.\d{2})", text)
    if match:
        return match.group(1).replace(" ", "")

    for i, line in enumerate(lines):
        if any(label in line for label in ["접수기간", "기간", "공모기간"]):
            same_line_match = re.search(
                r"(\d{4}[-\.]\d{2}[-\.]\d{2}\s*~\s*\d{4}[-\.]\d{2}[-\.]\d{2})",
                line
            )
            if same_line_match:
                return same_line_match.group(1).replace(" ", "")

            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = clean_text(lines[j])
                next_match = re.search(
                    r"(\d{4}[-\.]\d{2}[-\.]\d{2}\s*~\s*\d{4}[-\.]\d{2}[-\.]\d{2})",
                    next_line
                )
                if next_match:
                    return next_match.group(1).replace(" ", "")

    return "정보 없음"


def parse_end_date(period: str):
    match = re.search(r"~\s*(\d{4})[-\.](\d{2})[-\.](\d{2})", period)
    if not match:
        return None

    y, m, d = match.groups()

    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def calculate_dday(period: str) -> str:
    end_dt = parse_end_date(period)
    if end_dt is None:
        return "계산불가"

    today = date.today()
    diff = (end_dt - today).days

    if diff > 0:
        return f"D-{diff}"
    elif diff == 0:
        return "D-Day"
    else:
        return f"마감 {abs(diff)}일 지남"


def parse_detail_page(url: str) -> dict | None:
    try:
        soup = get_soup(url)
        full_text = soup.get_text("\n", strip=True)
        lines = [clean_text(line) for line in full_text.split("\n") if clean_text(line)]

        title = extract_title(soup)
        period = extract_period(full_text, lines)
        dday = calculate_dday(period)

        return {
            "title": title,
            "period": period,
            "dday": dday,
            "detail_url": url
        }

    except Exception as e:
        print(f"상세 페이지 파싱 실패: {url} / {e}")
        return None


def remove_duplicates(items: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for item in items:
        key = (item["title"], item["period"], item["detail_url"])
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def sort_items(items: list[dict]) -> list[dict]:
    def sort_key(item):
        end_dt = parse_end_date(item["period"])
        if end_dt is None:
            return date.max
        return end_dt

    return sorted(items, key=sort_key)


def save_json(items: list[dict]) -> dict:
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "wevity",
        "count": len(items),
        "items": items
    }

    with open("contests.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def save_html(data: dict):
    rows = []

    for item in data["items"]:
        row = f"""
        <div class="card">
            <h2><a href="{item['detail_url']}" target="_blank">{item['title']}</a></h2>
            <p><strong>접수기간:</strong> {item['period']}</p>
            <p><strong>D-day:</strong> {item['dday']}</p>
            <p><a href="{item['detail_url']}" target="_blank">상세 보기</a></p>
        </div>
        """
        rows.append(row)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>공모전 Daily Update</title>
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
        }}
        .info {{
            text-align: center;
            color: #555;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}
        .card h2 {{
            margin-top: 0;
            font-size: 22px;
        }}
        a {{
            color: #1565c0;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>공모전 Daily Update</h1>
    <div class="info">
        <p>마지막 업데이트: {data["updated_at"]}</p>
        <p>수집 건수: {data["count"]}</p>
        <p>출처: 위비티</p>
    </div>
    {''.join(rows)}
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    print("목록 페이지 수집 중...")
    detail_links = extract_detail_links()
    print(f"상세 링크 {len(detail_links)}개 발견")

    detail_links = detail_links[:20]

    items = []
    for idx, link in enumerate(detail_links, start=1):
        print(f"[{idx}/{len(detail_links)}] 상세 파싱 중: {link}")
        item = parse_detail_page(link)
        if item:
            items.append(item)

    items = remove_duplicates(items)
    items = sort_items(items)

    data = save_json(items)
    save_html(data)

    print("완료")
    print(f"총 {len(items)}건 저장")


if __name__ == "__main__":
    main()