#!/usr/bin/env python3
"""M3 검증기 — 주제 후보를 데이터랩 검색 추세로 검증해 발행 큐 스코어 산출.

데이터랩 ratio는 요청 그룹 내 상대값이므로, 모든 호출에 앵커 키워드를 포함해
앵커 대비 배율(demand)로 정규화해 호출 간 비교를 가능하게 한다.

사용법:
  python3 validate.py run [--top 50]
  python3 validate.py report
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kin.db"
REPORT_PATH = BASE_DIR / "data" / "validated.md"
DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-3.5-flash-lite:generateContent")
ANCHOR = "여권 발급"   # 중간 볼륨의 안정적 기준 키워드
GROUP_SIZE = 4         # 호출당 후보 4개 + 앵커 1개

KEYWORD_PROMPT = """다음 주제 목록 각각에 대해, 사람들이 네이버에 실제로 입력할 법한
대표 검색 키워드 1개를 만들어라 (2~4어절, 조사 없이).
JSON 배열 [{{"topic":"...","keyword":"..."}}] 만 출력.

주제 목록:
{topics}"""


def load_env():
    env = {}
    for line in (BASE_DIR / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def post_json(url, headers, body, timeout=60):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode())


def derive_keywords(env, topics):
    body = {
        "contents": [{"parts": [{"text": KEYWORD_PROMPT.format(
            topics="\n".join(f"- {t}" for t in topics))}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    data = post_json(GEMINI_URL, {"x-goog-api-key": env["GEMINI_API_KEY"]}, body,
                     timeout=120)
    items = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    return {i["topic"]: i["keyword"] for i in items
            if isinstance(i, dict) and i.get("topic") and i.get("keyword")}


def datalab_group(env, keywords):
    end = time.strftime("%Y-%m-%d")
    start = f"{int(end[:4]) - 1}{end[4:]}"
    body = {
        "startDate": start, "endDate": end, "timeUnit": "month",
        "keywordGroups": [{"groupName": k, "keywords": [k]}
                          for k in keywords + [ANCHOR]],
    }
    headers = {"X-Naver-Client-Id": env["NAVER_CLIENT_ID"],
               "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"]}
    data = post_json(DATALAB_URL, headers, body)
    time.sleep(0.3)
    out = {}
    for res in data.get("results", []):
        points = [d["ratio"] for d in res["data"]]
        if not points:
            continue
        # 마지막 데이터포인트는 진행 중인 달이라 제외
        points = points[:-1] if len(points) > 1 else points
        avg = sum(points) / len(points)
        recent = sum(points[-3:]) / min(3, len(points))
        base = sum(points[:-3]) / max(1, len(points) - 3) if len(points) > 3 else avg
        out[res["title"]] = {"avg": avg, "trend": recent / base if base else 1.0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "report"])
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS topic_scores (
             topic TEXT PRIMARY KEY,
             keyword TEXT,
             freq INTEGER,
             demand REAL,   -- 앵커 대비 검색량 배율
             trend REAL,    -- 최근3개월/이전 평균 배율
             score REAL,
             created_at TEXT
           )"""
    )

    if args.mode == "report":
        report(db)
        return

    env = load_env()
    rows = db.execute(
        """SELECT topic, MAX(count) AS c FROM topics
           GROUP BY topic ORDER BY c DESC LIMIT ?""",
        (args.top,),
    ).fetchall()
    topics = [r[0] for r in rows]
    freqs = dict(rows)

    print(f"1) 대표 키워드 생성 ({len(topics)}개 주제)")
    kw_map = {}
    for i in range(0, len(topics), 50):
        kw_map.update(derive_keywords(env, topics[i:i + 50]))

    print(f"2) 데이터랩 조회 (앵커: {ANCHOR})")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    items = [(t, k) for t, k in kw_map.items() if t in freqs]
    for i in range(0, len(items), GROUP_SIZE):
        group = items[i:i + GROUP_SIZE]
        try:
            stats = datalab_group(env, [k for _, k in group])
        except Exception as e:
            print(f"  ! 그룹 {i // GROUP_SIZE}: {e}", file=sys.stderr)
            continue
        anchor_avg = stats.get(ANCHOR, {}).get("avg") or 1.0
        for topic, kw in group:
            s = stats.get(kw)
            if not s:
                continue
            demand = s["avg"] / anchor_avg
            trend = s["trend"]
            score = freqs[topic] * demand * min(trend, 2.0)
            db.execute(
                """INSERT INTO topic_scores VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(topic) DO UPDATE SET
                     keyword=excluded.keyword, freq=excluded.freq,
                     demand=excluded.demand, trend=excluded.trend,
                     score=excluded.score, created_at=excluded.created_at""",
                (topic, kw, freqs[topic], round(demand, 3),
                 round(trend, 3), round(score, 1), now),
            )
        db.commit()
        print(f"  {min(i + GROUP_SIZE, len(items))}/{len(items)}")
    report(db)


def report(db):
    rows = db.execute(
        """SELECT topic, keyword, freq, demand, trend, score
           FROM topic_scores ORDER BY score DESC"""
    ).fetchall()
    lines = [
        "# 검증된 주제 랭킹 (M3 출력)",
        "",
        f"생성: {time.strftime('%Y-%m-%d %H:%M')} · demand는 앵커(여권 발급) 대비 검색량 배율, trend는 최근 3개월/이전 배율",
        "",
        "| 순위 | 주제 | 검색 키워드 | 빈도 | 수요 | 추세 | 점수 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(i, *r))
    REPORT_PATH.write_text("\n".join(lines))
    print(f"{REPORT_PATH} 저장 ({len(rows)}개)")


if __name__ == "__main__":
    main()
