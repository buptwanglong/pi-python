# 工程化 Skill 系统实现方案（basket-assistant）

**日期：** 2026-03-15  
**类型：** 实现方案  
**依赖设计：** [2026-03-15-engineering-skills-design.md](2026-03-15-engineering-skills-design.md)  
**范围：** packages/basket-assistant 内 loader、skill 工具、脚本与测试  

---

## 一、总览

| 阶段 | 内容 | 涉及文件 |
|------|------|----------|
| **Phase 1** | 加载器新增 references/scripts 索引 API；skill 工具返回中追加资源列表；单测 | `core/skills_loader.py`, `core/__init__.py`, `tools/skill.py`, `tests/test_skills.py`, `tests/test_skill_tool.py` |
| **Phase 2** | 新增 `quick_validate` 脚本，校验 skill 目录 | 新增 `scripts/quick_validate.py`，可选 `tests/test_quick_validate.py` |
| **Phase 3** | 新增 `init_skill` 脚本，初始化新 skill | 新增 `scripts/init_skill.py`，可选 `tests/test_init_skill.py` |

---

## 二、Phase 1：加载器与 Skill 工具

### 2.1 skills_loader.py 新增 API

**文件：** `packages/basket-assistant/basket_assistant/core/skills_loader.py`

**约定：**

- 子目录名：`references`、`scripts`（与设计一致，不包含 `assets` 的索引，因 assets 通常不列给 agent 使用；若需可后续加 `get_skill_assets_index`）。
- 只列**直接子级文件**（一层），不递归。路径为相对于 skill 根目录的字符串，如 `references/schema.md`、`scripts/rotate_pdf.py`。

**新增函数 1：`get_skill_references_index`**

```python
def get_skill_references_index(skill_id: str, dirs: List[Path]) -> List[str]:
    """
    Return relative paths of files under this skill's references/ directory.
    Example: ["references/schema.md", "references/api_docs.md"].
    Empty list if skill not found or references/ does not exist.
    """
```

实现要点：

1. 用现有 `get_skill_base_dir(skill_id, dirs)` 得到 base_dir；若为 `None` 则返回 `[]`。
2. `ref_dir = base_dir / "references"`；若 `not ref_dir.is_dir()` 则返回 `[]`。
3. 遍历 `ref_dir.iterdir()`，仅保留 `f.is_file()` 的项，路径格式为 `references/{f.name}`，排序后返回。

**新增函数 2：`get_skill_scripts_index`**

```python
def get_skill_scripts_index(skill_id: str, dirs: List[Path]) -> List[str]:
    """
    Return relative paths of files under this skill's scripts/ directory.
    Example: ["scripts/rotate_pdf.py", "scripts/validate.sh"].
    Empty list if skill not found or scripts/ does not exist.
    """
```

实现要点：同 references，目录改为 `scripts`，路径前缀为 `scripts/`。

**导出：** 在 `basket_assistant/core/__init__.py` 中增加：

```python
from .skills_loader import (
    get_skill_base_dir,
    get_skill_full_content,
    get_skill_references_index,
    get_skill_scripts_index,
    get_skills_index,
)
# __all__ 中增加 "get_skill_references_index", "get_skill_scripts_index"
```

### 2.2 skill 工具（tools/skill.py）增强

**文件：** `packages/basket-assistant/basket_assistant/tools/skill.py`

- 在文件顶部 import 中增加：`get_skill_references_index`, `get_skill_scripts_index`。
- 在 `execute_skill` 中，当 `content` 非空且 `base_dir is not None` 时：
  1. 调用 `get_skill_references_index(name, dirs_inner)`、`get_skill_scripts_index(name, dirs_inner)`。
  2. 若 references 非空，在 `lines` 末尾追加一行：  
     `References (load with read when needed): {', '.join(refs)}`
  3. 若 scripts 非空，在 `lines` 末尾追加一行：  
     `Scripts (run from skill base dir): {', '.join(scripts)}`
