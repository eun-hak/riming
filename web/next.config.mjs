/** @type {import('next').NextConfig} */
const nextConfig = {
  // 정적 export(output: 'export')를 쓰지 않는다. 글 1.1만 편을 매 배포마다 전부
  // 구우면 배포 1회가 960MB 라 Vercel 배포 스토리지(10GB)를 며칠 만에 채웠다.
  // 최근 글만 빌드 때 굽고 나머지는 첫 방문 때 렌더해 캐시한다(ISR).
  trailingSlash: true,
  // 방문 시 렌더되는 글 페이지 함수에만 색인과 gzip 본문을 싣는다.
  outputFileTracingIncludes: {
    '/posts/[slug]': ['./content/index.json', './content/gz/**/*'],
  },
  // 마크다운 원본(97MB)은 런타임에 쓰지 않으므로 어떤 함수에도 싣지 않는다.
  outputFileTracingExcludes: {
    '/**/*': ['./content/posts/**/*'],
  },
};

export default nextConfig;
