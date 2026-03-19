# 工程化 Skill 系统设计方案（Codex 风格）

**日期：** 2026-03-15  
**类型：** 功能设计  
**范围：** basket-assistant skill 目录结构、加载器、工具链与渐进式披露  

---

## 一、背景与目标

### 现状

当前 basket-assistant 采用 **OpenCode 风格** skill：

- 每个 skill 一个目录，内含 **唯一必选** `SKILL.md`（YAML frontmatter + Markdown body）
- `skills_loader` 仅解析 `name` / `description`，`get_skill_full_content()` 返回 **整份 body**（不含 frontmatter）
- skill 工具在加载时返回：`# Skill: {name}` + body + base_dir 提示
- **无** 脚本、参考资料、资源资产等附属结构；所有内容都塞在 SKILL.md body 里，易导致上下文膨胀且难以复用

### 目标

1. **工程化布局**：支持 Codex 风格的 `scripts/`、`references/`、`assets/` 目录，与现有 `SKILL.md` 并存
2. **渐进式披露**：索引阶段只读 metadata；按需加载 body 与 references，scripts 可执行而不必全部读入上下文
3. **工具链**：提供 `init_skill`、`quick_validate`（及可选的元数据生成），便于创建与校验 skill
4. **向后兼容**：仅含 `SKILL.md` 的现有 skill 无需改动即可继续工作

---

## 二、Skill 目录结构（Codex 风格）

### 约定布局

```
skill-name/                    # 目录名 = frontmatter name，小写+连字符
├── SKILL.md                   # 必选：frontmatter + 正文
├── scripts/                   # 可选：可执行脚本（Python/Bash 等）
│   ├── rotate_pdf.py
│   └── validate.sh
├── references/                # 可选：按需加载的参考文档
│   ├── schema.md
│   └── api_docs.md
└── assets/                    # 可选：输出用资源（模板、图片等），一般不读入上下文
    ├── template.docx
    └── logo.png
```

### 各目录语义

| 目录 | 用途 | 加载策略 |
|------|------|----------|
| `scripts/` | 确定性、可重复执行的脚本 | 不强制读入上下文；agent 可按路径执行；SKILL.md 中说明用法与参数 |
| `references/` | 领域文档、API、schema、策略 | 按需加载：由 SKILL.md 或 agent 决定读哪些文件 |
| `assets/` | 模板、图片、字体等 | 通常不读入上下文；供 agent 复制/引用路径 |

### 不纳入的目录/文件

与 Codex skill-creator 一致：不在 skill 内放 `README.md`、`CHANGELOG.md`、`INSTALLATION_GUIDE.md` 等与“使用该 skill 执行任务”无关的辅助文档。

---

## 三、SKILL.md 规范

### Frontmatter（保持不变）

- **name**（必填）：与目录名一致，`^[a-z0-9]+(-[a-z0-9]+)*$`，≤64 字符
- **description**（必填）：用于索引与触发；需包含「做什么」与「何时用」，≤1024 字符

不在 frontmatter 中增加新必填字段；可选字段（如 `version`、`short_description`）可在后续阶段用于 UI 或生成 openai.yaml，不参与核心加载逻辑。

### Body 编写原则

- 正文保持精简，核心流程与“何时用 scripts/references”的说明放在 SKILL.md
- 详细内容放到 `references/`，在 body 中用相对路径引用，例如：`详见 [references/schema.md](references/schema.md)`
- 避免在 body 中重复 references 的大段内容，实现渐进式披露

---

## 四、渐进式披露与加载 API

### 三级加载

1. **索引（始终）**：扫描 `skills_dirs` 下各子目录的 `SKILL.md`，只解析 frontmatter 的 `name`、`description`，用于 skill 列表与 skill 工具的 `<available_skills>`。
2. **Body（按 skill 加载时）**：用户或 agent 请求某 skill 时，返回该 skill 的 SKILL.md body（当前 `get_skill_full_content` 行为）。
3. **Resources（按需）**：agent 根据 body 或对话需要，再通过「读文件」工具读取 `references/` 下指定文件；scripts 通过 bash 等工具执行，不要求预先读入内容。

### 扩展的加载器 API（basket-assistant）

在保持现有接口的前提下，增加“按需资源”的解析与路径暴露：

| 接口 | 说明 |
|------|------|
| `get_skills_index(dirs, include_ids)` | 不变；仍返回 `[(name, description)]` |
| `get_skill_full_content(skill_id, dirs)` | 不变；返回 SKILL.md body |
| `get_skill_base_dir(skill_id, dirs)` | 已有；返回 skill 根目录 |
| **新增** `get_skill_references_index(skill_id, dirs) -> List[str]` | 返回该 skill 下 `references/` 内相对路径列表（如 `["schema.md", "api_docs.md"]`），供 agent 按需读取 |
| **新增** `get_skill_scripts_index(skill_id, dirs) -> List[str]` | 返回 `scripts/` 下相对路径列表，供 agent 选择执行 |

实现要点：

- `references/`、`scripts/` 仅当目录存在时扫描；不存在则返回空列表
- 仅列出直接子级文件（或一层子目录），避免深层嵌套；大仓库可后续再考虑递归或忽略规则

