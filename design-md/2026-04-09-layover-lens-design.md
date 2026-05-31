# 中转助手（Layover Lens）设计文档

**版本**: 1.0  
**日期**: 2026-04-09  
**作者**: Domin1c

---

## 1. 系统概述

### 1.1 项目背景

当前市场上缺乏有效的中转方案搜索工具。用户从城市A前往城市B时，往往面临以下痛点：
- 直飞价格过高
- 想顺路游览其他城市但不知如何规划
- 时间灵活但找不到最优组合

### 1.2 核心目标

开发一款全栈中转助手应用，帮助用户发现从城市A到城市B的最佳中转方案，支持飞机与火车之间的灵活组合。

### 1.3 核心功能

1. **智能搜索**：支持简单搜索、高级搜索、智能助手三种模式
2. **多维度路径规划**：支持价格优先、时间优先、最少换乘、综合评分四种优化目标
3. **可视化结果展示**：卡片式布局，内含时间轴可视化
4. **可插拔数据源**：支持模拟数据 → 爬虫数据 → 第三方API的渐进式演进

### 1.4 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | React + TypeScript | 浏览器端应用 |
| API网关 | Python FastAPI | 统一入口、路由分发 |
| 路径规划 | C++ | 高性能图算法引擎 |
| 数据/AI | Python | 数据源适配、智能助手 |
| 数据库 | MySQL | 城市、站点、路线、价格数据 |

---

## 2. 系统架构

### 2.1 整体架构

采用**模块化设计（Modular Monolith）**：

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                      │
│              React + TypeScript (浏览器)                      │
├─────────────────────────────────────────────────────────────┤
│                        API网关层                             │
│         Python FastAPI - 统一入口、路由、认证                   │
├─────────────────────────────────────────────────────────────┤
│                      核心业务模块                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Path Planner│  │ Data Source │  │ AI Assistant│         │
│  │    (C++)     │  │  (Python)   │  │  (Python)   │         │
│  │              │  │             │  │             │         │
│  │ 图算法引擎    │  │  Mock/爬虫  │  │ 对话引导     │         │
│  │ Dijkstra/A* │  │  /API适配器  │  │ 意图识别     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                        数据存储层 (MySQL)                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块通信方式

- **C++ 与 Python**：通过 pybind11 绑定或 gRPC 本地调用
- **模块间**：通过定义好的接口协议通信，确保各模块可独立替换

### 2.3 架构优势

1. **开发快速**：初期单体应用，减少运维复杂度
2. **性能保障**：路径规划核心用C++实现，满足性能要求
3. **易于演进**：模块化边界清晰，后期可拆分为微服务
4. **数据源灵活**：Data Source模块支持无缝切换实现方式

---

## 3. 功能模块详细设计

### 3.1 前端模块 (React + TypeScript)

#### 3.1.1 目录结构

```
/src
├── components/
│   ├── SearchForm/          # 搜索表单（简单+高级模式）
│   │   ├── SimpleForm.tsx
│   │   └── AdvancedForm.tsx
│   ├── ResultCards/         # 卡片列表组件
│   │   ├── RouteCard.tsx
│   │   └── CardList.tsx
│   ├── Timeline/            # 时间轴可视化组件
│   ├── AiChat/              # 智能助手对话框
│   └── common/              # 通用组件 (Button, Input, Loading)
├── pages/
│   ├── Home/                # 首页（搜索入口）
│   ├── Results/             # 结果展示页
│   └── Detail/              # 方案详情页
├── services/
│   └── api.ts               # API调用封装
├── hooks/                   # 自定义React Hooks
├── types/                   # TypeScript类型定义
└── utils/                   # 工具函数
```

#### 3.1.2 核心页面流程

**首页 (Home)**
- 简洁的搜索入口
- 默认展示简单搜索：起点、终点、日期
- 可切换至高级搜索（展开更多筛选条件）
- 智能助手入口（悬浮按钮或独立区域）

**结果页 (Results)**
- 顶部：搜索条件摘要 + 修改按钮
- 筛选栏：优化目标切换（价格/时间/换乘/综合）
- 结果区：垂直排列的卡片列表
- 每个卡片：价格、耗时、换乘次数、可视化时间轴、预订按钮

