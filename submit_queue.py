#!/usr/bin/env python3
"""네이버 웹페이지 수집 요청용 URL 큐 — 하루 N개씩 뽑아 외부 제출 시스템에 넘긴다.

사이트가 1,000편을 넘겨도 네이버 크롤은 하루 수 건 수준이라, 수집 요청으로
발견을 앞당긴다. 이미 넘긴 URL 은 기록해 다음 날 중복으로 나가지 않게 한다.

사용법:
  python3 submit_queue.py next --n 50                  # 미리보기(기록 안 함)
  python3 submit_queue.py next --n 50 --mark           # 뽑고 제출 기록
  python3 submit_queue.py next --n 50 --format json --mark
  python3 submit_queue.py stats
  python3 submit_queue.py reset --days 30              # 30일 지난 기록 해제(재제출용)
"""

import argparse
import csv
import io
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
POSTS = BASE / "web" / "content" / "posts"
SITE = "https://riming.plentyer.com"


def ensure(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS submitted_urls (
            url TEXT PRIMARY KEY,
            submitted_at TEXT NOT NULL,
            channel TEXT
        );
    """)
    db.commit()


def all_urls():
    """사이트의 제출 대상 URL — 홈·카테고리를 먼저, 그다음 글(오래된 순)."""
    urls = [f"{SITE}/"]
    cats, posts = set(), []
    for p in sorted(POSTS.glob("*.md")):
        txt = p.read_text(errors="ignore")
        head = txt[4:].partition("\n---\n")[0]
        cat = re.search(r'^category:\s*"?([^"\n]+)"?', head, re.M)
        date = re.search(r"^pubDate:\s*(\S+)", head, re.M)
        if cat:
            cats.add(cat.group(1).strip())
        posts.append((date.group(1) if date else "9999-99-99", p.stem))
    for c in sorted(cats):
        urls.append(f"{SITE}/category/{urllib.parse.quote(c)}/")
    # 발행이 오래된 글부터 — 가장 오래 기다린 페이지에 우선순위
    for _, slug in sorted(posts):
        urls.append(f"{SITE}/posts/{urllib.parse.quote(slug)}/")
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["next", "all", "stats", "reset"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--format", choices=["txt", "json", "csv"], default="txt")
    ap.add_argument("--mark", action="store_true", help="뽑은 URL 을 제출 기록에 남긴다")
    ap.add_argument("--channel", default="naver")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", help="파일로 저장 (미지정 시 표준출력)")
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    ensure(db)

    if args.mode == "stats":
        done = db.execute("SELECT COUNT(*) FROM submitted_urls").fetchone()[0]
        total = len(all_urls())
        today = db.execute(
            "SELECT COUNT(*) FROM submitted_urls WHERE submitted_at >= date('now')"
        ).fetchone()[0]
        print(f"전체 URL {total:,} / 제출 완료 {done:,} / 남은 {total - done:,}")
        print(f"오늘 제출 {today}")
        return

    if args.mode == "reset":
        cur = db.execute(
            "DELETE FROM submitted_urls WHERE submitted_at < date('now', ?)",
            (f"-{args.days} days",))
        db.commit()
        print(f"{cur.rowcount}건 제출 기록 해제 (재제출 대상)")
        return

    if args.mode == "all":
        picked = all_urls()
        args.mark = False   # 전체 목록 출력은 제출 기록에 영향 주지 않는다
    else:
        done = {r[0] for r in db.execute("SELECT url FROM submitted_urls")}
        picked = [u for u in all_urls() if u not in done]
        # 미제출분이 바닥나면 처음부터 재순회 (오래된 제출부터 다시)
        if not picked:
            old = [r[0] for r in db.execute(
                "SELECT url FROM submitted_urls ORDER BY submitted_at LIMIT ?",
                (args.n,))]
            db.executemany("DELETE FROM submitted_urls WHERE url=?",
                           [(u,) for u in old])
            db.commit()
            picked = old
        picked = picked[:args.n]

    if args.format == "json":
        payload = json.dumps({"site": SITE, "urls": picked},
                             ensure_ascii=False, indent=2)
    elif args.format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["url"])
        w.writerows([[u] for u in picked])
        payload = buf.getvalue().rstrip()
    else:
        payload = "\n".join(picked)

    if args.out:
        Path(args.out).write_text(payload + "\n")
        print(f"{len(picked)}건 → {args.out}", file=sys.stderr)
    else:
        print(payload)

    if args.mark and picked:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        db.executemany(
            "INSERT OR REPLACE INTO submitted_urls VALUES (?,?,?)",
            [(u, now, args.channel) for u in picked])
        db.commit()
        print(f"제출 기록 {len(picked)}건 저장", file=sys.stderr)


if __name__ == "__main__":
    main()
