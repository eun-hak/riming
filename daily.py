#!/usr/bin/env python3
"""M6 일일 배치 — 백업 → (주1회 수집·클러스터) → 검증 확장 → 초안 보충 → 발행 → push.

설계 (2026-07-30 사용자 결정):
- 검수 단계 없음 (사후 점검), 발행 상한 PUBLISH_PER_DAY
- 신규 수집은 일요일만 (평일은 기존 인기 질문 백로그 소화)
- launchd로 매일 07:00 실행 (com.simsimi.riming.daily)
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
PUBLISH_PER_DAY = 300     # 롱테일 전환 — 크롤 예산 성장에 맞춰 조정
GENERATE_PER_DAY = 350    # 발행분 + 재고 여유
DRAFT_FLOOR = 200         # 초안 재고 최소선
BACKUP_KEEP = 7


def run(step, args, timeout=3600):
    print(f"\n── {step} ──")
    try:
        r = subprocess.run(
            [sys.executable] + args, cwd=BASE, timeout=timeout,
            capture_output=True, text=True,
        )
        out = (r.stdout + r.stderr).strip()
        print(out[-2000:] if out else "(출력 없음)")
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
    c["published"] = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0]
    c["questions"] = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
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
    need = max(GENERATE_PER_DAY, DRAFT_FLOOR - before["draft"])
    run("롱테일 초안 생성", ["longtail.py", "run", "--n", str(need)], timeout=14400)

    # 발행 + 배포
    run("발행", ["publish.py", "run", "--n", str(PUBLISH_PER_DAY)])
    sh("git push (Vercel 자동배포)",
       'git add web/content/posts && '
       f'git commit -m "publish: {now:%Y-%m-%d} 자동 발행" && git push')

    after = counts()
    print(f"""
===== 요약 =====
질문 수집:   {before['questions']} → {after['questions']}
소진 질문:   {before['used_q']} → {after['used_q']} (재고 {after['questions'] - after['used_q']:,})
초안 재고:   {before['draft']} → {after['draft']}
발행 누적:   {before['published']} → {after['published']} (+{after['published'] - before['published']})
""")


if __name__ == "__main__":
    main()
