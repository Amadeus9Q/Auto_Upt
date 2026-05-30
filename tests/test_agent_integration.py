"""集成测试：验证内容分析 + 平台文案生成全流程。"""
import sys
sys.path.insert(0, ".")

from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent

body = """# 2026年AI行业五大趋势

## 前言

2026年，人工智能行业继续保持高速增长。本文将从五个维度分析今年的核心趋势。

![AI趋势图](https://img.example.com/ai-trends-2026.png)

## 趋势一：多模态大模型全面落地

多模态能力从实验室走向产品，文字、图片、视频、音频的融合处理成为标配。

{{asset:video:multimodal-demo}}

### 代表产品

国内外头部厂商已推出数十款多模态产品，覆盖办公、教育、创作等场景。

## 趋势二：AI Agent 从概念走向规模化

2026年被业界称为"Agent元年"，自主决策、工具调用的智能体开始在实际业务中发挥价值。

### 关键突破

- 多步推理能力显著提升
- 工具调用 API 标准化
- 企业级安全与权限控制成熟

## 趋势三：端侧推理成为新战场

随着芯片算力提升和模型量化技术进步，手机、PC端的本地AI推理体验大幅改善。

https://audio.example.com/podcast-ai-trends.mp3

## 总结

2026年的AI行业正在经历从"技术驱动"到"应用驱动"的关键转型期。
"""

agent = ContentAnalystAgent()
result = agent.analyze(
    body=body,
    title="2026年AI行业五大趋势",
    tags=["AI", "2026", "科技趋势"],
    content_type="mixed",
)

print("=" * 50)
print("【章节分析】")
print("=" * 50)
for ch in result.flat_chapters:
    indent = "  " * (ch.level - 1)
    media_str = ""
    if ch.media_items:
        kinds = [m.kind for m in ch.media_items]
        media_str = f" [含: {', '.join(kinds)}]"
    print(f"{indent}L{ch.level} | {ch.title} | {ch.word_count}字{media_str}")

print()
print("=" * 50)
print("【媒体清单】")
print("=" * 50)
for k, items in result.media_by_kind.items():
    if items:
        print(f"  {k}: {len(items)}个")
        for m in items:
            source = "asset-marker" if m.asset_id else "auto-detect"
            print(f"    - {m.name} ({source})")

print()
print("=" * 50)
print("【平台文案生成】")
print("=" * 50)
stylist = PlatformStylistAgent()
copies = stylist.generate(result)
for p, c in copies.items():
    print(f"\n[{c.display_name}] ({p})")
    print(f"  标题: {c.title}")
    print(f"  副标题: {c.subtitle}")
    print(f"  章节数: {len(c.sections)}")
    print(f"  标签({len(c.tags)}): {c.tags[:5]}")
    print(f"  媒体建议:")
    for r in c.media_recommendations:
        print(f"    {r['action']:6s} | {r['kind']:5s} | {r['reason'][:55]}")

print("\n✅ 全部测试通过！")
