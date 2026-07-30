import Link from 'next/link';
import { getAllPosts, getCategories } from '../lib/posts.js';
import { SITE_NAME, SITE_DESC } from '../lib/consts.js';

export default function Home() {
  const posts = getAllPosts();
  const categories = getCategories();
  const countBy = Object.fromEntries(
    categories.map((c) => [c, posts.filter((p) => p.category === c).length])
  );
  return (
    <>
      <div className="home-intro">
        <h1>{SITE_NAME}</h1>
        <p>{SITE_DESC} · 총 {posts.length}개 문서</p>
      </div>

      <div className="cat-grid">
        {categories.map((c) => (
          <Link key={c} className="cat-card" href={`/category/${c}/`}>
            {c}
            <span className="cnt">{countBy[c]}개 문서</span>
          </Link>
        ))}
      </div>

      <h2 className="section-title">최신 문서</h2>
      <ul className="post-list">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link className="title" href={`/posts/${post.slug}/`}>{post.title}</Link>
            <p>{post.description}</p>
            <span className="meta">{post.category} · {post.pubDate}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
