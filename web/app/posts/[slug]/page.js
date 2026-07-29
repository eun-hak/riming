import Link from 'next/link';
import { getAllPosts, getPost, renderMarkdown } from '../../../lib/posts.js';

export function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const post = getPost(decodeURIComponent(slug));
  if (!post) return {};
  return { title: post.title, description: post.description };
}

export default async function PostPage({ params }) {
  const { slug } = await params;
  const post = getPost(decodeURIComponent(slug));
  if (!post) return null;
  const html = await renderMarkdown(post.content);
  return (
    <article>
      <p>
        <Link className="cat" href={`/category/${post.category}/`}>{post.category}</Link>
        <span className="meta">{post.pubDate}</span>
      </p>
      <h1>{post.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </article>
  );
}
