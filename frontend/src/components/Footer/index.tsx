import './Footer.css';
import { useState } from 'react';
import { useLocale, type Lang } from '../../context/LocaleContext';
import AnimatedModal from '../common/AnimatedModal';

type FooterPageKey =
  | 'helpCenter'
  | 'safety'
  | 'contact'
  | 'aboutApp'
  | 'news'
  | 'joinUs'
  | 'terms'
  | 'privacy'
  | 'cookie';

interface FooterPageContent {
  title: string;
  subtitle: string;
  sections: Array<{
    heading: string;
    body: string[];
  }>;
}

const footerPageContent: Record<Lang, Record<FooterPageKey, FooterPageContent>> = {
  zh: {
    helpCenter: {
      title: '帮助中心',
      subtitle: '快速了解如何使用中转助手完成路线搜索、筛选和收藏。',
      sections: [
        { heading: '路线搜索', body: ['输入出发地、目的地和日期后，系统会给出飞机、火车和混合换乘方案。', '你可以按价格、耗时、换乘次数或综合推荐进行排序。'] },
        { heading: '筛选与收藏', body: ['高级搜索支持换乘次数、交通方式、预算和中转城市等条件。', '点击路线卡片上的收藏按钮，可以把常用方案保存到收藏行程。'] },
      ],
    },
    safety: {
      title: '安全信息',
      subtitle: '我们优先保护账户、会话和搜索数据的安全。',
      sections: [
        { heading: '账户保护', body: ['登录会话使用服务端校验和 CSRF 防护。建议开启更长会话前确认设备安全。', '不要向他人透露验证码、密码或双重验证动态码。'] },
        { heading: '出行提示', body: ['路线结果用于规划参考，购票前请在航空公司、铁路或第三方平台确认实时价格、余票和规则。'] },
      ],
    },
    contact: {
      title: '联系我们',
      subtitle: '如果你遇到问题或希望反馈路线数据，可以通过以下方式联系。',
      sections: [
        { heading: '产品反馈', body: ['请在反馈中说明出发地、目的地、日期、截图和复现步骤，方便定位问题。'] },
        { heading: '商务与合作', body: ['如需数据合作、渠道合作或校园/企业试用，请附上机构名称和合作目标。'] },
      ],
    },
    aboutApp: {
      title: '关于中转助手',
      subtitle: '中转助手帮助用户比较城市间多交通方式组合路线。',
      sections: [
        { heading: '产品定位', body: ['项目聚合飞机、火车和换乘策略，帮助用户在价格、时间和换乘复杂度之间做权衡。'] },
        { heading: '当前能力', body: ['普通搜索提供结构化筛选；AI 搜索在开启后支持用自然语言表达出行需求。'] },
      ],
    },
    news: {
      title: '新闻动态',
      subtitle: '这里展示产品版本和能力更新。',
      sections: [
        { heading: '近期更新', body: ['移动端界面已完成响应式适配，支持搜索、收藏、AI 对话和设置弹窗。', '新增搜索栏滚动形态切换与顶部导航层级优化。'] },
        { heading: '后续计划', body: ['继续完善实时票价、外部平台跳转提示、AI 搜索工具调用和路线解释能力。'] },
      ],
    },
    joinUs: {
      title: '加入我们',
      subtitle: '欢迎对出行规划、前端体验和智能搜索感兴趣的人参与。',
      sections: [
        { heading: '我们关注', body: ['前端交互体验、路线规划算法、交通数据治理、AI 工具调用和产品设计。'] },
        { heading: '如何开始', body: ['请准备个人介绍、相关项目经历和希望参与的方向。'] },
      ],
    },
    terms: {
      title: '服务条款',
      subtitle: '使用中转助手即表示你理解并接受以下服务说明。',
      sections: [
        { heading: '服务范围', body: ['中转助手提供路线规划和信息整理服务，不直接售票，也不保证第三方平台价格、余票或班次实时有效。'] },
        { heading: '用户责任', body: ['你需要确保输入信息真实有效，并在购票、退改签、出行前自行确认官方规则。'] },
      ],
    },
    privacy: {
      title: '隐私政策',
      subtitle: '我们仅在实现搜索、账户和 AI 对话功能所需范围内处理数据。',
      sections: [
        { heading: 'AI 搜索数据', body: ['使用 AI 搜索时，你输入的出行需求和对话内容会发送至 DeepSeek，用于理解搜索条件并生成回复。'] },
        { heading: '账户数据', body: ['账户邮箱、用户 ID、设备信息和认证数据不会发送给 DeepSeek。AI 对话状态会加密保存，并按你的历史保留设置清理。'] },
      ],
    },
    cookie: {
      title: 'Cookie 设置',
      subtitle: 'Cookie 用于维持登录状态、语言偏好和安全校验。',
      sections: [
        { heading: '必要 Cookie', body: ['必要 Cookie 始终启用，用于登录会话、CSRF 防护和基础安全功能。'] },
        { heading: '偏好设置', body: ['语言、主题等偏好会保存在本地浏览器中，用于提升下次访问体验。当前版本未启用广告追踪 Cookie。'] },
      ],
    },
  },
  en: {
    helpCenter: {
      title: 'Help Center',
      subtitle: 'Learn how to search routes, refine results, and save favorites.',
      sections: [
        { heading: 'Route search', body: ['Enter origin, destination, and date to compare flight, train, and mixed-transfer options.', 'Sort results by price, duration, transfers, or balanced recommendation.'] },
        { heading: 'Filters and favorites', body: ['Advanced search supports transfer count, transport type, budget, and required layover cities.', 'Use the favorite button on a route card to save useful trips.'] },
      ],
    },
    safety: {
      title: 'Safety',
      subtitle: 'We prioritize account, session, and search-data safety.',
      sections: [
        { heading: 'Account protection', body: ['Sessions are protected with server validation and CSRF safeguards.', 'Never share verification codes, passwords, or authenticator codes.'] },
        { heading: 'Travel notice', body: ['Route results are planning references. Confirm realtime fares, availability, and rules before booking.'] },
      ],
    },
    contact: {
      title: 'Contact Us',
      subtitle: 'Send us product issues, data feedback, or partnership requests.',
      sections: [
        { heading: 'Product feedback', body: ['Include origin, destination, date, screenshots, and reproduction steps when reporting issues.'] },
        { heading: 'Partnerships', body: ['For data, channel, campus, or enterprise pilots, include your organization and goals.'] },
      ],
    },
    aboutApp: {
      title: 'About Layover Lens',
      subtitle: 'Layover Lens compares multi-modal city-to-city transfer routes.',
      sections: [
        { heading: 'Positioning', body: ['The product combines flights, trains, and transfer strategies to balance cost, time, and complexity.'] },
        { heading: 'Capabilities', body: ['Structured search supports precise filters. AI Search, when enabled, accepts natural-language travel requests.'] },
      ],
    },
    news: {
      title: 'News',
      subtitle: 'Product version and capability updates.',
      sections: [
        { heading: 'Recent updates', body: ['The mobile interface now supports responsive search, favorites, AI chat, and settings modals.', 'Search-bar morphing and navigation layering have been improved.'] },
        { heading: 'Next', body: ['We will continue improving realtime fares, external-link notices, AI tool use, and route explanations.'] },
      ],
    },
    joinUs: {
      title: 'Join Us',
      subtitle: 'For people interested in trip planning, frontend experience, and intelligent search.',
      sections: [
        { heading: 'Focus areas', body: ['Frontend interaction, route-planning algorithms, transport data, AI tool use, and product design.'] },
        { heading: 'How to start', body: ['Prepare a short introduction, relevant project experience, and the area you want to contribute to.'] },
      ],
    },
    terms: {
      title: 'Terms of Service',
      subtitle: 'By using Layover Lens, you understand and accept these service notes.',
      sections: [
        { heading: 'Service scope', body: ['Layover Lens provides route planning and information organization. It does not sell tickets or guarantee third-party fares, inventory, or schedules.'] },
        { heading: 'User responsibility', body: ['You are responsible for entering accurate information and confirming official booking, refund, and travel rules before departure.'] },
      ],
    },
    privacy: {
      title: 'Privacy Policy',
      subtitle: 'We process data only as needed for search, accounts, and AI conversation features.',
      sections: [
        { heading: 'AI Search data', body: ['When you use AI Search, your travel request and conversation are sent to DeepSeek to understand search conditions and generate responses.'] },
        { heading: 'Account data', body: ['Your account email, user ID, device information, and authentication data are not sent to DeepSeek. AI conversation state is encrypted and cleaned according to your history retention setting.'] },
      ],
    },
    cookie: {
      title: 'Cookie Settings',
      subtitle: 'Cookies keep sessions, language preferences, and security checks working.',
      sections: [
        { heading: 'Required cookies', body: ['Required cookies are always enabled for login sessions, CSRF protection, and core security.'] },
        { heading: 'Preferences', body: ['Language and theme preferences are stored locally in your browser. This version does not use advertising tracking cookies.'] },
      ],
    },
  },
};

