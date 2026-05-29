# 平台扩展设计

新增平台时，只需要在 `backend/app/adapters/<platform>/` 下新增插件目录。

```text
backend/app/adapters/<platform>/
  adapter.py
  renderer.py
  profile.yaml
```

## 必须实现的接口

平台适配器需要继承 `PlatformAdapter`，并实现以下方法：

- `capabilities()`：声明支持的内容类型、发布模式、鉴权方式、限制能力。
- `render(content, profile)`：把统一内容 IR 转为平台草稿。
- `validate(draft)`：返回标题、正文、图片、标签、链接等校验问题。
- `publish(draft, account, mode)`：执行草稿、模拟或真实发布。
- `simulate(draft)`：生成预览、截图和模拟报告。

## profile.yaml 约定

`profile.yaml` 保存平台规则，不把规则硬编码在核心流程里。

需要包含：

- `platform`
- `display_name`
- `content_types`
- `limits`
- `publish_modes`
- `auth`
- `style`
- `assets`

核心流程只读取平台 profile 和 Adapter 能力，不关心平台内部实现。
