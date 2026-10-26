#!/usr/bin/env python3
"""M6 일일 배치 — 백업 → (주1회 수집) → 롱테일 생성 → 검증 → 발행 → push.

설계
- 2026-07-30: 사람 검수 없음(사후 점검), launchd 매일 07:00 (com.simsimi.riming.daily)
- 2026-08-07: 롱테일 전환. 원본 질문 1건=글 1편, 배치 10건 생성, 데이터랩 검증 폐지.
  대신 자동 검증(verify.py)이 규칙+LLM으로 걸러 ready 된 것만 발행한다.
"""

import datetime
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "kin.db"
BACKUP_DIR = BASE / "backup"
# 2026-10-26 감속: 9월 말 주제 사전(A·C형)이 소진된 뒤 한 달간 전량이 질문
# 폴백으로 넘어갔고, 그 폴백은 검색량을 보지 않는다. 미분류 질문을 분류해 보니
# 80%가 B(사실·제도)형 — 검색 상위를 공공기관이 점유해 신생 도메인이 못 이기는
# 유형이었다. 쓸 수 있는 A·C 재고에 맞춰 발행을 낮추고, 그 사이 연관어 21만 개로
# 주제 사전을 재생산한다. 재고가 회복되면 다시 올린다.
PUBLISH_PER_DAY = 100     # (감속 전 300)
GENERATE_PER_DAY = 120    # 검증 반려 약 15% 를 감안한 발행분 + 여유
DRAFT_FLOOR = 150         # 초안 재고 최소선
SUBMIT_PER_DAY = 50       # 네이버 수집요청 일일 제출량
SUBMIT_BUFFER_DAYS = 4    # 선생성 버퍼 (길수록 신규분 제출이 밀림)
BACKUP_KEEP = 7


def run(step, args, timeout=3600):
    print(f"\n── {step} ──")
    try:
        r = subprocess.run(
            [sys.executable] + args, cwd=BASE, timeout=timeout,
            capture_output=True, text=True,
        )
        out = (r.stdout + r.stderr).strip()
        # 뒤 2,000자만 남기면 진단 메시지가 앞에 찍히는 단계에서 머리가 잘린다.
        # (생성 단계의 "주제 사전 N건 + 질문 N건" 이 그렇게 한 달간 묻혔다)
        # 앞뒤를 같이 남긴다.
        if not out:
            print("(출력 없음)")
        elif len(out) <= 2500:
            print(out)
        else:
            print(out[:800] + f"\n… (중략 {len(out) - 2500:,}자) …\n" + out[-1700:])
        if r.returncode != 0:
            print(f"⚠ {step} 실패 (exit {r.returncode}) — 다음 단계 계속")
        return r.returncode == 0
    except Exception as e:
        print(f"⚠ {step} 예외: {e} — 다음 단계 계속")
        return False


def sh(step, cmd):
    print(f"\n── {step} ──")
    r = subprocess.run(cmd, cwd=BASE, shell=True, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(out[-1500:] if out else "(출력 없음)")
    return r.returncode == 0


def backup():
    print("\n── DB 백업 ──")
    BACKUP_DIR.mkdir(exist_ok=True)
    today = datetime.date.today().strftime("%Y%m%d")
    dst = BACKUP_DIR / f"kin-{today}.db"
    if not dst.exists():
        shutil.copy(DB, dst)
    olds = sorted(BACKUP_DIR.glob("kin-*.db"))
    for f in olds[:-BACKUP_KEEP]:
        f.unlink()
    print(f"백업 {dst.name}, 보관 {min(len(olds), BACKUP_KEEP)}개")


def counts():
    db = sqlite3.connect(DB)
    c = {}
    c["used_q"] = db.execute("SELECT COUNT(*) FROM used_questions").fetchone()[0]
    c["draft"] = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status='draft'").fetchone()[0]
    c["ready"] = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status='ready'").fetchone()[0]
    c["rejected"] = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status='rejected'").fetchone()[0]
    c["published"] = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0]
    c["questions"] = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    # 실제로 쓸 수 있는 주제 재고. questions - used_questions 는 연식·규칙 필터를
    # 거치기 전 숫자라 10배 넘게 부풀려 보인다(181,464 → 실제 약 1.2만).
    # 매일 눈에 보이게 요약에 싣는다.
    c["kw_ac"] = db.execute(
        """SELECT COUNT(*) FROM keyword_stats
           WHERE usable=1 AND used_at IS NULL
             AND topic_type IN ('A','C')""").fetchone()[0]
    c["q_ac"] = db.execute(
        """SELECT COUNT(*) FROM questions q
           JOIN question_type t ON t.doc_id = q.doc_id
           WHERE q.doc_id NOT IN (SELECT doc_id FROM used_questions)
             AND CAST(q.doc_id AS INTEGER) >= 478000000
             AND t.topic_type IN ('A','C')""").fetchone()[0]
    c["q_unclassified"] = db.execute(
        """SELECT COUNT(*) FROM questions q
           WHERE q.doc_id NOT IN (SELECT doc_id FROM used_questions)
             AND q.doc_id NOT IN (SELECT doc_id FROM question_type)
             AND CAST(q.doc_id AS INTEGER) >= 478000000""").fetchone()[0]
    db.close()
    return c


