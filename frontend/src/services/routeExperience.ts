import type { ExternalTicketLink, RecommendationSegment, SearchRequest, TicketProvider } from '../types';

const ANON_SESSION_KEY = 'layover_lens_anonymous_feedback_session';
const EXTERNAL_NOTICE_KEY = 'layover_lens_skip_external_ticket_notice';

export function getAnonymousFeedbackSessionId(): string {
  if (typeof window === 'undefined') return 'anon_server';
  const existing = window.localStorage.getItem(ANON_SESSION_KEY);
  if (existing) return existing;
  const id = `anon_${crypto.randomUUID()}`;
  window.localStorage.setItem(ANON_SESSION_KEY, id);
  return id;
}

export function shouldSkipExternalTicketNotice(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(EXTERNAL_NOTICE_KEY) === 'true';
}

export function setSkipExternalTicketNotice(skip: boolean): void {
  if (typeof window === 'undefined') return;
  if (skip) {
    window.localStorage.setItem(EXTERNAL_NOTICE_KEY, 'true');
  }
}

export function ticketProviderLabel(provider: TicketProvider): string {
  const labels: Record<TicketProvider, string> = {
    '12306': '12306',
    ctrip: 'Ctrip',
    fliggy: 'Fliggy',
    qunar: 'Qunar',
  };
  return labels[provider];
}

export function buildTicketLinks(segment: RecommendationSegment, request?: Partial<SearchRequest>): ExternalTicketLink[] {
  const from = encodeURIComponent(segment.from_city);
  const to = encodeURIComponent(segment.to_city);
  const date = encodeURIComponent(request?.travel_date || '');
  if (segment.recommended_transport_type === 'train') {
    return [{
      provider: '12306',
      label: '12306',
      url: `https://www.12306.cn/index/?from=${from}&to=${to}&date=${date}`,
    }];
  }
  return [
    {
      provider: 'ctrip',
      label: 'Ctrip',
      url: `https://flights.ctrip.com/online/channel/domestic?from=${from}&to=${to}&date=${date}`,
    },
    {
      provider: 'fliggy',
      label: 'Fliggy',
      url: `https://sjipiao.fliggy.com/?from=${from}&to=${to}&date=${date}`,
    },
    {
      provider: 'qunar',
      label: 'Qunar',
      url: `https://flight.qunar.com/?from=${from}&to=${to}&date=${date}`,
    },
  ];
}
