#!/usr/bin/env python3
"""발행 큐 → 사이트 게시. draft 상태 글을 매일 소량씩 사이트 콘텐츠로 내보낸다.

사용법:
  python3 publish.py run [--n 10]    # draft n편을 site/src/content/posts/로 발행
  python3 publish.py stats
"""

import argparse
import re
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kin.db"
POSTS_DIR = BASE_DIR / "web" / "content" / "posts"

# 시드 키워드 분야 → 사이트 카테고리 (seeds.txt 섹션 기준)
CATEGORY = {
    "행정·제도": ["전세 계약", "월세 보증금", "전입신고", "확정일자", "주민등록등본 발급",
                "연말정산", "청년 지원금", "실업급여", "국민연금", "건강보험료"],
    "자동차": ["자동차보험", "중고차 구매", "자동차 검사", "운전면허 갱신", "블랙박스"],
    "반려동물": ["강아지 키우기", "고양이 키우기", "강아지 사료", "반려동물 등록"],
    "IT·디지털": ["아이폰 설정", "갤럭시 사용법", "노트북 추천", "와이파이 연결",
                "유튜브 프리미엄", "넷플릭스 요금"],
    "생활팁": ["캠핑 준비물", "낚시 초보", "식물 키우기", "홈트레이닝", "에어컨 청소",
              "세탁기 청소", "반찬 보관", "냉동 보관", "전자레인지 요리"],
    "소비·쇼핑": ["환불 규정", "택배 반품", "해외직구 관세"],
    "여행": ["제주도 여행", "일본 여행 준비", "여권 발급"],
}
SEED_TO_CAT = {seed: cat for cat, seeds in CATEGORY.items() for seed in seeds}


def category_for(db, topic, stored=None):
    # 롱테일 생성분은 articles.category 에 이미 판정 결과가 들어 있다.
    if stored:
        return stored
    row = db.execute(
        "SELECT keyword FROM topics WHERE topic = ? ORDER BY count DESC LIMIT 1",
        (topic,),
    ).fetchone()
    return SEED_TO_CAT.get(row[0] if row else "", "생활")


def slugify(text, fallback):
    s = re.sub(r"[^\w가-힣]+", "-", text).strip("-").lower()
    return s[:60] or fallback


def unique_slug(base, fallback, taken):
    """대량 발행에서 제목이 겹쳐도 URL 이 충돌하지 않게 보정."""
    slug = slugify(base, fallback)
    if slug not in taken:
        taken.add(slug)
        return slug
    for i in range(2, 100):
        cand = f"{slug}-{i}"
        if cand not in taken:
            taken.add(cand)
            return cand
    taken.add(fallback)
    return fallback


def strip_title(md):
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return line[2:].strip(), "\n".join(lines[i + 1:]).strip()
    return "", md


def description_of(body):
    for para in body.split("\n\n"):
        text = re.sub(r"[#*_\[\]|>-]", "", para).strip()
        if len(text) > 40:
            return text[:150].rsplit(" ", 1)[0]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "stats"])
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    if args.mode == "stats":
        for status, n in db.execute(
                "SELECT status, COUNT(*) FROM articles GROUP BY status"):
            print(f"{status}: {n}")
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    cols = {r[1] for r in db.execute("PRAGMA table_info(articles)")}
    cat_col = "category" if "category" in cols else "NULL"
    rows = db.execute(
        # 검증(verify.py)을 통과한 ready 만 발행한다.
        f"""SELECT id, topic, keyword, body_md, title, {cat_col} FROM articles
            WHERE status = 'ready' ORDER BY id LIMIT ?""",
        (args.n,),
    ).fetchall()
    today = time.strftime("%Y-%m-%d")
    taken = {p.stem for p in POSTS_DIR.glob("*.md")}
    published = 0
    for aid, topic, keyword, body, stored_title, stored_cat in rows:
        title, rest = strip_title(body)
        # 롱테일 생성분은 본문에 h1 이 없고 title 컬럼에 SEO 제목이 들어 있다.
        title = title or stored_title or topic
        desc = description_of(rest).replace('"', "'")
        cat = category_for(db, topic, stored_cat)
        slug_base = title.split("|")[0].strip() or keyword or title
        slug = unique_slug(slug_base, str(aid), taken)
        front = "\n".join([
            "---",
            f'title: "{title.replace(chr(34), chr(39))}"',
            f'description: "{desc}"',
            f"pubDate: {today}",
            f'category: "{cat}"',
            f'keyword: "{keyword or ""}"',
            "---",
            "",
        ])
        (POSTS_DIR / f"{slug}.md").write_text(front + rest + "\n")
        db.execute("UPDATE articles SET status='published' WHERE id=?", (aid,))
        published += 1
        if published <= 5:
            print(f"  [{cat}] {title}")
    db.commit()
    print(f"{published}편 발행 → {POSTS_DIR}")


if __name__ == "__main__":
    main()
