-- 中转助手 - 数据库初始化脚本

CREATE TABLE IF NOT EXISTS cities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL COMMENT '城市代码',
    name VARCHAR(50) NOT NULL COMMENT '城市名称',
    name_en VARCHAR(50) COMMENT '英文名称',
    country VARCHAR(50) DEFAULT '中国' COMMENT '国家',
    latitude DECIMAL(10, 8) COMMENT '纬度',
    longitude DECIMAL(11, 8) COMMENT '经度',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市表';

CREATE TABLE IF NOT EXISTS stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL COMMENT '站点代码',
    name VARCHAR(100) NOT NULL COMMENT '站点名称',
    city_code VARCHAR(10) NOT NULL COMMENT '所属城市',
    type ENUM('airport', 'train_station', 'bus_station') NOT NULL COMMENT '站点类型',
    latitude DECIMAL(10, 8) COMMENT '纬度',
    longitude DECIMAL(11, 8) COMMENT '经度',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_code) REFERENCES cities(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交通站点表';

CREATE TABLE IF NOT EXISTS routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    from_station VARCHAR(20) NOT NULL COMMENT '出发站点',
    to_station VARCHAR(20) NOT NULL COMMENT '到达站点',
    transport_type ENUM('flight', 'train') NOT NULL COMMENT '交通方式',
    departure_time TIME NOT NULL COMMENT '出发时间',
    arrival_time TIME NOT NULL COMMENT '到达时间',
    price DECIMAL(10, 2) NOT NULL COMMENT '价格',
    duration_minutes INT NOT NULL COMMENT '行程时长(分钟)',
    company VARCHAR(50) COMMENT '航空公司/铁路局',
    flight_train_no VARCHAR(20) COMMENT '航班号/车次',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_station) REFERENCES stations(code),
    FOREIGN KEY (to_station) REFERENCES stations(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='路线表';

-- 插入示例城市数据
INSERT INTO cities (code, name, name_en, latitude, longitude) VALUES
('BJ', '北京', 'Beijing', 39.9042, 116.4074),
('SH', '上海', 'Shanghai', 31.2304, 121.4737),
('GZ', '广州', 'Guangzhou', 23.1291, 113.2644),
('SZ', '深圳', 'Shenzhen', 22.5431, 114.0579),
('HZ', '杭州', 'Hangzhou', 30.2741, 120.1551),
('NJ', '南京', 'Nanjing', 32.0603, 118.7969),
('WH', '武汉', 'Wuhan', 30.5928, 114.3055),
('CD', '成都', 'Chengdu', 30.5728, 104.0668),
('XA', '西安', 'Xi\'an', 34.3416, 108.9398),
('CQ', '重庆', 'Chongqing', 29.5630, 106.5516),
('TJ', '天津', 'Tianjin', 39.0842, 117.2009),
('SU', '苏州', 'Suzhou', 31.2990, 120.5853);

-- 插入示例站点数据
INSERT INTO stations (code, name, city_code, type) VALUES
('PEK', '北京首都国际机场', 'BJ', 'airport'),
('PKX', '北京大兴国际机场', 'BJ', 'airport'),
('BJX', '北京西站', 'BJ', 'train_station'),
('BJD', '北京南站', 'BJ', 'train_station'),
('PVG', '上海浦东国际机场', 'SH', 'airport'),
('SHA', '上海虹桥国际机场', 'SH', 'airport'),
('SHH', '上海虹桥站', 'SH', 'train_station'),
('SHS', '上海站', 'SH', 'train_station'),
('CAN', '广州白云国际机场', 'GZ', 'airport'),
('GZS', '广州南站', 'GZ', 'train_station'),
('SZX', '深圳宝安国际机场', 'SZ', 'airport'),
('SZS', '深圳北站', 'SZ', 'train_station'),
('HGH', '杭州萧山国际机场', 'HZ', 'airport'),
('HZS', '杭州东站', 'HZ', 'train_station'),
('NKG', '南京禄口国际机场', 'NJ', 'airport'),
('NJS', '南京南站', 'NJ', 'train_station');
