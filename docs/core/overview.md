# Nexus 核心概览

理解Nexus的核心架构和设计理念

## Nexus是什么

Nexus是一个轻量级的Python插件编排框架，专注于：

- **简单**：基于装饰器的插件注册，无需复杂配置
- **灵活**：4层配置系统，从全局到本地完全可控
- **清晰**：纯函数式插件，显式的上下文传递
- **实用**：开箱即用的模板系统，快速开始

## 核心设计理念

### 1. 简单优于复杂

**插件注册**：
```python
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

class MyConfig(PluginConfig):
    threshold: float = 0.5

@plugin(name="My Plugin", config=MyConfig)
def my_plugin(ctx):
    value = ctx.config.threshold
    return value
```

就这么简单！无需继承基类，无需注册表操作。

### 2. 显式优于隐式

**上下文传递**：
```python
@plugin(name="Data Generator")
def generate_data(ctx):  # 显式接收上下文
    # 显式获取配置
    num_rows = ctx.config.num_rows

    # 显式保存状态
    ctx.remember("last_result", data)

    # 显式解析路径
    output_path = ctx.resolve_path("output/data.csv")

    return data
```

所有操作都是显式的，不依赖全局状态或魔法变量。

### 3. 配置优于约定

**4层配置系统**：
```
CLI参数 (--config) > Case/Template配置 > 全局配置 > 插件默认值
```

每一层都是可选的，但优先级明确。

### 4. 模板优于重复

使用模板定义可重用的pipeline：

```yaml
# templates/etl.yaml
pipeline:
  - plugin: "Extract"
  - plugin: "Transform"
  - plugin: "Load"
```

多个case可以使用同一个模板，避免重复配置。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                        用户层                            │
│  CLI命令, YAML配置, Python API                          │
└────────────┬───────────────────────────┬────────────────┘
             │                           │
             v                           v
┌────────────────────────┐  ┌───────────────────────────┐
│     CaseManager        │  │   ConfigResolver          │
│  ─────────────────     │  │  ──────────────────       │
│  • Template发现        │  │  • 配置引用解析            │
│  • Case管理            │  │  • 配置合并                │
│  • 路径解析            │  │  • defaults支持            │
└────────┬───────────────┘  └─────────┬─────────────────┘
         │                            │
         v                            v
┌────────────────────────────────────────────────────────┐
│               PipelineEngine (执行引擎)                 │
│  ────────────────────────────────────────────────────  │
│  • 加载配置                                             │
│  • 解析引用                                             │
│  • 顺序执行插件                                         │
│  • 管理共享状态                                         │
└────────┬──────────────────────────────────────┬────────┘
         │                                      │
         v                                      v
┌────────────────────┐              ┌─────────────────────┐
│  Plugin Discovery  │              │   PluginContext     │
│  ───────────────   │              │   ──────────────    │
│  • 扫描packages    │              │   • config          │
│  • 导入模块        │◄─────────────┤   • logger          │
│  • 注册插件        │              │   • resolve_path    │
└────────────────────┘              │   • remember/recall │
                                    └─────────────────────┘
         ▲
         │  @plugin装饰器
         │
┌────────────────────────────────────────────────────────┐
│                    用户插件                             │
│  @plugin(name="...", config=...)                       │
│  def my_plugin(ctx): ...                               │
└────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Plugin System (插件系统)

**@plugin装饰器**：
- 注册插件到全局注册表
- 绑定配置模型
- 提供元数据

**PluginSpec**：
- 存储插件元信息
- 包含: name, func, config_model, description

**Plugin Discovery**：
- 扫描配置的package路径
- 自动导入 `package.nexus` 模块
- 触发装饰器注册

### 2. Configuration System (配置系统)

**4层配置**：
```python
# Layer 4: Plugin defaults (from Pydantic model)
class MyConfig(PluginConfig):
    threshold: float = 0.5

# Layer 3: Global config (config/global.yaml)
plugins:
  My Plugin:
    threshold: 0.8

# Layer 2: Case config (case.yaml)
pipeline:
  - plugin: "My Plugin"
    config:
      threshold: 0.9

# Layer 1: CLI override (--config)
--config threshold=1.0
```

**配置引用**：
```yaml
defaults:
  common_settings:
    tolerance: 50.0

pipeline:
  - plugin: "My Plugin"
    config:
      _extends: "@defaults.common_settings"  # 继承
      data_path: "input/data.jsonl"          # 新增
```

### 3. Execution Engine (执行引擎)

**PipelineEngine**：
- 加载和合并配置
- 解析配置引用
- 顺序执行插件
- 管理共享状态

**执行流程**：
```
1. 加载配置 (global + case/template + CLI)
2. 合并defaults
3. 解析@defaults引用
4. For each step:
   a. 获取插件spec
   b. 解析step配置
   c. 创建PluginContext
   d. 执行插件函数
   e. 保存结果到共享状态
5. 返回所有结果
```

### 4. Context System (上下文系统)

**NexusContext**：
- 项目级上下文
- 包含: project_root, case_path, logger, run_config

