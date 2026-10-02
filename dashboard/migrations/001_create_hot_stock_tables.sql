CREATE TABLE IF NOT EXISTS stock_hot_batch (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '采集批次主键ID',
    source VARCHAR(32) NOT NULL DEFAULT 'XUEQIU' COMMENT '数据来源，例如XUEQIU表示雪球',
    ranking_type VARCHAR(32) NOT NULL DEFAULT 'HOT_STOCK' COMMENT '榜单类型，例如HOT_STOCK表示热门股票榜',
    source_scope VARCHAR(32) NOT NULL DEFAULT 'GLOBAL' COMMENT '榜单市场范围：GLOBAL全部市场、CN_A股、HK港股、US美股',
    window_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 60 COMMENT '榜单统计窗口分钟数，例如60表示1小时热榜',
    capture_slot DATETIME NOT NULL COMMENT '标准化采集时间槽，用于任务幂等',
    captured_at DATETIME(3) NULL COMMENT '实际成功获取榜单数据的时间，精确到毫秒',
    primary_cutoff SMALLINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '核心热榜排名边界，默认前50名',
    observation_cutoff SMALLINT UNSIGNED NOT NULL DEFAULT 100 COMMENT '后台观察排名边界，默认前100名',
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT '采集状态：PENDING待执行、RUNNING执行中、SUCCESS成功、FAILED失败',
    item_count SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本批次实际采集到的股票数量',
    duration_ms INT UNSIGNED NULL COMMENT '本次采集耗时，单位毫秒',
    content_hash CHAR(64) NULL COMMENT '榜单内容SHA-256哈希，用于识别内容重复或异常',
    error_code VARCHAR(64) NULL COMMENT '采集失败错误代码，成功时为空',
    error_message VARCHAR(500) NULL COMMENT '采集失败错误说明，成功时为空',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录最后更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_hot_batch_slot (source, ranking_type, source_scope, window_minutes, capture_slot),
    KEY idx_hot_batch_status_time (status, capture_slot),
    KEY idx_hot_batch_captured_at (captured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='热点股票榜单采集批次及采集结果记录表';

CREATE TABLE IF NOT EXISTS stock_hot_snapshot (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '热榜快照主键ID',
    batch_id BIGINT UNSIGNED NOT NULL COMMENT '所属采集批次ID，关联stock_hot_batch.id',
    rank_no SMALLINT UNSIGNED NOT NULL COMMENT '股票在本批次热榜中的实际排名',
    external_symbol VARCHAR(32) NOT NULL COMMENT '数据源原始证券代码，例如SH688256、00700、NVDA',
    normalized_code VARCHAR(16) NULL COMMENT 'StockLens标准化证券代码，A股去除SH或SZ前缀',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票或证券名称',
    market VARCHAR(16) NOT NULL COMMENT '所属市场：CN_SH沪市、CN_SZ深市、HK港股、US美股、OTHER其他',
    heat_score DECIMAL(18,2) NOT NULL COMMENT '数据源返回的股票热度值',
    quote_change_pct DECIMAL(10,4) NULL COMMENT '数据源页面显示的股票涨跌幅百分比',
    topic VARCHAR(500) NULL COMMENT '股票关联的热门话题或讨论主题',
    raw_payload JSON NULL COMMENT '数据源返回的单只股票原始数据，用于排错和字段追溯',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '快照记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_hot_snapshot_symbol (batch_id, external_symbol),
    UNIQUE KEY uk_hot_snapshot_rank (batch_id, rank_no),
    KEY idx_hot_snapshot_symbol_batch (external_symbol, batch_id),
    KEY idx_hot_snapshot_code_batch (normalized_code, batch_id),
    CONSTRAINT fk_hot_snapshot_batch FOREIGN KEY (batch_id)
        REFERENCES stock_hot_batch(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='每次采集到的热点股票原始排名与热度快照表';

CREATE TABLE IF NOT EXISTS stock_hot_watch_state (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '热点股票跟踪状态主键ID',
    source VARCHAR(32) NOT NULL DEFAULT 'XUEQIU' COMMENT '数据来源，例如XUEQIU表示雪球',
    external_symbol VARCHAR(32) NOT NULL COMMENT '数据源原始证券代码，例如SH688256、00700、NVDA',
    normalized_code VARCHAR(16) NULL COMMENT 'StockLens标准化证券代码，用于关联内部股票数据',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票或证券名称',
    market VARCHAR(16) NOT NULL COMMENT '所属市场：CN_SH沪市、CN_SZ深市、HK港股、US美股、OTHER其他',
    tracking_status VARCHAR(24) NOT NULL COMMENT '跟踪状态：TOP50当前前50、OBSERVING离榜观察、OUTSIDE_TOP100前100外、HISTORY历史热点、PINNED持续关注',
    is_pinned TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否由用户固定关注：0否、1是',
    current_rank SMALLINT UNSIGNED NULL COMMENT '最近成功批次中的实际排名；未进入采集范围时为空',
    previous_rank SMALLINT UNSIGNED NULL COMMENT '上一成功批次中的实际排名；未进入采集范围时为空',
    current_heat DECIMAL(18,2) NULL COMMENT '最近成功批次中的热度；未知时为空，不能写为0',
    previous_heat DECIMAL(18,2) NULL COMMENT '上一成功批次中的热度；未知时为空',
    best_rank SMALLINT UNSIGNED NULL COMMENT '历史最佳热榜排名，数值越小排名越高',
    peak_heat DECIMAL(18,2) NULL COMMENT '历史最高热度值',
    first_top50_at DATETIME NULL COMMENT '历史首次进入前50名的时间',
    latest_top50_at DATETIME NULL COMMENT '最近一次处于前50名的时间',
    exited_top50_at DATETIME NULL COMMENT '最近一次跌出前50名的时间',
    watch_until DATE NULL COMMENT '离榜后继续观察的截止日期',
    last_seen_at DATETIME NULL COMMENT '最近一次在后台采集范围内出现的时间',
    last_seen_batch_id BIGINT UNSIGNED NULL COMMENT '最近一次出现时对应的采集批次ID',
    consecutive_missing_batches SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '连续未进入后台采集范围的成功批次数量',
    reentry_count SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '跌出前50后重新进入前50的累计次数',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '跟踪记录创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '跟踪记录最后更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_hot_watch_symbol (source, external_symbol),
    KEY idx_hot_watch_status (tracking_status, watch_until),
    KEY idx_hot_watch_code (normalized_code),
    KEY idx_hot_watch_current_rank (current_rank),
    KEY idx_hot_watch_last_seen_batch (last_seen_batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='热点股票当前排名、热度及离榜观察状态表';

CREATE TABLE IF NOT EXISTS stock_hot_event (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '热点状态事件主键ID',
    batch_id BIGINT UNSIGNED NOT NULL COMMENT '触发本事件的采集批次ID，关联stock_hot_batch.id',
    source VARCHAR(32) NOT NULL DEFAULT 'XUEQIU' COMMENT '数据来源，例如XUEQIU表示雪球',
    external_symbol VARCHAR(32) NOT NULL COMMENT '数据源原始证券代码',
    normalized_code VARCHAR(16) NULL COMMENT 'StockLens标准化证券代码，用于关联内部股票数据',
    stock_name VARCHAR(100) NOT NULL COMMENT '事件发生时的股票或证券名称',
    event_type VARCHAR(32) NOT NULL COMMENT '事件类型：FIRST_ENTER_TOP50首次入榜、EXIT_TOP50跌出前50、REENTER_TOP50重新入榜、EXIT_TOP100跌出前100、TRACKING_EXPIRED观察到期',
    event_at DATETIME NOT NULL COMMENT '事件发生时间，通常取对应批次实际采集时间',
    from_rank SMALLINT UNSIGNED NULL COMMENT '状态变化前的排名；未知时为空',
    to_rank SMALLINT UNSIGNED NULL COMMENT '状态变化后的排名；跌出采集范围时为空',
    from_heat DECIMAL(18,2) NULL COMMENT '状态变化前的热度；未知时为空',
    to_heat DECIMAL(18,2) NULL COMMENT '状态变化后的热度；未知时为空',
    event_data JSON NULL COMMENT '事件扩展信息，例如离榜时长及观察截止日期',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '事件记录创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_hot_event_once (batch_id, external_symbol, event_type),
    KEY idx_hot_event_symbol_time (external_symbol, event_at),
    KEY idx_hot_event_type_time (event_type, event_at),
    CONSTRAINT fk_hot_event_batch FOREIGN KEY (batch_id)
        REFERENCES stock_hot_batch(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='热点股票进入、退出、重新入榜及观察到期事件记录表';
