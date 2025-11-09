# Nexus

> 轻量级Python插件编排框架

Nexus是一个专注于简单性的插件编排框架，核心理念：

- **Case-based工作空间**: 每个case目录包含数据和配置
- **Template pipeline**: 可重用的YAML定义插件执行流程
- **纯Python插件**: 使用`@plugin`装饰器，Pydantic验证配置

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-org/nexus.git
cd nexus

# 安装依赖
pip install -e ".[dev]"

# 验证安装
nexus --version
```

### 第一个示例

```bash
# 列出可用资源
nexus list plugins
nexus list templates
nexus list cases

# 运行模板pipeline
nexus run --case quickstart --template quickstart

# 运行视频数据回放
nexus run --case my_repro --template repro/repro

# 执行单个插件
nexus plugin "Data Generator" --case mycase --config num_rows=500
```

### 内置模板

| 模板 | 说明 | 主要插件 |
|------|------|---------|
| `quickstart` | 最小示例：单步数据生成 | Data Generator |
| `repro/repro` | 视频数据回放：分割帧 → 渲染数据 → 合成视频 | Video Splitter, Data Renderer, Video Composer |
| `repro/repro_datagen` | 完整合成数据生成：视频 → 时间戳 → 速度 → 目标 | Synthetic Video Generator, Timeline Generator, Speed Data Generator, ADB Target Generator |

## 核心概念

### 编写插件

```python
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

class CleanConfig(PluginConfig):
    drop_nulls: bool = True

@plugin(name="Clean Data", config=CleanConfig)
def clean_data(ctx):
    df = ctx.recall("last_result")
    if df is None:
        raise RuntimeError("需要上游数据")
    if ctx.config.drop_nulls:
        df = df.dropna()
    ctx.remember("last_result", df)
    return df
```

**PluginContext提供**：
- `ctx.config` - 验证后的配置模型
- `ctx.logger` - 项目日志器
- `ctx.resolve_path(str)` - 解析相对路径
- `ctx.remember(key, value)` / `ctx.recall(key)` - 共享状态

### Pipeline定义

`case.yaml` 或模板文件定义pipeline：

```yaml
case_info:
  name: "数据处理"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 500

  - plugin: "Data Filter"
    config:
      column: "value"
      operator: ">"
      threshold: 100
```

### 配置引用

使用`@defaults`共享配置：

```yaml
defaults:
  common_settings:
    tolerance_ms: 50.0

pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        - name: "speed"
          kwargs:
            _extends: "@defaults.common_settings"  # 继承
            data_path: "input/speed.jsonl"         # 新增
```

## 文档

**完整文档请访问 [docs/](docs/README.md)**

### 推荐阅读路径

**新用户**：
1. [快速开始指南](docs/getting-started.md) - 5分钟上手
2. [核心概览](docs/core/overview.md) - 理解架构
3. [插件系统](docs/core/plugins.md) - 插件机制（待完善）

**插件开发者**：
1. [编写插件](docs/guides/writing-plugins.md) - 完整指南
2. [配置系统](docs/core/configuration.md) - 配置机制（待完善）
3. [配置最佳实践](docs/guides/configuration-best-practices.md)（待完善）

**Repro用户**：
1. [Repro概览](docs/repro/README.md) - 视频数据回放
2. [渲染器系统](docs/repro/renderers.md)（待完善）
3. [编写渲染器](docs/guides/writing-renderers.md) - 自定义渲染器

**高级用户**：
- [配置引用系统](docs/config-references.md) - `@defaults`语法
- [路径解析约定](docs/path-resolution-convention.md) - `*_path`自动解析
- [API文档](docs/api/README.md) - 自动生成的API参考


## 项目结构

```
nexus/
├── src/nexus/           # 源代码
│   ├── core/           # 核心框架
│   └── contrib/        # 内置插件和模块
│       ├── basic/      # 基础插件
│       ├── repro/      # 视频回放模块
│       └── nexus/      # Nexus适配器
├── templates/          # Pipeline模板
│   ├── quickstart.yaml
│   └── repro/
├── cases/              # Case工作空间
├── config/             # 全局配置
│   └── global.yaml
├── docs/               # 文档
│   ├── core/          # 核心框架文档
│   ├── repro/         # Repro模块文档
│   └── guides/        # 开发指南
└── examples/           # 示例代码
```

## 外部插件

在`config/global.yaml`或`config/local.yaml`中配置：

```yaml
framework:
  packages:
    - "src/nexus/contrib"           # 内置
    - "/path/to/my/custom/plugins"  # 外部
```

**外部插件结构**：
```
my_custom_plugins/
├── __init__.py          # 业务逻辑
├── data_processing.py
└── nexus/               # Nexus适配器
    └── __init__.py      # @plugin装饰器
```

## 编程API

```python
from pathlib import Path
import nexus

# 创建引擎并运行pipeline
case_path = "mycase"
manager, _ = nexus._build_case_manager(Path.cwd())
config_path, case_config = manager.get_case_config(case_path)
engine = nexus.create_engine(case_path)
results = engine.run_pipeline(case_config)
```

## 为什么选择Nexus？

- ✨ **简单**: `@plugin`装饰器，无需复杂配置
- 📝 **声明式**: YAML定义pipeline，清晰易读
- 🔧 **灵活**: 4层配置系统，完全可控
- 🎯 **实用**: 开箱即用的模板和插件
- 🔌 **解耦**: 纯函数式插件，显式上下文传递

## 特色模块

### Repro - 视频数据回放

独立的视频时序数据可视化模块：

```python
from nexus.contrib.repro import render, BaseDataRenderer

@render("speed")
class SpeedRenderer(BaseDataRenderer):
    def render(self, frame, timestamp_ms):
        matched = self.match_data(timestamp_ms, self.tolerance_ms)
        if matched:
            speed = matched[0]['speed']
            cv2.putText(frame, f"Speed: {speed:.1f} km/h", ...)
        return frame
```

详见 [Repro模块文档](docs/repro/README.md)

## 许可证

MIT License. 详见 `LICENSE` 文件。

## 贡献

欢迎贡献！请查看 [docs/](docs/README.md) 了解项目架构。

---

**文档更新**: 2025-11-09
**版本**: 1.0.0

