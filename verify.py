#!/usr/bin/env python3
"""생성 글 검증 — 통과분만 발행 큐에 올린다.

draft → (검증) → ready(발행 대상) / rejected(폐기, 사유 기록)

2단 검사
  1) 규칙 검사: 분량·구조·잘림·중복·금칙어·한글비율 — 비용 0, 확정적
  2) LLM 검사: 원본 질문과 어긋나거나 사실이 위험한 글 — 배치 10건, 저비용

사용법:
  python3 verify.py run [--n 400]
  python3 verify.py report          # 최근 반려 사유 통계
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
      "gemini-3.5-flash-lite:generateContent?key={k}")

MIN_CHARS = 1500   # longtail.py 와 동일하게 유지할 것
MIN_SECTIONS = 4
LLM_BATCH = 10

# AI 상투구 — 문장 단위로 잘라내면 되는 것들 (글 전체를 버리지 않는다).
# '도움이 되었는지' 같은 본문 서술과 겹치지 않게 종결형만 좁혀서 매칭한다.
CLICHE = re.compile(
    r"(알아보겠습니다|살펴보겠습니다|소개해 ?드리겠습니다|정리해 ?드리겠습니다|"
    r"도움이 ?되(시|셨)길|도움이 ?되(기를|길) ?바랍니다|마무리하겠습니다|"
    r"이상으로|글을 ?마칩니다)")
# 지어낼 위험이 큰 구체값 (전화번호·연도 박힌 금액 등)
FABRICATION = re.compile(r"(1[5-9]\d{2}-\d{4}|0\d{1,2}-\d{3,4}-\d{4}|https?://)")
# 원문 오염 (질문자 말투가 그대로 옮겨진 경우)
RAW_LEAK = re.compile(r"(내공\s*\d|ㅠㅠ|ㅜㅜ|답변 ?부탁|급해요|채택)")


def load_key():
    for line in (BASE / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY 없음")


def hangul_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "가" <= c <= "힣") / len(letters)


def body_signature(md):
    """본문 중복 판정용 — 소제목 집합."""
    heads = re.findall(r"^## (.+)$", md, re.M)
    return "|".join(sorted(h.strip()[:20] for h in heads))


def autofix(body):
    """상투구가 든 문장만 제거한다. 대부분 도입부 끝 예고문 한 줄이라
    통째로 반려하는 것보다 잘라내는 편이 낫다."""
    fixed, removed = [], 0
    for para in body.split("\n\n"):
        if para.startswith("## ") or not CLICHE.search(para):
            fixed.append(para)
            continue
        keep = [s for s in re.split(r"(?<=[.!?])\s+", para)
                if not CLICHE.search(s)]
        removed += len(re.split(r"(?<=[.!?])\s+", para)) - len(keep)
        if keep:
            fixed.append(" ".join(keep))
    return "\n\n".join(fixed), removed


def rule_check(title, body, seen_sigs, seen_titles):
    """확정적으로 걸러낼 문제만 반환. 통과하면 빈 리스트."""
    flags = []
    if len(body) < MIN_CHARS:
        flags.append(f"분량미달({len(body)})")
    heads = re.findall(r"^## (.+)$", body, re.M)
    if len(heads) < MIN_SECTIONS:
        flags.append(f"섹션부족({len(heads)})")
    if len(set(heads)) != len(heads):
        flags.append("소제목중복")
    # 문장 잘림 — 마지막이 종결부호가 아니면 출력이 끊긴 것
    if not body.rstrip().endswith((".", "!", "?", "다", "요")):
        flags.append("문장잘림")
    if hangul_ratio(body) < 0.7:
        flags.append("한글비율낮음")
    if FABRICATION.search(body):
        flags.append("허구위험값")
    if RAW_LEAK.search(body):
        flags.append("원문오염")
    if not (15 <= len(title) <= 60):
        flags.append(f"제목길이({len(title)})")
    sig = body_signature(body)
    if sig and sig in seen_sigs:
        flags.append("본문중복")
    tkey = re.sub(r"[^\w가-힣]", "", title.split("|")[0])[:20]
    if tkey and tkey in seen_titles:
        flags.append("제목중복")
    return flags, sig, tkey


LLM_PROMPT = """다음은 자동 생성된 정보성 글 {n}건의 요약이다. 각각 발행해도 되는지 판정하라.

반려(ok=false) 기준 — 아래에 해당할 때만:
- 원본 질문과 주제가 어긋남
- 사실로 단정했는데 위험한 내용(의료·법률·금융에서 잘못된 조언)
- 내용이 텅 비어 있음(일반론만 반복, 실질 정보 없음)
- 명백히 존재하지 않는 기관명·제도명을 사실처럼 서술

