import fs from 'fs';
import path from 'path';
import zlib from 'zlib';
import matter from 'gray-matter';
import { remark } from 'remark';
import remarkGfm from 'remark-gfm';
import remarkHtml from 'remark-html';

// 빌드 전 scripts/build-index.mjs 가 만든다. 목록·사이드바는 메타데이터 JSON만,
// 글 본문은 요청된 1편의 gzip 만 읽어 ISR 함수의 CPU·용량을 아낀다.
const CONTENT = path.join(process.cwd(), 'content');
const INDEX = path.join(CONTENT, 'index.json');
const GZ_DIR = path.join(CONTENT, 'gz');

let cache = null;
let bySlug = null;

/** 전체 글의 메타데이터 (본문 제외, 최신순) */
export function getAllPosts() {
  if (cache) return cache;
  cache = fs.existsSync(INDEX) ? JSON.parse(fs.readFileSync(INDEX, 'utf8')) : [];
  bySlug = new Map(cache.map((p) => [p.slug, p]));
  return cache;
}

/** 글 1편 (본문 포함). 색인에 있는 slug 만 읽어 URL 로 임의 경로를 여는 것을 막는다. */
export function getPost(slug) {
  getAllPosts();
  const meta = slug && bySlug.get(slug);
  if (!meta) return undefined;
  const file = path.join(GZ_DIR, `${slug}.md.gz`);
  if (!file.startsWith(GZ_DIR + path.sep) || !fs.existsSync(file)) return undefined;
  const { content } = matter(zlib.gunzipSync(fs.readFileSync(file)).toString('utf8'));
  return { ...meta, content };
}

/** dev/프로덕션에서 인코딩 횟수가 달라도 안전하게 원문으로 복원 */
export function decodeParam(value) {
  let prev = value;
  try {
    let cur = decodeURIComponent(value);
    while (cur !== prev) {
      prev = cur;
      cur = decodeURIComponent(cur);
    }
    return cur;
  } catch {
    return prev;
  }
}

export function getCategories() {
  return [...new Set(getAllPosts().map((p) => p.category))];
}

export function getRelated(post, limit = 5) {
  return getAllPosts()
    .filter((p) => p.category === post.category && p.slug !== post.slug)
    .slice(0, limit);
}

function headingId(text, used) {
  let id = text
    .trim()
    .replace(/[^\w가-힣\s-]/g, '')
    .replace(/\s+/g, '-')
    .toLowerCase() || 'section';
  while (used.has(id)) id += '-1';
  used.add(id);
  return id;
}

/** 마크다운 → { html, toc }. h2/h3에 앵커 id를 붙이고 목차를 추출한다. */
export async function renderMarkdown(md) {
  const raw = String(
    await remark().use(remarkGfm).use(remarkHtml).process(md)
  );
  const toc = [];
  const used = new Set();
  const html = raw.replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (m, lvl, inner) => {
    const text = inner.replace(/<[^>]+>/g, '').trim();
    const id = headingId(text, used);
    toc.push({ level: Number(lvl), text, id });
    return `<h${lvl} id="${id}">${inner}</h${lvl}>`;
  });
  return { html, toc };
}

/** "자주 묻는 질문" 섹션에서 Q/A 추출 (FAQPage 구조화 데이터용). */
export function extractFaq(md) {
  const idx = md.search(/#{2,4}\s*자주 묻는 질문/);
  if (idx === -1) return [];
  const lines = md.slice(idx).split('\n').slice(1);
  const faqs = [];
  let q = null;
  let a = [];
  const push = () => {
    if (q && a.length) faqs.push({ q, a: a.join(' ').trim() });
  };
  for (const line of lines) {
    const qm =
      line.match(/^\*\*Q[.)]?\s*(.+?)\*\*\s*$/) ||
      line.match(/^#{2,4}\s+(?:\d+[.)]\s*)?(.+)/);
    if (qm) {
      push();
      q = qm[1].replace(/\*\*/g, '').trim();
      a = [];
    } else if (q && line.trim()) {
      a.push(line.replace(/^A[.)]?\s*/, '').replace(/[*_#]/g, '').trim());
    }
  }
  push();
  return faqs.filter((f) => f.q.length > 5 && f.a.length > 10);
}
