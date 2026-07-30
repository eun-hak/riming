// 빌드 후 out/sitemap.xml에 XSL 스타일시트 선언을 삽입한다.
// 검색엔진 봇은 무시하고, 브라우저로 열면 사람이 읽기 좋은 표로 렌더링된다.
import fs from 'fs';

const FILE = 'out/sitemap.xml';
const PI = '<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>';

let xml = fs.readFileSync(FILE, 'utf8');
if (!xml.includes('sitemap.xsl')) {
  xml = xml.replace(/(<\?xml[^?]*\?>)/, `$1\n${PI}`);
  fs.writeFileSync(FILE, xml);
  console.log('sitemap.xml: XSL 스타일 적용');
}