애매하면 통과(ok=true)시킨다. 문체·분량은 판정 대상이 아니다.
JSON 배열 [{{"i":번호,"ok":true/false,"why":"20자 이내"}}] 만 출력.

{items}"""


def llm_check(key, batch):
    items = "\n\n".join(
        f"[{i}] 원본질문: {q}\n제목: {t}\n소제목: {' / '.join(re.findall(r'^## (.+)$', b, re.M))}\n"
        f"도입부: {b[:300]}"
        for i, (_, q, t, b) in enumerate(batch))
    payload = json.dumps({
        "contents": [{"parts": [{"text": LLM_PROMPT.format(n=len(batch), items=items)}]}],
        "generationConfig": {"response_mime_type": "application/json",
                             "maxOutputTokens": 4000, "temperature": 0.0},
    }).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                EP.format(k=key), data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            return json.loads(
                data["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("    LLM 쿼터 소진 — 규칙 검사만 적용", file=sys.stderr)
                return None
            time.sleep(15 * (attempt + 1))
        except Exception:
            time.sleep(5)
    return None


def ensure(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(articles)")}
    if "qa_flags" not in cols:
        db.execute("ALTER TABLE articles ADD COLUMN qa_flags TEXT")
    if "qa_at" not in cols:
        db.execute("ALTER TABLE articles ADD COLUMN qa_at TEXT")
    db.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "report"])
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    ensure(db)

    if args.mode == "report":
        rows = db.execute(
            """SELECT qa_flags, COUNT(*) FROM articles
               WHERE status='rejected' GROUP BY qa_flags
               ORDER BY COUNT(*) DESC LIMIT 15""").fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM articles WHERE status='rejected'").fetchone()[0]
        print(f"반려 누적 {total}건")
        for f, n in rows:
            print(f"  {n:>4}  {f}")
        return

    # 이미 통과·발행된 글의 지문을 미리 모아 중복 판정 기준으로 쓴다
    seen_sigs, seen_titles = set(), set()
    for t, b in db.execute(
            "SELECT title, body_md FROM articles WHERE status IN ('ready','published')"):
        seen_sigs.add(body_signature(b or ""))
        seen_titles.add(re.sub(r"[^\w가-힣]", "", (t or "").split("|")[0])[:20])

    rows = db.execute(
        """SELECT id, topic, title, body_md FROM articles
           WHERE status='draft' ORDER BY id LIMIT ?""", (args.n,)).fetchall()
    if not rows:
        print("검증할 초안 없음")
        return
    print(f"초안 {len(rows)}건 검증 시작")

    passed, rejected, fixes = [], [], []
    for aid, q, title, body in rows:
        body = body or ""
        body, removed = autofix(body)      # 상투구 문장 제거 후 검사
        if removed:
            fixes.append((body, aid))
        flags, sig, tkey = rule_check(title or "", body, seen_sigs, seen_titles)
        if flags:
            rejected.append((aid, ",".join(flags)))
        else:
            seen_sigs.add(sig)
            seen_titles.add(tkey)
            passed.append((aid, q, title, body))
    if fixes:
        db.executemany("UPDATE articles SET body_md=? WHERE id=?", fixes)
        db.commit()
        print(f"  상투구 자동 수정 {len(fixes)}건")

    # 2단: 규칙 통과분만 LLM 검사
    if passed and not args.no_llm:
        key = load_key()
        survivors = []
        for i in range(0, len(passed), LLM_BATCH):
            batch = passed[i:i + LLM_BATCH]
            verdicts = llm_check(key, batch)
            if verdicts is None:
                survivors.extend(batch)
                continue
            bad = {v["i"]: v.get("why", "") for v in verdicts
                   if isinstance(v, dict) and v.get("ok") is False}
            for j, item in enumerate(batch):
                if j in bad:
                    rejected.append((item[0], f"LLM:{bad[j][:20]}"))
                else:
                    survivors.append(item)
            time.sleep(2)
        passed = survivors

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    db.executemany("UPDATE articles SET status='ready', qa_at=? WHERE id=?",
                   [(now, p[0]) for p in passed])
    db.executemany(
        "UPDATE articles SET status='rejected', qa_flags=?, qa_at=? WHERE id=?",
        [(f, now, aid) for aid, f in rejected])
    db.commit()

    rate = 100 * len(passed) / len(rows)
    print(f"통과 {len(passed)}건 / 반려 {len(rejected)}건 (통과율 {rate:.0f}%)")
    if rejected:
        from collections import Counter
        for f, n in Counter(f for _, f in rejected).most_common(8):
            print(f"  반려 {n:>3}  {f}")


if __name__ == "__main__":
    main()