def main():
    now = datetime.datetime.now()
    print(f"===== riming daily batch {now:%Y-%m-%d %H:%M} =====")
    backup()
    before = counts()

    # 일요일: 시드 확장 + 질문 재고 보충 (클러스터링은 롱테일 전환으로 불필요)
    if now.weekday() == 6:
        run("시드 키워드 확장", ["expand_seeds.py", "run", "--add", "20"])
        run("주간 수집(sim/point 리프레시)",
            ["collect.py", "bulk", "--sorts", "sim,point", "--pages", "5"],
            timeout=7200)

    # 초안 보충 — 원본 질문 1건 = 글 1편, 배치 10건씩
    need = max(GENERATE_PER_DAY, DRAFT_FLOOR - before["ready"])
    run("롱테일 초안 생성", ["longtail.py", "run", "--n", str(need)], timeout=14400)

    # 검증 — 통과분(ready)만 발행 대상이 된다
    run("초안 검증", ["verify.py", "run", "--n", str(need + 100)], timeout=3600)

    # 발행 + 배포
    run("발행", ["publish.py", "run", "--n", str(PUBLISH_PER_DAY)])

    # 수집요청용 파일 2종을 사이트에 배포한다.
    #  today.txt — 오늘 제출할 50개만. 서버는 받아서 전부 넘기면 되고 상태를 안 가진다
    #  urls.txt  — 전체 목록(백업·재순회용)
    # 맥이 며칠 꺼져도 서버가 그날 파일을 받도록 버퍼를 둔다. 다만 길게 잡으면
    # 그만큼 신규 발행분의 제출이 밀리므로 4일치까지만 미리 만든다.
    sh("수집요청 URL 4일치 유지",
       f'python3 submit_queue.py prepare --days {SUBMIT_BUFFER_DAYS} --n {SUBMIT_PER_DAY}')
    sh("전체 URL 목록 갱신",
       'python3 submit_queue.py all --out web/public/urls.txt')

    sh("git push (Vercel 자동배포)",
       'git add web/content/posts web/public && '
       f'git commit -m "publish: {now:%Y-%m-%d} 자동 발행" && git push')

    after = counts()
    print(f"""
===== 요약 =====
질문 수집:   {before['questions']} → {after['questions']}
소진 질문:   {before['used_q']} → {after['used_q']}
주제 재고:   사전 A·C {after['kw_ac']:,} + 질문 A·C {after['q_ac']:,} = {after['kw_ac'] + after['q_ac']:,}건 \
({(after['kw_ac'] + after['q_ac']) / max(PUBLISH_PER_DAY, 1):.0f}일치)  미분류 대기 {after['q_unclassified']:,}
발행 대기:   {before['ready']} → {after['ready']} (검증 반려 누적 {after['rejected']})
발행 누적:   {before['published']} → {after['published']} (+{after['published'] - before['published']})
""")
    low = after['kw_ac'] + after['q_ac']
    if low < PUBLISH_PER_DAY * 14:
        print(f"⚠ 주제 재고 {low:,}건 — 2주 미만. 사전 재생산(연관어 재조사) 필요")


if __name__ == "__main__":
    main()
