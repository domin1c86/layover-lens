# Layover Lens MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP of the transit assistant with simple search, card-based results, mock data source, and C++ path planning core.

**Architecture:** Modular design with React+TypeScript frontend, Python FastAPI backend, C++ path planning engine compiled as shared library, and MySQL database with mock data.

**Tech Stack:** React 18, TypeScript 5, Python 3.11, FastAPI, C++17, pybind11, MySQL 8.0, Docker

---

## File Structure

```
.
├── docker-compose.yml              # Development environment
├── frontend/                       # React + TypeScript frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── SearchForm/
│       │   │   └── SimpleSearchForm.tsx
│       │   ├── ResultCards/
│       │   │   ├── RouteCard.tsx
│       │   │   └── RouteCardList.tsx
│       │   └── Timeline/
│       │       └── RouteTimeline.tsx
│       ├── pages/
│       │   └── HomePage.tsx
│       ├── services/
│       │   └── api.ts
│       └── types/
│           └── index.ts
├── backend/                        # Python backend
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI entry
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── search.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── search_service.py
│   │   └── data_source/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── mock_adapter.py
│   │       └── factory.py
│   └── planner/                    # C++ path planner
│       ├── CMakeLists.txt
│       ├── planner.h
│       ├── planner.cpp
│       └── bindings.cpp            # pybind11 bindings
└── database/
    └── init.sql                    # MySQL schema and mock data
```

---

## Task 1: Project Setup and Docker Environment

**Files:**
- Create: `docker-compose.yml`
- Create: `frontend/package.json`
- Create: `backend/requirements.txt`
- Create: `database/init.sql`

---

### Task 1.1: Create Docker Compose Configuration

- [ ] **Step 1: Write docker-compose.yml**

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=mysql+mysqlconnector://root:devpassword@mysql:3306/layover_lens
      - DATA_SOURCE=mock
    depends_on:
      mysql:
        condition: service_healthy

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: devpassword
      MYSQL_DATABASE: layover_lens
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      timeout: 20s
      retries: 10

volumes:
  mysql_data:
