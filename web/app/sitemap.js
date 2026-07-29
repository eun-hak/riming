import { getAllPosts, getCategories } from '../lib/posts.js';
import { SITE_URL } from '../lib/consts.js';

export const dynamic = 'force-static';

export default function sitemap() {
  const posts = getAllPosts().map((p) => ({
    url: `${SITE_URL}/posts/${encodeURIComponent(p.slug)}/`,
    lastModified: p.pubDate,
  }));
  const categories = getCategories().map((c) => ({
    url: `${SITE_URL}/category/${encodeURIComponent(c)}/`,
  }));
  return [{ url: `${SITE_URL}/` }, ...categories, ...posts];
}
