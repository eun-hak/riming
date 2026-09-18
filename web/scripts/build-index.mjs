// 빌드 전 단계: 글 메타데이터 색인과 편별 gzip 본문을 만든다.
//
// ISR 전환 후 글 페이지는 방문 시 서버리스 함수에서 렌더된다. 이때
//  - 사이드바·관련글·목록에는 전체 글의 '메타데이터'만 필요하고
//  - 본문은 요청된 1편만 필요하다.
// 마크다운 1.1만 편(97MB)을 매번 전부 파싱하면 콜드스타트마다 수 초의 CPU를
// 쓰고, 원본을 함수에 그대로 실으면 함수 용량 한도(250MB)도 금방 찬다.
// 그래서 메타데이터는 JSON 하나로, 본문은 편별 gzip 으로 미리 만들어 둔다.
import fs from 'fs';
import path from 'path';
import zlib from 'zlib';
import matter from 'gray-matter';

const ROOT = process.cwd();
const SRC = path.join(ROOT, 'content', 'posts');
const GZ = path.join(ROOT, 'content', 'gz');
const INDEX = path.join(ROOT, 'content', 'index.json');

fs.rmSync(GZ, { recursive: true, force: true });
fs.mkdirSync(GZ, { recursive: true });

const posts = [];
for (const file of fs.readdirSync(SRC)) {
  if (!file.endsWith('.md')) continue;
  const raw = fs.readFileSync(path.join(SRC, file));
  const { data } = matter(raw.toString('utf8'));
  const slug = file.slice(0, -3);
  posts.push({
    slug,
    title: data.title ?? slug,
    description: data.description ?? '',
    pubDate: new Date(data.pubDate ?? Date.now()).toISOString().slice(0, 10),
    category: data.category ?? '생활',
    keyword: data.keyword ?? '',
  });
  fs.writeFileSync(path.join(GZ, `${slug}.md.gz`), zlib.gzipSync(raw, { level: 9 }));
}
// 같은 날 발행분이 수백 편이라 slug 로 동점을 풀어 순서를 고정한다
posts.sort((a, b) =>
  a.pubDate === b.pubDate ? a.slug.localeCompare(b.slug) : (a.pubDate < b.pubDate ? 1 : -1));
fs.writeFileSync(INDEX, JSON.stringify(posts));
console.log(`색인 ${posts.length}편 → content/index.json, 본문 gzip → content/gz/`);
