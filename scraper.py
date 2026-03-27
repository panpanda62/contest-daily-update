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


def extract_items_from_text(text: str) -> list[dict]:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]

    items = []
    i = 0

    while i < len(lines):
        line = lines[i]

        dday_match = re.match(r"^(D-\d+|D-Day|D-\d+\s+접수중|D-\d+\s+접수예정|D-\d+\s+마감임박|D-\d+\s+접수마감|D-\d+\s+접수중)$", line)
        if line.startswith("D-") or line == "D-Day":
            dday = line.split()[0]

            title = ""
            host = ""
            period = ""
            detail_url = ""

            # 다음 몇 줄 안에서 제목/주최/접수기간 찾기
            for j in range(i + 1, min(i + 8, len(lines))):
                cur = lines[j]

                # 주최
                if cur.startswith("주최 ."):
                    host = cur.replace("주최 .", "").strip()

                # 접수기간
                period_match = re.search(r"접수\s+(\d{2}\.\d{2}~\d{2}\.\d{2})", cur)
                if period_match:
                    period = period_match.group(1)

                # 제목 후보: 주최/대상/접수 줄이 아니고 어느 정도 길이가 있는 줄
                if (
                    not cur.startswith("주최 .")
                    and not cur.startswith("대상 .")
                    and "접수 " not in cur
                    and not cur.startswith("심사 ")
                    and not cur.startswith("발표 ")
                    and len(cur) >= 4
                    and not cur.startswith("￦")
                ):
                    if not title:
                        title = cur

            if title and period:
                items.append({
                    "title": title,
                    "host": host if host else "정보 없음",
                    "period": period,
                    "dday": dday,
                    "detail_url": detail_url
                })

        i += 1

    # 중복 제거
    unique = []
    seen = set()
    for item in items:
        key = (item["title"], item["period"], item["dday"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


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
        title_html = item["title"]
        if item["detail_url"]:
            title_html = f'<a href="{item["detail_url"]}" target="_blank">{item["title"]}</a>'

        row = f"""
        <div class="card">
            <h2>{title_html}</h2>
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

    # HTML 전체 텍스트 기반 파싱
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    items = extract_items_from_text(text)

    # 너무 많으면 앞쪽 일부만
    items = items[:20]

    data = save_json(items)
    save_html(data)

    print("완료")
    print(f"총 {len(items)}건 저장")


if __name__ == "__main__":
    main()
