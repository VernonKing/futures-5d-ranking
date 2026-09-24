# 期货近5日收益分类榜

公开静态行情网站，按国内期货具体主力合约最近5个完整交易日的收益率进行分类排名。

## 页面口径

- 品种收益：`最新完整日K收盘价 / 5个交易日前收盘价 - 1`。
- 主力合约：每次抓取先按持仓量优先、成交量次优识别具体到期合约；收益、价格、小时线和日线全程使用同一合约，不拼接连续合约。
- 品类收益：品类内全部有效品种收益率的中位数。
- 展示中位数最高的3个品类及各自涨幅最高的3个品种。
- 展示中位数最低的3个品类及各自跌幅最大的3个品种。
- 生猪和航运是单独品类，目前各只有一个品种，因此不会复制品种补足三个。
- 有夜盘品种使用2小时K线，由60分钟K线按时间顺序每两根聚合；无夜盘品种使用1小时K线。
- 小时图显示MA5、MA10、MA60，日线图显示MA5、MA10。

## 自动更新

`.github/workflows/deploy.yml`在工作日北京时间16:00首次触发，并在16:25、17:00、18:00和20:00分段补跑。新浪日线可能分批发布，覆盖达到75/78即可先发布；后续补跑继续运行并用78/78完整快照覆盖，只有当天完整快照生成后才自动跳过。GitHub定时任务可能排队延迟，因此不保证分秒不差；无人访问时仍会更新，也不依赖用户电脑或Codex运行。

工作流会依次执行：

1. 安装Python依赖并运行测试。
2. 从新浪财经公开接口获取行情并生成`site/data/latest.json`。
3. 将最新JSON提交回公开仓库，保留更新时间并避免公开仓库长期无活动导致定时任务停用。
4. 上传`site/`静态目录并部署到GitHub Pages。

GitHub Pages自定义工作流需要在仓库的`Settings > Pages > Build and deployment`中选择`GitHub Actions`。也可以在`Actions`页面手动运行`Update market data and deploy Pages`。

## 本地运行

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m generator.build --output site/data/latest.json
python -m http.server 8767 --directory site
```

访问`http://127.0.0.1:8767/`。

## 目录

- `generator/market.py`：品种池、分类、收益排名、周期聚合和均线。
- `generator/build.py`：行情抓取及静态JSON生成。
- `site/`：无需后端服务的网页。
- `tests/`：数据口径、生成器、页面及部署配置测试。

## 数据说明

行情为新浪财经国内期货具体主力合约公开数据，可能存在延迟、缺失或主力切换。页面仅用于趋势观察，不构成投资建议。

部署步骤依据[GitHub Pages自定义工作流文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。
