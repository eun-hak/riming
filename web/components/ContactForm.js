'use client';

import { useState } from 'react';

// 실제 전송으로 전환하려면: Formspree 등에서 폼 생성 후 ENDPOINT에 URL을 넣고
// handleSubmit의 가짜 지연 부분을 fetch(ENDPOINT, ...) 호출로 교체하면 된다.
const ENDPOINT = null;

const CATEGORIES = ['오류 제보', '주제 제안', '제휴·광고', '개인정보 문의', '기타'];

export default function ContactForm() {
  const [status, setStatus] = useState('idle'); // idle | sending | done

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus('sending');
    await new Promise((r) => setTimeout(r, 900));
    setStatus('done');
  }

  if (status === 'done') {
    return (
      <div className="form-success" role="status">
        <div className="form-success-icon">✓</div>
        <h2>문의가 접수되었습니다</h2>
        <p>
          소중한 의견 감사합니다. 내용을 확인한 뒤 영업일 기준 2~3일 내에
          남겨주신 이메일로 답변드리겠습니다.
        </p>
      </div>
    );
  }

  return (
    <form className="contact-form" onSubmit={handleSubmit}>
      <div className="form-row-2">
        <label>
          이름 <span className="req">*</span>
          <input name="name" type="text" required placeholder="홍길동" />
        </label>
        <label>
          답변받을 이메일 <span className="req">*</span>
          <input name="email" type="email" required placeholder="you@example.com" />
        </label>
      </div>
      <label>
        문의 유형 <span className="req">*</span>
        <select name="category" required defaultValue="">
          <option value="" disabled>선택해주세요</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      <label>
        제목 <span className="req">*</span>
        <input name="subject" type="text" required placeholder="문의 제목을 입력해주세요" />
      </label>
      <label>
        내용 <span className="req">*</span>
        <textarea
          name="message"
          required
          rows={7}
          placeholder="문의 내용을 자세히 적어주세요. 오류 제보라면 해당 문서 링크를 함께 남겨주시면 처리가 빨라집니다."
        />
      </label>
      <button type="submit" disabled={status === 'sending'}>
        {status === 'sending' ? '전송 중…' : '문의 보내기'}
      </button>
    </form>
  );
}
