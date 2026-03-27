import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.contestkorea.com"
LIST_URL = "https://www.contestkorea.com/sub/list.php?int_gbn=1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.contestkorea.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def is_dday_line(text: str) -> bool:
    text = clean_text(text)
    return bool(re.fullmatch(r"D-\d+|D-Day", text))


def is_period_line(text: str) -> bool:
    text = clean_text(text)
    return bool(re.search(r"접수\s*\d{2}\.\d{2}\s*[~\-]\s*\d{2}\.\d{2}", text))


def extract_period(text: str) -> str:
    text = clean_text(text)
    match = re.search(r"접수\s*(\d{2}\.\d{2}\s*[~\-]\s*\d{2}\.\d{2})", text)
    if match:
        return match.group(1).replace(" ", "")
    return "정보 없음"


def is_host_line(text: str) -> bool:
    text = clean_text(text)
    return text.startswith("주최") or text.startswith("주관")


def extract_host(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"^(주최|주관)\s*[.:·∙]?\s*", "", text)
    return text if text else "정보 없음"


def is_bad_title(text: str) -> bool:
    text = clean_text(text)

    if not text:
        return True
    if len(text) < 4:
        return True
    if text in {
        "대상", "지역", "주최·주관", "총상금", "1등상금",
        "전체", "누구나", "대학생", "일반인", "온라인"
    }:
        return True
    if text.startswith("접수"):
        return True
    if text.startswith("주최") or text.startswith("주관"):
        return True
    if text.startswith("심사") or text.startswith("발표"):
        return True
    if text.startswith("조회"):
        return True
    if text.startswith("관심"):
        return True
    if text.startswith("스크랩"):
        return True
    if text.startswith("정부") or text.startswith("신문") or text.startswith("학교"):
        return True
    if re.fullmatch(r"D-\d+|D-Day", text):
        return True

    return False


def extract_items_from_lines(lines: list[str]) -> list[dict]:
    items = []

    for i, line in enumerate(lines):
        if not is_dday_line(line):
            continue

        dday = clean_text(line)
        title = ""
        host = "정보 없음"
        period = "정보 없음"

        # D-day 앞뒤 범위에서 정보 찾기
        start = max(0, i - 6)
        end = min(len(lines), i + 8)
        window = lines[start:end]

        # 접수기간 찾기
        for w in window:
            if is_period_line(w):
                period = extract_period(w)
                break

        # 주최 찾기
        for w in window:
            if is_host_line(w):
                host = extract_host(w)
                break

        # 제목 찾기: D-day 바로 뒤쪽 우선, 없으면 앞쪽도 탐색
        candidate_lines = lines[i + 1:min(len(lines), i + 7)] + lines[max(0, i - 6):i]
        for w in candidate_lines:
            if not is_bad_title(w):
                title = clean_text(w)
                break

        if title and period != "정보 없음":
            items.append({
                "title": title,
                "host": host,
                "period": period,
                "dday": dday,
                "detail_url": ""
            })

    # 중복 제거
    unique_items = []
    seen = set()
    for item in items:
        key = (item["title"], item["host"], item["period"], item["dday"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items


def save_json(items: list[dict]) -> dict:
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "contestkorea",
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
            <h2>{item['title']}</h2>
            <p><strong>주최:</strong> {item['host']}</p>
            <p><strong>접수기간:</strong> {item['period']}</p>
            <p><strong>D-day:</strong> {item['dday']}</p>
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
    </style>
</head>
<body>
    <h1>공모전 Daily Update</h1>
    <div class="info">
        <p>마지막 업데이트: {data["updated_at"]}</p>
        <p>수집 건수: {data["count"]}</p>
        <p>출처: ContestKorea</p>
    </div>
    {''.join(rows)}
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    print("ContestKorea 목록 수집 중...")
    html = get_html(LIST_URL)

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]

    items = extract_items_from_lines(lines)

    # 너무 많으면 앞부분만 사용
    items = items[:20]

    data = save_json(items)
    save_html(data)

    print("완료")
    print(f"총 {len(items)}건 저장")


if __name__ == "__main__":
    main()
