import Script from 'next/script';
import { SITE_NAME, SITE_DESC, SITE_URL } from '../lib/consts.js';
import { getAllPosts, getCategories } from '../lib/posts.js';
import './globals.css';

const GA_ID = 'G-FWP892TKRV';
const NAVER_WA = '2b17c85a35f5ea';
const ADSENSE_ID = 'pub-1410200096892996';

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
      'google-adsense-account': `ca-${ADSENSE_ID}`,
      'msvalidate.01': '112BB0292D8A2BCD2A6CA3E7C8C100B4',
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
              <a href={`/posts/${p.slug}/`}>
                <span className="rank">{i + 1}</span>
                <span className="w-title">{p.title}</span>
              </a>
            </li>
          ))}
        </ol>
      </div>
      <div className="widget">
        <div className="widget-head">카테고리</div>
        <ul>
          {categories.map((c) => (
            <li key={c}>
              <a href={`/category/${c}/`}>
                <span className="w-title">{c}</span>
                <span className="w-cnt">
                  {posts.filter((p) => p.category === c).length}
                </span>
              </a>
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
        {/* 네이버 애널리틱스 — wcslog.js 로드가 끝난 뒤 wcs_do() 를 호출해야 집계된다.
            원본 스니펫은 로드 전이면 조용히 건너뛰므로, 스크립트를 주입하고 onload 에서 호출한다. */}
        <Script id="naver-wcs" strategy="afterInteractive">
          {`window.wcs_add = window.wcs_add || {};
            window.wcs_add['wa'] = '${NAVER_WA}';
            (function(){
              var s = document.createElement('script');
              s.src = 'https://wcs.pstatic.net/wcslog.js';
              s.async = true;
              s.onload = function(){ if (window.wcs) { window.wcs_do(); } };
              document.head.appendChild(s);
            })();`}
        </Script>
        <header className="site-header">
          <div className="header-inner">
            <a href="/" className="brand">
              {SITE_NAME}<span className="brand-dot">.</span>
            </a>
            <span className="tagline">{SITE_DESC}</span>
          </div>
          <nav className="cat-nav" aria-label="카테고리">
            <div className="cat-nav-inner">
              <a href="/">전체</a>
              {categories.map((c) => (
                <a key={c} href={`/category/${c}/`}>{c}</a>
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
              <a href="/about/">소개</a>
              <a href="/contact/">문의하기</a>
              <a href="/privacy/">개인정보처리방침</a>
              <a href="/terms/">이용약관</a>
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
        {/* 애드센스 자동광고 — body 끝, hydration 이후 로드.
            게재 강도는 코드가 아니라 애드센스 콘솔에서 조절한다.
            목표: PV당 노출 3~4회 이하, CTR 2% 이하 (몽글은 8.3회·4.24%로 과밀) */}
        <Script
          async
          src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-${ADSENSE_ID}`}
          crossOrigin="anonymous"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
