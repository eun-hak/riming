import { pagerHref } from '../lib/paging.js';

export default function Pager({ category, current, total }) {
  if (total <= 1) return null;
  const pages = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <nav className="pager" aria-label="페이지 이동">
      {current > 1 && (
        <a href={pagerHref(category, current - 1)}>‹ 이전</a>
      )}
      {pages.map((n) =>
        n === current ? (
          <span key={n} className="cur">{n}</span>
        ) : (
          <a key={n} href={pagerHref(category, n)}>{n}</a>
        )
      )}
      {current < total && (
        <a href={pagerHref(category, current + 1)}>다음 ›</a>
      )}
    </nav>
  );
}
