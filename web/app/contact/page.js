import { SITE_NAME, CONTACT_EMAIL } from '../../lib/consts.js';

export const metadata = {
  title: '문의하기',
  description: `${SITE_NAME}에 오류 제보, 제휴 등 문의를 보내는 방법을 안내합니다.`,
};

export default function ContactPage() {
  return (
    <div className="doc">
      <h1 className="doc-title">문의하기</h1>
      <div className="doc-body">
        <p>
          {SITE_NAME}에 대한 모든 문의는 아래 이메일로 받고 있습니다. 보통
          영업일 기준 2~3일 내에 답변드립니다.
        </p>
        <p style={{ fontSize: '1.15rem' }}>
          📮 <a href={`mailto:${CONTACT_EMAIL}`}><strong>{CONTACT_EMAIL}</strong></a>
        </p>
        <h2>이런 문의를 환영합니다</h2>
        <ul>
          <li>
            <strong>오류 제보</strong> — 문서 내용 중 잘못되었거나 바뀐 정보를
            알려주시면 확인 후 신속히 수정합니다. 해당 문서 링크를 함께
            보내주시면 처리가 빨라집니다.
          </li>
          <li><strong>주제 제안</strong> — 다뤄줬으면 하는 생활 궁금증을 제안해주세요.</li>
          <li><strong>제휴·광고 문의</strong></li>
          <li><strong>개인정보 관련 문의</strong></li>
        </ul>
        <p className="meta">
          * 개별 상황에 대한 법률·세무·의료 상담은 제공하지 않습니다. 해당
          분야 전문가 또는 관계 기관에 문의해주세요.
        </p>
      </div>
    </div>
  );
}
