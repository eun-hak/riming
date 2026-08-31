#!/usr/bin/env python3
"""주제 유형 분류 — 검색결과에서 이길 수 있는 영역으로 발행을 옮긴다.

실측(상위 10개 중 기관·대형사 점유):
  사실·제도형 8.8/10  → 공공기관이 정답을 갖고 있어 신생 도메인이 못 이김
  생활노하우형 3.8/10  → 권위 있는 출처가 없어 틈이 있음
  해석형      2.2/10  → 몽글이 성공한 영역

리밍 정체성(생활 궁금증)에 맞는 것은 노하우형이므로 그쪽을 우선 소비한다.

사용법:
  python3 classify_type.py run [--limit N]
  python3 classify_type.py stats
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
MODEL = "gemini-3.1-flash-lite"
BATCH = 300

PROMPT = """다음 검색 키워드를 유형으로 분류하라.

A = 생활 노하우형: 방법·요령·손질·보관·청소·수리·관리·사용법·비교처럼
    경험으로 답하는 주제. 공공기관이 정답을 제시하지 않는다.
    예) 삼겹살 냉동보관, 세탁조 곰팡이 제거, 청바지 늘리는법, 화분 물주기

B = 사실·제도형: 법령·행정·세금·보험·자격·급여·신고처럼 공공기관이
    공식 답을 제공하는 주제. 검색하면 정부·공단 사이트가 1위다.
    예) 실업급여 신청방법, 증여세 세율, 전입신고, 기초연금 수급자격

C = 해석·의견형: 꿈해몽·사주·심리·이름풀이처럼 정해진 정답이 없는 주제.

D = 그 외: 위 어디에도 맞지 않거나 상품·브랜드·고유명사.

JSON 배열만 출력. 입력 수와 출력 수를 맞추고 i 는 입력 번호를 그대로 쓴다.

키워드:
"""
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object",
    "properties": {"i": {"type": "integer"},
                   "t": {"type": "string", "description": "A, B, C, D 중 하나"}},
    "required": ["i", "t"]}}}, "required": ["items"]}


def key():
    for line in (BASE / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY 없음")


def ensure(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(keyword_stats)")}
    if "topic_type" not in cols:
        db.execute("ALTER TABLE keyword_stats ADD COLUMN topic_type TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS question_type (
        doc_id TEXT PRIMARY KEY, topic_type TEXT, at TEXT)""")
    db.commit()


def classify_questions(db, limit):
    """생성 후보 질문에 같은 유형 분류를 붙인다 (사전보다 노하우형 비중이 높다)."""
    import longtail as L
    rows = db.execute(
        """SELECT q.doc_id, q.title FROM questions q
           WHERE q.doc_id NOT IN (SELECT doc_id FROM used_questions)
             AND q.doc_id NOT IN (SELECT doc_id FROM question_type)
             AND CAST(q.doc_id AS INTEGER) >= ?
           ORDER BY (SELECT MIN(rank) FROM hits h WHERE h.doc_id = q.doc_id)""",
        (L.MIN_DOC_ID,)).fetchall()
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
    print(f"[질문 분류] 대상 {len(pool):,}건")
    k = key()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    done = 0
    for i in range(0, len(pool), BATCH):
        chunk = pool[i:i + BATCH]
        try:
            out = call(k, [q for _, q in chunk])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  쿼터 소진 — 중단", file=sys.stderr)
                break
            continue
        except Exception:
            continue
        recs = []
        for x in out:
            j = x.get("i")
            t = str(x.get("t", "")).strip().upper()[:1]
            if isinstance(j, int) and 0 <= j < len(chunk) and t in "ABCD":
                recs.append((chunk[j][0], t, now))
        db.executemany("INSERT OR REPLACE INTO question_type VALUES (?,?,?)", recs)
        db.commit()
        done += len(recs)
        if done % 3000 < BATCH:
            print(f"  {done:,}/{len(pool):,}")
        time.sleep(2)
    print(f"[질문 분류] 완료 {done:,}건")


def call(k, kws):
    items = "\n".join(f"{i}. {w}" for i, w in enumerate(kws))
    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT + items}]}],
        "generationConfig": {"response_mime_type": "application/json",
                             "response_schema": SCHEMA,
                             "maxOutputTokens": 20000, "temperature": 0.0},
    }).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={k}",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])["items"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "questions", "stats"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    ensure(db)

    if args.mode == "questions":
        classify_questions(db, args.limit)
        return

    if args.mode == "stats":
        qt = dict(db.execute(
            "SELECT COALESCE(topic_type,'?'), COUNT(*) FROM question_type GROUP BY 1"))
        if qt:
            print("  [질문]  " + "  ".join(f"{k}:{v:,}" for k, v in sorted(qt.items())))
        rows = db.execute(
            """SELECT COALESCE(topic_type,'미분류'), COUNT(*) FROM keyword_stats
               WHERE usable=1 AND used_at IS NULL GROUP BY 1 ORDER BY 2 DESC""")
        names = {"A": "A 생활노하우(권장)", "B": "B 사실·제도(회피)",
                 "C": "C 해석·의견", "D": "D 그 외"}
        for t, n in rows:
            print(f"  {names.get(t, t):20} {n:>6,}개")
        return

    todo = [r[0] for r in db.execute(
        """SELECT keyword FROM keyword_stats
           WHERE usable=1 AND used_at IS NULL AND topic_type IS NULL""")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[분류] 대상 {len(todo):,}개 (배치 {BATCH})")
    k = key()
    done = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            out = call(k, chunk)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  쿼터 소진 — 중단(재실행하면 이어서)", file=sys.stderr)
                break
            continue
        except Exception:
            continue
        recs = []
        for x in out:
            j = x.get("i")
            t = str(x.get("t", "")).strip().upper()[:1]
            if isinstance(j, int) and 0 <= j < len(chunk) and t in "ABCD":
                recs.append((t, chunk[j]))
        db.executemany(
            "UPDATE keyword_stats SET topic_type=? WHERE keyword=?", recs)
        db.commit()
        done += len(recs)
        print(f"  {done:,}/{len(todo):,}")
        time.sleep(2)
    print(f"[분류] 완료 {done:,}건")


if __name__ == "__main__":
    main()
