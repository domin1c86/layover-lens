import { useState } from 'react';
import TopNav from '../components/TopNav';
import SearchTab from '../components/SearchTab';
import AiSearchTab from '../components/AiSearchTab';
import FavoritesTab from '../components/FavoritesTab';
import Footer from '../components/Footer';
import './HomePage.css';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<'search' | 'ai' | 'favorites'>('search');

  return (
    <div className="home-page">
      <TopNav activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="home-page__content">
        {activeTab === 'search' && <SearchTab />}
        {activeTab === 'ai' && <AiSearchTab />}
        {activeTab === 'favorites' && <FavoritesTab />}
      </div>

      <Footer />
    </div>
  );
}
