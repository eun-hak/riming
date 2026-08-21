#!/usr/bin/env python3
"""주제 사전 선별 필터 — 검색량·경쟁도를 통과해도 우리가 쓸 수 없는 키워드를 걸러낸다.

전수 조사로 18,037개가 게이트를 통과했지만, 그중 상당수는 정보성 글을 써도
검색자가 원하는 답이 될 수 없는 유형이다.
  · 제품 모델번호 (RH9SG, F877AW35)  — 스펙 검색, 우리가 답할 수 없음
  · 지역 업체·맛집 (인천지게차학원)    — 로컬 정보, 직접 모름
  · 개인 실명 (최동욱변호사)          — 특정인 탐색
  · 브랜드 탐색형 (엘지닷컴, 쿠팡대출) — 공식 사이트로 갈 검색
  · 의미 모호한 단발어 (일지, GO)

사용법:
  python3 keyword_filter.py test           # 필터 효과 측정
  python3 keyword_filter.py picks --n 40   # 통과 주제 미리보기
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

MIN_VOL, MAX_VOL = 100, 30_000
OK_COMP = ("낮음", "중간")

# 광역·주요 지자체 + 흔한 지명 접미 — 지역 업체성 키워드 판별용
REGION = (
    r"서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|"
    r"경북|경남|제주|수원|성남|고양|용인|부천|안산|안양|남양주|화성|평택|의정부|"
    r"시흥|파주|김포|광명|군포|하남|오산|양주|구리|안성|포천|여주|이천|양평|"
    r"청주|천안|아산|전주|익산|군산|목포|여수|순천|포항|경주|구미|김해|양산|"
    r"진주|거제|통영|창원|천호|강남|강북|송파|노원|마포|영등포|관악|성북|은평|"
    r"동작|서초|중랑|광진|용산|종로|금천|도봉|양천|강서|강동|주문진|속초|강릉|"
    r"동해|삼척|원주|춘천|홍천|평창|정선|태백|장흥|해남|완도|보성|담양|곡성"
)
# 지역명과 붙으면 로컬 업체 검색이 되는 업종어
LOCAL_BIZ = (
    r"학원|맛집|병원|의원|치과|한의원|약국|미용실|펜션|카페|식당|낚시터|"
    r"백숙|체험|유원지|캠핑장|글램핑|스터디카페|헬스장|필라테스|요가원|"
    r"부동산|공인중개사|중개소|주택조합|장례식장|웨딩홀|스튜디오|정비소|"
    r"세차장|주유소|마트|시장|국밥|칼국수|막국수|갈비|삼겹살|횟집|찜질방"
)
# 특정인 탐색 (○○변호사, ○○원장)
PERSON = r"(변호사|법무사|세무사|노무사|변리사|원장|교수|선생님|대표원장|한의사)$"
# 브랜드 + 탐색 의도 → 공식 사이트로 갈 검색
BRAND = (
    r"(삼성|엘지|LG|SK|KT|현대|기아|롯데|쿠팡|네이버|카카오|배민|토스|국민|"
    r"신한|하나|우리|농협|기업은행|이마트|홈플러스|다이소|올리브영|무신사|지마켓)"
)
NAV_INTENT = (
    r"(고객센터|채용|주가|공시|매장|지점|본사|대리점|서비스센터|닷컴|홈페이지|"
    r"로그인|회원가입|앱|어플|고객상담|콜센터|영업시간|위치|주소|전화번호|"
    r"베스트샵|직영점|플래그십)"
)
# 성인·도박 등 (생성 단계와 동일 기준)
BAD = r"(성인|야동|도박|카지노|바카라|토토|대출.*급전|담배|유흥|룸싸롱)"

_re_region_biz = re.compile(rf"({REGION}).*({LOCAL_BIZ})|({LOCAL_BIZ})")
_re_person = re.compile(PERSON)
_re_brand_nav = re.compile(rf"{BRAND}.*{NAV_INTENT}|{NAV_INTENT}")
_re_bad = re.compile(BAD)
_re_model = re.compile(r"[A-Za-z]")
_re_digit = re.compile(r"[0-9]")


def reject_reason(kw):
    """차단 사유를 돌려준다. 통과면 None."""
    k = (kw or "").strip()
    if len(k) < 3:
        return "너무 짧음"
    if len(re.findall(r"[가-힣]", k)) < 2:
        return "한글 부족"          # RH9SG, GO 등
    if _re_model.search(k) and _re_digit.search(k) and len(re.findall(r"[가-힣]", k)) < 4:
        return "모델번호"           # F877AW35, 삼성32인치TV 는 한글 4자라 통과
    if _re_bad.search(k):
        return "부적절"
    if _re_person.search(k):
        return "특정인"
    if _re_brand_nav.search(k):
        return "브랜드탐색"
    if _re_region_biz.search(k):
        return "지역업체"
    return None


# ── 2단: LLM 판정 ────────────────────────────────────────────────────
# 상호명·특정 상품·지역 기관처럼 고유명사라 정규식으로 못 잡는 것을 걸러낸다.
JUDGE_BATCH = 300
JUDGE_MODEL = "gemini-3.1-flash-lite"

JUDGE_PROMPT = """다음은 검색 키워드 목록이다. 각각에 대해 **일반 독자에게 도움이 되는
정보성 글을 쓸 수 있는 주제인지** 판정하라.

쓸 수 있다(ok=true): 방법·기준·절차·비교·효과처럼 일반적인 설명이 가능한 주제
  예) 실리콘곰팡이제거제, 국민연금 안내면, 경추마사지, 좀벌레약, 교통사고 합의금

