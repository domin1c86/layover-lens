-- 中转助手 - 数据库初始化脚本（扩充版）
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

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
    departure_date DATE NOT NULL COMMENT '出发日期',
    departure_time TIME NOT NULL COMMENT '出发时间',
    arrival_date DATE NOT NULL COMMENT '到达日期',
    arrival_time TIME NOT NULL COMMENT '到达时间',
    price DECIMAL(10, 2) NOT NULL COMMENT '价格',
    duration_minutes INT NOT NULL COMMENT '行程时长(分钟)',
    company VARCHAR(50) COMMENT '航空公司/铁路局',
    flight_train_no VARCHAR(20) COMMENT '航班号/车次',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_station) REFERENCES stations(code),
    FOREIGN KEY (to_station) REFERENCES stations(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='路线表';

-- ============================================
-- 插入城市数据（40个主要城市）
-- ============================================
INSERT INTO cities (code, name, name_en, latitude, longitude) VALUES
-- 一线城市
('BJ', '北京', 'Beijing', 39.9042, 116.4074),
('SH', '上海', 'Shanghai', 31.2304, 121.4737),
('GZ', '广州', 'Guangzhou', 23.1291, 113.2644),
('SZ', '深圳', 'Shenzhen', 22.5431, 114.0579),
-- 新一线城市
('HZ', '杭州', 'Hangzhou', 30.2741, 120.1551),
('NJ', '南京', 'Nanjing', 32.0603, 118.7969),
('CD', '成都', 'Chengdu', 30.5728, 104.0668),
('CQ', '重庆', 'Chongqing', 29.5630, 106.5516),
('WH', '武汉', 'Wuhan', 30.5928, 114.3055),
('XA', '西安', 'Xi''an', 34.3416, 108.9398),
('SU', '苏州', 'Suzhou', 31.2990, 120.5853),
('TJ', '天津', 'Tianjin', 39.0842, 117.2009),
('ZZ', '郑州', 'Zhengzhou', 34.7466, 113.6253),
('CS', '长沙', 'Changsha', 28.2280, 112.9388),
('SY', '沈阳', 'Shenyang', 41.8057, 123.4315),
('QD', '青岛', 'Qingdao', 36.0671, 120.3826),
('NB', '宁波', 'Ningbo', 29.8683, 121.5440),
('DL', '大连', 'Dalian', 38.9140, 121.6147),
('XM', '厦门', 'Xiamen', 24.4798, 118.0894),
('HE', '哈尔滨', 'Harbin', 45.8038, 126.5350),
-- 二线城市
('JN', '济南', 'Jinan', 36.6512, 117.1201),
('HF', '合肥', 'Hefei', 31.8206, 117.2272),
('FZ', '福州', 'Fuzhou', 26.0745, 119.2965),
('NN', '南宁', 'Nanning', 22.8170, 108.3665),
('KMG', '昆明', 'Kunming', 25.0389, 102.7183),
('CC', '长春', 'Changchun', 43.8171, 125.3235),
('SJZ', '石家庄', 'Shijiazhuang', 38.0428, 114.5149),
('GY', '贵阳', 'Guiyang', 26.6470, 106.6302),
('LZ', '兰州', 'Lanzhou', 36.0611, 103.8343),
('WLMQ', '乌鲁木齐', 'Urumqi', 43.8256, 87.6168),
('HUZ', '呼和浩特', 'Hohhot', 40.8414, 111.7519),
('YC', '银川', 'Yinchuan', 38.4872, 106.2309),
('XN', '西宁', 'Xining', 36.6171, 101.7782),
('LS', '拉萨', 'Lhasa', 29.6500, 91.1000),
('TY', '太原', 'Taiyuan', 37.8706, 112.5489),
('NT', '南通', 'Nantong', 32.0146, 120.8372),
('WX', '无锡', 'Wuxi', 31.4912, 120.3119),
('XZ', '徐州', 'Xuzhou', 34.2610, 117.1848),
('BO', '珠海', 'Zhuhai', 22.2710, 113.5670),
('YT', '烟台', 'Yantai', 37.4638, 121.4481),
('SW', '威海', 'Weihai', 37.5091, 122.1206);

-- ============================================
-- 插入站点数据（机场+火车站）
-- ============================================
INSERT INTO stations (code, name, city_code, type) VALUES
-- 北京
('PEK', '首都国际机场T1/T2', 'BJ', 'airport'),
('PKX', '大兴国际机场', 'BJ', 'airport'),
('BJS', '北京南站', 'BJ', 'train_station'),
('BJX', '北京西站', 'BJ', 'train_station'),
('BJN', '北京北站', 'BJ', 'train_station'),
-- 上海
('PVG', '浦东国际机场', 'SH', 'airport'),
('SHA', '虹桥国际机场', 'SH', 'airport'),
('SHH', '上海虹桥站', 'SH', 'train_station'),
('SHS', '上海站', 'SH', 'train_station'),
-- 广州
('CAN', '白云国际机场', 'GZ', 'airport'),
('GZS', '广州南站', 'GZ', 'train_station'),
('GZE', '广州东站', 'GZ', 'train_station'),
-- 深圳
('SZX', '宝安国际机场', 'SZ', 'airport'),
('SZS', '深圳北站', 'SZ', 'train_station'),
('SZA', '深圳站', 'SZ', 'train_station'),
-- 杭州
('HGH', '萧山国际机场', 'HZ', 'airport'),
('HZS', '杭州东站', 'HZ', 'train_station'),
('HZH', '杭州站', 'HZ', 'train_station'),
-- 南京
('NKG', '禄口国际机场', 'NJ', 'airport'),
('NJS', '南京南站', 'NJ', 'train_station'),
('NJH', '南京站', 'NJ', 'train_station'),
-- 成都
('CTU', '天府国际机场', 'CD', 'airport'),
('TFU', '双流国际机场', 'CD', 'airport'),
('CDS', '成都东站', 'CD', 'train_station'),
-- 重庆
('CKG', '江北国际机场', 'CQ', 'airport'),
('CQS', '重庆北站', 'CQ', 'train_station'),
('CQW', '重庆西站', 'CQ', 'train_station'),
-- 武汉
('WUH', '天河国际机场', 'WH', 'airport'),
('WHS', '武汉站', 'WH', 'train_station'),
('WHH', '汉口站', 'WH', 'train_station'),
-- 西安
('XIY', '咸阳国际机场', 'XA', 'airport'),
('XAS', '西安北站', 'XA', 'train_station'),
('XAH', '西安站', 'XA', 'train_station'),
-- 苏州
('SZV', '苏南硕放机场', 'SU', 'airport'),
('SUS', '苏州站', 'SU', 'train_station'),
('SUN', '苏州北站', 'SU', 'train_station'),
-- 天津
('TSN', '滨海国际机场', 'TJ', 'airport'),
('TJS', '天津西站', 'TJ', 'train_station'),
('TJT', '天津站', 'TJ', 'train_station'),
-- 郑州
('CGO', '新郑国际机场', 'ZZ', 'airport'),
('ZZS', '郑州东站', 'ZZ', 'train_station'),
-- 长沙
('CSX', '黄花国际机场', 'CS', 'airport'),
('CSS', '长沙南站', 'CS', 'train_station'),
-- 沈阳
('SHE', '桃仙国际机场', 'SY', 'airport'),
('SYS', '沈阳北站', 'SY', 'train_station'),
('SYH', '沈阳站', 'SY', 'train_station'),
-- 青岛
('TAO', '胶东国际机场', 'QD', 'airport'),
('QDS', '青岛北站', 'QD', 'train_station'),
-- 宁波
('NGB', '栎社国际机场', 'NB', 'airport'),
('NBS', '宁波站', 'NB', 'train_station'),
-- 大连
('DLC', '周水子国际机场', 'DL', 'airport'),
('DLS', '大连北站', 'DL', 'train_station'),
-- 厦门
('XMN', '高崎国际机场', 'XM', 'airport'),
('XMS', '厦门站', 'XM', 'train_station'),
-- 哈尔滨
('HRB', '太平国际机场', 'HE', 'airport'),
('HES', '哈尔滨西站', 'HE', 'train_station'),
-- 济南
('TNA', '遥墙国际机场', 'JN', 'airport'),
('JNS', '济南西站', 'JN', 'train_station'),
-- 合肥
('HFE', '新桥国际机场', 'HF', 'airport'),
('HFS', '合肥南站', 'HF', 'train_station'),
-- 福州
('FOC', '长乐国际机场', 'FZ', 'airport'),
('FZS', '福州站', 'FZ', 'train_station'),
-- 南宁
('NNG', '吴圩国际机场', 'NN', 'airport'),
('NNS', '南宁东站', 'NN', 'train_station'),
-- 昆明
('KMG', '长水国际机场', 'KMG', 'airport'),
('KMGS', '昆明南站', 'KMG', 'train_station'),
-- 长春
('CGQ', '龙嘉国际机场', 'CC', 'airport'),
('CCS', '长春站', 'CC', 'train_station'),
-- 石家庄
('SJW', '正定国际机场', 'SJZ', 'airport'),
('SJZS', '石家庄站', 'SJZ', 'train_station'),
-- 贵阳
('KWE', '龙洞堡国际机场', 'GY', 'airport'),
('GYS', '贵阳北站', 'GY', 'train_station'),
-- 兰州
('LHW', '中川国际机场', 'LZ', 'airport'),
('LZS', '兰州西站', 'LZ', 'train_station'),
-- 乌鲁木齐
('URC', '地窝堡国际机场', 'WLMQ', 'airport'),
('WLMQS', '乌鲁木齐站', 'WLMQ', 'train_station'),
-- 呼和浩特
('HET', '白塔国际机场', 'HUZ', 'airport'),
('HUZS', '呼和浩特东站', 'HUZ', 'train_station'),
-- 银川
('INC', '河东国际机场', 'YC', 'airport'),
('YCS', '银川站', 'YC', 'train_station'),
-- 西宁
('XNN', '曹家堡国际机场', 'XN', 'airport'),
('XNS', '西宁站', 'XN', 'train_station'),
-- 拉萨
('LXA', '贡嘎国际机场', 'LS', 'airport'),
('LSS', '拉萨站', 'LS', 'train_station'),
-- 太原
('TYN', '武宿国际机场', 'TY', 'airport'),
('TYS', '太原南站', 'TY', 'train_station'),
-- 南通
('NTG', '兴东国际机场', 'NT', 'airport'),
('NTS', '南通站', 'NT', 'train_station'),
-- 无锡
('WUX', '硕放国际机场', 'WX', 'airport'),
('WXS', '无锡东站', 'WX', 'train_station'),
-- 徐州
('XUZ', '观音国际机场', 'XZ', 'airport'),
('XZS', '徐州东站', 'XZ', 'train_station'),
-- 珠海
('ZUH', '金湾机场', 'BO', 'airport'),
('BOS', '珠海站', 'BO', 'train_station'),
-- 烟台
('YNT', '蓬莱国际机场', 'YT', 'airport'),
('YTS', '烟台站', 'YT', 'train_station'),
-- 威海
('WEH', '大水泊国际机场', 'SW', 'airport'),
('SWS', '威海站', 'SW', 'train_station');

-- ============================================
-- 插入飞机路线（120条）