- 不改变 `SkillParams`、`create_skill_tool` 的签名与主返回格式（`# Skill: {name}` + body + base_dir 说明），仅追加上述两行（当有数据时）。

### 2.3 Phase 1 单测

**文件：** `packages/basket-assistant/tests/test_skills.py`

- 新增 fixture 或沿用 `skills_dir`，并增加一个带 `references/` 和 `scripts/` 的 skill，例如：
  - `some-skill/references/schema.md`、`some-skill/references/api_docs.md`
  - `some-skill/scripts/rotate.py`
- 新增测试：
  - `test_get_skill_references_index`: 对包含 references 的 skill 返回 `["references/schema.md", "references/api_docs.md"]`（或等价排序）；对不含 references 的 skill 返回 `[]`；对不存在的 skill_id 返回 `[]`。
  - `test_get_skill_scripts_index`: 对包含 scripts 的 skill 返回 `["scripts/rotate.py"]`；对不含 scripts 的 skill 返回 `[]`；对不存在的 skill_id 返回 `[]`。

**文件：** `packages/basket-assistant/tests/test_skill_tool.py`

- 在现有“加载 skill 返回 content + base_dir”的测试基础上，增加一个带 references/scripts 的 skill fixture。
- 新增测试：`test_skill_tool_includes_references_and_scripts_when_present`：调用 skill 工具加载该 skill，断言返回字符串中包含 "References (load with read" 和 "Scripts (run from skill base dir)" 以及至少一个 references 路径和一个 scripts 路径。
- 可选：断言仅 SKILL.md、无 references/scripts 的 skill 返回中**不**包含 "References (load with read" 和 "Scripts (run from skill base dir)"（或这两行不存在），保证向后兼容。

---

## 三、Phase 2：quick_validate 脚本

### 3.1 脚本位置与入口

- **路径：** `packages/basket-assistant/scripts/quick_validate.py`
- 若 package 内尚无 `scripts` 目录，则新建；并添加 `scripts/__init__.py`（可为空）以便作为包引用。
- **调用方式：**  
  `poetry run python -m basket_assistant.scripts.quick_validate <path>`  
  其中 `<path>` 为单个 skill 根目录（即包含 SKILL.md 的目录），例如 `~/.basket/skills/pdf-rotate`。

### 3.2 校验逻辑（与 skills_loader 规则一致）

1. **路径存在且为目录**，否则报错退出。
2. **SKILL.md 存在** 且为文件，否则报错。
3. **解析 frontmatter**：可复用 `skills_loader._parse_frontmatter_and_body`（若保持内部可考虑复制一份简单解析逻辑到脚本内，或从 `basket_assistant.core.skills_loader` 导入；若 skills_loader 未导出 `_parse_frontmatter_and_body`，则在 quick_validate 内实现相同逻辑）。
4. **name 存在且非空**；**description 存在且非空**。
5. **name 与目录名一致**：`path.name == name_fm`。
6. **name 符合正则**：`_NAME_RE.match(name_fm)` 且 `len(name_fm) <= _NAME_MAX_LEN`（与 skills_loader 相同常量）。
7. **description 长度**：`len(description) <= _DESCRIPTION_MAX_LEN`。

任一失败即打印错误并退出码非 0；全部通过则打印 "OK" 或 "Validation passed" 并退出码 0。

### 3.3 输出与退出码

- 建议：每项错误一行，格式如 `ERROR: <message>`；最后若通过则 `Validation passed.`。
- 退出码：0 表示全部通过，非 0 表示校验失败。

### 3.4 可选测试

**文件：** `packages/basket-assistant/tests/test_quick_validate.py`

- 使用 `tmp_path` 构造合法 skill 目录、缺 name、缺 description、name 与目录名不一致、name 非法、description 超长等用例，通过 `subprocess.run` 调用 `python -m basket_assistant.scripts.quick_validate <tmp_path>`，断言退出码与输出中是否包含预期错误或 "Validation passed"。

