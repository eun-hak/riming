import Link from 'next/link';
import { getAllPosts, getCategories } from '../lib/posts.js';

export default function Home() {
  const posts = getAllPosts();
  const categories = getCategories();
  return (
    <>
      {categories.map((c) => {
        const catPosts = posts.filter((p) => p.category === c).slice(0, 5);
        if (!catPosts.length) return null;
        return (
          <section className="box" key={c}>
            <div className="box-head">
              <h2>{c}</h2>
              <Link className="more" href={`/category/${c}/`}>더보기 ›</Link>
            </div>
            <ul className="board">
              {catPosts.map((post) => (
                <li key={post.slug}>
                  <Link className="title" href={`/posts/${post.slug}/`}>{post.title}</Link>
                  <span className="date">{post.pubDate.slice(5)}</span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}
