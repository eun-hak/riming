import Link from 'next/link';
import { getAllPosts, getCategories, decodeParam } from '../../../../../lib/posts.js';
import { pageCount, slice } from '../../../../../lib/paging.js';
import Pager from '../../../../../components/Pager.js';

export const dynamicParams = false;

export function generateStaticParams() {
  const posts = getAllPosts();
  const params = [];
  for (const category of getCategories()) {
    const total = pageCount(posts.filter((p) => p.category === category).length);
    for (let n = 2; n <= total; n += 1) params.push({ category, n: String(n) });
  }
  return params;
}

export async function generateMetadata({ params }) {
  const { category, n } = await params;
  const name = decodeParam(category);
  const page = Number(decodeParam(n)) || 1;
  return {
    title: `${name} 문서 모음 (${page}페이지)`,
    description: `${name} 관련 생활 정보 문서 ${page}페이지입니다.`,
    // 1페이지 폴백은 본 페이지(/category/x/)를 정본으로 지정해 중복 색인 방지
    ...(page === 1
      ? { alternates: { canonical: `/category/${encodeURIComponent(name)}/` } }
      : {}),
  };
}

export default async function CategoryPagedPage({ params }) {
  const { category, n } = await params;
  const name = decodeParam(category);
  const page = Number(decodeParam(n)) || 1;
  const posts = getAllPosts().filter((p) => p.category === name);
  const total = pageCount(posts.length);
  return (
    <section className="box">
      <div className="box-head">
        <h1>{name}</h1>
        <span className="more">{posts.length}개 문서 · {page}/{total}페이지</span>
      </div>
      <ul className="board">
        {slice(posts, page).map((post) => (
          <li key={post.slug}>
            <Link className="title" href={`/posts/${post.slug}/`}>{post.title}</Link>
            <span className="date">{post.pubDate.slice(5)}</span>
          </li>
        ))}
      </ul>
      <Pager category={name} current={page} total={total} />
    </section>
  );
}
