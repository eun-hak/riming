import Link from 'next/link';
import { pagerHref } from '../lib/paging.js';

export default function Pager({ category, current, total }) {
  if (total <= 1) return null;
  const pages = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <nav className="pager" aria-label="페이지 이동">
      {current > 1 && (
        <Link href={pagerHref(category, current - 1)}>‹ 이전</Link>
      )}
      {pages.map((n) =>
        n === current ? (
          <span key={n} className="cur">{n}</span>
        ) : (
          <Link key={n} href={pagerHref(category, n)}>{n}</Link>
        )
      )}
      {current < total && (
        <Link href={pagerHref(category, current + 1)}>다음 ›</Link>
      )}
    </nav>
  );
}
