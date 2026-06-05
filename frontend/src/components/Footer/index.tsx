import './Footer.css';
import { useState } from 'react';
import { useLocale } from '../../context/LocaleContext';
import AnimatedModal from '../common/AnimatedModal';

export default function Footer() {
  const { lang, t } = useLocale();
  const [privacyOpen, setPrivacyOpen] = useState(false);

  return (
    <>
      <footer className="footer">
        <div className="container">
        <div className="footer__grid">
          <div>
            <div className="footer__col-title">{t('footer.support')}</div>
            <a href="#" className="footer__link">{t('footer.helpCenter')}</a>
            <a href="#" className="footer__link">{t('footer.safety')}</a>
            <a href="#" className="footer__link">{t('footer.contact')}</a>
          </div>
          <div>
            <div className="footer__col-title">{t('footer.about')}</div>
            <a href="#" className="footer__link">{t('footer.aboutApp')}</a>
            <a href="#" className="footer__link">{t('footer.news')}</a>
            <a href="#" className="footer__link">{t('footer.joinUs')}</a>
          </div>
          <div>
            <div className="footer__col-title">{t('footer.legal')}</div>
            <a href="#" className="footer__link">{t('footer.terms')}</a>
            <button type="button" className="footer__link footer__link--button" onClick={() => setPrivacyOpen(true)}>
              {t('footer.privacy')}
            </button>
            <a href="#" className="footer__link">{t('footer.cookie')}</a>
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
        isOpen={privacyOpen}
        overlayClassName="footer-privacy__overlay"
        dialogClassName="footer-privacy__dialog"
        ariaLabel={t('footer.privacyTitle')}
        onClose={() => setPrivacyOpen(false)}
      >
        <h2>{t('footer.privacyTitle')}</h2>
        <p>{t('footer.privacyAiDisclosure')}</p>
        <p>{t('footer.privacyDataStored')}</p>
        <button type="button" className="btn btn--primary" onClick={() => setPrivacyOpen(false)}>
          {t('footer.privacyClose')}
        </button>
      </AnimatedModal>
    </>
  );
}
