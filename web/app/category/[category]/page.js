import Link from 'next/link';
import { getAllPosts, getCategories } from '../../../lib/posts.js';

export function generateStaticParams() {
  return getCategories().map((category) => ({
    category: encodeURIComponent(category),
  }));
}

export async function generateMetadata({ params }) {
  const { category } = await params;
  const name = decodeURIComponent(category);
  return {
    title: `${name} 문서 모음`,
    description: `${name} 관련 생활 정보 문서를 모아 보여드립니다.`,
  };
}

export default async function CategoryPage({ params }) {
  const { category } = await params;
  const name = decodeURIComponent(category);
  const posts = getAllPosts().filter((p) => p.category === name);
  return (
    <div className="doc">
      <nav className="breadcrumb" aria-label="현재 위치">
        <Link href="/">홈</Link>
        <span className="sep">›</span>
        <span>{name}</span>
      </nav>
      <h1 className="doc-title">{name}</h1>
      <p className="meta">{posts.length}개 문서</p>
      <ul className="post-list">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link className="title" href={`/posts/${post.slug}/`}>{post.title}</Link>
            <p>{post.description}</p>
            <span className="meta">{post.pubDate}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
