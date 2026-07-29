#!/usr/bin/env python3
"""M4 콘텐츠 생성기 — 검증된 주제로 독자 콘텐츠 초안 생성, 발행 큐 적재.

안전선: 프롬프트에는 주제·검색키워드·질문의도만 입력. 지식iN 원문 사용 금지.

사용법:
  python3 generate.py sample --topics 2      # 1호출 vs 3호출 품질 비교
  python3 generate.py run --n 10             # 큐 상위 n개 주제로 초안 생성
  python3 generate.py export                 # draft 글을 마크다운 파일로 내보내기
  python3 generate.py stats
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

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kin.db"
SAMPLES_DIR = BASE_DIR / "data" / "samples"
DRAFTS_DIR = BASE_DIR / "data" / "drafts"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.5-flash-lite"
SLEEP_SEC = 4

STYLE_RULES = """규칙:
- 한국어, 존댓말("~합니다"), 마크다운
- 분량 2,500자 이상. ## 소제목 4~6개로 구조화, 필요한 곳에 표·리스트 사용
- 첫 문단은 검색자가 원하는 핵심 답을 바로 제시 (결론 우선)
- 마지막에 "## 자주 묻는 질문" 섹션: 관련 질문 3개와 간결한 답
- 수수료·기한·법조항 등 구체 수치는 확실한 것만 쓰고, 변동 가능한 것은
  "정부24, 관할 기관 등 공식 채널에서 최신 기준을 확인하세요"로 안내
- 기관명·사이트명·서비스명은 널리 알려진 확실한 것만 사용 (정부24, 홈택스,
  한국교통안전공단 등). 조금이라도 불확실한 고유명사는 지어내지 말고
  "해당 기관 공식 홈페이지" 같은 일반 표현으로 대체
- 과장·광고 문구 금지, AI 상투 표현("~에 대해 알아보겠습니다", "결론적으로") 금지
- 특정 사이트·블로그 문체 모방 금지, 독자적으로 작성"""

SINGLE_PROMPT = """당신은 생활정보 전문 에디터다. 아래 주제로 검색 사용자에게 실제로 도움이 되는
완결형 정보 글 한 편을 작성하라.

주제: {topic}
타겟 검색 키워드: {keyword}
독자가 알고 싶은 것: {intent}

{style}

작성 후 스스로 검토해서 사실 불확실 표현, 중복 문장, 어색한 번역투를 고친 최종본만 출력하라.
첫 줄은 "# 제목" 형식의 SEO 제목(키워드 포함, 30자 이내)으로 시작하라."""

OUTLINE_PROMPT = """다음 주제의 정보 글 개요를 작성하라.
주제: {topic} / 키워드: {keyword} / 독자 니즈: {intent}
출력: SEO 제목 1개(30자 이내, 키워드 포함), ## 소제목 4~6개와 각 섹션에 담을 내용 1줄씩, FAQ 질문 3개."""

DRAFT_PROMPT = """다음 개요대로 정보 글 본문을 작성하라.

{outline}

{style}"""

REVIEW_PROMPT = """다음 글을 검토해서 수정한 최종본만 출력하라 (설명 없이 글만).
점검: 사실 불확실한 단정 완화, 중복 제거, 번역투·AI 상투 표현 제거, 분량 2,500자 미만이면 보강.

{draft}"""


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
        self.calls = 0

    def generate(self, prompt, retries=3):
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192},
        }).encode()
        req = urllib.request.Request(
            f"{API_BASE}/{MODEL}:generateContent", data=body,
            headers={"x-goog-api-key": self.api_key,
                     "Content-Type": "application/json"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as res:
                    data = json.loads(res.read().decode())
                self.calls += 1
                time.sleep(SLEEP_SEC)
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(30 * (attempt + 1))
                    continue
                raise
            except (KeyError, IndexError):
                if attempt < retries - 1:
                    continue
                raise RuntimeError("응답 파싱 실패")


def gen_single(gem, topic, keyword, intent):
    return gem.generate(SINGLE_PROMPT.format(
        topic=topic, keyword=keyword, intent=intent, style=STYLE_RULES))


def gen_multi(gem, topic, keyword, intent):
    outline = gem.generate(OUTLINE_PROMPT.format(
        topic=topic, keyword=keyword, intent=intent))
    draft = gem.generate(DRAFT_PROMPT.format(outline=outline, style=STYLE_RULES))
    return gem.generate(REVIEW_PROMPT.format(draft=draft))


def slugify(text, fallback):
    s = re.sub(r"[^\w가-힣]+", "-", text).strip("-").lower()
    return s[:60] or fallback


def get_queue(db, n, skip_done=True):
    done = set()
    if skip_done:
        done = {r[0] for r in db.execute("SELECT topic FROM articles")}
    rows = db.execute(
        """SELECT s.topic, s.keyword, COALESCE(t.intent, '') FROM topic_scores s
           LEFT JOIN topics t ON t.topic = s.topic
           GROUP BY s.topic ORDER BY s.score DESC"""
    ).fetchall()
    return [r for r in rows if r[0] not in done][:n]


def ensure_tables(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS articles (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             topic TEXT NOT NULL,
             keyword TEXT,
             title TEXT,
             body_md TEXT NOT NULL,
             method TEXT,
             model TEXT,
             status TEXT DEFAULT 'draft',  -- draft → reviewed → published
             created_at TEXT NOT NULL
           )"""
    )


def first_title(md):
    for line in md.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "run", "export", "stats"])
    ap.add_argument("--topics", type=int, default=2)
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    ensure_tables(db)

    if args.mode == "stats":
        for status, n in db.execute(
                "SELECT status, COUNT(*) FROM articles GROUP BY status"):
            print(f"{status}: {n}")
        return

    if args.mode == "export":
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        rows = db.execute(
            "SELECT id, topic, title, body_md FROM articles WHERE status='draft'"
        ).fetchall()
        for aid, topic, title, body in rows:
            path = DRAFTS_DIR / f"{aid:05d}-{slugify(title or topic, str(aid))}.md"
            path.write_text(body)
        print(f"{len(rows)}편 → {DRAFTS_DIR}")
        return

    gem = Gemini(load_env()["GEMINI_API_KEY"])
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if args.mode == "sample":
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        queue = get_queue(db, args.topics, skip_done=False)
        for topic, keyword, intent in queue:
            print(f"주제: {topic}")
            for method, fn in (("single", gen_single), ("multi", gen_multi)):
                t0 = time.time()
                md = fn(gem, topic, keyword, intent)
                path = SAMPLES_DIR / f"{slugify(keyword, topic)}-{method}.md"
                path.write_text(md)
                print(f"  {method}: {len(md)}자, {time.time()-t0:.0f}s → {path.name}")
        print(f"Gemini 호출: {gem.calls}")
        return

    # run: 발행 큐 상위 n개 생성 (기본 single)
    queue = get_queue(db, args.n)
    print(f"{len(queue)}개 주제 생성 시작")
    for topic, keyword, intent in queue:
        try:
            md = gen_single(gem, topic, keyword, intent)
        except Exception as e:
            print(f"  ! {topic}: {e}", file=sys.stderr)
            continue
        db.execute(
            "INSERT INTO articles (topic, keyword, title, body_md, method, model, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (topic, keyword, first_title(md), md, "single", MODEL, now))
        db.commit()
        print(f"  {topic}: {len(md)}자")
    print(f"완료. Gemini 호출: {gem.calls}")


if __name__ == "__main__":
    main()
