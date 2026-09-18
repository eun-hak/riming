import { getAllPosts, getCategories } from '../../lib/posts.js';
import { SITE_URL } from '../../lib/consts.js';

export const dynamic = 'force-static';

// 브라우저로 열면 /sitemap.xsl 이 표로 보여 주도록 스타일시트 선언을 넣는다(봇은 무시).
// 정적 export 시절엔 빌드 뒤 out/sitemap.xml 을 후처리했는데, ISR 전환으로
// out/ 이 없어져 여기서 직접 만든다.
export function GET() {
  const urls = [
    `  <url><loc>${SITE_URL}/</loc></url>`,
    ...getCategories().map((c) =>
      `  <url><loc>${SITE_URL}/category/${encodeURIComponent(c)}/</loc></url>`),
    ...getAllPosts().map((p) =>
      `  <url><loc>${SITE_URL}/posts/${encodeURIComponent(p.slug)}/</loc><lastmod>${p.pubDate}</lastmod></url>`),
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>
`;
  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
