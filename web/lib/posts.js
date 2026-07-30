import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { remark } from 'remark';
import remarkGfm from 'remark-gfm';
import remarkHtml from 'remark-html';

const POSTS_DIR = path.join(process.cwd(), 'content', 'posts');

// 빌드 시 페이지마다 전체 파일을 다시 읽지 않도록 모듈 캐시 (1만 편 규모 대비)
let cache = null;

export function getAllPosts() {
  if (cache) return cache;
  if (!fs.existsSync(POSTS_DIR)) return [];
  cache = fs
    .readdirSync(POSTS_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((file) => {
      const slug = file.replace(/\.md$/, '');
      const { data, content } = matter(
        fs.readFileSync(path.join(POSTS_DIR, file), 'utf8')
      );
      return {
        slug,
        title: data.title ?? slug,
        description: data.description ?? '',
        pubDate: new Date(data.pubDate ?? Date.now()).toISOString().slice(0, 10),
        category: data.category ?? '생활',
        keyword: data.keyword ?? '',
        content,
      };
    })
    .sort((a, b) => (a.pubDate < b.pubDate ? 1 : -1));
  return cache;
}

export function getPost(slug) {
  return getAllPosts().find((p) => p.slug === slug);
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
