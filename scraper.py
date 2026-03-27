import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://www.thinkcontest.com/thinkgood/index.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.thinkcontest.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def extract_best_titles(lines: list[str]) -> list[dict]:
    items = []
    in_best_section = False

    for line in lines:
        line = clean_text(line)

        # "주간 조회수 베스트" 구간 진입
        if "주간 조회수 베스트" in line:
            in_best_section = True
            continue

        if not in_best_section:
            continue

        # 패턴: * 1. 2026 대한민국 헌혈 공모전
        match = re.match(r"^\*\s*(\d+)\.\s*(.+)$", line)
        if match:
            rank = int(match.group(1))
            title = clean_text(match.group(2))

            if 1 <= rank <= 10:
                items.append({
                    "rank": rank,
                    "title": title,
                    "source_url": URL
                })

            # 10개까지만 수집
            if len(items) >= 10:
                break

    return items


def save_json(items: list[dict]) -> dict:
    kst_now = datetime.now(ZoneInfo("Asia/Seoul"))

    data = {
        "updated_at": kst_now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Seoul",
        "source": "thinkcontest",
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
            <h2>{item['rank']}. {item['title']}</h2>
            <p><a href="{item['source_url']}" target="_blank">씽굿 바로가기</a></p>
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
        <p>마지막 업데이트: {data["updated_at"]} ({data["timezone"]})</p>
        <p>수집 건수: {data["count"]}</p>
        <p>출처: ThinkContest(씽굿)</p>
    </div>
    {''.join(rows)}
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    print("씽굿 홈페이지 수집 중...")
    html = get_html(URL)

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]

    items = extract_best_titles(lines)

    print("추출 건수:", len(items))
    for item in items:
        print(item)

    data = save_json(items)
    save_html(data)

    print("완료")
    print(f"총 {len(items)}건 저장")


if __name__ == "__main__":
    main()
