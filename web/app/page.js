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
              <a className="more" href={`/category/${c}/`}>더보기 ›</a>
            </div>
            <ul className="board">
              {catPosts.map((post) => (
                <li key={post.slug}>
                  <a className="title" href={`/posts/${post.slug}/`}>{post.title}</a>
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
