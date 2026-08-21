#!/usr/bin/env python3
"""롱테일 생성기 — 수집한 원본 질문 1건 = 글 1편, 배치 10건씩 생성.

기존 파이프라인(클러스터 471개 → 데이터랩 검증)은 9만 개 질문을 수백 개로 압축하고,
데이터랩 특성상 검색량 큰 = 경쟁 극심한 키워드만 통과시켜 신규 도메인이 이길 수 없었다.
여기서는 원본 질문의 롱테일 표현을 그대로 주제로 쓰고 검증 게이트를 두지 않는다.

사용법:
  python3 longtail.py run [--n 300]     # n편 생성 (배치 10건 단위)
  python3 longtail.py stats
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
EP = ("https://generativelanguage.googleapis.com/v1beta/models/"
      "{m}:generateContent?key={k}")

BATCH = 10
# 목표는 분량이 아니라 정보 밀도다. 섹션을 늘리면 글자 수는 늘지만 내용이 아니라
# 일반론이 늘어난다 (11~12 섹션 시험: "성향테스트" 4,515자 중 구체 문장 1개).
# 쓸 내용이 있는 만큼만 쓰도록 섹션을 5~6 으로 낮추고 하한만 지킨다.
MODELS = [
    ("gemini-3.1-flash-lite", 5, 6),
    ("gemini-3.5-flash-lite", 5, 6),
]
MIN_CHARS = 1500
SLEEP = 3

CATEGORIES = ["행정·제도", "자동차", "반려동물", "IT·디지털",
              "생활팁", "소비·쇼핑", "여행", "건강·의료", "금융·보험", "생활"]

RULES = """당신은 네이버 검색에 최적화된 한국어 정보성 블로그 작가입니다.
아래 원본 질문들 각각에 대해, 그 질문을 검색한 사람이 실제로 답을 얻는 글을 쓴다.

공통 원칙
- 존댓말(~합니다/~습니다). 단정·과장 금지. "도움이 되었길" 류 인사 금지.
- 질문의 구체적 상황을 그대로 다룬다. 일반론으로 퍼뜨리지 말 것.
- 확실한 것만 쓴다. 금액·기한·법조항처럼 변동되는 값은 단정하지 말고
  "공식 채널에서 최신 기준 확인"으로 안내한다.
- 기관명·서비스명은 널리 알려진 확실한 것만(정부24, 홈택스 등). 불확실하면 일반 표현.
- 조건에 따라 답이 갈리면 "A인 경우 / B인 경우"로 나눠 설명한다.
- 원본 질문의 오탈자·비속어·개인정보는 글에 옮기지 않는다."""

KW_RULES = """당신은 네이버 검색에 최적화된 한국어 정보성 블로그 작가입니다.
아래는 사람들이 네이버에 실제로 검색하는 키워드 목록이다.
각 키워드를 검색한 사람이 원하는 답을 주는 글을 쓴다.

공통 원칙
- 존댓말(~합니다/~습니다). 단정·과장 금지. "도움이 되었길" 류 인사 금지.
- 그 키워드를 검색하는 사람의 실제 의도를 짚어 그것부터 답한다.
  (예: "폐업신고" -> 어디서 어떻게 언제까지 하는지, 안 하면 어떻게 되는지)
- 확실한 것만 쓴다. 금액·기한·법조항처럼 변동되는 값은 단정하지 말고
  "공식 채널에서 최신 기준 확인"으로 안내한다.
- 기관명·서비스명은 널리 알려진 확실한 것만(정부24, 홈택스 등). 불확실하면 일반 표현.
- 특정 업체·상품을 추천하거나 홍보하지 않는다. 고르는 기준을 설명한다.
- 조건에 따라 답이 갈리면 "A인 경우 / B인 경우"로 나눠 설명한다.

정보 밀도 (가장 중요)
- 각 섹션에는 구체적 사실을 최소 하나 넣는다: 절차 순서, 신청처, 필요 서류,
  기한, 판단 기준, 조건별 차이 등. 확인 가능한 내용만 쓴다.
- "~이 중요합니다", "~해야 합니다", "꼼꼼히 확인하십시오" 같은 조언·훈계로
  문단을 채우지 않는다. 독자가 이미 아는 당연한 말은 쓰지 않는다.
