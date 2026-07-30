import Link from 'next/link';
import { SITE_NAME, SITE_DESC, SITE_URL } from '../lib/consts.js';
import { getCategories } from '../lib/posts.js';
import './globals.css';

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME} — ${SITE_DESC}`, template: `%s | ${SITE_NAME}` },
  description: SITE_DESC,
  openGraph: {
    siteName: SITE_NAME,
    locale: 'ko_KR',
    type: 'website',
  },
};

export default function RootLayout({ children }) {
  const categories = getCategories();
  return (
    <html lang="ko">
      <body>
        <header className="site-header">
          <div className="header-inner">
            <Link href="/" className="brand">
              {SITE_NAME}<span className="brand-dot">.</span>
            </Link>
            <span className="tagline">{SITE_DESC}</span>
          </div>
          <nav className="cat-nav" aria-label="카테고리">
            <div className="cat-nav-inner">
              {categories.map((c) => (
                <Link key={c} href={`/category/${c}/`}>{c}</Link>
              ))}
            </div>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <div className="footer-inner">
            <p>
              <strong>{SITE_NAME}</strong>은 생활 속 궁금증을 문서 형태로
              정리하는 정보 사이트입니다.
            </p>
            <p className="fine">
              본 사이트의 정보는 참고용으로 제공되며 법적 효력이 없습니다.
              수수료·기한 등 세부 기준은 변경될 수 있으니 반드시 각 기관의
              공식 채널에서 최신 정보를 확인하세요. © {new Date().getFullYear()} {SITE_NAME}
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
