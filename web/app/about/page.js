import { SITE_NAME, CONTACT_EMAIL } from '../../lib/consts.js';

export const metadata = {
  title: '소개',
  description: `${SITE_NAME}이 어떤 사이트인지, 콘텐츠를 어떤 원칙으로 만드는지 소개합니다.`,
};

export default function AboutPage() {
  return (
    <div className="doc">
      <h1 className="doc-title">{SITE_NAME} 소개</h1>
      <div className="doc-body">
        <p>
          <strong>{SITE_NAME}</strong>은 일상에서 자주 마주치는 궁금증 —
          행정 절차, 자동차, IT·디지털, 생활 정보, 소비, 여행 — 을
          문서 형태로 정리해 제공하는 생활 정보 사이트입니다.
        </p>
        <h2>콘텐츠 원칙</h2>
        <ul>
          <li>
            <strong>수요 기반 주제 선정</strong> — 실제로 많은 분들이 궁금해하는
            질문을 데이터로 분석해 주제를 선정합니다.
          </li>
          <li>
            <strong>검색자가 원하는 답 우선</strong> — 서론 없이 핵심 답부터
            제시하고, 절차·조건·비용을 구조적으로 정리합니다.
          </li>
          <li>
            <strong>공식 출처 확인 안내</strong> — 수수료·기한 등 변동 가능한
            정보는 단정하지 않고, 반드시 공식 채널 확인을 함께 안내합니다.
          </li>
          <li>
            <strong>지속 업데이트</strong> — 제도나 기준이 바뀌면 문서를
            갱신합니다. 오류를 발견하시면 언제든 알려주세요.
          </li>
        </ul>
        <h2>정보 이용 시 유의사항</h2>
        <p>
          본 사이트의 모든 문서는 일반적인 정보 제공을 목적으로 하며, 법률·세무·
          의료 등 전문 상담을 대체하지 않습니다. 중요한 의사결정 전에는 반드시
          해당 분야 전문가 또는 관계 기관의 확인을 받으시기 바랍니다.
        </p>
        <h2>문의</h2>
        <p>
          내용 오류 제보, 제휴 등 모든 문의는{' '}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> 로 보내주세요.
        </p>
      </div>
    </div>
  );
}