#### 3.1.3 关键技术选型

- **状态管理**：React Query (TanStack Query) - 管理服务端状态
- **样式方案**：Tailwind CSS 或 Styled Components
- **UI组件库**：Ant Design 或 Material-UI
- **性能优化**：
  - 虚拟列表 (react-window) 处理大量结果
  - 防抖处理搜索输入
  - 图片懒加载

### 3.2 Path Planner 模块 (C++)

#### 3.2.1 核心职责

高性能路径规划，支持多目标优化的中转方案搜索。

#### 3.2.2 数据结构

```cpp
// 交通方式枚举
enum TransportType { FLIGHT, TRAIN };

// 节点：城市/站点
struct Node {
    string id;              // 唯一标识
    string name;            // 显示名称
    string city_id;         // 所属城市
    double lat, lon;        // 经纬度
    TransportType type;     // 机场/火车站
    vector<Edge> edges;     // 邻接边（出站可达的线路）
};

// 边：交通线路
struct Edge {
    string to_node_id;      // 目的地节点ID
    TransportType type;     // 航班/火车
    int duration;           // 行程时长（分钟）
    double base_price;      // 基础票价
    string schedule_id;     // 关联时刻表ID
    string carrier;         // 承运商（航司/铁路局）
};

// 行程段
struct Leg {
    string from_node;       // 出发站点
    string to_node;         // 到达站点
    TransportType type;     // 交通方式
    DateTime departure;     // 出发时间
    DateTime arrival;       // 到达时间
    double price;           // 票价
    string flight_no;       // 航班号/车次号
};

// 完整路径方案
struct RoutePlan {
    string id;                      // 方案ID
    vector<Leg> legs;               // 行程段列表
    int total_duration;             // 总耗时（分钟）
    double total_price;             // 总价格
    int transfer_count;             // 换乘次数
    double score;                   // 综合评分
    
    // 便捷方法
    DateTime get_departure() const { return legs.front().departure; }
    DateTime get_arrival() const { return legs.back().arrival; }
};
```

#### 3.2.3 算法设计

**多目标路径规划算法**

基于改进的 Dijkstra 算法：

```cpp
vector<RoutePlan> find_routes(
    const string& from_city,
    const string& to_city,
    const DateTime& date,
    OptimizeTarget target,      // 优化目标
    const SearchConstraints& constraints
);
```

**优化目标处理**：

| 目标 | 算法策略 |
|------|----------|
| 最低价格 | 按总价格排序，优先队列以价格为key |
| 最短时间 | 按总耗时排序，优先队列以时间为key |
| 最少换乘 | 限制最大换乘次数，BFS搜索 |
| 综合评分 | 多目标加权：score = w1/price + w2/time + w3/(transfer+1) |

**剪枝策略**：
- 中转停留时间超过最大值（如8小时）丢弃
- 换乘次数超过限制（如3次）丢弃
- 总价格超过直飞价格1.5倍的方案降级排序

#### 3.2.4 Python 绑定

使用 pybind11 暴露 C++ 接口给 Python：

```cpp
// planner_binding.cpp
#include <pybind11/pybind11.h>
#include "planner.h"

namespace py = pybind11;

PYBIND11_MODULE(route_planner, m) {
    m.doc() = "Route planning engine";
    
    py::class_<RoutePlan>(m, "RoutePlan")
        .def_readonly("total_duration", &RoutePlan::total_duration)
        .def_readonly("total_price", &RoutePlan::total_price)
        .def_readonly("transfer_count", &RoutePlan::transfer_count)
        .def_readonly("score", &RoutePlan::score);
    
    m.def("find_routes", &find_routes, "Find optimal routes");
}
```

### 3.3 Data Source 模块 (Python)

#### 3.3.1 设计模式：策略模式

支持多种数据源实现，运行时通过配置切换。

#### 3.3.2 抽象基类

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import date

@dataclass
class Flight:
    flight_no: str
    airline: str
    from_airport: str
    to_airport: str
    departure: datetime
    arrival: datetime
    price: float
    seats_available: int

