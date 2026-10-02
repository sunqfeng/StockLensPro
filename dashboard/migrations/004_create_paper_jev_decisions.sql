CREATE TABLE IF NOT EXISTS `paper_jev_decisions` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '决策记录ID',
    `signal_id` BIGINT NOT NULL COMMENT '关联的模拟交易信号ID',
    `run_mode` VARCHAR(20) NOT NULL DEFAULT 'SHADOW' COMMENT '运行模式：SHADOW影子评估，GATE交易门控',
    `question_version` VARCHAR(100) NOT NULL COMMENT 'Jev问题模板版本',
    `status` VARCHAR(20) NOT NULL COMMENT '调用状态：SUCCESS成功，ERROR失败，DISABLED未启用',
    `model_requested` VARCHAR(100) DEFAULT NULL COMMENT '请求的Jev模型名称',
    `model_resolved` VARCHAR(100) DEFAULT NULL COMMENT '实际响应的Jev模型版本',
    `quality_probability` DECIMAL(9,6) DEFAULT NULL COMMENT '信号质量充足的概率',
    `risk_probability` DECIMAL(9,6) DEFAULT NULL COMMENT '存在买入冲突风险的概率',
    `setup_score` DECIMAL(9,6) DEFAULT NULL COMMENT '交易形态质量分，范围0至3',
    `setup_confidence` DECIMAL(9,6) DEFAULT NULL COMMENT '交易形态评分置信度',
    `request_state_json` LONGTEXT NOT NULL COMMENT '发送给Jev的结构化状态JSON',
    `response_json` LONGTEXT DEFAULT NULL COMMENT 'Jev原始响应JSON',
    `latency_ms` INT DEFAULT NULL COMMENT 'Jev调用耗时（毫秒）',
    `error_message` TEXT DEFAULT NULL COMMENT '调用失败信息',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_paper_jev_signal_version` (`signal_id`, `question_version`),
    KEY `idx_paper_jev_status_time` (`status`, `created_at`),
    CONSTRAINT `fk_paper_jev_signal`
        FOREIGN KEY (`signal_id`) REFERENCES `paper_signals` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟交易Jev影子决策记录表';
