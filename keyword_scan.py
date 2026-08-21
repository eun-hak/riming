#!/usr/bin/env python3
"""키워드 전수 조사 — 질문에서 검색어를 뽑고 네이버 검색광고로 수요·경쟁도를 확인한다.

배경: 지식iN 질문의 44% 는 네이버에서 아무도 검색하지 않고, 수요가 있는 것은
대부분 경쟁이 극심하다(실측). 무작정 글을 쓰면 노출되지 않으므로, 미리 전수
조사해 "수요 있고 경쟁이 낮은 주제 사전"을 만들어 두고 거기서만 생성한다.

2단계로 나뉘며 각각 중단 후 재실행하면 남은 것부터 이어서 처리한다.
  1) 키워드 추출 — Gemini 배치 300건 (질문 1건 = 검색어 1개)
  2) 수요 조회   — 검색광고 keywordstool 배치 5건, 0.7초 간격
     조회하면 연관 키워드가 딸려오므로 그것도 함께 저장한다(무료 부산물).

사용법:
  python3 keyword_scan.py extract [--limit N]   # 1단계만
  python3 keyword_scan.py lookup  [--limit N]   # 2단계만
  python3 keyword_scan.py run     [--limit N]   # 1→2 연속
  python3 keyword_scan.py stats
  python3 keyword_scan.py picks   [--n 30]      # 통과 주제 미리보기
"""

import argparse
import base64
import hashlib
import hmac
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
GEMINI_EP = ("https://generativelanguage.googleapis.com/v1beta/models/"
             "{m}:generateContent?key={k}")
AD_BASE = "https://api.searchad.naver.com"

EXTRACT_BATCH = 300     # 무손실 확인된 크기
EXTRACT_MODEL = "gemini-3.1-flash-lite"   # 여유 있는 쪽 사용
LOOKUP_BATCH = 5        # keywordstool 이 한 번에 받는 힌트 수
LOOKUP_SLEEP = 0.7      # 초당 5회 넘기면 429

# 게이트 기준 — 너무 크면 못 이기고 너무 작으면 써도 트래픽이 없다
MIN_VOL, MAX_VOL = 100, 30_000
OK_COMP = ("낮음", "중간")

PROMPT = """다음 질문 각각에 대해, 그 질문을 검색하는 사람이 네이버 검색창에
실제로 입력할 키워드를 1개씩 만들어라.
- 2~3어절, 조사 없이. 실제 검색되는 형태로.
- 개인 사정(지역·나이·상황 설명)은 빼고 일반화한다.
- 실제로 검색되지 않을 조합어를 지어내지 말 것.
- 입력 질문 수와 출력 항목 수가 반드시 같고, i 는 입력 번호를 그대로 쓴다.

질문:
"""
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object",
    "properties": {"i": {"type": "integer"}, "kw": {"type": "string"}},
    "required": ["i", "kw"]}}}, "required": ["items"]}


