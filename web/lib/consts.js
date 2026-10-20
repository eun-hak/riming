// 서브도메인 운영: riming.plentyer.com (Vercel에 도메인 연결)
export const SITE_URL = 'https://riming.plentyer.com';
export const SITE_NAME = '리밍';
export const SITE_DESC = '생활 속 궁금증을 근거 있게 풀어주는 정보 사전';
// 여러 사이트가 같은 사서함(plentyer.comp@gmail.com)을 쓰므로, 받은편지함에서
// 어느 사이트에서 온 문의인지 바로 구분되도록 +riming 을 붙인다.
// Gmail 은 + 뒤를 무시하고 같은 사서함으로 배달하되, 받는사람(To) 에는 그대로 남는다.
// 제목 말머리는 보낸 사람이 지울 수 있지만 To 는 남으므로 둘을 함께 쓴다.
export const CONTACT_EMAIL = 'plentyer.comp+riming@gmail.com';
export const LAUNCH_DATE = '2026-07-30'; // 정책 페이지 시행일

/** 사이트 말머리가 붙은 mailto 링크. 평문 링크로 눌러도 출처가 남는다. */
export function mailtoHref(subject = '문의') {
  const s = encodeURIComponent(`[${SITE_NAME}] ${subject}`);
  return `mailto:${CONTACT_EMAIL}?subject=${s}`;
}