@dataclass
class Train:
    train_no: str
    train_type: str  # G/D/K/T/etc
    from_station: str
    to_station: str
    departure: datetime
    arrival: datetime
    price: float
    seats_available: int

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
    def get_flight_price(
        self, 
        flight_no: str, 
        travel_date: date,
        seat_class: str = "economy"
    ) -> Optional[float]:
        """获取航班实时价格"""
        pass
    
    @abstractmethod
    def get_train_price(
        self, 
        train_no: str, 
        travel_date: date,
        seat_type: str = "second_class"
    ) -> Optional[float]:
        """获取火车实时价格"""
        pass
```

#### 3.3.3 具体实现

**1. MockAdapter（初期使用）**

```python
class MockAdapter(DataSourceBase):
    """模拟数据适配器 - 用于开发和测试"""
    
    def __init__(self):
        self.cities = self._load_mock_cities()
        self.routes = self._load_mock_routes()
    
    def search_flights(self, from_code, to_code, travel_date):
        # 从预定义数据中生成随机航班
        base_price = self._calculate_base_price(from_code, to_code)
        flights = []
        for i in range(random.randint(3, 8)):
            flights.append(Flight(
                flight_no=f"CA{random.randint(1000, 9999)}",
                airline=random.choice(["国航", "东航", "南航"]),
                from_airport=from_code,
                to_airport=to_code,
                departure=self._random_time(travel_date),
                arrival=self._random_time(travel_date),
                price=base_price * random.uniform(0.8, 1.5),
                seats_available=random.randint(5, 200)
            ))
        return flights
    
    # ... 其他方法实现
```

**2. ScraperAdapter（中期使用）**

```python
class ScraperAdapter(DataSourceBase):
    """爬虫数据适配器 - 从各大平台抓取"""
    
    def __init__(self):
        self.xiecheng_scraper = XiechengScraper()
        self.qunaer_scraper = QunaerScraper()
        self._12306_scraper = Train12306Scraper()
    
    def search_flights(self, from_code, to_code, travel_date):
        # 聚合多个平台的爬虫结果
        results = []
        results.extend(self.xiecheng_scraper.search(from_code, to_code, travel_date))
        results.extend(self.qunaer_scraper.search(from_code, to_code, travel_date))
        return self._deduplicate(results)
    
    # ... 其他方法实现
```

**3. ApiAdapter（后期使用）**

```python
class ApiAdapter(DataSourceBase):
    """第三方API适配器 - 官方/商业接口"""
    
    def __init__(self):
        self.flight_api = FlightApiClient(api_key=Config.FLIGHT_API_KEY)
        self.train_api = TrainApiClient(api_key=Config.TRAIN_API_KEY)
    
    def search_flights(self, from_code, to_code, travel_date):
        return self.flight_api.search(from_code, to_code, travel_date)
    
    # ... 其他方法实现
```

#### 3.3.4 工厂模式创建实例

```python
# data_source/factory.py
from enum import Enum

class DataSourceType(Enum):
    MOCK = "mock"
    SCRAPER = "scraper"
    API = "api"

def create_data_source(source_type: DataSourceType = None) -> DataSourceBase:
    """工厂函数 - 根据配置创建对应的数据源实例"""
    if source_type is None:
        source_type = DataSourceType(Config.DATA_SOURCE)
    
    if source_type == DataSourceType.MOCK:
        return MockAdapter()
    elif source_type == DataSourceType.SCRAPER:
        return ScraperAdapter()
    elif source_type == DataSourceType.API:
        return ApiAdapter()
    else:
        raise ValueError(f"Unknown data source type: {source_type}")
```

### 3.4 AI Assistant 模块 (Python)

#### 3.4.1 核心职责

通过自然语言对话，引导用户完成搜索条件的收集。

#### 3.4.2 工作流程

```
用户输入 → 意图识别 → 槽位填充 → 检查完整性 → 生成回复
              ↓
         更新对话状态
