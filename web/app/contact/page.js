import { SITE_NAME } from '../../lib/consts.js';
import ContactForm from '../../components/ContactForm.js';

export const metadata = {
  title: '문의하기',
  description: `${SITE_NAME}에 오류 제보, 주제 제안, 제휴 문의를 보낼 수 있습니다.`,
};

export default function ContactPage() {
  return (
    <div className="doc">
      <h1 className="doc-title">문의하기</h1>
      <div className="doc-body">
        <p>
          {SITE_NAME}에 대한 의견을 들려주세요. 오류 제보, 다뤄줬으면 하는 주제
          제안, 제휴 문의 모두 환영합니다. 보통 영업일 기준 2~3일 내에
          답변드립니다.
        </p>
        <ContactForm />
        <p className="meta" style={{ marginTop: '1.2rem' }}>
          * 개별 상황에 대한 법률·세무·의료 상담은 제공하지 않습니다. 해당
          분야 전문가 또는 관계 기관에 문의해주세요.
        </p>
      </div>
    </div>
  );
}