export default function Footer() {
  const { lang, t } = useLocale();
  const [activePage, setActivePage] = useState<FooterPageKey | null>(null);
  const activeContent = activePage ? footerPageContent[lang][activePage] : null;

  const openPage = (page: FooterPageKey) => {
    setActivePage(page);
  };

  const closePage = () => {
    setActivePage(null);
  };

  return (
    <>
      <footer className="footer">
        <div className="container">
        <div className="footer__grid">
          <div>
            <div className="footer__col-title">{t('footer.support')}</div>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('helpCenter')}>{t('footer.helpCenter')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('safety')}>{t('footer.safety')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('contact')}>{t('footer.contact')}</button>
          </div>
          <div>
            <div className="footer__col-title">{t('footer.about')}</div>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('aboutApp')}>{t('footer.aboutApp')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('news')}>{t('footer.news')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('joinUs')}>{t('footer.joinUs')}</button>
          </div>
          <div>
            <div className="footer__col-title">{t('footer.legal')}</div>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('terms')}>{t('footer.terms')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('privacy')}>{t('footer.privacy')}</button>
            <button type="button" className="footer__link footer__link--button" onClick={() => openPage('cookie')}>{t('footer.cookie')}</button>
          </div>
        </div>
        <div className="footer__legal">
          <div className="footer__copyright">{t('footer.copyright')}</div>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--muted)' }}>{lang === 'en' ? 'English (US)' : '简体中文 (CN)'}</span>
            <span style={{ fontSize: '13px', color: 'var(--muted)' }}>¥ CNY</span>
          </div>
        </div>
        </div>
      </footer>
      <AnimatedModal
        isOpen={activeContent !== null}
        overlayClassName="footer-privacy__overlay"
        dialogClassName="footer-privacy__dialog"
        ariaLabel={activeContent?.title || t('footer.privacyTitle')}
        onClose={closePage}
      >
        {activeContent ? (
          <>
            <div className="footer-info__head">
              <div>
                <h2>{activeContent.title}</h2>
                <p className="footer-info__subtitle">{activeContent.subtitle}</p>
              </div>
              <button type="button" className="footer-info__close" onClick={closePage} aria-label={lang === 'en' ? 'Close' : '关闭'}>
                ×
              </button>
            </div>
            <div className="footer-info__body">
              {activeContent.sections.map((section) => (
                <section key={section.heading} className="footer-info__section">
                  <h3>{section.heading}</h3>
                  {section.body.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </section>
              ))}
            </div>
          </>
        ) : null}
        <button type="button" className="btn btn--primary" onClick={closePage}>
          {t('footer.privacyClose')}
        </button>
      </AnimatedModal>
    </>
  );
}
