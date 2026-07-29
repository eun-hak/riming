#!/usr/bin/env python3
"""지식iN 질문 수집기 (네이버 공식 검색 API 전용).

수집 데이터는 내부 분석 전용 — 사이트 게시·콘텐츠 생성 프롬프트 입력 금지 (PLAN.md 안전선).

사용법:
  python3 collect.py bulk [--seeds seeds.txt] [--sorts sim,point] [--pages 5]
  python3 collect.py daily [--seeds seeds.txt] [--pages 2]
  python3 collect.py stats
"""

import argparse
import html
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kin.db"
API_URL = "https://openapi.naver.com/v1/search/kin.json"
DISPLAY = 100          # 호출당 결과 수 (최대 100)
MAX_START = 1000       # API가 허용하는 start 상한
SLEEP_SEC = 0.15       # 초당 10회 제한 준수 여유


def load_env():
    env = {}
    for line in (BASE_DIR / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def clean(text):
    return html.unescape(re.sub(r"</?b>", "", text)).strip()


def doc_id_from_link(link):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return q.get("docId", [None])[0]


class Collector:
    def __init__(self):
        env = load_env()
        self.headers = {
            "X-Naver-Client-Id": env["NAVER_CLIENT_ID"],
            "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"],
        }
        DB_PATH.parent.mkdir(exist_ok=True)
        self.db = sqlite3.connect(DB_PATH)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS questions (
                doc_id     TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                description TEXT,
                link       TEXT NOT NULL,
                dir_id     TEXT,
                first_seen TEXT NOT NULL,
                last_seen  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hits (
                doc_id     TEXT NOT NULL,
                keyword    TEXT NOT NULL,
                sort       TEXT NOT NULL,
                rank       INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (doc_id, keyword, sort)
            );
            CREATE TABLE IF NOT EXISTS api_log (
                fetched_at TEXT NOT NULL,
                keyword    TEXT NOT NULL,
                sort       TEXT NOT NULL,
                start      INTEGER NOT NULL,
                returned   INTEGER NOT NULL,
                total      INTEGER NOT NULL
            );
            """
        )
        self.calls = 0

    def fetch_page(self, keyword, sort, start):
        params = urllib.parse.urlencode(
            {"query": keyword, "display": DISPLAY, "start": start, "sort": sort}
        )
        req = urllib.request.Request(f"{API_URL}?{params}", headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode())
        self.calls += 1
        time.sleep(SLEEP_SEC)
        return data

    def collect_keyword(self, keyword, sort, max_pages):
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        today = now[:10]
        new_docs = 0
        for page in range(max_pages):
            start = page * DISPLAY + 1
            if start > MAX_START:
                break
            try:
                data = self.fetch_page(keyword, sort, start)
            except Exception as e:
                print(f"  ! {keyword}/{sort} start={start}: {e}", file=sys.stderr)
                break
            items = data.get("items", [])
            self.db.execute(
                "INSERT INTO api_log VALUES (?,?,?,?,?,?)",
                (now, keyword, sort, start, len(items), data.get("total", 0)),
            )
            for i, item in enumerate(items):
                doc_id = doc_id_from_link(item["link"])
                if not doc_id:
                    continue
                dir_q = urllib.parse.parse_qs(
                    urllib.parse.urlparse(item["link"]).query
                )
                cur = self.db.execute(
                    """INSERT INTO questions VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(doc_id) DO UPDATE SET last_seen=excluded.last_seen""",
                    (
                        doc_id,
                        clean(item["title"]),
                        clean(item.get("description", "")),
                        item["link"],
                        dir_q.get("dirId", [None])[0],
                        today,
                        today,
                    ),
                )
                if cur.lastrowid:
                    new_docs += 1
                self.db.execute(
                    """INSERT INTO hits VALUES (?,?,?,?,?)
                       ON CONFLICT(doc_id, keyword, sort) DO UPDATE SET
                         rank=excluded.rank, fetched_at=excluded.fetched_at""",
                    (doc_id, keyword, sort, start + i, now),
                )
            self.db.commit()
            if len(items) < DISPLAY:
                break
        return new_docs

    def run(self, keywords, sorts, max_pages):
        for kw in keywords:
            for sort in sorts:
                n = self.collect_keyword(kw, sort, max_pages)
                total = self.db.execute(
                    "SELECT COUNT(*) FROM questions"
                ).fetchone()[0]
                print(f"  {kw} [{sort}]: +{n} new (DB total {total}, calls {self.calls})")

    def stats(self):
        q = self.db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        h = self.db.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        c = self.db.execute(
            "SELECT COUNT(*) FROM api_log WHERE fetched_at >= date('now')"
        ).fetchone()[0]
        print(f"questions: {q}\nhits: {h}\napi calls today: {c}")
        print("\ntop dirIds:")
        for dir_id, n in self.db.execute(
            """SELECT COALESCE(dir_id,'?'), COUNT(*) AS n FROM questions
               GROUP BY dir_id ORDER BY n DESC LIMIT 10"""
        ):
            print(f"  {dir_id}: {n}")


def read_seeds(path):
    seeds = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            seeds.append(line)
    return seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["bulk", "daily", "stats"])
    ap.add_argument("--seeds", default=str(BASE_DIR / "seeds.txt"))
    ap.add_argument("--sorts", default=None)
    ap.add_argument("--pages", type=int, default=None)
    args = ap.parse_args()

    col = Collector()
    if args.mode == "stats":
        col.stats()
        return

    keywords = read_seeds(args.seeds)
    if args.mode == "bulk":
        sorts = (args.sorts or "sim,point").split(",")
        pages = args.pages or 5
    else:  # daily: 신규 질문 증분
        sorts = (args.sorts or "date").split(",")
        pages = args.pages or 2

    est = len(keywords) * len(sorts) * pages
    print(f"{args.mode}: {len(keywords)} keywords x {sorts} x {pages}p ≈ {est} calls")
    col.run(keywords, sorts, pages)
    print(f"done. total API calls this run: {col.calls}")


if __name__ == "__main__":
    main()
