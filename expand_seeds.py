#!/usr/bin/env python3
"""시드 키워드 자동 확장 — 수집된 질문에서 새 검색 키워드를 발굴해 seeds.txt에 추가.

원리: 기존 시드로 수집한 질문 제목 안에는 아직 시드가 아닌 파생 주제가 들어 있다
(예: "전세 계약" 질문들 속 "묵시적 갱신", "임차권등기"). 이를 Gemini로 추출해
시드로 재투입하면 그 키워드의 인기 질문 상위 1,000개를 새로 캘 수 있다 (자기증식).

사용법:
  python3 expand_seeds.py run [--add 20] [--sample 400]
"""

import argparse
import json
import random
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
SEEDS = BASE / "seeds.txt"
API = ("https://generativelanguage.googleapis.com/v1beta/models/"
       "gemini-3.5-flash-lite:generateContent")

PROMPT = """다음은 지식iN 질문 제목 샘플과, 이미 사용 중인 검색 키워드 목록이다.
질문들 속에서 반복 등장하지만 기존 키워드로는 커버되지 않는 '새 검색 키워드'를 {n}개 뽑아라.

규칙:
- 사람들이 네이버에 실제 입력할 법한 2~4어절 명사구 (조사 없이)
- 기존 키워드와 실질적으로 같은 것(동의어·어순 변형) 금지
- 특정 상호명·개인 정보·일회성 이슈 금지, 에버그린 생활 주제 위주
- JSON 배열 ["키워드", ...] 만 출력

기존 키워드:
{seeds}

질문 샘플:
{titles}"""


def load_env():
    env = {}
    for line in (BASE / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def read_seeds():
    seeds = []
    for line in SEEDS.read_text().splitlines():
        s = line.split("#")[0].strip()
        if s:
            seeds.append(s)
    return seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run"])
    ap.add_argument("--add", type=int, default=20)
    ap.add_argument("--sample", type=int, default=400)
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    titles = [r[0] for r in db.execute(
        "SELECT title FROM questions").fetchall()]
    random.shuffle(titles)
    sample = titles[:args.sample]
    seeds = read_seeds()

    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT.format(
            n=args.add,
            seeds="\n".join(f"- {s}" for s in seeds),
            titles="\n".join(f"- {t}" for t in sample),
        )}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "x-goog-api-key": load_env()["GEMINI_API_KEY"],
        "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                new = json.loads(json.loads(res.read())
                                 ["candidates"][0]["content"]["parts"][0]["text"])
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(30)
                continue
            raise

    existing = set(seeds)
    added = []
    for kw in new:
        kw = str(kw).strip()
        if kw and kw not in existing and len(kw) <= 25:
            added.append(kw)
            existing.add(kw)
    if added:
        stamp = time.strftime("%Y-%m-%d")
        with SEEDS.open("a") as f:
            f.write(f"\n# 자동 확장 {stamp}\n")
            for kw in added:
                f.write(kw + "\n")
    print(f"시드 {len(seeds)}개 → {len(seeds) + len(added)}개 (+{len(added)})")
    for kw in added:
        print(f"  + {kw}")


if __name__ == "__main__":
    main()