def env():
    e = {}
    for line in (BASE / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            e[k.strip()] = v.strip()
    return e


def ensure(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS question_keyword (
            doc_id TEXT PRIMARY KEY,
            keyword TEXT NOT NULL,
            extracted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_qk_kw ON question_keyword(keyword);
        CREATE TABLE IF NOT EXISTS keyword_stats (
            keyword TEXT PRIMARY KEY,
            vol INTEGER,
            comp TEXT,
            source TEXT,
            checked_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ks_vol ON keyword_stats(vol);
    """)
    db.commit()


def norm(kw):
    return str(kw or "").replace(" ", "").strip()


def num(v):
    try:
        return int(str(v).replace("<", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


# ── 1단계: 키워드 추출 ────────────────────────────────────────────────
def extract(db, e, limit):
    import longtail as L
    rows = db.execute(
        """SELECT q.doc_id, q.title FROM questions q
           WHERE q.doc_id NOT IN (SELECT doc_id FROM question_keyword)
             AND CAST(q.doc_id AS INTEGER) >= ?
           ORDER BY (SELECT MIN(rank) FROM hits h WHERE h.doc_id = q.doc_id)""",
        (L.MIN_DOC_ID,)).fetchall()
    # 생성 단계와 같은 품질 필터를 적용해 조사 대상 자체를 줄인다
    pool = []
    for doc_id, title in rows:
        t = (title or "").strip()
        if not (10 <= len(t) <= 60) or L.BAD.search(t):
            continue
        if L.AD.search(t) or L.EXPIRED.search(t):
            continue
        pool.append((doc_id, L.STOP.sub("", t).strip()))
        if limit and len(pool) >= limit:
            break

    print(f"[추출] 대상 {len(pool):,}건 → 배치 {EXTRACT_BATCH}건")
    key = e["GEMINI_API_KEY"]
    done = 0
    for i in range(0, len(pool), EXTRACT_BATCH):
        chunk = pool[i:i + EXTRACT_BATCH]
        items = "\n".join(f"{j}. {q}" for j, (_, q) in enumerate(chunk))
        body = json.dumps({
            "contents": [{"parts": [{"text": PROMPT + items}]}],
            "generationConfig": {"response_mime_type": "application/json",
                                 "response_schema": SCHEMA,
                                 "maxOutputTokens": 30000, "temperature": 0.2},
        }).encode()
        try:
            req = urllib.request.Request(
                GEMINI_EP.format(m=EXTRACT_MODEL, k=key), data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read())
            out = json.loads(
                d["candidates"][0]["content"]["parts"][0]["text"])["items"]
        except urllib.error.HTTPError as ex:
            if ex.code == 429:
                print("  쿼터 소진 — 중단 (재실행하면 이어서 진행)", file=sys.stderr)
                break
            print(f"  HTTP {ex.code} — 이 배치 건너뜀", file=sys.stderr)
            continue
        except Exception as ex:
            print(f"  실패({type(ex).__name__}) — 이 배치 건너뜀", file=sys.stderr)
            continue

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        recs = []
        for x in out:
            j = x.get("i")
            if isinstance(j, int) and 0 <= j < len(chunk) and x.get("kw"):
                recs.append((chunk[j][0], str(x["kw"]).strip(), now))
        db.executemany(
            "INSERT OR REPLACE INTO question_keyword VALUES (?,?,?)", recs)
        db.commit()
        done += len(recs)
        print(f"  {done:,}/{len(pool):,}")
    print(f"[추출] 완료 {done:,}건")


# ── 2단계: 검색광고 조회 ──────────────────────────────────────────────
def ad_call(e, hint):
    path, ts = "/keywordstool", str(int(time.time() * 1000))
    sig = base64.b64encode(hmac.new(
        e["NAVER_AD_SECRET_KEY"].encode(),
        f"{ts}.GET.{path}".encode(), hashlib.sha256).digest()).decode()
    url = (f"{AD_BASE}{path}?hintKeywords={urllib.parse.quote(hint)}"
           "&showDetail=1")
    req = urllib.request.Request(url, headers={
        "X-Timestamp": ts, "X-API-KEY": e["NAVER_AD_ACCESS_LICENSE"],
        "X-Customer": e["NAVER_AD_CUSTOMER_ID"], "X-Signature": sig})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("keywordList", [])


def lookup(db, e, limit):
    todo = [r[0] for r in db.execute(
        """SELECT DISTINCT keyword FROM question_keyword
           WHERE keyword NOT IN (SELECT keyword FROM keyword_stats)""")]
    if limit:
        todo = todo[:limit]
    print(f"[조회] 미조사 키워드 {len(todo):,}개 → 배치 {LOOKUP_BATCH}개, "
          f"예상 {len(todo)//LOOKUP_BATCH*LOOKUP_SLEEP/60:.0f}분")

    done = rel_saved = 0
    for i in range(0, len(todo), LOOKUP_BATCH):
        chunk = todo[i:i + LOOKUP_BATCH]
        hint = ",".join(norm(k) for k in chunk)
        for attempt in range(4):
            try:
                lst = ad_call(e, hint)
                break
            except urllib.error.HTTPError as ex:
                if ex.code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                lst = []
                break
            except Exception:
                time.sleep(2)
                lst = []
        else:
            lst = []

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        by_norm = {norm(k.get("relKeyword")): k for k in lst}
        recs = []
        for kw in chunk:      # 요청한 키워드 — 없으면 수요 없음으로 기록
            m = by_norm.get(norm(kw))
            recs.append((kw,
                         num(m.get("monthlyPcQcCnt")) + num(m.get("monthlyMobileQcCnt")) if m else 0,
                         (m or {}).get("compIdx", "없음"), "question", now))
        # 연관 키워드는 네이버가 실제 검색어로 인정한 것들 — 부산물로 축적
        rel = [(k.get("relKeyword"),
                num(k.get("monthlyPcQcCnt")) + num(k.get("monthlyMobileQcCnt")),
                k.get("compIdx", "없음"), "related", now)
               for kn, k in by_norm.items() if kn not in {norm(c) for c in chunk}]
        db.executemany("INSERT OR REPLACE INTO keyword_stats VALUES (?,?,?,?,?)", recs)
        db.executemany(
            "INSERT OR IGNORE INTO keyword_stats VALUES (?,?,?,?,?)", rel)
        db.commit()
        done += len(chunk)
        rel_saved += len(rel)
        if done % 250 < LOOKUP_BATCH:
            print(f"  {done:,}/{len(todo):,} (연관어 누적 {rel_saved:,})")
        time.sleep(LOOKUP_SLEEP)
    print(f"[조회] 완료 {done:,}건 / 연관어 {rel_saved:,}건 확보")


def stats(db):
    q = db.execute("SELECT COUNT(*) FROM question_keyword").fetchone()[0]
    ks = db.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0]
    src = dict(db.execute(
        "SELECT source, COUNT(*) FROM keyword_stats GROUP BY source"))
    good = db.execute(
        "SELECT COUNT(*) FROM keyword_stats WHERE vol BETWEEN ? AND ? AND comp IN (?,?)",
        (MIN_VOL, MAX_VOL, *OK_COMP)).fetchone()[0]
    print(f"질문 키워드 추출: {q:,}건")
    print(f"키워드 조사:     {ks:,}개 (질문발 {src.get('question',0):,} / 연관어 {src.get('related',0):,})")
    print(f"게이트 통과:     {good:,}개  (월 {MIN_VOL}~{MAX_VOL:,} + 경쟁 {'/'.join(OK_COMP)})")


def picks(db, n):
    rows = db.execute(
        """SELECT k.keyword, k.vol, k.comp, q.title
           FROM keyword_stats k
           LEFT JOIN question_keyword qk ON qk.keyword = k.keyword
           LEFT JOIN questions q ON q.doc_id = qk.doc_id
           WHERE k.vol BETWEEN ? AND ? AND k.comp IN (?,?)
           GROUP BY k.keyword ORDER BY k.vol DESC LIMIT ?""",
        (MIN_VOL, MAX_VOL, *OK_COMP, n)).fetchall()
    print(f"{'키워드':24} {'월검색':>8} 경쟁   원본질문")
    for kw, vol, comp, title in rows:
        print(f"  {kw[:22]:24} {vol:>8,} {comp:4}  {(title or '(연관어)')[:30]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["extract", "lookup", "run", "stats", "picks"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--n", type=int, default=30)
    args = ap.parse_args()

    sys.path.insert(0, str(BASE))
    db = sqlite3.connect(DB)
    ensure(db)
    e = env()

    if args.mode == "stats":
        stats(db)
    elif args.mode == "picks":
        picks(db, args.n)
    elif args.mode == "extract":
        extract(db, e, args.limit)
    elif args.mode == "lookup":
        lookup(db, e, args.limit)
    else:
        extract(db, e, args.limit)
        lookup(db, e, 0)
        stats(db)


if __name__ == "__main__":
    main()
