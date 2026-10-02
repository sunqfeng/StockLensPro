-- 建议增加唯一索引，防止同一天、同股票、同策略重复登记。
-- 如果你暂时不想加，也没关系，代码里已经做了查询后更新。
ALTER TABLE stock_recommend_record
ADD UNIQUE KEY uk_date_code_strategy (recommend_date, stock_code, strategy_name);
