import { SITE_NAME, CONTACT_EMAIL, LAUNCH_DATE } from '../../lib/consts.js';

export const metadata = {
  title: '이용약관',
  description: `${SITE_NAME}의 이용약관입니다.`,
  robots: { index: false },
};

export default function TermsPage() {
  return (
    <div className="doc">
      <h1 className="doc-title">이용약관</h1>
      <div className="doc-body">
        <h2>제1조 (목적)</h2>
        <p>
          본 약관은 {SITE_NAME}(이하 &quot;사이트&quot;)이 제공하는 정보 서비스의
          이용 조건과 책임 사항을 규정함을 목적으로 합니다.
        </p>

        <h2>제2조 (서비스의 내용)</h2>
        <p>
          사이트는 생활 정보를 문서 형태로 정리해 무료로 제공합니다. 사이트는
          서비스의 내용을 사전 고지 없이 추가·변경·중단할 수 있습니다.
        </p>

        <h2>제3조 (정보의 성격과 면책)</h2>
        <ul>
          <li>
            사이트의 모든 콘텐츠는 <strong>일반적인 정보 제공 목적</strong>으로
            작성되었으며, 법률·세무·의료 등 전문가의 상담을 대체하지 않습니다.
          </li>
          <li>
            수수료·기한·법령 등은 변경될 수 있으며, 사이트는 정보의 완전성·최신성을
            보증하지 않습니다. 중요한 결정은 반드시 관계 기관의 공식 정보를
            확인한 후 진행하시기 바랍니다.
          </li>
          <li>
            사이트가 제공한 정보의 이용으로 발생한 손해에 대해 사이트는 법령이
            허용하는 범위 내에서 책임을 지지 않습니다.
          </li>
        </ul>

        <h2>제4조 (저작권)</h2>
        <ul>
          <li>사이트에 게시된 콘텐츠의 저작권은 사이트에 있습니다.</li>
          <li>
            사전 동의 없이 콘텐츠를 복제·배포·2차 가공하여 상업적으로 이용할 수
            없습니다. 출처를 명시한 인용과 링크 공유는 자유롭게 가능합니다.
          </li>
        </ul>

        <h2>제5조 (광고)</h2>
        <p>
          사이트는 무료 서비스 유지를 위해 제3자 광고(Google AdSense 등)를 게재할
          수 있습니다. 광고를 통한 거래는 이용자와 광고주 간의 문제이며 사이트는
          이에 관여하지 않습니다.
        </p>

        <h2>제6조 (문의)</h2>
        <p>
          약관에 대한 문의: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
        <p className="meta">시행일: {LAUNCH_DATE}</p>
      </div>
    </div>
  );
}
