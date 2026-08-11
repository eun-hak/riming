import { SITE_URL } from '../lib/consts.js';

export const dynamic = 'force-static';

export default function robots() {
  return {
    // urls.txt 는 수집요청 크론이 가져가는 목록 파일이라 색인 대상이 아니다
    rules: [{ userAgent: '*', allow: '/', disallow: '/urls.txt' }],
    sitemap: [`${SITE_URL}/sitemap.xml`, `${SITE_URL}/rss.xml`],
  };
}
