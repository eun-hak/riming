import Link from 'next/link';
import { SITE_NAME, SITE_DESC, SITE_URL } from '../lib/consts.js';
import './globals.css';

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: SITE_DESC,
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        <header>
          <nav>
            <Link href="/" className="brand">{SITE_NAME}</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer>
          <p>
            © {new Date().getFullYear()} {SITE_NAME} · 본 사이트의 정보는
            참고용이며, 최신 기준은 각 기관 공식 채널에서 확인하세요.
          </p>
        </footer>
      </body>
    </html>
  );
}