---

## 五、Skill 工具行为增强

当前 skill 工具返回：

- `# Skill: {name}` + body + base_dir + 一句“相对路径相对于 base_dir”的说明

增强后（保持兼容）：

- 若存在 `references/` 或 `scripts/`，在返回末尾追加简短说明，例如：
  - `References (load with read when needed): references/schema.md, references/api_docs.md`
  - `Scripts (run from skill base dir): scripts/rotate_pdf.py, scripts/validate.sh`
- 不在此处自动注入 references 内容，由 agent 按需用 read/bash 使用

这样 agent 知道有哪些资源可用，且 base_dir 已提供，路径拼接可由现有 read/bash 工具完成。

---

## 六、工具链设计

### 6.1 init_skill（初始化新 skill）

**位置建议：** `packages/basket-assistant/scripts/init_skill.py` 或 `tools/init_skill.py`（与现有 scripts 约定一致）

**功能：**

- 创建指定名称的 skill 目录（符合 `name` 命名规范）
- 生成带 frontmatter 占位和简单 body 模板的 `SKILL.md`
- 可选：`--resources scripts,references,assets` 创建对应空目录
- 可选：`--examples` 在 scripts/references 下放占位文件（如 `README.txt` 说明用途），便于后续替换

**示例：**

```bash
poetry run python -m basket_assistant.scripts.init_skill pdf-rotate --path ~/.basket/skills --resources scripts,references
```

### 6.2 quick_validate（校验 skill 目录）

**位置建议：** `packages/basket-assistant/scripts/quick_validate.py`

**功能：**

- 校验指定 skill 目录或单个 skill 路径
- 检查：SKILL.md 存在、frontmatter 含 name/description、name 与目录名一致、name 符合正则与长度、description 长度
- 可选：检查 `references/` 下是否存在 SKILL.md 中引用的文件（简单字符串匹配即可）
- 输出：通过 / 失败及具体错误项，便于 CI 或本地迭代

**示例：**

```bash
poetry run python -m basket_assistant.scripts.quick_validate ~/.basket/skills/pdf-rotate
```

### 6.3 generate_openai_yaml（可选）

若后续需要为 UI 或外部 agent 提供展示用元数据，可增加：

- 从 SKILL.md 的 name/description（及可选 short_description）生成 `agents/openai.yaml` 等
- 本设计不强制此步骤，仅预留扩展点

---

## 七、与现有实现的衔接

### 7.1 skills_loader.py

- **保持** `_collect_skill_entries` 只读 `SKILL.md` 的 frontmatter 与 body，不依赖 scripts/references 存在
- **新增** 两个函数：`get_skill_references_index`、`get_skill_scripts_index`，基于 `get_skill_base_dir` 的路径扫描子目录
- 现有 `get_skills_index`、`get_skill_full_content`、`get_skill_base_dir` 保持不变，保证向后兼容

### 7.2 skill 工具（tools/skill.py）

- `execute_skill` 在得到 body 和 base_dir 后，若 base_dir 存在，调用 `get_skill_references_index` / `get_skill_scripts_index`，将结果以简短文本追加到返回内容
- 不改变参数和主返回格式，仅增加“可选资源列表”的说明

### 7.3 配置与发现

- `skills_dirs`、`skills_include` 不变
- 索引与加载逻辑仍只认「子目录 + SKILL.md」；scripts/references/assets 为可选附属，不影响“是否算作有效 skill”的判断

---

## 八、实施阶段建议

| 阶段 | 内容 |
|------|------|
| **Phase 1** | 在 `skills_loader.py` 中实现 `get_skill_references_index`、`get_skill_scripts_index`；skill 工具返回中追加 references/scripts 列表说明；补充单测 |
| **Phase 2** | 新增 `scripts/quick_validate.py`，对单个/多个 skill 目录做 frontmatter 与命名校验 |
| **Phase 3** | 新增 `scripts/init_skill.py`，支持 `--path`、`--resources`、`--examples` |
| **Phase 4**（可选） | 在 SKILL.md body 中约定“引用 references 的写法”（如相对路径链接），或提供简单 linter 检查 broken 引用 |

---

## 九、设计原则小结

1. **向后兼容**：仅 SKILL.md 的 skill 无需任何改动
2. **渐进式披露**：metadata → body → references/scripts 按需加载，控制上下文体积
3. **目录即约定**：scripts/references/assets 的语义由文档与工具链统一，loader 只做“列出路径”，不解释内容
4. **工具链可独立**：init_skill 与 quick_validate 可作为独立脚本使用，不依赖 agent 运行时
5. **与 Codex 对齐**：目录结构、命名、frontmatter、不引入冗余文档等与 Codex skill-creator 一致，便于用户迁移或复用 skill 内容

---

## 十、参考

- 项目内：`packages/basket-assistant/basket_assistant/core/skills_loader.py`、`basket_assistant/tools/skill.py`、`tests/test_skills.py`、`tests/test_skill_tool.py`
- Codex skill-creator：`~/.codex/skills/.system/skill-creator/SKILL.md`（工程化 skill 布局、渐进式披露、init_skill/quick_validate 流程）
