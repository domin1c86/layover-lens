import './Footer.css';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer__grid">
          <div>
            <div className="footer__col-title">支持</div>
            <a href="#" className="footer__link">帮助中心</a>
            <a href="#" className="footer__link">安全信息</a>
            <a href="#" className="footer__link">取消选项</a>
            <a href="#" className="footer__link">联系我们</a>
          </div>
          <div>
            <div className="footer__col-title">关于</div>
            <a href="#" className="footer__link">关于中转助手</a>
            <a href="#" className="footer__link">新闻动态</a>
            <a href="#" className="footer__link">加入我们</a>
            <a href="#" className="footer__link">合作伙伴</a>
          </div>
          <div>
            <div className="footer__col-title">法律</div>
            <a href="#" className="footer__link">服务条款</a>
            <a href="#" className="footer__link">隐私政策</a>
            <a href="#" className="footer__link">Cookie 设置</a>
          </div>
        </div>
        <div className="footer__legal">
          <div className="footer__copyright">© 2026 中转助手 Layover Lens, Inc.</div>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--muted)' }}>简体中文 (CN)</span>
            <span style={{ fontSize: '13px', color: 'var(--muted)' }}>¥ CNY</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
