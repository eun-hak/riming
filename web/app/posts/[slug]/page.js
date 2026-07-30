import Link from 'next/link';
import {
  getAllPosts, getPost, getRelated, renderMarkdown, extractFaq, decodeParam,
} from '../../../lib/posts.js';
import { SITE_NAME, SITE_URL } from '../../../lib/consts.js';

export function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: encodeURIComponent(post.slug) }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const post = getPost(decodeParam(slug));
  if (!post) return {};
  const url = `${SITE_URL}/posts/${encodeURIComponent(post.slug)}/`;
  return {
    title: post.title,
    description: post.description,
    keywords: post.keyword ? [post.keyword, post.category] : [post.category],
    alternates: { canonical: url },
    openGraph: {
      title: post.title,
      description: post.description,
      url,
      type: 'article',
      publishedTime: post.pubDate,
      images: ['/opengraph-image'],
    },
  };
}

function Toc({ toc }) {
  if (toc.length < 3) return null;
  const items = [];
  let current = null;
  for (const h of toc) {
    if (h.level === 2) {
      current = { ...h, children: [] };
      items.push(current);
    } else if (current) {
      current.children.push(h);
    }
  }
  return (
    <nav className="toc" aria-label="목차">
      <div className="toc-title">목차</div>
      <ol>
        {items.map((h) => (
          <li key={h.id}>
            <a href={`#${h.id}`}>{h.text}</a>
            {h.children.length > 0 && (
              <ol>
                {h.children.map((c) => (
                  <li key={c.id}><a href={`#${c.id}`}>{c.text}</a></li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export default async function PostPage({ params }) {
  const { slug } = await params;
  const post = getPost(decodeParam(slug));
  if (!post) return null;
  const { html, toc } = await renderMarkdown(post.content);
  const related = getRelated(post);
  const faqs = extractFaq(post.content);
  const url = `${SITE_URL}/posts/${encodeURIComponent(post.slug)}/`;

  const jsonLd = [
    {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: post.title,
      description: post.description,
      datePublished: post.pubDate,
      mainEntityOfPage: url,
      publisher: { '@type': 'Organization', name: SITE_NAME },
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: '홈', item: SITE_URL },
        {
          '@type': 'ListItem', position: 2, name: post.category,
          item: `${SITE_URL}/category/${encodeURIComponent(post.category)}/`,
        },
        { '@type': 'ListItem', position: 3, name: post.title, item: url },
      ],
    },
    ...(faqs.length >= 2
      ? [{
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: faqs.map((f) => ({
            '@type': 'Question',
            name: f.q,
            acceptedAnswer: { '@type': 'Answer', text: f.a },
          })),
        }]
      : []),
  ];

  return (
    <div className="doc">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <nav className="breadcrumb" aria-label="현재 위치">
        <Link href="/">홈</Link>
        <span className="sep">›</span>
        <Link href={`/category/${post.category}/`}>{post.category}</Link>
        <span className="sep">›</span>
        <span>{post.title}</span>
      </nav>
      <article>
        <h1 className="doc-title">{post.title}</h1>
        <div className="doc-meta">
          <Link className="chip" href={`/category/${post.category}/`}>{post.category}</Link>
          <span>최종 업데이트 {post.pubDate}</span>
        </div>
        <Toc toc={toc} />
        <div className="doc-body" dangerouslySetInnerHTML={{ __html: html }} />
      </article>
      {related.length > 0 && (
        <aside className="related">
          <h2>함께 보면 좋은 문서</h2>
          <ul>
            {related.map((r) => (
              <li key={r.slug}>
                <Link href={`/posts/${r.slug}/`}>{r.title}</Link>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