```

#### 3.4.3 槽位定义

```python
@dataclass
class SearchSlots:
    """搜索条件槽位"""
    from_city: Optional[str] = None      # 出发城市
    to_city: Optional[str] = None        # 目的城市
    date: Optional[date] = None          # 出发日期
    prefer_cheap: bool = False           # 偏好低价
    prefer_fast: bool = False            # 偏好快速
    prefer_fewer_transfer: bool = False  # 偏好少换乘
    flexible_time: bool = False          # 时间灵活
    max_transfer_time: int = 480         # 最大中转时间（分钟）
    
    def is_complete(self) -> bool:
        """检查必要信息是否已收集"""
        return all([self.from_city, self.to_city, self.date])
```

#### 3.4.4 意图识别

**方案A：规则匹配（初期）**

```python
class RuleBasedIntentClassifier:
    """基于规则的意图分类器"""
    
    PATTERNS = {
        "set_from_city": [
            r"从(.+?)[出发|去|到]",
            r"[我|咱们][在|从](.+?)[出发]",
        ],
        "set_to_city": [
            r"[到|去](.+?)$",
            r"[想去|要去](.+?)",
        ],
        "set_date": [
            r"(明天|后天|下周[一二三四五六日]|\d{1,2}月\d{1,2}日)",
        ],
        # ... 更多模式
    }
    
    def classify(self, user_input: str) -> Tuple[str, Optional[str]]:
        """返回(意图, 提取的值)"""
        for intent, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if match := re.search(pattern, user_input):
                    return intent, match.group(1)
        return "unknown", None
```

**方案B：LLM API（后期）**

```python
class LLMIntentClassifier:
    """基于大语言模型的意图分类器"""
    
    SYSTEM_PROMPT = """
    你是一个中转助手。请分析用户输入，提取以下信息：
    - 出发城市
    - 目的城市
    - 出发日期
    - 用户偏好（价格/时间/换乘次数）
    
    以JSON格式返回：
    {"intent": "set_from_city", "value": "北京", "slots": {...}}
    """
    
    def classify(self, user_input: str, current_slots: SearchSlots) -> dict:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"当前已收集信息: {current_slots}\n用户输入: {user_input}"}
            ]
        )
        return json.loads(response.choices[0].message.content)
```

#### 3.4.5 对话管理器

```python
class DialogueManager:
    """对话管理器 - 维护对话状态，生成回复"""
    
    def __init__(self):
        self.intent_classifier = RuleBasedIntentClassifier()  # 或 LLMIntentClassifier()
        self.sessions: Dict[str, SearchSlots] = {}  # 会话状态存储
    
    def process_message(self, session_id: str, user_input: str) -> str:
        """处理用户消息，返回AI回复"""
        
        # 获取或创建会话
        if session_id not in self.sessions:
            self.sessions[session_id] = SearchSlots()
        slots = self.sessions[session_id]
        
        # 意图识别
        intent, value = self.intent_classifier.classify(user_input)
        
        # 槽位填充
        self._fill_slot(slots, intent, value)
        
        # 生成回复
        if slots.is_complete():
            return self._generate_search_confirmation(slots)
        else:
            return self._generate_clarification_request(slots)
    
    def _fill_slot(self, slots: SearchSlots, intent: str, value: str):
        """根据意图填充槽位"""
        if intent == "set_from_city":
            slots.from_city = value
        elif intent == "set_to_city":
            slots.to_city = value
        elif intent == "set_date":
            slots.date = self._parse_date(value)
        # ...
    
    def _generate_clarification_request(self, slots: SearchSlots) -> str:
        """生成澄清请求"""
        if not slots.from_city:
            return "请问您从哪里出发？"
        elif not slots.to_city:
            return f"好的，从{slots.from_city}出发。您要去哪里？"
        elif not slots.date:
            return f"明白了，从{slots.from_city}到{slots.to_city}。请问您计划什么时候出发？"
        # ...
    
    def _generate_search_confirmation(self, slots: SearchSlots) -> str:
        """生成搜索确认"""
        return f"好的，我为您搜索从{slots.from_city}到{slots.to_city}，{slots.date}出发的中转方案。"
