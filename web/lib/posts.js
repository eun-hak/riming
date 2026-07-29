import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { remark } from 'remark';
import remarkGfm from 'remark-gfm';
import remarkHtml from 'remark-html';

const POSTS_DIR = path.join(process.cwd(), 'content', 'posts');

export function getAllPosts() {
  if (!fs.existsSync(POSTS_DIR)) return [];
  return fs
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
}

export function getPost(slug) {
  return getAllPosts().find((p) => p.slug === slug);
}

export function getCategories() {
  return [...new Set(getAllPosts().map((p) => p.category))];
}

export async function renderMarkdown(md) {
  const out = await remark().use(remarkGfm).use(remarkHtml).process(md);
  return out.toString();
}