- 속담·격언·감상적 마무리 문장 금지.
- 쓸 구체적 내용이 부족한 주제라면 억지로 늘리지 말고 짧게 끝낸다.
  분량을 채우려고 같은 말을 다르게 반복하는 것이 가장 나쁘다."""

TAIL = """

※각 필드 설명의 하한 글자 수를 반드시 지킨다. 항목 수를 채우려고 짧게 줄이지 말 것.
※모든 항목을 같은 밀도로 쓴다. 뒤로 갈수록 짧아지면 안 된다."""


def build_schema(n, lo, hi):
    section = {
        "type": "object",
        "properties": {
            "heading": {"type": "string",
                        "description": "이 섹션의 소제목. 12~30자. 번호나 ## 기호 없이 제목 문구만."},
            "body": {"type": "string",
                     "description": "이 섹션의 본문. 4~8문장. 구체적 사실을 담되 채우기 위한 반복은 금지."},
        },
        "required": ["heading", "body"],
    }
    item = {
        "type": "object",
        "properties": {
            "title": {"type": "string",
                      "description": ('"핵심 키워드 | 부연 설명" 형식의 SEO 제목. 전체 28~55자. '
                                      "파이프 앞은 원본 질문의 검색 키워드를 띄어쓰기 교정해 1~4단어로.")},
            # enum 을 쓰면 배치 10 스키마가 API 복잡도 한도를 넘어 400 이 된다.
            # 자유 문자열로 받고 코드에서 정규화한다.
            "category": {"type": "string",
                         "description": "다음 중 하나만: " + ", ".join(CATEGORIES)},
            "intro": {"type": "string",
                      "description": ("도입 문단. 3~4문장, 공백 포함 250~350자. "
                                      "첫 문장에서 질문의 대상을 호명하고 핵심 결론부터 말한다(두괄식). "
                                      "'알아보겠습니다' 류 예고 금지.")},
            "sections": {"type": "array", "minItems": lo, "maxItems": hi, "items": section,
                         "description": f"본문 섹션 {lo}~{hi}개. 서로 겹치지 않게 각각 다른 측면."},
            "outro": {"type": "string",
                      "description": "마무리 문단. 2~3문장, 공백 포함 120~180자. 새 정보 없이 핵심만."},
        },
        "required": ["title", "category", "intro", "sections", "outro"],
    }
    return {"type": "object",
            "properties": {"items": {"type": "array", "minItems": n,
                                     "maxItems": n, "items": item}},
            "required": ["items"]}


def norm_category(raw):
    """모델이 준 자유 문자열을 사이트 카테고리로 정규화."""
    s = re.sub(r"[\s·/]", "", str(raw or ""))
    for c in CATEGORIES:
        if re.sub(r"[\s·/]", "", c) == s:
            return c
    for c in CATEGORIES:
        head = re.sub(r"[\s·/]", "", c)[:2]
        if head and head in s:
            return c
    return "생활"


def assemble(it):
    parts = [it["intro"].strip()]
    for s in it["sections"]:
        parts.append(f"## {s['heading'].strip()}")
        parts.append(s["body"].strip())
    parts.append(it["outro"].strip())
    return "\n\n".join(parts)


def load_key():
    for line in (BASE / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY 없음")


# ── 질문 선별 ────────────────────────────────────────────────────────────
STOP = re.compile(r"(내공|급함|급해요|제발|ㅠ|ㅜ|ㅋ|\?|!|\.{2,})")

# 지식iN docId 는 시간순으로 증가한다 (2021년 ≈ 3.87억, 2026년 ≈ 4.94억).
# 오래된 질문은 "아이폰 13 사전예약", "소상공인 손실보전금"처럼 검색 수요가
# 이미 사라진 주제가 많아, 2024년 이후분(≈4.78억)만 사용한다.
MIN_DOC_ID = 478_000_000

# 지식iN 상위에는 업체가 자문자답하는 홍보성 질문이 섞여 있다. 이런 주제로 글을
# 써도 검색 수요가 없고 사이트 품질만 떨어뜨린다.
AD = re.compile(
    r"(지금\s*저렴|저렴하게|저렴한\s*곳|할인\s*중|이벤트\s*중|프로모션|최저가|"
    r"1타\s*강사|유명한\s*곳|잘하는\s*곳|괜찮은\s*곳|어디가\s*좋|추천\s*부탁드려요|"
    r"문의\s*드립니다\s*$|상담\s*받고|견적\s*문의)")

# 종료·만료된 제도나 시점 지난 이벤트 — 지금 검색되지 않는다
EXPIRED = re.compile(
    r"(손실보전금|재난지원금|방역패스|백신패스|거리두기|코로나|위드코로나|"
    r"박람회|페어|전시회|사전\s*예약|출시일|언제\s*나오|공모전|수능\s*접수|"
    r"올림픽|월드컵|대선|총선)")
BAD = re.compile(r"(성인|야동|도박|대출.*급전|담배|술.*판매|주식.*리딩|낙태|자살|"
                 r"[0-9]{2,3}-[0-9]{3,4}-[0-9]{4}|010[0-9]{8})")


def norm_key(title):
    """중복 판정용 정규화 키 — 조사·군더더기 제거 후 핵심 토큰 집합."""
    t = re.sub(r"[^\w가-힣 ]", " ", title)
    t = re.sub(r"(질문|문의|알려주세요|알려주쎄요|궁금해요|궁금합니다|좀요|해주세요|"
               r"부탁드립니다|드립니다|입니다|인가요|나요|어떻게|어떡해|어떤가요)", " ", t)
    toks = sorted({w for w in t.split() if len(w) >= 2})
    return " ".join(toks[:6])


def pick_questions(db, n):
    """미사용 질문 중 품질 필터 + 중복 제거를 통과한 것을 뽑는다."""
    used_keys = {r[0] for r in db.execute(
        "SELECT norm_key FROM used_questions WHERE norm_key IS NOT NULL")}
    picked, keys = [], set()
    cur = db.execute(
        """SELECT q.doc_id, q.title FROM questions q
           WHERE q.doc_id NOT IN (SELECT doc_id FROM used_questions)
             AND CAST(q.doc_id AS INTEGER) >= ?
           ORDER BY (SELECT MIN(rank) FROM hits h WHERE h.doc_id = q.doc_id)""",
        (MIN_DOC_ID,))
    for doc_id, title in cur:
        t = title.strip()
        if not (10 <= len(t) <= 60) or BAD.search(t):
            continue
        if AD.search(t) or EXPIRED.search(t):
            continue
        clean = STOP.sub("", t).strip()
        if len(clean) < 8:
            continue
        k = norm_key(clean)
        if not k or k in used_keys or k in keys:
            continue
        keys.add(k)
        picked.append((doc_id, clean, k))
        if len(picked) >= n:
            break
    return picked


def pick_keywords(db, n):
    """주제 사전(keyword_stats)에서 미사용 키워드를 우선순위대로 꺼낸다.

    우선순위: 경쟁 '낮음' -> 볼륨 스위트스팟(300~8,000) -> 검색량 큰 순.
    검색량이 아주 큰 것은 경쟁도 그만큼 세므로 중간 구간을 먼저 태운다.
    """
    return db.execute(
        """SELECT keyword, vol, comp FROM keyword_stats
           WHERE usable = 1 AND used_at IS NULL
           ORDER BY CASE comp WHEN '낮음' THEN 0 ELSE 1 END,
                    CASE WHEN vol BETWEEN 300 AND 8000 THEN 0 ELSE 1 END,
                    vol DESC
           LIMIT ?""", (n,)).fetchall()


def ensure_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS used_questions (
            doc_id TEXT PRIMARY KEY,
            norm_key TEXT,
            used_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_used_key ON used_questions(norm_key);
    """)
    cols = {r[1] for r in db.execute("PRAGMA table_info(articles)")}
    if "category" not in cols:
        db.execute("ALTER TABLE articles ADD COLUMN category TEXT")
    if "source_doc" not in cols:
        db.execute("ALTER TABLE articles ADD COLUMN source_doc TEXT")
    ks = {r[1] for r in db.execute("PRAGMA table_info(keyword_stats)")}
    if ks and "used_at" not in ks:
        db.execute("ALTER TABLE keyword_stats ADD COLUMN used_at TEXT")
    db.commit()


