import { SITE_NAME, CONTACT_EMAIL, LAUNCH_DATE } from '../../lib/consts.js';

export const metadata = {
  title: '개인정보처리방침',
  description: `${SITE_NAME}의 개인정보처리방침입니다.`,
  robots: { index: false },
};

export default function PrivacyPage() {
  return (
    <div className="doc">
      <h1 className="doc-title">개인정보처리방침</h1>
      <div className="doc-body">
        <p>
          {SITE_NAME}(이하 &quot;사이트&quot;)은 이용자의 개인정보를 중요하게
          생각하며, 「개인정보 보호법」 등 관련 법령을 준수합니다.
        </p>

        <h2>1. 수집하는 개인정보</h2>
        <p>
          사이트는 회원가입 없이 이용할 수 있으며, 이용자로부터 직접 개인정보를
          수집하지 않습니다. 다만 아래 정보가 서비스 이용 과정에서 자동으로
          생성·수집될 수 있습니다.
        </p>
        <ul>
          <li>방문 기록, 접속 로그, 쿠키, 접속 기기 정보(브라우저 종류, OS)</li>
          <li>이메일 문의 시: 보내주신 이메일 주소와 문의 내용</li>
        </ul>

        <h2>2. 쿠키 및 광고 서비스</h2>
        <p>
          사이트는 서비스 개선과 광고 제공을 위해 다음 제3자 서비스를 사용할 수
          있으며, 이 과정에서 쿠키가 사용될 수 있습니다.
        </p>
        <ul>
          <li>
            <strong>Google Analytics</strong> — 방문 통계 분석. 수집된 정보는
            통계 목적으로만 사용됩니다.
          </li>
          <li>
            <strong>Google AdSense</strong> — 맞춤형 광고 제공. Google은 광고
            쿠키를 사용해 이용자의 이전 방문 기록에 기반한 광고를 게재할 수
            있습니다. 이용자는{' '}
            <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer">
              Google 광고 설정
            </a>
            에서 맞춤 광고를 해제할 수 있습니다.
          </li>
        </ul>
        <p>
          쿠키 수집을 원하지 않는 경우 브라우저 설정에서 쿠키 저장을 거부할 수
          있습니다. 다만 일부 기능 이용에 제한이 있을 수 있습니다.
        </p>

        <h2>3. 개인정보의 보유 및 파기</h2>
        <p>
          이메일 문의로 수집된 정보는 문의 처리 완료 후 지체 없이 파기합니다.
          자동 수집 정보는 각 제3자 서비스의 정책에 따라 처리됩니다.
        </p>

        <h2>4. 개인정보의 제3자 제공</h2>
        <p>
          사이트는 이용자의 개인정보를 외부에 판매하거나 제공하지 않습니다. 단,
          법령에 따른 요청이 있는 경우는 예외로 합니다.
        </p>

        <h2>5. 개인정보 보호책임자 및 문의</h2>
        <p>
          개인정보 관련 문의:{' '}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>

        <h2>6. 고지 의무</h2>
        <p>
          본 방침이 변경되는 경우 사이트 공지를 통해 안내합니다.
        </p>
        <p className="meta">시행일: {LAUNCH_DATE}</p>
      </div>
    </div>
  );
}