**PluginContext**：
- 插件级上下文
- 包含: config, logger, resolve_path(), remember(), recall()

**路径解析**：
```python
# 所有*_path参数自动解析为绝对路径
ctx.auto_resolve_paths({
    "data_path": "input/data.jsonl",      # -> /abs/case/path/input/data.jsonl
    "calibration_path": "calib.yaml",     # -> /abs/case/path/calib.yaml
    "threshold": 0.5                       # -> 0.5 (保持不变)
})
```

### 5. Case Management (Case管理)

**CaseManager**：
- Template发现和加载
- Case路径解析
- 模板与case.yaml互斥处理

**Template vs Case**：
- Template: 可重用pipeline定义
- Case: 工作空间 + 可选的case.yaml
- 互斥: `--template` 指定时忽略case.yaml

## 典型工作流程

### 场景：使用模板运行pipeline

```bash
nexus run --case my_analysis --template quickstart --config num_rows=5000
```

**执行步骤**：

1. **CLI解析**：
   - case: "my_analysis"
   - template: "quickstart"
   - config_overrides: {"num_rows": 5000}

2. **加载配置**：
   - 加载 `config/global.yaml`
   - 加载 `templates/quickstart.yaml` (忽略case.yaml)
   - 应用CLI覆盖

3. **插件发现**：
   - 扫描 `src/nexus/contrib`
   - 导入 `nexus.contrib.nexus` 等模块
   - 注册所有 `@plugin` 装饰的函数

4. **执行Pipeline**：
   ```python
   # For step in pipeline:
   step = {"plugin": "Data Generator", "config": {...}}

   # 获取插件
   plugin_spec = get_plugin("Data Generator")

   # 合并配置 (defaults < global < step < CLI)
   merged_config = merge_configs(...)

   # 创建上下文
   ctx = PluginContext(config=merged_config, ...)

   # 执行插件
   result = plugin_spec.func(ctx)

   # 保存到共享状态
   shared_state["last_result"] = result
   ```

5. **完成**：
   - 所有步骤执行完成
   - 返回结果字典

## 高级特性

### 1. 配置引用系统

使用 `@defaults` 引用共享配置：

```yaml
defaults:
  renderer_base:
    tolerance_ms: 50.0
    time_offset_ms: 0

pipeline:
  - plugin: "Data Renderer"
    config:
      renderers:
        - name: "speed"
          kwargs:
            _extends: "@defaults.renderer_base"  # 继承
            data_path: "input/speed.jsonl"       # 新增
```

**特性**：
- 支持嵌套引用: `@defaults.camera.main.calibration`
- 深度合并: 嵌套dict自动合并
- 循环检测: 自动检测循环引用

### 2. 路径自动解析

所有 `*_path` 参数自动解析：

```python
# 插件中
@plugin(name="My Plugin")
def my_plugin(ctx):
    # 自动解析所有*_path参数
    config = ctx.auto_resolve_paths({
        "data_path": "input/data.jsonl",        # 自动解析
        "output_path": "output/result.csv",     # 自动解析
        "threshold": 0.5                         # 保持不变
    })

    # config["data_path"] 现在是绝对路径
```

**约定**：
- 相对路径 → 相对于case目录
- 绝对路径 → 保持不变
- 递归处理嵌套dict和list

### 3. 模块化插件

**Sideload外部插件**：

```yaml
# config/global.yaml
framework:
  packages:
    - "src/nexus/contrib"           # 内置插件
    - "/path/to/my/custom/plugins"   # 外部插件
```

**目录结构**：
```
my_custom_plugins/
├── __init__.py           # 业务逻辑
├── logic.py
└── nexus/                # Nexus适配器
    └── __init__.py       # @plugin装饰器
```

## 设计权衡

### 为什么是装饰器而不是类继承？

✅ **装饰器**：
- 简单：一行代码注册
- 灵活：任何函数都可以是插件
- 解耦：业务逻辑独立于框架

❌ **类继承**：
- 侵入性强
- 需要了解基类API
- 业务逻辑与框架耦合

### 为什么Template和Case互斥？

Template和Case.yaml **不合并**，而是互斥选择：

✅ **互斥**：
- 语义清晰：要么用模板，要么自定义
- 避免混淆：配置来源明确
- 简化理解：减少心智负担

❌ **合并**：
- 复杂：需要理解合并规则
- 混乱：配置来源不清楚
- 难以调试：优先级难以推理

### 为什么使用共享状态而不是数据管道？

✅ **共享状态** (remember/recall):
- 简单：显式的get/set
- 灵活：任何数据类型
- 透明：没有隐藏的序列化

❌ **数据管道**：
- 复杂：需要序列化/反序列化
- 限制：只能传递特定类型
- 性能：内存复制开销

## 下一步

- [插件系统](plugins.md) - 深入了解插件机制
- [配置系统](configuration.md) - 掌握配置层次
- [执行上下文](context.md) - 理解上下文传递
- [高级特性](advanced.md) - 路径解析和配置引用
