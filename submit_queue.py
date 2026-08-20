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
    # 새로 발행한 글부터 — 신선한 콘텐츠를 먼저 수집 요청해야 색인 가치가 크다.
    # (오래된 글은 큐 뒤로 밀리는데, 필터 이전 저품질 분량이라 의도된 결과다)
    for _, slug in sorted(posts, reverse=True):
        urls.append(f"{SITE}/posts/{urllib.parse.quote(slug)}/")
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["next", "all", "prepare", "stats", "reset"])
    ap.add_argument("--days", type=int, default=14,
                    help="prepare: 며칠치를 미리 만들어 둘지")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--format", choices=["txt", "json", "csv"], default="txt")
    ap.add_argument("--mark", action="store_true", help="뽑은 URL 을 제출 기록에 남긴다")
    ap.add_argument("--channel", default="naver")
    ap.add_argument("--out", help="파일로 저장 (미지정 시 표준출력)")
    ap.add_argument("--dir", default="web/public/naver",
                    help="prepare: 날짜별 파일을 둘 디렉터리")
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

    if args.mode == "prepare":
        # 맥이 꺼져 배치가 걸러도 서버가 그날 파일을 받을 수 있게 미리 채워둔다.
        # 이미 만들어 둔 날짜는 건드리지 않고 부족한 날짜만 새로 만든다.
        import datetime
        outdir = BASE / args.dir
        outdir.mkdir(parents=True, exist_ok=True)
        done = {r[0] for r in db.execute("SELECT url FROM submitted_urls")}
        pool = [u for u in all_urls() if u not in done]
        today = datetime.date.today()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        made, cur = [], 0
        for d in range(args.days):
            day = today + datetime.timedelta(days=d)
            f = outdir / f"{day:%Y-%m-%d}.txt"
            if f.exists():
                continue
            chunk = pool[cur:cur + args.n]
            if not chunk:      # 재고 소진 — 오래된 제출부터 재순회
                old = [r[0] for r in db.execute(
                    "SELECT url FROM submitted_urls ORDER BY submitted_at LIMIT ?",
                    (args.n,))]
                db.executemany("DELETE FROM submitted_urls WHERE url=?",
                               [(u,) for u in old])
                chunk = old
            cur += args.n
            f.write_text("\n".join(chunk) + "\n")
            db.executemany("INSERT OR REPLACE INTO submitted_urls VALUES (?,?,?)",
                           [(u, now, args.channel) for u in chunk])
            made.append(f.name)
        # 최신 파일을 today.txt 로도 복사 (날짜 모를 때의 기본 경로)
        latest = outdir / f"{today:%Y-%m-%d}.txt"
        if latest.exists():
            (outdir / "today.txt").write_text(latest.read_text())
        # 오래된 날짜 파일 정리
        for f in outdir.glob("20*.txt"):
            if f.stem < f"{today - datetime.timedelta(days=7)}":
                f.unlink()
        db.commit()
        print(f"미리 생성 {len(made)}일치 (총 {args.days}일 버퍼 유지)")
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