쓸 수 없다(ok=false):
  - 특정 상호·브랜드·회사명 (육심당, 휴고코리아, 거북이샵)
  - 특정 상품 모델·카드명 (블리스5카드, 갤럭시북4가격)
  - 지역 기관·시설 (인천검찰청, 용인유기견센터)
  - 특정 기업의 일회성 이벤트·공시 (메타비티상장, 듀오링고할인코드)
  - 의미가 모호해 무엇을 묻는지 알 수 없는 말 (차지권, 일지)
  - 연예인·인물·작품 제목 등 고유명사

JSON 배열만 출력. 입력 수와 출력 수를 반드시 맞추고 i 는 입력 번호를 그대로 쓴다.

키워드:
"""
JUDGE_SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object",
    "properties": {"i": {"type": "integer"}, "ok": {"type": "boolean"}},
    "required": ["i", "ok"]}}}, "required": ["items"]}


def gemini_key():
    for line in (BASE / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY 없음")


def judge_batch(key, kws):
    items = "\n".join(f"{i}. {k}" for i, k in enumerate(kws))
    body = json.dumps({
        "contents": [{"parts": [{"text": JUDGE_PROMPT + items}]}],
        "generationConfig": {"response_mime_type": "application/json",
                             "response_schema": JUDGE_SCHEMA,
                             "maxOutputTokens": 20000, "temperature": 0.0},
    }).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{JUDGE_MODEL}:generateContent?key={key}",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])["items"]


def run_judge(limit=0):
    """정규식 통과분에 LLM 판정을 적용해 keyword_stats.usable 을 채운다."""
    db = sqlite3.connect(DB)
    cols = {r[1] for r in db.execute("PRAGMA table_info(keyword_stats)")}
    if "usable" not in cols:
        db.execute("ALTER TABLE keyword_stats ADD COLUMN usable INTEGER")
        db.commit()

    rows = db.execute(
        """SELECT keyword FROM keyword_stats
           WHERE vol BETWEEN ? AND ? AND comp IN (?,?) AND usable IS NULL""",
        (MIN_VOL, MAX_VOL, *OK_COMP)).fetchall()
    pending = [k for (k,) in rows if not reject_reason(k)]
    # 정규식에서 걸린 것은 판정 없이 바로 0 으로 확정
    blocked = [(k,) for (k,) in rows if reject_reason(k)]
    db.executemany("UPDATE keyword_stats SET usable=0 WHERE keyword=?", blocked)
    db.commit()

    if limit:
        pending = pending[:limit]
    print(f"[판정] 정규식 차단 {len(blocked):,}개 확정 / LLM 대상 {len(pending):,}개")
    key = gemini_key()
    ok_n = no_n = 0
    for i in range(0, len(pending), JUDGE_BATCH):
        chunk = pending[i:i + JUDGE_BATCH]
        try:
            out = judge_batch(key, chunk)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  쿼터 소진 — 중단(재실행하면 이어서)", file=sys.stderr)
                break
            print(f"  HTTP {e.code} — 배치 건너뜀", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  실패({type(e).__name__}) — 배치 건너뜀", file=sys.stderr)
            continue
        recs = []
        for x in out:
            j = x.get("i")
            if isinstance(j, int) and 0 <= j < len(chunk):
                recs.append((1 if x.get("ok") else 0, chunk[j]))
        db.executemany("UPDATE keyword_stats SET usable=? WHERE keyword=?", recs)
        db.commit()
        ok_n += sum(1 for v, _ in recs if v)
        no_n += sum(1 for v, _ in recs if not v)
        print(f"  {ok_n + no_n:,}/{len(pending):,} (사용가능 {ok_n:,})")
        time.sleep(2)
    print(f"[판정] 완료 — 사용가능 {ok_n:,} / 차단 {no_n:,}")


def load(db, extra_where=""):
    return db.execute(
        f"""SELECT keyword, vol, comp FROM keyword_stats
            WHERE vol BETWEEN ? AND ? AND comp IN (?,?) {extra_where}
            ORDER BY vol DESC""",
        (MIN_VOL, MAX_VOL, *OK_COMP)).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["test", "picks", "judge", "final"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    if args.mode == "judge":
        run_judge(args.limit)
        return

    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    if args.mode == "final":
        rows = db.execute(
            """SELECT keyword, vol, comp FROM keyword_stats
               WHERE usable = 1 ORDER BY vol DESC""").fetchall()
        print(f"최종 사용 가능 주제: {len(rows):,}개")
        for kw, vol, comp in rows[:args.n]:
            print(f"  {kw[:24]:26} {vol:>8,} {comp}")
        return
    rows = load(db)

    if args.mode == "test":
        from collections import Counter
        c = Counter()
        for kw, _, _ in rows:
            c[reject_reason(kw) or "통과"] += 1
        total = len(rows)
        print(f"게이트 통과분 {total:,}개에 선별 필터 적용\n")
        for reason, n in c.most_common():
            mark = "✓" if reason == "통과" else " "
            print(f"  {mark} {reason:10} {n:6,}개 ({n*100//total}%)")
        return

    shown = 0
    print(f"{'키워드':26} {'월검색':>8} 경쟁")
    for kw, vol, comp in rows:
        if reject_reason(kw):
            continue
        print(f"  {kw[:24]:26} {vol:>8,} {comp}")
        shown += 1
        if shown >= args.n:
            break


if __name__ == "__main__":
    main()
