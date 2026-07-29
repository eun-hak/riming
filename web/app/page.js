import Link from 'next/link';
import { getAllPosts, getCategories } from '../lib/posts.js';
import { SITE_NAME, SITE_DESC } from '../lib/consts.js';

export default function Home() {
  const posts = getAllPosts();
  const categories = getCategories();
  return (
    <>
      <h1>{SITE_NAME}</h1>
      <p className="meta">{SITE_DESC}</p>
      <p>
        {categories.map((c) => (
          <Link key={c} className="cat" href={`/category/${c}/`}>{c}</Link>
        ))}
      </p>
      <ul className="post-list">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link href={`/posts/${post.slug}/`}>{post.title}</Link>
            <p>{post.description}</p>
            <span className="meta">{post.category} · {post.pubDate}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
