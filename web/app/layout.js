import Link from 'next/link';
import Script from 'next/script';
import { SITE_NAME, SITE_DESC, SITE_URL } from '../lib/consts.js';
import { getAllPosts, getCategories } from '../lib/posts.js';
import './globals.css';

const GA_ID = 'G-FWP892TKRV';

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME} — ${SITE_DESC}`, template: `%s | ${SITE_NAME}` },
  description: SITE_DESC,
  openGraph: {
    siteName: SITE_NAME,
    locale: 'ko_KR',
    type: 'website',
    images: [{ url: '/og.png', width: 1200, height: 630, alt: SITE_NAME }],
  },
  twitter: {
    card: 'summary_large_image',
  },
  alternates: {
    types: { 'application/rss+xml': `${SITE_URL}/rss.xml` },
  },
  verification: {
    google: 'nGLC6wqeingyxdWpDtTR9DKlBw7TNDT9A8_l8PrHWt0',
    other: {
      'naver-site-verification': 'f9f942680d91d430826dae257b3824eaf1652c8e',
    },
  },
};

function Sidebar() {
  const posts = getAllPosts();
  const categories = getCategories();
  return (
    <aside className="sidebar">
      <div className="widget">
        <div className="widget-head">최신 문서</div>
        <ol>
          {posts.slice(0, 10).map((p, i) => (
            <li key={p.slug}>
              <Link href={`/posts/${p.slug}/`}>
                <span className="rank">{i + 1}</span>
                <span className="w-title">{p.title}</span>
              </Link>
            </li>
          ))}
        </ol>
      </div>
      <div className="widget">
        <div className="widget-head">카테고리</div>
        <ul>
          {categories.map((c) => (
            <li key={c}>
              <Link href={`/category/${c}/`}>
                <span className="w-title">{c}</span>
                <span className="w-cnt">
                  {posts.filter((p) => p.category === c).length}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export default function RootLayout({ children }) {
  const categories = getCategories();
  return (
    <html lang="ko">
      <body>
        <Script
          src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
          strategy="afterInteractive"
        />
        <Script id="ga-init" strategy="afterInteractive">
          {`window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${GA_ID}');`}
        </Script>
        <header className="site-header">
          <div className="header-inner">
            <Link href="/" className="brand">
              {SITE_NAME}<span className="brand-dot">.</span>
            </Link>
            <span className="tagline">{SITE_DESC}</span>
          </div>
          <nav className="cat-nav" aria-label="카테고리">
            <div className="cat-nav-inner">
              <Link href="/">전체</Link>
              {categories.map((c) => (
                <Link key={c} href={`/category/${c}/`}>{c}</Link>
              ))}
            </div>
          </nav>
        </header>
        <div className="wrap">
          <div className="content">{children}</div>
          <Sidebar />
        </div>
        <footer className="site-footer">
          <div className="footer-inner">
            <nav className="footer-nav" aria-label="사이트 정보">
              <Link href="/about/">소개</Link>
              <Link href="/contact/">문의하기</Link>
              <Link href="/privacy/">개인정보처리방침</Link>
              <Link href="/terms/">이용약관</Link>
            </nav>
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
