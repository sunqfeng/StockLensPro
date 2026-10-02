# StockLensPro

股票策略推荐、价格跟踪与模拟交易的合并源码仓库。

## 目录

- `dashboard/`：Streamlit 看板、推荐跟踪、每日价格走势图、模拟交易、Typesafe/Jev 辅助评估、任务中心。
- `strategies/`：MySQL 日线驱动的选股策略、推荐登记、版本化筛选规则与冻结快照流程。

此仓库是 2026-10-02 的脱敏源码快照，未导入服务器旧 Git 历史。源码、测试与数据库迁移脚本已保留；真实密码、API Key、服务器地址、机器用户名、运行数据、快照、日志、备份和本地开发设置未上传。

## 本地配置

先安装各子项目 `requirements.txt` 中的依赖。把相应的 `config/secrets.env.example` 复制成同目录下的 `secrets.env`，只在本地填写自己的数据库配置和 API Key。环境变量优先于本地配置文件。

启动看板：

```sh
cd dashboard
python -m pip install -r requirements.txt
streamlit run stock_strategy_dashboard_pro_pie_v5.py
```

执行选股会登记数据库记录；不要在生产数据库上为测试而随意运行：

```sh
cd strategies
python -m pip install -r requirements.txt
python run_select_and_record.py --help
```

应用需要已配置的 MySQL 数据库以及现有日线、推荐、跟踪和技术评分数据表；`migrations/` 不是整个数据库的完整备份。技术评分、行情采集等部分任务调用部署环境中的外部项目，未包含在此仓库。它们的位置需要由部署方配置，示例路径不代表真实服务器位置。

可配置路径：

- `STOCKLENS_WORKSPACE_DIR`：任务中心依赖的外部项目根目录。
- `STOCKLENS_TECH_SCORE_DIR`：选股后调用的外部技术评分项目目录。
- `STOCKLENS_SHADOW_DIR`：看板读取的新规则快照目录；不设置时默认读取本仓库 `strategies/outputs/recommendation_shadow/`。

数据库账号应只具备业务所需权限。不要上传真实 `secrets.env`、数据库导出文件、运行快照或密钥文件，即使仓库改成私有也一样。

## 推荐规则与验证口径

`candidate-v1.2` 在原选股结果上记录筛选快照，不删除原推荐，也不改变模拟交易执行。看板以 2026-10-02 为生效日：此前的历史推荐保留，此后展示新规则保留结果。跨期统计包含旧推荐；验证新规则时应单独选择生效日后的日期或批次。

规则说明见 `strategies/SHADOW_OPTIMIZATION.md`。技术指标和历史重放不保证盈利；“20日内曾达到收益门槛”不等于持有到第20日盈利。

## 测试

在对应子目录中分别执行，避免两个子项目同名模块互相影响：

```sh
python -m unittest discover -s tests -q
```

脱敏副本已通过看板 47 项、选股 10 项测试。数据库配置测试使用虚构的测试值，不连接生产数据库。