def generate(key, model, lo, hi, questions, retries=4, mode="question"):
    head = KW_RULES if mode == "keyword" else RULES
    label = "검색 키워드" if mode == "keyword" else "원본 질문"
    prompt = (head + f"\n\n{label} {len(questions)}개:\n"
              + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions)) + TAIL)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": build_schema(len(questions), lo, hi),
            "temperature": 0.7,
            "maxOutputTokens": 60000,
        },
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                EP.format(m=model, k=key), data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                data = json.loads(r.read())
            items = json.loads(
                data["candidates"][0]["content"]["parts"][0]["text"])["items"]
            out = [{"title": x["title"], "category": norm_category(x.get("category")),
                    "md": assemble(x)} for x in items]
            short = [o for o in out if len(o["md"]) < MIN_CHARS]
            if short:
                print(f"    분량 미달 {len(short)}/{len(out)} → 재시도", file=sys.stderr)
                time.sleep(5)
                continue
            return out
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError(f"{model} 쿼터 소진") from e
            if e.code == 400:
                raise RuntimeError(f"{model} 스키마 거부(400)") from e
            print(f"    HTTP {e.code} → 대기 후 재시도", file=sys.stderr)
            time.sleep(20 * (attempt + 1))
        except (KeyError, json.JSONDecodeError) as e:
            print(f"    파싱 실패({e}) → 재시도", file=sys.stderr)
            time.sleep(5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "stats"])
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    ensure_tables(db)

    if args.mode == "stats":
        for label, q in [
            ("질문 총계", "SELECT COUNT(*) FROM questions"),
            ("사용됨", "SELECT COUNT(*) FROM used_questions"),
            ("초안", "SELECT COUNT(*) FROM articles WHERE status='draft'"),
            ("발행", "SELECT COUNT(*) FROM articles WHERE status='published'"),
        ]:
            print(f"{label}: {db.execute(q).fetchone()[0]:,}")
        return

    key = load_key()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    # 주제 사전(검색 수요·경쟁도 검증분)을 우선 소비하고, 바닥나면 질문으로 보충한다.
    kw_pool = pick_keywords(db, args.n)
    q_pool = pick_questions(db, args.n - len(kw_pool)) if len(kw_pool) < args.n else []
    print(f"주제 사전 {len(kw_pool)}건 + 질문 {len(q_pool)}건 → 배치 {BATCH}건씩 생성")

    # (모드, 생성입력, 식별자) 로 통일해 한 루프에서 처리
    pool = ([("keyword", kw, kw) for kw, _, _ in kw_pool]
            + [("question", q, doc) for doc, q, _ in q_pool])
    qkeys = {doc: k for doc, _, k in q_pool}
    made = quota_hit = 0

    for i in range(0, len(pool), BATCH):
        chunk = pool[i:i + BATCH]
        mode = chunk[0][0]
        chunk = [c for c in chunk if c[0] == mode]   # 모드가 섞이지 않게
        model, lo, hi = MODELS[(i // BATCH) % len(MODELS)]
        try:
            out = generate(key, model, lo, hi, [c[1] for c in chunk], mode=mode)
        except RuntimeError as e:
            print(f"  ! {e}", file=sys.stderr)
            quota_hit += 1
            if quota_hit >= len(MODELS):
                print("  모든 모델 쿼터 소진 — 중단", file=sys.stderr)
                break
            continue
        if not out:
            continue
        for (m, src, ident), art in zip(chunk, out):
            db.execute(
                """INSERT INTO articles
                   (topic, keyword, title, body_md, method, model, status,
                    created_at, category, source_doc)
                   VALUES (?,?,?,?,?,?,'draft',?,?,?)""",
                (src, src, art["title"], art["md"], f"{m}-b{BATCH}",
                 model, now, art["category"], None if m == "keyword" else ident))
            if m == "keyword":
                db.execute("UPDATE keyword_stats SET used_at=? WHERE keyword=?",
                           (now, ident))
            else:
                db.execute("INSERT OR REPLACE INTO used_questions VALUES (?,?,?)",
                           (ident, qkeys.get(ident), now))
            made += 1
        db.commit()
        print(f"  {made}/{len(pool)}편  [{mode}/{model}]  예: {out[0]['title'][:38]}")
        time.sleep(SLEEP)

    print(f"완료: {made}편 생성")


if __name__ == "__main__":
    main()