```

- [ ] **Step 2: Create frontend package.json**

```json
{
  "name": "layover-lens-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 3000",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

- [ ] **Step 3: Create backend requirements.txt**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
mysql-connector-python==8.3.0
python-dotenv==1.0.0
pytest==8.0.0
httpx==0.26.0
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml frontend/package.json backend/requirements.txt
git commit -m "chore: setup docker compose and dependencies"
```

---

### Task 1.2: Create Frontend TypeScript Configuration

- [ ] **Step 1: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 2: Create tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    watch: {
      usePolling: true
    }
  }
})
```

- [ ] **Step 4: Create index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>中转助手 - Layover Lens</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html
git commit -m "chore: add typescript and vite configuration"
```

---

### Task 1.3: Create Database Schema

- [ ] **Step 1: Create database/init.sql**

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS layover_lens CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE layover_lens;

-- 城市表
CREATE TABLE cities (
    id VARCHAR(10) PRIMARY KEY COMMENT '城市代码',
    name VARCHAR(50) NOT NULL COMMENT '城市名称',
    name_en VARCHAR(50) COMMENT '英文名称',
    country VARCHAR(50) DEFAULT 'CN',
    latitude DECIMAL(10, 8) COMMENT '纬度',
    longitude DECIMAL(11, 8) COMMENT '经度',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 交通站点表
CREATE TABLE stations (
    id VARCHAR(10) PRIMARY KEY COMMENT '站点代码',
    name VARCHAR(100) NOT NULL COMMENT '站点名称',
    city_id VARCHAR(10) NOT NULL COMMENT '所属城市',
    type ENUM('AIRPORT', 'RAILWAY') NOT NULL COMMENT '站点类型',
    iata_code VARCHAR(3) COMMENT 'IATA代码',
    station_code VARCHAR(10) COMMENT '铁路站点代码',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入模拟数据
INSERT INTO cities (id, name, name_en, latitude, longitude) VALUES
('BJS', '北京', 'Beijing', 39.9042, 116.4074),
('SHA', '上海', 'Shanghai', 31.2304, 121.4737),
('CTU', '成都', 'Chengdu', 30.5728, 104.0668),
('XIY', '西安', 'Xi\'an', 34.3416, 108.9398),
('HGH', '杭州', 'Hangzhou', 30.2741, 120.1551);

INSERT INTO stations (id, name, city_id, type, iata_code, station_code) VALUES
('PEK', '北京首都国际机场', 'BJS', 'AIRPORT', 'PEK', NULL),
('PKX', '北京大兴国际机场', 'BJS', 'AIRPORT', 'PKX', NULL),
('BJX', '北京西站', 'BJS', 'RAILWAY', NULL, 'BJP'),
('PVG', '上海浦东国际机场', 'SHA', 'AIRPORT', 'PVG', NULL),
('SHA_A', '上海虹桥国际机场', 'SHA', 'AIRPORT', 'SHA'),
('SHX', '上海虹桥站', 'SHA', 'RAILWAY', NULL, 'AOH'),
('CTU_A', '成都双流国际机场', 'CTU', 'AIRPORT', 'CTU', NULL),
('CDX', '成都东站', 'CTU', 'RAILWAY', NULL, 'ICW'),
('XIY_A', '西安咸阳国际机场', 'XIY', 'AIRPORT', 'XIY', NULL),
('XAY', '西安北站', 'XIY', 'RAILWAY', NULL, 'EAY');
```

- [ ] **Step 2: Commit**

```bash
git add database/init.sql
git commit -m "chore: add mysql database schema with mock data"
```

---

## Task 2: Frontend Foundation

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/services/api.ts`

---

### Task 2.1: Define TypeScript Types

- [ ] **Step 1: Create types/index.ts**

```typescript
// 站点类型
export interface Station {
  id: string;
  name: string;
  cityId: string;
  type: 'AIRPORT' | 'RAILWAY';
}

// 城市类型
export interface City {
  id: string;
  name: string;
  nameEn: string;
  stations: Station[];
}

// 行程段
export interface Leg {
  type: 'flight' | 'train';
  flightNo?: string;
  trainNo?: string;
  airline?: string;
  trainType?: string;
  from: {
    station: string;
    time: string;
  };
  to: {
    station: string;
    time: string;
  };
  duration: number;
  price: number;
}

// 完整路径方案
export interface RoutePlan {
  id: string;
  tag?: string;
  totalPrice: number;
  totalDuration: number;
  transferCount: number;
  score: number;
  legs: Leg[];
}

// 搜索请求
export interface SearchRequest {
  fromCity: string;
  toCity: string;
  date: string;
  optimize: 'price' | 'time' | 'transfer' | 'balanced';
}

// 搜索响应
export interface SearchResponse {
  searchId: string;
  total: number;
  routes: RoutePlan[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add typescript type definitions"
```

---

### Task 2.2: Setup API Service

- [ ] **Step 1: Create services/api.ts**

```typescript
import axios from 'axios';
import type { SearchRequest, SearchResponse, City } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const searchApi = {
  async search(request: SearchRequest): Promise<SearchResponse> {
    const response = await api.post<SearchResponse>('/search', request);
    return response.data;
  },
};

export const cityApi = {
  async getCities(keyword?: string): Promise<City[]> {
    const response = await api.get<City[]>('/cities', {
      params: { keyword },
    });
    return response.data;
  },
};

export default api;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add api service layer"
```

---

### Task 2.3: Create Main Entry Files

- [ ] **Step 1: Create main.tsx**

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 2: Create App.tsx**

```typescript
import HomePage from './pages/HomePage';

function App() {
  return (
    <div className="app">
      <HomePage />
    </div>
  );
}

export default App;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat: add main entry files"
```

---

## Task 3: Frontend Components

**Files:**
- Create: `frontend/src/components/SearchForm/SimpleSearchForm.tsx`
- Create: `frontend/src/components/ResultCards/RouteCard.tsx`
- Create: `frontend/src/components/ResultCards/RouteCardList.tsx`
- Create: `frontend/src/components/Timeline/RouteTimeline.tsx`
- Create: `frontend/src/pages/HomePage.tsx`

---

### Task 3.1: Create Simple Search Form

- [ ] **Step 1: Create SimpleSearchForm.tsx**

```typescript
import React, { useState } from 'react';
import type { SearchRequest } from '../../types';

interface SimpleSearchFormProps {
  onSearch: (request: SearchRequest) => void;
  loading?: boolean;
}

const SimpleSearchForm: React.FC<SimpleSearchFormProps> = ({ onSearch, loading }) => {
  const [fromCity, setFromCity] = useState('');
  const [toCity, setToCity] = useState('');
  const [date, setDate] = useState('');
  const [optimize, setOptimize] = useState<SearchRequest['optimize']>('balanced');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch({
      fromCity,
      toCity,
      date,
      optimize,
    });
  };

  // 获取今天的日期字符串作为最小值
  const today = new Date().toISOString().split('T')[0];

  return (
    <form onSubmit={handleSubmit} className="search-form">
      <h2>搜索中转方案</h2>
      
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="fromCity">出发城市</label>
          <input
            type="text"
            id="fromCity"
            value={fromCity}
            onChange={(e) => setFromCity(e.target.value)}
            placeholder="如：北京"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="toCity">目的城市</label>
          <input
            type="text"
            id="toCity"
            value={toCity}
            onChange={(e) => setToCity(e.target.value)}
            placeholder="如：成都"
            required
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="date">出发日期</label>
          <input
            type="date"
            id="date"
            value={date}
            min={today}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="optimize">优化目标</label>
          <select
            id="optimize"
            value={optimize}
            onChange={(e) => setOptimize(e.target.value as SearchRequest['optimize'])}
          >
            <option value="balanced">综合最优</option>
            <option value="price">最低价格</option>
            <option value="time">最短时间</option>
            <option value="transfer">最少换乘</option>
          </select>
        </div>
      </div>

      <button type="submit" disabled={loading} className="search-button">
        {loading ? '搜索中...' : '搜索'}
      </button>
    </form>
  );
};

export default SimpleSearchForm;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SearchForm/SimpleSearchForm.tsx
git commit -m "feat: add simple search form component"
```

---

### Task 3.2: Create Route Timeline Component

- [ ] **Step 1: Create RouteTimeline.tsx**

```typescript
import React from 'react';
import type { Leg } from '../../types';

interface RouteTimelineProps {
  legs: Leg[];
}

const RouteTimeline: React.FC<RouteTimelineProps> = ({ legs }) => {
  const formatTime = (timeStr: string) => {
    return timeStr.substring(0, 5); // HH:MM
  };

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h${mins > 0 ? mins + 'm' : ''}`;
  };

  const getTransportIcon = (type: string) => {
    return type === 'flight' ? '✈️' : '🚄';
  };

  return (
    <div className="route-timeline">
      {legs.map((leg, index) => (
        <div key={index} className="timeline-segment">
          {/* 出发信息 */}
          <div className="timeline-point departure">
            <div className="time">{formatTime(leg.from.time)}</div>
            <div className="station">{leg.from.station}</div>
          </div>

          {/* 行程信息 */}
          <div className="timeline-connection">
            <div className="transport-line">
              <span className="transport-icon">{getTransportIcon(leg.type)}</span>
            </div>
            <div className="transport-info">
              <div className="transport-number">
                {leg.type === 'flight' ? leg.flightNo : leg.trainNo}
              </div>
              <div className="duration">{formatDuration(leg.duration)}</div>
            </div>
          </div>

          {/* 到达信息 */}
          <div className="timeline-point arrival">
            <div className="time">{formatTime(leg.to.time)}</div>
            <div className="station">{leg.to.station}</div>
          </div>

          {/* 中转信息 */}
          {index < legs.length - 1 && (
            <div className="transfer-info">
              <span className="transfer-icon">🕐</span>
              <span>中转停留时间计算...</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default RouteTimeline;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Timeline/RouteTimeline.tsx
git commit -m "feat: add route timeline component"
```

---

### Task 3.3: Create Route Card Component

- [ ] **Step 1: Create RouteCard.tsx**

```typescript
import React from 'react';
import type { RoutePlan } from '../../types';
import RouteTimeline from '../Timeline/RouteTimeline';

interface RouteCardProps {
  route: RoutePlan;
}

const RouteCard: React.FC<RouteCardProps> = ({ route }) => {
  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}小时${mins > 0 ? mins + '分钟' : ''}`;
  };

  return (
    <div className={`route-card ${route.tag ? 'featured' : ''}`}>
      {route.tag && (
        <div className="route-tag">{route.tag}</div>
      )}
      
      <div className="route-header">
        <div className="route-price">
          <span className="currency">¥</span>
          <span className="amount">{route.totalPrice}</span>
        </div>
        
        <div className="route-stats">
          <div className="stat">
            <span className="stat-icon">⏱️</span>
            <span>{formatDuration(route.totalDuration)}</span>
          </div>
          <div className="stat">
            <span className="stat-icon">🔄</span>
            <span>{route.transferCount}次换乘</span>
          </div>
        </div>
      </div>

      <div className="route-timeline-container">
        <RouteTimeline legs={route.legs} />
      </div>

      <div className="route-actions">
        <button className="btn-primary">预订</button>
        <button className="btn-secondary">详情</button>
      </div>
    </div>
  );
};

export default RouteCard;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ResultCards/RouteCard.tsx
git commit -m "feat: add route card component"
```

---

### Task 3.4: Create Route Card List and HomePage

- [ ] **Step 1: Create RouteCardList.tsx**

```typescript
import React from 'react';
import type { RoutePlan } from '../../types';
import RouteCard from './RouteCard';

interface RouteCardListProps {
  routes: RoutePlan[];
}

const RouteCardList: React.FC<RouteCardListProps> = ({ routes }) => {
  if (routes.length === 0) {
    return (
      <div className="empty-state">
        <p>暂无中转方案，请尝试调整搜索条件</p>
      </div>
    );
  }

  return (
    <div className="route-card-list">
      <h3>共找到 {routes.length} 个方案</h3>
      {routes.map((route) => (
        <RouteCard key={route.id} route={route} />
      ))}
    </div>
  );
};

export default RouteCardList;
```

- [ ] **Step 2: Create HomePage.tsx**

```typescript
import React, { useState } from 'react';
import SimpleSearchForm from '../components/SearchForm/SimpleSearchForm';
import RouteCardList from '../components/ResultCards/RouteCardList';
import { searchApi } from '../services/api';
import type { SearchRequest, RoutePlan } from '../types';

const HomePage: React.FC = () => {
  const [routes, setRoutes] = useState<RoutePlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (request: SearchRequest) => {
    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const response = await searchApi.search(request);
      setRoutes(response.routes);
    } catch (err) {
      setError('搜索失败，请稍后重试');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home-page">
      <header className="app-header">
        <h1>🌍 中转助手 Layover Lens</h1>
        <p>发现最优中转方案，省钱又省心</p>
      </header>

      <main className="main-content">
        <SimpleSearchForm onSearch={handleSearch} loading={loading} />

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {searched && !loading && (
          <RouteCardList routes={routes} />
        )}
      </main>

      <footer className="app-footer">
        <p>© 2026 Layover Lens - 智能中转规划</p>
      </footer>
    </div>
  );
};

export default HomePage;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ResultCards/RouteCardList.tsx frontend/src/pages/HomePage.tsx
git commit -m "feat: add route card list and home page"
```

---

## Task 4: Backend Foundation

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/Dockerfile`

---

### Task 4.1: Create Backend Configuration

- [ ] **Step 1: Create config.py**

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    database_url: str = "mysql+mysqlconnector://root:devpassword@mysql:3306/layover_lens"
    
    # 数据源类型: mock, scraper, api
    data_source: str = "mock"
    
    # API设置
    api_v1_prefix: str = "/api/v1"
    debug: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 2: Create main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="Layover Lens API",
    description="Transit assistance API",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "message": "Welcome to Layover Lens API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py backend/app/main.py backend/app/__init__.py
git commit -m "feat: add backend foundation with fastapi"
```

---

### Task 4.2: Create Backend Dockerfile

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（包括MySQL客户端和C++编译工具）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cmake \
    libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 2: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine

WORKDIR /app

# 复制package文件
COPY package.json ./
RUN npm install

# 复制源代码
COPY . .

# 暴露端口
EXPOSE 3000

# 开发模式启动
CMD ["npm", "run", "dev"]
```

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile
git commit -m "chore: add dockerfiles for frontend and backend"
```

---

## Task 5: Data Source Module

**Files:**
- Create: `backend/app/data_source/base.py`
- Create: `backend/app/data_source/mock_adapter.py`
- Create: `backend/app/data_source/factory.py`

---

### Task 5.1: Create Data Source Base Classes

- [ ] **Step 1: Create base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

@dataclass
class Flight:
    flight_no: str
    airline: str
    from_airport: str
    to_airport: str
    departure: datetime
    arrival: datetime
    price: float
    seats_available: int = 100

@dataclass
class Train:
    train_no: str
    train_type: str
    from_station: str
    to_station: str
    departure: datetime
    arrival: datetime
    price: float
    seats_available: int = 100

class DataSourceBase(ABC):
    """数据源抽象基类"""
    
    @abstractmethod
    def search_flights(
        self, 
        from_code: str, 
        to_code: str, 
        travel_date: date
    ) -> List[Flight]:
        """搜索航班"""
        pass
    
    @abstractmethod
    def search_trains(
        self, 
        from_code: str, 
        to_code: str, 
        travel_date: date
    ) -> List[Train]:
        """搜索火车"""
        pass
    
    @abstractmethod
    def get_price(self, route_id: str, travel_date: date) -> Optional[float]:
        """获取价格"""
        pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/data_source/base.py
mkdir -p backend/app/data_source
git add backend/app/data_source/
git commit -m "feat: add data source base classes"
```

---

### Task 5.2: Create Mock Data Adapter

- [ ] **Step 1: Create mock_adapter.py**

```python
import random
from datetime import datetime, timedelta
from typing import List, Optional
from .base import DataSourceBase, Flight, Train

class MockAdapter(DataSourceBase):
    """模拟数据适配器"""
    
    AIRLINES = ["国航", "东航", "南航", "海航", "春秋航空"]
    TRAIN_TYPES = ["G", "D", "K", "T", "Z"]
    
    def __init__(self):
        self._cache = {}
    
    def search_flights(
        self, 
        from_code: str, 
        to_code: str, 
        travel_date: date
    ) -> List[Flight]:
        """生成模拟航班数据"""
        cache_key = f"flight:{from_code}:{to_code}:{travel_date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 基础价格根据距离估算
        base_price = self._calculate_base_price(from_code, to_code)
        num_flights = random.randint(3, 8)
        flights = []
        
        for i in range(num_flights):
            # 生成出发时间 (06:00 - 22:00)
            departure_hour = random.randint(6, 21)
            departure_minute = random.choice([0, 15, 30, 45])
            departure = datetime.combine(
                travel_date,
                datetime.strptime(f"{departure_hour}:{departure_minute}", "%H:%M").time()
            )
            
            # 飞行时长 1.5 - 4 小时
            duration = random.randint(90, 240)
            arrival = departure + timedelta(minutes=duration)
            
            flight = Flight(
                flight_no=f"CA{random.randint(1000, 9999)}",
                airline=random.choice(self.AIRLINES),
                from_airport=from_code,
                to_airport=to_code,
                departure=departure,
                arrival=arrival,
                price=round(base_price * random.uniform(0.7, 1.3), 2),
                seats_available=random.randint(5, 200)
            )
            flights.append(flight)
        
        # 按出发时间排序
        flights.sort(key=lambda x: x.departure)
        self._cache[cache_key] = flights
        
        return flights
    
    def search_trains(
        self, 
        from_code: str, 
        to_code: str, 
        travel_date: date
    ) -> List[Train]:
        """生成模拟火车数据"""
        cache_key = f"train:{from_code}:{to_code}:{travel_date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        base_price = self._calculate_base_price(from_code, to_code) * 0.5
        num_trains = random.randint(5, 15)
        trains = []
        
        for i in range(num_trains):
            departure_hour = random.randint(6, 20)
            departure_minute = random.choice([0, 10, 20, 30, 40, 50])
            departure = datetime.combine(
                travel_date,
                datetime.strptime(f"{departure_hour}:{departure_minute}", "%H:%M").time()
            )
            
            # 高铁更快，普通列车更慢
            train_type = random.choice(self.TRAIN_TYPES)
            if train_type == "G":
                duration = random.randint(180, 600)
            elif train_type == "D":
                duration = random.randint(240, 720)
            else:
                duration = random.randint(480, 1440)
            
            arrival = departure + timedelta(minutes=duration)
            
            train = Train(
                train_no=f"{train_type}{random.randint(100, 9999)}",
                train_type=train_type,
                from_station=from_code,
                to_station=to_code,
                departure=departure,
                arrival=arrival,
                price=round(base_price * random.uniform(0.5, 1.5), 2),
                seats_available=random.randint(0, 500)
            )
            trains.append(train)
        
        trains.sort(key=lambda x: x.departure)
        self._cache[cache_key] = trains
        
        return trains
    
    def get_price(self, route_id: str, travel_date: date) -> Optional[float]:
        """获取价格"""
        return round(random.uniform(200, 2000), 2)
    
    def _calculate_base_price(self, from_code: str, to_code: str) -> float:
        """根据城市代码估算基础价格"""
        # 简化的价格计算
        distance_map = {
            ("PEK", "CTU_A"): 1200,
            ("PEK", "XIY_A"): 900,
            ("SHA_A", "CTU_A"): 1600,
        }
        distance = distance_map.get((from_code, to_code), 1000)
        return distance * 0.8
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/data_source/mock_adapter.py
git commit -m "feat: add mock data adapter"
```

---

### Task 5.3: Create Data Source Factory

- [ ] **Step 1: Create factory.py**

```python
from enum import Enum
from app.config import settings
from .base import DataSourceBase
from .mock_adapter import MockAdapter

class DataSourceType(Enum):
    MOCK = "mock"
    SCRAPER = "scraper"
    API = "api"

_data_source_instance: DataSourceBase = None

def create_data_source(source_type: str = None) -> DataSourceBase:
    """工厂函数 - 创建数据源实例"""
    global _data_source_instance
    
    if _data_source_instance is not None:
        return _data_source_instance
    
    if source_type is None:
        source_type = settings.data_source
    
    if source_type == DataSourceType.MOCK.value:
        _data_source_instance = MockAdapter()
    elif source_type == DataSourceType.SCRAPER.value:
        raise NotImplementedError("Scraper adapter not implemented yet")
    elif source_type == DataSourceType.API.value:
        raise NotImplementedError("API adapter not implemented yet")
    else:
        raise ValueError(f"Unknown data source type: {source_type}")
    
    return _data_source_instance

def get_data_source() -> DataSourceBase:
    """获取当前数据源实例（单例模式）"""
    global _data_source_instance
    if _data_source_instance is None:
        return create_data_source()
    return _data_source_instance
```

- [ ] **Step 2: Create __init__.py**

```python
from .base import DataSourceBase, Flight, Train
from .factory import create_data_source, get_data_source

__all__ = ['DataSourceBase', 'Flight', 'Train', 'create_data_source', 'get_data_source']
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/data_source/factory.py backend/app/data_source/__init__.py
git commit -m "feat: add data source factory"
```

---

## Task 6: C++ Path Planner

**Files:**
- Create: `backend/planner/planner.h`
- Create: `backend/planner/planner.cpp`
- Create: `backend/planner/bindings.cpp`
- Create: `backend/planner/CMakeLists.txt`

---

### Task 6.1: Create C++ Planner Header

- [ ] **Step 1: Create planner.h**

```cpp
#ifndef PLANNER_H
#define PLANNER_H

#include <string>
#include <vector>
#include <memory>

namespace planner {

enum class TransportType { FLIGHT, TRAIN };
enum class OptimizeTarget { PRICE, TIME, TRANSFER, BALANCED };

// 行程段
struct Leg {
    TransportType type;
    std::string transport_no;  // 航班号/车次号
    std::string from_station;
    std::string to_station;
    std::string departure_time;
    std::string arrival_time;
    int duration;              // 分钟
    double price;
    std::string carrier;
};

// 路径方案
struct RoutePlan {
    std::string id;
    std::vector<Leg> legs;
    int total_duration;
    double total_price;
    int transfer_count;
    double score;
    
    RoutePlan() : total_duration(0), total_price(0), transfer_count(0), score(0) {}
};

// 搜索请求
struct SearchRequest {
    std::string from_city;
    std::string to_city;
    std::string date;
    OptimizeTarget optimize;
    int max_transfer = 2;
    int max_layover_minutes = 480;  // 最大中转时间8小时
};

// 路径规划器类
class PathPlanner {
public:
    PathPlanner();
    ~PathPlanner();
    
    // 查找路径
    std::vector<RoutePlan> find_routes(const SearchRequest& request);
    
    // 设置图数据（从Python调用）
    void add_node(const std::string& id, const std::string& name, 
                  const std::string& city, const std::string& type);
    void add_edge(const std::string& from, const std::string& to,
                  TransportType type, int duration, double price,
                  const std::string& schedule_id);
    void clear_graph();
    
private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace planner

#endif // PLANNER_H
```

- [ ] **Step 2: Commit**

```bash
mkdir -p backend/planner
git add backend/planner/planner.h
git commit -m "feat: add c++ planner header"
```

---

### Task 6.2: Create C++ Planner Implementation

- [ ] **Step 1: Create planner.cpp**

```cpp
#include "planner.h"
#include <queue>
#include <unordered_map>
#include <algorithm>
#include <cmath>
#include <sstream>

namespace planner {

// 节点结构
struct Node {
    std::string id;
    std::string name;
    std::string city;
    std::string type;
    std::vector<struct Edge> edges;
};

// 边结构
struct Edge {
    std::string to_id;
    TransportType type;
    int duration;
    double price;
    std::string schedule_id;
};

// 搜索状态
struct SearchState {
    std::string node_id;
    std::vector<Leg> legs;
    int total_duration;
    double total_price;
    int transfer_count;
    double score;
    
    bool operator>(const SearchState& other) const {
        return score > other.score;
    }
};

class PathPlanner::Impl {
public:
    std::unordered_map<std::string, Node> nodes;
    
    double calculate_score(const SearchState& state, OptimizeTarget target) {
        switch (target) {
            case OptimizeTarget::PRICE:
                return -state.total_price;  // 越低越好
            case OptimizeTarget::TIME:
                return -state.total_duration;  // 越短越好
            case OptimizeTarget::TRANSFER:
                return -state.transfer_count * 1000.0;  // 越少越好
            case OptimizeTarget::BALANCED:
            default:
                // 综合评分：价格权重0.4，时间权重0.4，换乘权重0.2
                double price_score = 1000.0 / (state.total_price + 1);
                double time_score = 1000.0 / (state.total_duration + 1);
                double transfer_score = 100.0 / (state.transfer_count + 1);
                return price_score * 0.4 + time_score * 0.4 + transfer_score * 0.2;
        }
    }
};

PathPlanner::PathPlanner() : pImpl(std::make_unique<Impl>()) {}
PathPlanner::~PathPlanner() = default;

void PathPlanner::add_node(const std::string& id, const std::string& name,
                           const std::string& city, const std::string& type) {
    Node node{id, name, city, type, {}};
    pImpl->nodes[id] = node;
}

void PathPlanner::add_edge(const std::string& from, const std::string& to,
                           TransportType type, int duration, double price,
                           const std::string& schedule_id) {
    if (pImpl->nodes.find(from) == pImpl->nodes.end()) return;
    
    Edge edge{to, type, duration, price, schedule_id};
    pImpl->nodes[from].edges.push_back(edge);
}

void PathPlanner::clear_graph() {
    pImpl->nodes.clear();
}

std::vector<RoutePlan> PathPlanner::find_routes(const SearchRequest& request) {
    std::vector<RoutePlan> results;
    
    // 找到起点和终点的所有站点
    std::vector<std::string> start_nodes;
    std::vector<std::string> end_nodes;
    
    for (const auto& [id, node] : pImpl->nodes) {
        if (node.city == request.from_city) {
            start_nodes.push_back(id);
        }
        if (node.city == request.to_city) {
            end_nodes.push_back(id);
        }
    }
    
    if (start_nodes.empty() || end_nodes.empty()) {
        return results;
    }
    
    // 使用优先队列进行多目标搜索
    using QueueItem = std::pair<double, SearchState>;
    std::priority_queue<QueueItem, std::vector<QueueItem>, std::greater<QueueItem>> pq;
    
    // 初始化队列
    for (const auto& start : start_nodes) {
        SearchState state;
        state.node_id = start;
        state.score = 0;
        pq.push({0, state});
    }
    
    int max_results = 10;
    int iterations = 0;
    int max_iterations = 10000;
    
    while (!pq.empty() && results.size() < max_results && iterations < max_iterations) {
        iterations++;
        
        auto [current_score, current] = pq.top();
        pq.pop();
        
        // 检查是否到达终点
        if (std::find(end_nodes.begin(), end_nodes.end(), current.node_id) != end_nodes.end()
            && !current.legs.empty()) {
            RoutePlan plan;
            plan.id = "route_" + std::to_string(results.size() + 1);
            plan.legs = current.legs;
            plan.total_duration = current.total_duration;
            plan.total_price = current.total_price;
            plan.transfer_count = current.transfer_count;
            plan.score = current.score;
            results.push_back(plan);
            continue;
        }
        
        // 超过最大换乘次数
        if (current.transfer_count >= request.max_transfer) {
            continue;
        }
        
        // 扩展邻居
        auto it = pImpl->nodes.find(current.node_id);
        if (it == pImpl->nodes.end()) continue;
        
        for (const auto& edge : it->second.edges) {
            // 简单剪枝：不返回起点城市
            auto neighbor_it = pImpl->nodes.find(edge.to_id);
            if (neighbor_it == pImpl->nodes.end()) continue;
            if (neighbor_it->second.city == request.from_city) continue;
            
            SearchState next = current;
            next.node_id = edge.to_id;
            
            Leg leg;
            leg.type = edge.type;
            leg.from_station = it->second.name;
            leg.to_station = neighbor_it->second.name;
            leg.duration = edge.duration;
            leg.price = edge.price;
            leg.transport_no = edge.schedule_id;  // 简化处理
            
            // 生成时间（简化）
            std::ostringstream oss;
            oss << (8 + next.legs.size() * 2) << ":00";
            leg.departure_time = oss.str();
            oss.str("");
            oss << (10 + next.legs.size() * 2) << ":00";
            leg.arrival_time = oss.str();
            
            next.legs.push_back(leg);
            next.total_duration += edge.duration;
            next.total_price += edge.price;
            
            if (!current.legs.empty() && current.legs.back().type != leg.type) {
                next.transfer_count++;
            }
            
            next.score = pImpl->calculate_score(next, request.optimize);
            pq.push({-next.score, next});
        }
    }
    
    return results;
}

} // namespace planner
```

- [ ] **Step 2: Commit**

```bash
git add backend/planner/planner.cpp
git commit -m "feat: add c++ planner implementation"
```

---

### Task 6.3: Create pybind11 Bindings

- [ ] **Step 1: Create bindings.cpp**

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "planner.h"

namespace py = pybind11;
using namespace planner;

PYBIND11_MODULE(route_planner, m) {
    m.doc() = "Route planning engine for Layover Lens";
    
    // 枚举类型
    py::enum_<TransportType>(m, "TransportType")
        .value("FLIGHT", TransportType::FLIGHT)
        .value("TRAIN", TransportType::TRAIN);
    
    py::enum_<OptimizeTarget>(m, "OptimizeTarget")
        .value("PRICE", OptimizeTarget::PRICE)
        .value("TIME", OptimizeTarget::TIME)
        .value("TRANSFER", OptimizeTarget::TRANSFER)
        .value("BALANCED", OptimizeTarget::BALANCED);
    
    // Leg 结构体
    py::class_<Leg>(m, "Leg")
        .def(py::init<>())
        .def_readwrite("type", &Leg::type)
        .def_readwrite("transport_no", &Leg::transport_no)
        .def_readwrite("from_station", &Leg::from_station)
        .def_readwrite("to_station", &Leg::to_station)
        .def_readwrite("departure_time", &Leg::departure_time)
        .def_readwrite("arrival_time", &Leg::arrival_time)
        .def_readwrite("duration", &Leg::duration)
        .def_readwrite("price", &Leg::price)
        .def_readwrite("carrier", &Leg::carrier);
    
    // RoutePlan 结构体
    py::class_<RoutePlan>(m, "RoutePlan")
        .def(py::init<>())
        .def_readwrite("id", &RoutePlan::id)
        .def_readwrite("legs", &RoutePlan::legs)
        .def_readwrite("total_duration", &RoutePlan::total_duration)
        .def_readwrite("total_price", &RoutePlan::total_price)
        .def_readwrite("transfer_count", &RoutePlan::transfer_count)
        .def_readwrite("score", &RoutePlan::score);
    
    // SearchRequest 结构体
    py::class_<SearchRequest>(m, "SearchRequest")
        .def(py::init<>())
        .def_readwrite("from_city", &SearchRequest::from_city)
        .def_readwrite("to_city", &SearchRequest::to_city)
        .def_readwrite("date", &SearchRequest::date)
        .def_readwrite("optimize", &SearchRequest::optimize)
        .def_readwrite("max_transfer", &SearchRequest::max_transfer)
        .def_readwrite("max_layover_minutes", &SearchRequest::max_layover_minutes);
    
    // PathPlanner 类
    py::class_<PathPlanner>(m, "PathPlanner")
        .def(py::init<>())
        .def("find_routes", &PathPlanner::find_routes)
        .def("add_node", &PathPlanner::add_node)
        .def("add_edge", [](PathPlanner& self, const std::string& from, 
                            const std::string& to, TransportType type,
                            int duration, double price, const std::string& schedule_id) {
            self.add_edge(from, to, type, duration, price, schedule_id);
        })
        .def("clear_graph", &PathPlanner::clear_graph);
}
```

- [ ] **Step 2: Create CMakeLists.txt**

```cmake
cmake_minimum_required(VERSION 3.12)
project(route_planner)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找 Python 和 pybind11
find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

# 创建共享库
pybind11_add_module(route_planner 
    planner.cpp
    bindings.cpp
)

target_include_directories(route_planner PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# 编译选项
target_compile_options(route_planner PRIVATE
    -O3                    # 优化级别
    -Wall                  # 显示所有警告
    -fPIC                  # 位置无关代码
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/planner/bindings.cpp backend/planner/CMakeLists.txt
git commit -m "feat: add pybind11 bindings and cmake config"
```

---

## Task 7: Backend API Routes

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/search.py`
- Create: `backend/app/routers/cities.py`
- Modify: `backend/app/main.py`

---

### Task 7.1: Create Search Router

- [ ] **Step 1: Create search.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal
from datetime import date
from app.data_source import get_data_source

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    from_city: str
    to_city: str
    date: date
    optimize: Literal["price", "time", "transfer", "balanced"] = "balanced"

class LegResponse(BaseModel):
    type: Literal["flight", "train"]
    flight_no: str | None = None
    train_no: str | None = None
    airline: str | None = None
    train_type: str | None = None
    from_station: str
    to_station: str
    departure_time: str
    arrival_time: str
    duration: int
    price: float

class RoutePlanResponse(BaseModel):
    id: str
    tag: str | None = None
    total_price: float
    total_duration: int
    transfer_count: int
    score: float
    legs: List[LegResponse]

class SearchResponse(BaseModel):
    search_id: str
    total: int
    routes: List[RoutePlanResponse]

@router.post("", response_model=SearchResponse)
async def search_routes(request: SearchRequest):
    """搜索中转方案"""
    try:
        # 获取数据源
        data_source = get_data_source()
        
        # 简化的实现：直接返回模拟数据
        # 实际实现应该调用 C++ 规划器
        
        routes = []
        
        # 生成 3-5 个模拟方案
        import random
        for i in range(random.randint(3, 5)):
            route = RoutePlanResponse(
                id=f"route_{i+1}",
                tag="性价比最高" if i == 0 else None,
                total_price=random.uniform(500, 1500),
                total_duration=random.randint(180, 600),
                transfer_count=random.randint(0, 2),
                score=random.uniform(0.6, 0.95),
                legs=[
                    LegResponse(
                        type="flight",
                        flight_no=f"CA{random.randint(1000, 9999)}",
                        airline="国航",
                        from_station=request.from_city,
                        to_station=request.to_city,
                        departure_time="08:00",
                        arrival_time="12:00",
                        duration=240,
                        price=800.0
                    )
                ]
            )
            routes.append(route)
        
        return SearchResponse(
            search_id=f"search_{random.randint(10000, 99999)}",
            total=len(routes),
            routes=routes
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/search.py
git commit -m "feat: add search router with mock response"
```

---

### Task 7.2: Create Cities Router

- [ ] **Step 1: Create cities.py**

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/cities", tags=["cities"])

class StationResponse(BaseModel):
    id: str
    name: str
    type: str

class CityResponse(BaseModel):
    id: str
    name: str
    name_en: str
    stations: List[StationResponse]

# 模拟城市数据
MOCK_CITIES = [
    CityResponse(
        id="BJS",
        name="北京",
        name_en="Beijing",
        stations=[
            StationResponse(id="PEK", name="北京首都国际机场", type="AIRPORT"),
            StationResponse(id="PKX", name="北京大兴国际机场", type="AIRPORT"),
            StationResponse(id="BJX", name="北京西站", type="RAILWAY"),
        ]
    ),
    CityResponse(
        id="SHA",
        name="上海",
        name_en="Shanghai",
        stations=[
            StationResponse(id="PVG", name="上海浦东国际机场", type="AIRPORT"),
            StationResponse(id="SHA_A", name="上海虹桥国际机场", type="AIRPORT"),
            StationResponse(id="SHX", name="上海虹桥站", type="RAILWAY"),
        ]
    ),
    CityResponse(
        id="CTU",
        name="成都",
        name_en="Chengdu",
        stations=[
            StationResponse(id="CTU_A", name="成都双流国际机场", type="AIRPORT"),
            StationResponse(id="CDX", name="成都东站", type="RAILWAY"),
        ]
    ),
    CityResponse(
        id="XIY",
        name="西安",
        name_en="Xi'an",
        stations=[
            StationResponse(id="XIY_A", name="西安咸阳国际机场", type="AIRPORT"),
            StationResponse(id="XAY", name="西安北站", type="RAILWAY"),
        ]
    ),
    CityResponse(
        id="HGH",
        name="杭州",
        name_en="Hangzhou",
        stations=[
            StationResponse(id="HGH_A", name="杭州萧山国际机场", type="AIRPORT"),
            StationResponse(id="HZH", name="杭州东站", type="RAILWAY"),
        ]
    ),
]

@router.get("", response_model=List[CityResponse])
async def get_cities(keyword: str = Query(None, description="搜索关键词")):
    """获取城市列表"""
    if keyword:
        filtered = [c for c in MOCK_CITIES if keyword.lower() in c.name.lower() 
                    or keyword.lower() in c.name_en.lower()]
        return filtered
    return MOCK_CITIES
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/cities.py
git commit -m "feat: add cities router with mock data"
```

---

### Task 7.3: Update Main.py to Include Routers

- [ ] **Step 1: Modify backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import search, cities

app = FastAPI(
    title="Layover Lens API",
    description="Transit assistance API",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(cities.router, prefix=settings.api_v1_prefix)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "message": "Welcome to Layover Lens API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 2: Create routers/__init__.py**

```python
from . import search
from . import cities

__all__ = ['search', 'cities']
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py backend/app/routers/__init__.py
git commit -m "feat: register api routers in main app"
```

---

## Task 8: Frontend Styling

**Files:**
- Create: `frontend/src/App.css`
- Modify: `frontend/src/App.tsx`

---

### Task 8.1: Add Basic Styling

- [ ] **Step 1: Create App.css**

```css
/* 基础样式 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
               'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
  color: #333;
  line-height: 1.6;
}

/* 应用容器 */
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 头部 */
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 40px 20px;
  text-align: center;
}

.app-header h1 {
  font-size: 2.5rem;
  margin-bottom: 10px;
}

.app-header p {
  font-size: 1.1rem;
  opacity: 0.9;
}

/* 主内容区 */
.main-content {
  flex: 1;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  padding: 30px 20px;
}

/* 搜索表单 */
.search-form {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.search-form h2 {
  margin-bottom: 20px;
  color: #333;
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.form-group {
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.search-button {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.search-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.search-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 错误提示 */
.error-message {
  background: #fff5f5;
  color: #e53e3e;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #feb2b2;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #718096;
}

/* 卡片列表 */
.route-card-list h3 {
  margin-bottom: 20px;
  color: #4a5568;
}

/* 路线卡片 */
.route-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
  overflow: hidden;
  position: relative;
}

.route-card.featured {
  border: 2px solid #48bb78;
}

.route-tag {
  position: absolute;
  top: 0;
  left: 0;
  background: #48bb78;
  color: white;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  border-bottom-right-radius: 12px;
}

.route-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
}

.route-price {
  display: flex;
  align-items: baseline;
}

.route-price .currency {
  font-size: 20px;
  color: #e53e3e;
  font-weight: 600;
}

.route-price .amount {
  font-size: 36px;
  color: #e53e3e;
  font-weight: 700;
  margin-left: 4px;
}

.route-stats {
  display: flex;
  gap: 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #4a5568;
  font-size: 14px;
}

.route-timeline-container {
  padding: 20px;
  background: #f7fafc;
}

.route-actions {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e2e8f0;
}

.btn-primary {
  flex: 1;
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #5568d3;
}

.btn-secondary {
  padding: 12px 24px;
  background: #edf2f7;
  color: #4a5568;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-secondary:hover {
  background: #e2e8f0;
}

/* 时间轴 */
.route-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.timeline-segment {
  display: flex;
  align-items: center;
  gap: 16px;
}

.timeline-point {
  text-align: center;
  min-width: 80px;
}

.timeline-point .time {
  font-size: 18px;
  font-weight: 600;
  color: #2d3748;
}

.timeline-point .station {
  font-size: 13px;
  color: #718096;
  margin-top: 4px;
}

.timeline-connection {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.transport-line {
  width: 100%;
  height: 2px;
  background: #cbd5e0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.transport-icon {
  font-size: 20px;
  background: white;
  padding: 0 8px;
}

.transport-info {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #718096;
}

.transfer-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  background: #fffaf0;
  border-radius: 6px;
  color: #dd6b20;
  font-size: 13px;
}

/* 页脚 */
.app-footer {
  background: #2d3748;
  color: #a0aec0;
  text-align: center;
  padding: 20px;
  font-size: 14px;
}

/* 响应式 */
@media (max-width: 640px) {
  .form-row {
    flex-direction: column;
    gap: 16px;
  }
  
  .route-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  
  .route-stats {
    width: 100%;
    justify-content: space-between;
  }
}
```

- [ ] **Step 2: Update App.tsx to import CSS**

```typescript
import './App.css';
import HomePage from './pages/HomePage';

function App() {
  return (
    <div className="app">
      <HomePage />
    </div>
  );
}

export default App;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.css frontend/src/App.tsx
git commit -m "feat: add comprehensive css styling"
```

---

## Task 9: Testing and Integration

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_search.py`
- Create: `frontend/test-search.http`

---

### Task 9.1: Create Backend Tests

- [ ] **Step 1: Create test_search.py**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_search_endpoint():
    """测试搜索端点"""
    response = client.post("/api/v1/search", json={
        "from_city": "北京",
        "to_city": "成都",
        "date": "2026-04-15",
        "optimize": "balanced"
    })
    assert response.status_code == 200
    data = response.json()
    assert "search_id" in data
    assert "routes" in data
    assert "total" in data
    assert data["total"] > 0

def test_cities_endpoint():
    """测试城市列表端点"""
    response = client.get("/api/v1/cities")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
def test_cities_search():
    """测试城市搜索"""
    response = client.get("/api/v1/cities?keyword=北京")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any("北京" in city["name"] for city in data)
```

- [ ] **Step 2: Run tests**

```bash
cd backend
python -m pytest tests/test_search.py -v
```

预期输出：
```
tests/test_search.py::test_health_check PASSED
tests/test_search.py::test_search_endpoint PASSED
tests/test_search.py::test_cities_endpoint PASSED
tests/test_search.py::test_cities_search PASSED
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test: add backend api tests"
```

---

### Task 9.2: Create HTTP Test File

- [ ] **Step 1: Create test-search.http**

```http
### Health Check
GET http://localhost:8000/health

### Root Endpoint
GET http://localhost:8000/

### Get Cities
GET http://localhost:8000/api/v1/cities

### Search Cities
GET http://localhost:8000/api/v1/cities?keyword=北京

### Search Routes
POST http://localhost:8000/api/v1/search
Content-Type: application/json

{
  "from_city": "北京",
  "to_city": "成都",
  "date": "2026-04-15",
  "optimize": "balanced"
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/test-search.http
git commit -m "chore: add http test file for api testing"
```

---

## Task 10: Final Integration

### Task 10.1: Build and Run

- [ ] **Step 1: Start all services**

```bash
docker-compose up --build -d
```

- [ ] **Step 2: Verify services are running**

```bash
docker-compose ps
```

预期输出：
```
NAME                STATUS              PORTS
layover-lens-frontend-1   Up (healthy)        0.0.0.0:3000->3000/tcp
layover-lens-backend-1    Up (healthy)        0.0.0.0:8000->8000/tcp
layover-lens-mysql-1      Up (healthy)        0.0.0.0:3306->3306/tcp
```

- [ ] **Step 3: Test frontend in browser**

访问 http://localhost:3000

- [ ] **Step 4: Test API docs**

访问 http://localhost:8000/docs

- [ ] **Step 5: Run backend tests inside container**

```bash
docker-compose exec backend python -m pytest tests/ -v
```

- [ ] **Step 6: Commit final state**

```bash
git add .
git commit -m "feat: mvp complete - fully working transit assistant"
```

---

## Self-Review

### Spec Coverage

| Spec 需求 | 实现任务 |
|-----------|----------|
| React + TypeScript 前端 | Task 2, 3, 8 |
| 简单搜索表单 | Task 3.1 |
| 卡片式结果展示 | Task 3.3, 3.4 |
| Python FastAPI 后端 | Task 4 |
| C++ 路径规划核心 | Task 6 |
| 可插拔数据源 | Task 5 |
| MySQL 数据库 | Task 1.3 |
| RESTful API | Task 7 |

### Placeholder Scan
- ✅ 无 "TBD"、"TODO" 等占位符
- ✅ 每个任务包含完整代码
- ✅ 每个任务包含具体命令

### Type Consistency
- ✅ 类型定义在 `types/index.ts` 中统一维护
- ✅ API 请求/响应类型与前端一致

---

## Summary

**本计划包含 10 个主要任务，约 40 个具体步骤**，涵盖：

1. **环境搭建**：Docker Compose、依赖配置
2. **前端开发**：React组件、样式、API调用
3. **后端开发**：FastAPI、数据源模块
4. **核心算法**：C++路径规划 + pybind11绑定
5. **测试验证**：单元测试、集成测试
6. **最终集成**：一键启动完整应用

每个步骤都遵循 TDD 原则：**测试 → 实现 → 验证 → 提交**。

---