```

---

## 4. 数据模型设计

### 4.1 数据库选型

**MySQL 8.0** - 关系型数据库，适合结构化查询和复杂关联。

### 4.2 表结构设计

```sql
-- 城市表
CREATE TABLE cities (
    id VARCHAR(10) PRIMARY KEY COMMENT '城市代码，如 BJS',
    name VARCHAR(50) NOT NULL COMMENT '城市名称',
    name_en VARCHAR(50) COMMENT '英文名称',
    country VARCHAR(50) DEFAULT 'CN',
    latitude DECIMAL(10, 8) COMMENT '纬度',
    longitude DECIMAL(11, 8) COMMENT '经度',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 交通站点表（机场、火车站）
CREATE TABLE stations (
    id VARCHAR(10) PRIMARY KEY COMMENT '站点代码',
    name VARCHAR(100) NOT NULL COMMENT '站点名称',
    city_id VARCHAR(10) NOT NULL COMMENT '所属城市',
    type ENUM('AIRPORT', 'RAILWAY') NOT NULL COMMENT '站点类型',
    iata_code VARCHAR(3) COMMENT 'IATA代码（仅机场）',
    station_code VARCHAR(10) COMMENT '铁路站点代码',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 路线表（航班/车次基础信息）
CREATE TABLE routes (
    id VARCHAR(20) PRIMARY KEY COMMENT '路线ID',
    route_no VARCHAR(20) NOT NULL COMMENT '航班号/车次号',
    carrier VARCHAR(50) NOT NULL COMMENT '承运商',
    from_station VARCHAR(10) NOT NULL,
    to_station VARCHAR(10) NOT NULL,
    type ENUM('FLIGHT', 'TRAIN') NOT NULL,
    distance_km INT COMMENT '距离（公里）',
    duration_base INT COMMENT '基础时长（分钟）',
    seat_classes JSON COMMENT '座位类型配置',
    schedule_type ENUM('DAILY', 'WEEKLY', 'IRREGULAR') DEFAULT 'DAILY',
    valid_from DATE,
    valid_until DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_station) REFERENCES stations(id),
    FOREIGN KEY (to_station) REFERENCES stations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 时刻表（具体到某天的班次）
CREATE TABLE schedules (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    route_id VARCHAR(20) NOT NULL,
    schedule_date DATE NOT NULL,
    departure_time TIME NOT NULL,
    arrival_time TIME NOT NULL,
    status ENUM('SCHEDULED', 'DELAYED', 'CANCELLED') DEFAULT 'SCHEDULED',
    aircraft_type VARCHAR(20) COMMENT '机型（仅航班）',
    train_type VARCHAR(10) COMMENT '列车类型G/D/K（仅火车）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (route_id) REFERENCES routes(id),
    UNIQUE KEY uk_route_date (route_id, schedule_date, departure_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 价格表
CREATE TABLE prices (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    schedule_id BIGINT NOT NULL,
    seat_class VARCHAR(20) NOT NULL COMMENT '座位等级',
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'CNY',
    seats_available INT DEFAULT 0,
    source ENUM('MOCK', 'SCRAPER', 'API') DEFAULT 'MOCK',
    expires_at TIMESTAMP COMMENT '价格过期时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedules(id),
    UNIQUE KEY uk_price (schedule_id, seat_class)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 中转方案缓存表（热门路线预计算）
CREATE TABLE route_plan_cache (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    from_city VARCHAR(10) NOT NULL,
    to_city VARCHAR(10) NOT NULL,
    travel_date DATE NOT NULL,
    optimize_target VARCHAR(20) NOT NULL,
    plan_data JSON NOT NULL COMMENT '方案数据（JSON数组）',
    hit_count INT DEFAULT 0 COMMENT '命中次数',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_city) REFERENCES cities(id),
    FOREIGN KEY (to_city) REFERENCES cities(id),
    UNIQUE KEY uk_plan (from_city, to_city, travel_date, optimize_target),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 搜索历史表（用于分析优化）
CREATE TABLE search_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    from_city VARCHAR(10),
    to_city VARCHAR(10),
    travel_date DATE,
    optimize_target VARCHAR(20),
    results_count INT,
    response_time_ms INT COMMENT '响应时间（毫秒）',
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 5. API 接口设计

### 5.1 RESTful API 规范

**Base URL**: `/api/v1`

### 5.2 接口列表

#### 搜索相关

**POST /search**

请求体：
```json
{
  "from_city": "北京",
  "to_city": "成都", 
  "date": "2026-04-15",
  "optimize": "price",
  "filters": {
    "max_transfer": 2,
    "max_transfer_time": 480,
    "transport_types": ["flight", "train"]
  }
}
```

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "search_id": "search_abc123",
    "total": 15,
    "routes": [
      {
        "id": "route_1",
        "tag": "性价比最高",
        "total_price": 650.00,
        "total_duration": 510,
        "transfer_count": 1,
        "legs": [
          {
            "type": "flight",
            "flight_no": "CA1234",
            "airline": "国航",
            "from": {
              "station": "北京首都T3",
              "time": "08:00"
            },
            "to": {
              "station": "西安咸阳T2", 
              "time": "10:15"
            },
            "duration": 135,
            "price": 450.00
          },
          {
            "type": "train",
            "train_no": "G1234",
            "train_type": "G",
            "from": {
              "station": "西安北",
              "time": "13:00"
            },
            "to": {
              "station": "成都东",
              "time": "18:30"
            },
            "transfer_time": 165,
            "duration": 330,
            "price": 200.00
          }
        ]
      }
    ]
  }
}
```

#### 城市/站点查询

**GET /cities?keyword=北京**

响应：
```json
{
  "code": 0,
  "data": [
    {"id": "BJS", "name": "北京", "name_en": "Beijing", "stations": [...]}
  ]
}
```

#### AI 助手对话

**POST /chat**

请求体：
```json
{
  "session_id": "sess_xyz789",
  "message": "我想从北京去成都"
}
```

响应：
```json
{
  "code": 0,
  "data": {
    "reply": "好的，从北京出发。请问您计划什么时候去成都？",
    "slots": {
      "from_city": "北京",
      "to_city": "成都",
      "date": null
    },
    "is_complete": false
  }
}
```

---

## 6. 部署方案

### 6.1 开发环境

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATA_SOURCE=mock
      
  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=devpassword
      - MYSQL_DATABASE=layover_lens
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      
volumes:
  mysql_data:
```

### 6.2 生产环境（初期）

**单服务器部署**：
- 前端：Nginx 静态托管 + CDN
- 后端：Gunicorn + FastAPI
- C++ 模块：编译为共享库，与 Python 同机部署
- MySQL：单机部署，定期备份

**目录结构**：
```
/opt/layover-lens/
├── frontend/          # 构建后的 React 静态文件
├── backend/           # Python 后端代码
│   ├── api/
│   ├── data_source/
│   ├── ai_assistant/
│   └── planner.so     # C++ 编译的共享库
├── config/            # 配置文件
└── logs/              # 日志文件
```

---

## 7. 开发阶段规划

### 阶段一：MVP（4-6周）

**目标**：可运行的基础版本

**范围**：
- 前端：简单搜索 + 卡片结果展示
- 后端：Mock 数据源 + C++ 路径规划（基础算法）
- 数据库：基础表结构 + 模拟数据

**可交付**：
- 用户可输入起终点，获取 3-5 个中转方案

### 阶段二：功能完善（3-4周）

**目标**：完整的核心功能

**范围**：
- 高级搜索筛选
- AI 助手（规则版）
- 方案详情页
- 响应式优化

### 阶段三：数据源升级（4-6周）

**目标**：真实数据接入

**范围**：
- 实现爬虫模块
- 价格数据自动更新
- 缓存策略优化

### 阶段四：性能优化（2-3周）

**目标**：支持更大规模

**范围**：
- 路径规划算法优化
- 数据库索引优化
- 引入 Redis 缓存

---

## 8. 附录

### 8.1 术语表

| 术语 | 说明 |
|------|------|
| Leg | 行程段，一次直达交通（如一个航班） |
| Route | 路线，从A到B的完整方案，可能包含多个 Leg |
| Transfer | 换乘，从一段交通切换到另一段 |
| Layover | 中转停留，两段交通之间的等待时间 |
| IATA | 国际航空运输协会，机场三字代码 |

### 8.2 参考资料

- Dijkstra 算法：https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm
- FastAPI 文档：https://fastapi.tiangolo.com/
- pybind11 文档：https://pybind11.readthedocs.io/

---

**文档结束**
