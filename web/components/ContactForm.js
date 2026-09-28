'use client';

import { useState } from 'react';
import { CONTACT_EMAIL } from '../lib/consts.js';

// 별도 메일 서버 없이 동작하는 문의 경로.
// 작성한 내용을 mailto 로 넘겨 방문자의 메일 앱에서 실제로 발송되게 한다.
// (서버 전송으로 바꾸려면 /api/contact 라우트를 만들고 handleSubmit 에서 fetch 하면 된다)
const CATEGORIES = ['오류 제보', '주제 제안', '제휴·광고', '개인정보 문의', '기타'];

export default function ContactForm() {
  const [opened, setOpened] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const subject = `[리밍 문의/${f.get('category')}] ${f.get('subject')}`;
    const body = [
      `이름: ${f.get('name')}`,
      `답변받을 이메일: ${f.get('email')}`,
      `문의 유형: ${f.get('category')}`,
      '',
      f.get('message'),
    ].join('\n');
    window.location.href = `mailto:${CONTACT_EMAIL}`
      + `?subject=${encodeURIComponent(subject)}`
      + `&body=${encodeURIComponent(body)}`;
    setOpened(true);
  }

  return (
    <>
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
        <button type="submit">메일 앱으로 문의 작성</button>
      </form>
      {opened && (
        <p className="form-note" role="status">
          메일 앱이 열리지 않았다면 아래 주소로 직접 보내주세요.
        </p>
      )}
      <p className="form-note">
        메일 앱을 쓰지 않으신다면{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        {' '}로 바로 보내주셔도 됩니다.
      </p>
    </>
  );
}
