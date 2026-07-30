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
    <section className="box">
      <div className="box-head">
        <h1>{name}</h1>
        <span className="more">{posts.length}개 문서</span>
      </div>
      <ul className="board">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link className="title" href={`/posts/${post.slug}/`}>{post.title}</Link>
            <span className="date">{post.pubDate.slice(5)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
