#!/usr/bin/env python3
"""M2 주제 발굴 — 수집된 지식iN 질문을 Gemini로 클러스터링해 주제 후보 랭킹 생성.

사용법:
  python3 cluster.py run [--keywords "전세 계약,강아지 사료"] [--titles 300]
  python3 cluster.py report
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kin.db"
REPORT_PATH = BASE_DIR / "data" / "topics.md"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
EXTRACT_MODEL = "gemini-3.1-flash-lite"   # 대량 1차 분류
MERGE_MODEL = "gemini-3.5-flash-lite"     # 통합·정제
BATCH_SIZE = 100
SLEEP_SEC = 4  # 무료 쿼터 RPM 여유

EXTRACT_PROMPT = """다음은 네이버 지식iN 질문 제목 목록이다.
같은 것을 궁금해하는 질문끼리 묶어서 반복되는 주제를 추출하라.

규칙:
- topic: 주제를 나타내는 간결한 명사구 (예: "전세 보증금 반환 절차")
- count: 이 주제에 속하는 질문 수
- intent: 질문자들이 알고 싶어하는 핵심을 한 문장으로
- 1건짜리 산발 주제는 "기타"로 합치지 말고 제외
- JSON 배열만 출력

질문 목록:
{titles}"""

MERGE_PROMPT = """다음은 같은 검색 키워드에서 배치별로 추출한 주제 목록이다.
중복·유사 주제를 통합하고 count를 합산해서 상위 15개 주제만 남겨라.
형식은 동일하게 JSON 배열 [{{"topic","count","intent"}}] 만 출력.

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


class Gemini:
    def __init__(self, api_key):
        self.api_key = api_key
        self.calls = {}

    def generate(self, model, prompt, retries=3):
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }).encode()
        req = urllib.request.Request(
            f"{API_BASE}/{model}:generateContent",
            data=body,
            headers={"x-goog-api-key": self.api_key,
                     "Content-Type": "application/json"},
        )
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as res:
                    data = json.loads(res.read().decode())
                self.calls[model] = self.calls.get(model, 0) + 1
                time.sleep(SLEEP_SEC)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait = 30 * (attempt + 1)
                    print(f"    429, {wait}s 대기 후 재시도", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
            except (KeyError, json.JSONDecodeError) as e:
                if attempt < retries - 1:
                    continue
                raise RuntimeError(f"응답 파싱 실패: {e}")


def get_keywords(db):
    return [r[0] for r in db.execute(
        "SELECT DISTINCT keyword FROM hits ORDER BY keyword")]


def get_titles(db, keyword, limit):
    rows = db.execute(
        """SELECT DISTINCT q.title FROM questions q
           JOIN hits h ON h.doc_id = q.doc_id
           WHERE h.keyword = ? AND h.sort IN ('sim','point')
           ORDER BY h.rank LIMIT ?""",
        (keyword, limit),
    ).fetchall()
    return [r[0] for r in rows]


def cluster_keyword(gem, db, keyword, title_limit):
    titles = get_titles(db, keyword, title_limit)
    if len(titles) < 20:
        print(f"  {keyword}: 질문 {len(titles)}건 — 건너뜀")
        return
    batch_results = []
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i + BATCH_SIZE]
        topics = gem.generate(
            EXTRACT_MODEL,
            EXTRACT_PROMPT.format(titles="\n".join(f"- {t}" for t in batch)),
        )
        batch_results.extend(topics)
    merged = gem.generate(
        MERGE_MODEL,
        MERGE_PROMPT.format(topics=json.dumps(batch_results, ensure_ascii=False)),
    )
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    db.execute("DELETE FROM topics WHERE keyword = ?", (keyword,))
    for t in merged:
        try:
            db.execute(
                "INSERT INTO topics VALUES (?,?,?,?,?)",
                (keyword, str(t["topic"]), int(t["count"]),
                 str(t.get("intent", "")), now),
            )
        except (KeyError, TypeError, ValueError):
            continue
    db.commit()
    print(f"  {keyword}: {len(titles)}건 → 주제 {len(merged)}개")


def report(db):
    rows = db.execute(
        """SELECT keyword, topic, count, intent FROM topics
           ORDER BY count DESC"""
    ).fetchall()
    lines = [
        "# 주제 후보 랭킹 (M2 출력)",
        "",
        f"생성: {time.strftime('%Y-%m-%d %H:%M')} · 총 {len(rows)}개 주제",
        "",
        "| 순위 | 주제 | 빈도 | 키워드 | 질문 의도 |",
        "|---|---|---|---|---|",
    ]
    for i, (kw, topic, count, intent) in enumerate(rows, 1):
        lines.append(f"| {i} | {topic} | {count} | {kw} | {intent} |")
    REPORT_PATH.write_text("\n".join(lines))
    print(f"{REPORT_PATH} 저장 ({len(rows)}개 주제)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "report"])
    ap.add_argument("--keywords", default=None, help="쉼표 구분, 미지정 시 전체")
    ap.add_argument("--titles", type=int, default=300)
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS topics (
             keyword TEXT NOT NULL,
             topic   TEXT NOT NULL,
             count   INTEGER NOT NULL,
             intent  TEXT,
             created_at TEXT NOT NULL
           )"""
    )

    if args.mode == "report":
        report(db)
        return

    gem = Gemini(load_env()["GEMINI_API_KEY"])
    keywords = (args.keywords.split(",") if args.keywords
                else get_keywords(db))
    print(f"{len(keywords)}개 키워드 클러스터링 시작")
    for kw in keywords:
        try:
            cluster_keyword(gem, db, kw.strip(), args.titles)
        except Exception as e:
            print(f"  ! {kw}: {e}", file=sys.stderr)
    print(f"완료. Gemini 호출: {gem.calls}")
    report(db)


if __name__ == "__main__":
    main()
