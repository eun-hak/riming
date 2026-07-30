<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html lang="ko">
      <head>
        <title>사이트맵 — 리밍</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <style>
          body { margin: 0; font-family: "Pretendard", "Apple SD Gothic Neo", sans-serif;
                 background: #f8f9fb; color: #222; }
          .head { background: #2b4d8c; color: #fff; padding: 1.1rem 1.5rem; }
          .head h1 { margin: 0; font-size: 1.15rem; }
          .head p { margin: 0.3rem 0 0; font-size: 0.82rem; color: #c9d8f2; }
          .wrap { max-width: 880px; margin: 1.2rem auto; padding: 0 1rem; }
          table { width: 100%; border-collapse: collapse; background: #fff;
                  border: 1px solid #dcdfe3; border-radius: 6px; overflow: hidden;
                  font-size: 0.9rem; }
          th { background: #f5f7fa; text-align: left; padding: 0.55rem 0.9rem;
               border-bottom: 1px solid #dcdfe3; }
          td { padding: 0.5rem 0.9rem; border-bottom: 1px solid #ececee; }
          tr:last-child td { border-bottom: 0; }
          a { color: #2969d1; text-decoration: none; }
          a:hover { text-decoration: underline; }
          .date { color: #888; white-space: nowrap; font-size: 0.82rem; }
        </style>
      </head>
      <body>
        <div class="head">
          <h1>리밍 사이트맵</h1>
          <p>검색엔진에 제공되는 페이지 목록입니다 · 총 <xsl:value-of select="count(sm:urlset/sm:url)"/>개 URL</p>
        </div>
        <div class="wrap">
          <table>
            <tr><th>페이지</th><th>최종 수정</th></tr>
            <xsl:for-each select="sm:urlset/sm:url">
              <tr>
                <td>
                  <a class="loc"><xsl:attribute name="href"><xsl:value-of select="sm:loc"/></xsl:attribute>
                    <xsl:value-of select="sm:loc"/>
                  </a>
                </td>
                <td class="date"><xsl:value-of select="sm:lastmod"/></td>
              </tr>
            </xsl:for-each>
          </table>
        </div>
        <script>
          document.querySelectorAll('a.loc').forEach(function (a) {
            try { a.textContent = decodeURIComponent(a.textContent); } catch (e) {}
          });
        </script>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
