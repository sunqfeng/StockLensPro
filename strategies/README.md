# sequoia_mysql_strategy_complete_v4

## 1. 作用

把 Sequoia-X 的几个选股策略改造成读取你的 MySQL `stock_daily` 数据源，选股后登记到你的 `stock_recommend_record` 表。

## 2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 3. 配置数据库（不在源码中填写密码）

把 `config/secrets.env.example` 复制为本地 `config/secrets.env`，填写自己的连接信息：

```dotenv
DB_HOST=
DB_PORT=3306
DB_USER=
DB_PASSWORD=
DB_NAME=
```

也可以由部署环境设置上述环境变量，它们优先于本地文件。真实 `secrets.env` 已被 Git 忽略，不要提交到仓库。

## 4. 运行

执行全部策略：

```powershell
python run_select_and_record.py
```

指定交易日：

```powershell
python run_select_and_record.py --trade-date 2026-05-15
```

只执行海龟突破：

```powershell
python run_select_and_record.py --strategy TURTLE_TRADE
```

只执行 RPS：

```powershell
python run_select_and_record.py --strategy RPS_BREAKOUT
```

## 5. 可用策略

- TURTLE_TRADE：海龟20日突破
- MA_VOLUME：均线金叉放量
- HIGH_TIGHT_FLAG：高旗形整理
- LIMIT_UP_SHAKEOUT：涨停洗盘
- UPTREND_LIMIT_DOWN：上升趋势放量跌停
- RPS_BREAKOUT：RPS强势突破
- PRIVATE_PLACEMENT：定向增发公告

## 6. 登记表

代码适配你的真实表：

```sql
stock_recommend_record
```

字段：

- recommend_batch_no
- recommend_date
- stock_code
- stock_name
- industry
- recommend_price
- recommend_score
- strategy_name
- reason
- status

## 7. 防重复

代码按下面三个字段判断是否重复：

```text
recommend_date + stock_code + strategy_name
```

存在则更新，不存在则插入。

建议后续执行：

```sql
ALTER TABLE stock_recommend_record
ADD UNIQUE KEY uk_date_code_strategy (recommend_date, stock_code, strategy_name);
```
