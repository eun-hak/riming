import { getAllPosts } from '../../lib/posts.js';
import { SITE_URL, SITE_NAME, SITE_DESC } from '../../lib/consts.js';

export const dynamic = 'force-static';

const esc = (s = '') =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

export async function GET() {
  // 네이버 서치어드바이저는 RSS를 사이트맵과 별개 발견 채널로 사용한다 (최근분 위주).
  const posts = getAllPosts().slice(0, 100);
  const items = posts.map((p) => {
    const url = `${SITE_URL}/posts/${encodeURIComponent(p.slug)}/`;
    return `    <item>
      <title>${esc(p.title)}</title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <description>${esc(p.description)}</description>
      <category>${esc(p.category)}</category>
      <pubDate>${new Date(`${p.pubDate}T09:00:00+09:00`).toUTCString()}</pubDate>
    </item>`;
  }).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${esc(SITE_NAME)}</title>
    <link>${SITE_URL}</link>
    <description>${esc(SITE_DESC)}</description>
    <language>ko</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/rss.xml" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' },
  });
}
