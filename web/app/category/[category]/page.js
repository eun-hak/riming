import Link from 'next/link';
import { getAllPosts, getCategories } from '../../../lib/posts.js';

export function generateStaticParams() {
  return getCategories().map((category) => ({ category }));
}

export async function generateMetadata({ params }) {
  const { category } = await params;
  const name = decodeURIComponent(category);
  return { title: `${name} 글 모음`, description: `${name} 관련 생활 정보 모음` };
}

export default async function CategoryPage({ params }) {
  const { category } = await params;
  const name = decodeURIComponent(category);
  const posts = getAllPosts().filter((p) => p.category === name);
  return (
    <>
      <h1>{name}</h1>
      <ul className="post-list">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link href={`/posts/${post.slug}/`}>{post.title}</Link>
            <p>{post.description}</p>
            <span className="meta">{post.pubDate}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
