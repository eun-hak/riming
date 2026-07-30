import { ImageResponse } from 'next/og';
import fs from 'fs';
import path from 'path';
import { SITE_NAME, SITE_DESC } from '../lib/consts.js';

export const dynamic = 'force-static';
export const alt = `${SITE_NAME} — ${SITE_DESC}`;
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OgImage() {
  const font = fs.readFileSync(
    path.join(process.cwd(), 'assets', 'Pretendard-Bold.ttf')
  );
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #24406f 0%, #2b4d8c 60%, #3a63ad 100%)',
          color: '#ffffff',
          fontFamily: 'Pretendard',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline' }}>
          <div style={{ fontSize: 110, fontWeight: 700, letterSpacing: '-0.03em' }}>
            {SITE_NAME}
          </div>
          <div style={{ fontSize: 110, fontWeight: 700, color: '#7fb2ff' }}>.</div>
        </div>
        <div style={{ fontSize: 34, marginTop: 18, color: '#c9d8f2' }}>
          {SITE_DESC}
        </div>
      </div>
    ),
    { ...size, fonts: [{ name: 'Pretendard', data: font, weight: 700 }] }
  );
}
