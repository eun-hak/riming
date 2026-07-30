export const PER_PAGE = 30;

export function pageCount(total) {
  return Math.max(1, Math.ceil(total / PER_PAGE));
}

export function slice(posts, page) {
  return posts.slice((page - 1) * PER_PAGE, page * PER_PAGE);
}

export function pagerHref(category, n) {
  return n === 1 ? `/category/${category}/` : `/category/${category}/p/${n}/`;
}
