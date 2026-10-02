-- 你的 stock_recommend_record 表结构
-- 如果你已经建过这张表，不需要重复执行。

CREATE TABLE IF NOT EXISTS `stock_recommend_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `recommend_batch_no` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '推荐批次号，例如 20260516_001',
  `recommend_date` date NOT NULL COMMENT '推荐日期',
  `stock_code` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `stock_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '股票名称',
  `industry` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '行业/板块',
  `recommend_price` decimal(10,3) DEFAULT NULL COMMENT '推荐时收盘价或当前价',
  `recommend_score` decimal(10,3) DEFAULT NULL COMMENT '推荐总分',
  `strategy_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '策略名称，例如 趋势回踩策略、主线板块策略',
  `reason` text COLLATE utf8mb4_unicode_ci COMMENT '推荐理由',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'TRACKING' COMMENT '状态：TRACKING-跟踪中，FINISHED-已完成',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_recommend_date` (`recommend_date`),
  KEY `idx_stock_code` (`stock_code`),
  KEY `idx_batch_no` (`recommend_batch_no`),
  KEY `idx_strategy_name` (`strategy_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票推荐记录表';
