# 自动化测试说明

自动化测试按照 `docs/test-cases-full-lifecycle.csv` 分为三层：

1. **默认测试**：不需要数据库、外网或真实平台账号，覆盖内容标准化、导入、分析、平台适配、预览校验、规则 Agent 和测试用例表完整性。
2. **部署环境测试**：使用 `live` 标记，连接已经启动的 Docker 环境，覆盖前端/API 可达性、素材 CRUD、模拟发布和任务查询。
3. **真实平台发布测试**：使用 `external_publish` 标记并默认跳过，防止自动化脚本误发公众号或 B站内容。

## 默认测试

```powershell
python -m pytest -m "not live and not external_publish"
```

## Docker 部署环境测试

先启动服务：

```powershell
docker compose up -d --build
```

推荐在 Compose 内部网络执行，避免宿主机代理和端口转发干扰：

```powershell
docker compose build backend
docker compose run --rm --no-deps `
  -e AUTO_UPT_RUN_LIVE_TESTS=1 `
  -e AUTO_UPT_TEST_BASE_URL=http://frontend `
  --entrypoint python backend `
  -m pytest tests/test_live_deployment_lifecycle.py -m live -q
```

部署环境测试会创建并删除一条临时素材，同时创建可保留的模拟发布任务，不会调用真实平台发布接口。

## 全部安全测试

```powershell
python -m pytest -m "not external_publish"
```

真实平台发布用例需要专用测试账号、平台沙箱或严格隔离环境后再单独实现和启用。
