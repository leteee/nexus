# Nexus 快速开始

5分钟上手Nexus插件编排框架

## 安装

```bash
# 克隆项目
git clone https://github.com/your-org/nexus.git
cd nexus

# 安装依赖（开发模式）
pip install -e ".[dev]"

# 验证安装
nexus --version
```

## 第一个示例

### 1. 运行Quickstart模板

```bash
# 使用quickstart模板创建case并运行
nexus run --case my_first_case --template quickstart
```

这个命令会：
- 自动创建 `cases/my_first_case` 目录
- 使用 `templates/quickstart.yaml` 作为配置
- 执行数据生成插件
- 输出生成的数据

### 2. 查看结果

```bash
# 查看case目录
ls cases/my_first_case/

# 输出：
# data/          # 生成的数据文件
```

### 3. 修改配置并重新运行

创建 `cases/my_first_case/case.yaml`:

```yaml
case_info:
  name: "My First Case"
  description: "Learning Nexus with custom config"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 5000      # 修改行数
      num_categories: 10   # 修改类别数
```

运行自定义配置：

```bash
# 不指定template，使用case.yaml
nexus run --case my_first_case
```

## 核心概念

### Case (案例)
- 一个工作空间目录，包含数据和配置
- 位于 `cases/` 目录下
- 可以包含 `case.yaml` 配置文件

### Template (模板)
- 可重用的pipeline定义
- 位于 `templates/` 目录下
- 使用 `--template` 参数指定

### Plugin (插件)
- 使用 `@plugin` 装饰器注册的Python函数
- 接收 `PluginContext` 参数
- 返回处理结果

### Pipeline (流水线)
- 顺序执行的插件列表
- 在YAML配置中定义
- 插件之间共享上下文和数据

## CLI命令快速参考

### 运行Pipeline

```bash
# 使用模板
nexus run --case mycase --template quickstart

# 使用case.yaml
nexus run --case mycase

# 使用配置覆盖
nexus run --case mycase --template quickstart \
  --config num_rows=10000
```

### 运行单个插件

```bash
# 执行单个插件
nexus plugin "Data Generator" --case mycase \
  --config num_rows=1000 \
  --config random_seed=42
```

### 列出资源

```bash
# 列出所有插件
nexus list plugins

# 列出所有模板
nexus list templates

# 列出所有case
nexus list cases
```

### 查看帮助

```bash
# 查看整体帮助
nexus help

# 查看插件详细信息
nexus help --plugin "Data Generator"
```

## 配置层次

Nexus使用4层配置，优先级从高到低：

1. **CLI参数** (`--config key=value`)
2. **Case/Template配置** (`case.yaml` 或 template)
3. **全局配置** (`config/global.yaml`)
4. **插件默认值** (Pydantic模型)

示例：

```bash
# 使用模板，但覆盖num_rows
nexus run --case mycase --template quickstart \
  --config num_rows=5000

# 最终 num_rows=5000 (来自CLI，最高优先级)
```

## 项目结构

```
nexus/
├── cases/                    # Case工作空间
│   └── mycase/
│       ├── case.yaml        # Case配置（可选）
│       └── data/            # 数据文件
├── templates/                # 模板定义
│   ├── quickstart.yaml
│   └── repro/
│       ├── repro.yaml
│       └── repro_datagen.yaml
├── config/
│   ├── global.yaml          # 全局配置
│   └── local.yaml           # 本地覆盖（可选）
└── src/nexus/
    └── contrib/             # 内置插件
```

## 下一步

### 学习核心概念
- [核心概览](core/overview.md) - 理解Nexus架构
- [插件系统](core/plugins.md) - 了解插件机制
- [配置系统](core/configuration.md) - 掌握配置层次

### 开发自定义插件
- [编写插件](guides/writing-plugins.md) - 创建你的第一个插件
- [配置最佳实践](guides/configuration-best-practices.md) - 配置系统最佳实践

### 使用Repro模块
- [Repro快速开始](repro/quick-start.md) - 视频数据回放
- [渲染器系统](repro/renderers.md) - 数据可视化

## 常见问题

### Q: Template和Case的区别？

**Template**：
- 可重用的pipeline定义
- 多个case可以使用同一个template
- 不包含具体数据

**Case**：
- 具体的工作空间
- 包含数据文件和可选的case.yaml
- case.yaml可以自定义pipeline

### Q: 什么时候使用Template，什么时候使用Case.yaml？

- 使用 **Template**：标准化工作流，快速开始
- 使用 **Case.yaml**：需要定制化的pipeline

### Q: CLI配置覆盖如何工作？

CLI覆盖只影响 `plugins.*` 命名空间：

```bash
# 正确：覆盖插件配置
--config num_rows=1000

# 也可以写完整路径
--config plugins.Data\ Generator.num_rows=1000
```

### Q: 如何查看可用的插件和配置？

```bash
# 列出所有插件
nexus list plugins

# 查看插件详细配置
nexus help --plugin "Data Generator"
```

## 实用技巧

### 1. 使用详细日志调试

```bash
nexus run --case mycase --template quickstart --verbose
```

### 2. 配置覆盖多个参数

```bash
nexus run --case mycase --template quickstart \
  --config num_rows=5000 \
  --config random_seed=42 \
  --config num_categories=10
```

### 3. 生成插件API文档

```bash
# 生成markdown文档到docs/api/
nexus doc --force
```

### 4. 快速实验

```bash
# 直接运行插件而不创建pipeline
nexus plugin "Data Generator" --case test \
  --config num_rows=100
```

---

**准备好了吗？** 继续阅读 [核心概览](core/overview.md) 深入了解Nexus！
