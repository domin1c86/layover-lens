# Layover Lens 中转助手 - 执行计划

> 本文档包含从当前状态开始的详细实施步骤  
> 设计文档：`docs/superpowers/specs/2026-04-09-layover-lens-design.md`  
> 详细实施计划：`docs/superpowers/plans/2026-04-09-layover-lens-mvp.md`

---

## 当前状态

✅ 设计阶段已完成  
⬜ 开发阶段未开始  

---

## 阶段一：环境搭建（预计 1-2 小时）

### Step 1.1: 创建项目结构

```bash
# 创建目录结构
mkdir -p frontend/src/{components/{SearchForm,ResultCards,Timeline},pages,services,types}
mkdir -p backend/app/{routers,services,data_source}
mkdir -p backend/planner
mkdir -p backend/tests
mkdir -p database
```

### Step 1.2: 配置 Docker Compose

创建 `docker-compose.yml`：

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

### Step 1.3: 初始化前端项目

在 `frontend/` 目录下创建：

**package.json**
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

**tsconfig.json**
```json
{
  "compilerOptions": {
    "target": "ES2020",
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
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"]
}
```

**vite.config.ts**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000
  }
})
```

### Step 1.4: 初始化后端项目

在 `backend/` 目录下创建：

**requirements.txt**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0
mysql-connector-python==8.3.0
python-dotenv==1.0.0
pytest==8.0.0
httpx==0.26.0
pybind11==2.11.1
```

**Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ cmake libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY planner/ ./planner/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Step 1.5: 初始化数据库

创建 `database/init.sql`（包含城市和站点基础数据）

---

## 阶段二：前端开发（预计 4-6 小时）

### Step 2.1: 类型定义

创建 `frontend/src/types/index.ts`：
- `City`, `Station` 类型
- `Leg`, `RoutePlan` 类型
- `SearchRequest`, `SearchResponse` 类型

### Step 2.2: API 服务层

创建 `frontend/src/services/api.ts`：
- `searchApi.search()` - 搜索接口
- `cityApi.getCities()` - 城市列表接口
- axios 实例配置

### Step 2.3: 搜索表单组件

创建 `frontend/src/components/SearchForm/SimpleSearchForm.tsx`：
- 起点/终点城市输入
- 日期选择
- 优化目标选择（价格/时间/换乘/综合）
- 表单验证

### Step 2.4: 时间轴组件

创建 `frontend/src/components/Timeline/RouteTimeline.tsx`：
- 展示行程段（飞机/火车）
- 出发/到达时间
- 中转停留时间

### Step 2.5: 卡片组件

创建 `frontend/src/components/ResultCards/RouteCard.tsx`：
- 价格展示
- 总耗时/换乘次数
- 时间轴嵌入
- 预订/详情按钮

创建 `frontend/src/components/ResultCards/RouteCardList.tsx`：
- 卡片列表渲染
- 空状态处理

### Step 2.6: 主页

创建 `frontend/src/pages/HomePage.tsx`：
- 页面布局
- 搜索表单 + 结果列表组合
- 加载状态
- 错误处理

### Step 2.7: 样式

创建 `frontend/src/App.css`：
- 搜索表单样式
- 卡片样式
- 时间轴样式
- 响应式布局

---

## 阶段三：后端开发（预计 4-6 小时）

### Step 3.1: FastAPI 基础

创建 `backend/app/main.py`：
- FastAPI 应用实例
- CORS 配置
- 路由注册

创建 `backend/app/config.py`：
- 环境变量配置
- 数据库连接字符串
- 数据源类型配置

### Step 3.2: 数据源模块

创建 `backend/app/data_source/base.py`：
- `DataSourceBase` 抽象类
- `Flight`, `Train` 数据类

创建 `backend/app/data_source/mock_adapter.py`：
- `MockAdapter` 实现
- 生成模拟航班/火车数据

创建 `backend/app/data_source/factory.py`：
- `create_data_source()` 工厂函数
- 单例模式

### Step 3.3: API 路由

创建 `backend/app/routers/search.py`：
- `POST /search` 端点
- 请求/响应模型
- 调用数据源

创建 `backend/app/routers/cities.py`：
- `GET /cities` 端点
- 城市搜索

### Step 3.4: C++ 路径规划器

创建 `backend/planner/planner.h`：
- `PathPlanner` 类声明
- `RoutePlan`, `Leg` 结构体
- 枚举类型定义

创建 `backend/planner/planner.cpp`：
- 图算法实现（Dijkstra/A*）
- 多目标优化
- 剪枝策略

创建 `backend/planner/bindings.cpp`：
- pybind11 绑定代码
- Python 可调用的接口

创建 `backend/planner/CMakeLists.txt`：
- CMake 构建配置
- pybind11 模块编译

### Step 3.5: 编译 C++ 模块

```bash
cd backend/planner
mkdir build && cd build
cmake ..
make
```

---

## 阶段四：集成测试（预计 2 小时）

### Step 4.1: 后端测试

创建 `backend/tests/test_search.py`：
- 健康检查测试
- 搜索接口测试
- 城市接口测试

运行测试：
```bash
cd backend
python -m pytest tests/ -v
```

### Step 4.2: 启动完整环境

```bash
# 构建并启动所有服务
docker-compose up --build -d

# 检查状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### Step 4.3: 手动测试

1. 打开 http://localhost:3000 - 前端页面
2. 输入搜索条件，点击搜索
3. 验证结果卡片展示
4. 打开 http://localhost:8000/docs - API 文档
5. 测试各个端点

---

## 关键命令速查

```bash
# 启动开发环境
docker-compose up -d

# 停止环境
docker-compose down

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker-compose exec backend bash
docker-compose exec frontend sh

# 运行测试
docker-compose exec backend python -m pytest tests/ -v

# 重新构建
docker-compose up --build -d

# 清理数据卷
docker-compose down -v
```

---

## 技术栈参考

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | React + TypeScript | 18 + 5 |
| 构建 | Vite | 5 |
| 后端 | FastAPI | 0.109 |
| 数据库 | MySQL | 8.0 |
| C++ | C++标准 | 17 |
| 绑定 | pybind11 | 2.11 |

---

## 下一步

1. 开始阶段一：创建项目结构和 Docker 配置
2. 验证环境可以正常启动
3. 按顺序完成各阶段开发任务

**如需开始实施，请告诉我从哪个步骤开始。**