---

## 四、Phase 3：init_skill 脚本

### 4.1 脚本位置与入口

- **路径：** `packages/basket-assistant/scripts/init_skill.py`
- **调用方式：**  
  `poetry run python -m basket_assistant.scripts.init_skill <skill-name> --path <output-dir> [--resources scripts,references,assets] [--examples]`

- **&lt;skill-name&gt;**：必须符合与 skills_loader 相同的命名规则（`^[a-z0-9]+(-[a-z0-9]+)*$`，≤64 字符），否则报错并退出。
- **--path**：必填，输出根目录（可 `~/.basket/skills`）；将在其下创建子目录 `&lt;skill-name&gt;`。
- **--resources**：可选，逗号分隔，取值 `scripts`、`references`、`assets` 的任意组合；创建对应空目录。
- **--examples**：可选；若指定，在 `scripts/` 或 `references/` 下各放一个占位文件（如 `scripts/.gitkeep` 或 `references/README.txt` 内容为 "Replace with your reference files"），便于后续替换；不创建 assets 占位也可接受。

### 4.2 行为

1. 校验 skill-name 符合正则与长度；校验 --path 存在且为目录（若不存在可询问是否创建或直接创建，建议直接创建父目录）。
2. 在 `path / skill_name` 下创建目录。
3. 写入 `SKILL.md`，内容为模板，例如：

```markdown
---
name: <skill-name>
description: <TODO: describe what this skill does and when to use it>
---

# <Skill Name>

<TODO: Add instructions and when to use scripts/references.>
```

4. 若 `--resources` 含 `scripts`、`references`、`assets`，则创建对应空目录；若 `--examples`，则在 scripts/references 下写入占位文件（见上）。
5. 打印创建结果，如 "Created skill at ..."，退出码 0。

### 4.3 可选测试

**文件：** `packages/basket-assistant/tests/test_init_skill.py`

- 使用 `tmp_path` 作为 `--path`，调用 `init_skill` 生成 skill，断言目录存在、SKILL.md 存在且 frontmatter 含正确 name、description 占位；带 `--resources scripts,references` 时断言 `scripts/`、`references/` 存在；带 `--examples` 时断言占位文件存在。再调用 `quick_validate` 应失败（因 description 为 TODO），或先替换 description 后再通过 validate。

---

## 五、与现有代码的衔接要点

- **skills_loader**：不修改 `_collect_skill_entries`、`get_skills_index`、`get_skill_full_content`、`get_skill_base_dir` 的现有逻辑；仅新增两个纯路径扫描函数，不读文件内容（除 base_dir 解析依赖的既有逻辑）。
- **skill 工具**：仅增加对 `get_skill_references_index`、`get_skill_scripts_index` 的调用与两行追加输出，无新参数。
- **配置**：不新增配置项；`skills_dirs`、`skills_include` 不变；发现逻辑仍以「子目录 + SKILL.md」为准，references/scripts 仅为可选附属。

---

## 六、验收与顺序

1. **Phase 1 验收**：`poetry run pytest packages/basket-assistant/tests/test_skills.py packages/basket-assistant/tests/test_skill_tool.py -v` 全部通过；手动加载一个带 references/scripts 的 skill，确认工具返回包含 References/Scripts 行。
2. **Phase 2 验收**：对合法 skill 目录运行 `quick_validate` 退出 0；对缺 SKILL.md 或 name 错误的目录退出非 0 并看到明确错误信息。
3. **Phase 3 验收**：运行 `init_skill my-skill --path ~/.basket/skills --resources scripts,references`，确认目录与 SKILL.md 及子目录创建正确；再对该路径运行 `quick_validate`，修正 description 后应通过。

按 Phase 1 → 2 → 3 顺序实现即可；Phase 2/3 的脚本可独立于 agent 运行时使用。
