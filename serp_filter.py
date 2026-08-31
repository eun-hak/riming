#!/usr/bin/env python3
"""SERP 난이도 판정 — 검색결과에서 실제로 이길 수 있는 키워드만 남긴다.

배경: 검색광고 API 의 compIdx 는 '광고주 경쟁'이지 'SEO 경쟁'이 아니다.
"기초연금모의계산기"는 광고 경쟁 '낮음'이지만 유기 검색 1위는 보건복지부라
신생 도메인이 뚫을 수 없다. 실측 결과 주제 사전 기반 글 20편 전부가 대상
키워드 100위 밖이었다.

그래서 후보 키워드로 실제 웹문서 검색을 돌려 상위 10개 구성을 본다.
  · 기관·대형 상업·위키·언론이 다수면  → 탈락 (못 이김)
  · 개인 블로그·소규모 사이트가 섞여 있으면 → 통과 (틈이 있음)

사용법:
  python3 serp_filter.py sample --n 30   # 기준 보정용 표본
  python3 serp_filter.py run [--limit N] # 전수 판정
  python3 serp_filter.py stats
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
SLEEP = 0.15          # 검색 API 는 초당 10회 수준까지 허용
MAX_HARD = 3          # 상위 10개 중 강자가 이 수를 넘으면 탈락
MIN_SOFT = 2          # 소규모 사이트가 최소 이만큼은 있어야 틈이 있다고 본다

# 신생 도메인이 유기 검색에서 이길 수 없는 상대
HARD = re.compile(
    r"(\.go\.kr|\.or\.kr|\.ac\.kr|\.mil\.kr|namu\.wiki|wikipedia\.org|"
    r"naver\.com|daum\.net|kakao\.com|google\.|youtube\.com|"
    # 대형 언론
    r"(chosun|joongang|donga|hani|khan|hankyung|ytn|sbs|kbs|imbc|mbn|jtbc|"
    r"news1|newsis|yna|edaily|seoul|segye|kmib|nocutnews|mt|mk|fnnews)\.(co\.)?kr|"
    # 대형 상업·플랫폼
    r"(11st|coupang|gmarket|auction|ssg|lotteon|interpark|danawa|wemakeprice|"
    r"tmon|oliveyoung|musinsa|kurly|banksalad|toss|kakaobank|trip|agoda|"
    r"yanolja|goodchoice|hotels|expedia|10000recipe|jobkorea|saramin|"
    r"incruit|wanted|zigbang|dabang|kbland|hogangnono)\.|"
    # 제조사·대기업 공식
    r"(samsung|lge|apple|lg|sk|kt|skt|uplus|hyundai|kia|posco)\.(com|co\.kr)|"
    r"\.samsung\.com|\.lge\.co\.kr)")

# 소규모·개인 매체 — 여기가 상위에 있으면 우리도 들어갈 여지가 있다
SOFT = re.compile(
    r"(tistory\.com|blogspot\.com|brunch\.co\.kr|wordpress\.com|"
    r"blog\.me|postype\.com|velog\.io|medium\.com|xn--)")


def load_env():
    e = {}
    for line in (BASE / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            e[k.strip()] = v.strip()
    return e


def ensure(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(keyword_stats)")}
    for c, t in (("serp_hard", "INTEGER"), ("serp_soft", "INTEGER"),
                 ("serp_total", "INTEGER"), ("serp_ok", "INTEGER"),
                 ("serp_at", "TEXT")):
        if c not in cols:
            db.execute(f"ALTER TABLE keyword_stats ADD COLUMN {c} {t}")
    db.commit()


def serp(headers, kw):
    """상위 10개의 (강자 수, 소규모 수, 전체 문서 수)"""
    u = ("https://openapi.naver.com/v1/search/webkr.json?display=10&query="
         + urllib.parse.quote(kw))
    req = urllib.request.Request(u, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    doms = [i["link"].split("/")[2] for i in d.get("items", []) if "://" in i["link"]]
    hard = sum(1 for x in doms if HARD.search(x))
    soft = sum(1 for x in doms if SOFT.search(x))
    return hard, soft, d.get("total", 0), doms


def judge(hard, soft, total, n_results):
    """이길 여지가 있는가."""
    if n_results < 3:            # 결과 자체가 거의 없음 = 수요 의심
        return 0
    if hard > MAX_HARD:
        return 0
    if soft < MIN_SOFT:          # 소규모 사이트가 아예 없으면 진입 여지 없음
        return 0
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "run", "stats"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    ensure(db)
    e = load_env()
    H = {"X-Naver-Client-Id": e["NAVER_CLIENT_ID"],
         "X-Naver-Client-Secret": e["NAVER_CLIENT_SECRET"]}

    if args.mode == "stats":
        row = db.execute(
            """SELECT COUNT(*), SUM(serp_ok IS NOT NULL), SUM(serp_ok=1)
               FROM keyword_stats WHERE usable=1""").fetchone()
        print(f"사용가능 {row[0]:,} / 판정완료 {row[1] or 0:,} / SERP 통과 {row[2] or 0:,}")
        return

    if args.mode == "sample":
        kws = [r[0] for r in db.execute(
            "SELECT keyword FROM keyword_stats WHERE usable=1 ORDER BY RANDOM() LIMIT ?",
            (args.n,))]
        ok = 0
        print(f"{'키워드':22}{'강자':>4}{'소규모':>5}  판정  상위 도메인")
        for kw in kws:
            try:
                h, s, t, doms = serp(H, kw)
            except Exception:
                continue
            v = judge(h, s, t, len(doms))
            ok += v
            print(f"  {kw[:20]:22}{h:>4}{s:>5}  {'통과' if v else '탈락'}  {', '.join(doms[:2])[:34]}")
            time.sleep(SLEEP)
        print(f"\n  통과 {ok}/{len(kws)} ({ok*100//max(len(kws),1)}%)")
        return

    rows = db.execute(
        """SELECT keyword FROM keyword_stats
           WHERE usable=1 AND serp_ok IS NULL AND used_at IS NULL""").fetchall()
    todo = [k for (k,) in rows][:args.limit or None]
    print(f"[SERP] 판정 대상 {len(todo):,}개 (예상 {len(todo)*SLEEP/60:.0f}분)")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    done = ok = 0
    for kw in todo:
        try:
            h, s, t, doms = serp(H, kw)
        except urllib.error.HTTPError as ex:
            if ex.code == 429:
                print("  검색 API 한도 — 중단(재실행하면 이어서)", file=sys.stderr)
                break
            time.sleep(1)
            continue
        except Exception:
            time.sleep(1)
            continue
        v = judge(h, s, t, len(doms))
        db.execute(
            """UPDATE keyword_stats SET serp_hard=?, serp_soft=?, serp_total=?,
               serp_ok=?, serp_at=? WHERE keyword=?""", (h, s, t, v, now, kw))
        done += 1
        ok += v
        if done % 200 == 0:
            db.commit()
            print(f"  {done:,}/{len(todo):,} (통과 {ok:,})")
        time.sleep(SLEEP)
    db.commit()
    print(f"[SERP] 완료 {done:,}건 판정 / 통과 {ok:,}건 ({ok*100//max(done,1)}%)")


if __name__ == "__main__":
    main()
