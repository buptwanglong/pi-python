# 工程化 Skill 系统设计（Codex 风格）

本方案为 basket-assistant 引入 **Codex 风格** 的工程化 skill：支持 `scripts/`、`references/`、`assets/` 目录与渐进式披露，并提供 init/validate 工具链。

**完整设计文档：** [docs/plans/2026-03-15-engineering-skills-design.md](plans/2026-03-15-engineering-skills-design.md)  
**基于 basket-assistant 的实现方案：** [docs/plans/2026-03-15-engineering-skills-implementation.md](plans/2026-03-15-engineering-skills-implementation.md)

---

## 目标

| 目标 | 说明 |
|------|------|
| **工程化布局** | 每个 skill 除 `SKILL.md` 外可包含 `scripts/`、`references/`、`assets/` |
| **渐进式披露** | 索引只读 metadata → 按需加载 body → references/scripts 由 agent 按需读或执行 |
| **工具链** | `init_skill` 初始化新 skill，`quick_validate` 校验 frontmatter 与命名 |
| **向后兼容** | 仅含 `SKILL.md` 的现有 skill 无需改动 |

---

## 目录结构约定

```
skill-name/
├── SKILL.md          # 必选：name + description frontmatter + 正文
├── scripts/          # 可选：可执行脚本（按路径执行，不强制读入上下文）
├── references/       # 可选：按需加载的参考文档（由 agent 用 read 读取）
└── assets/           # 可选：模板、图片等，一般不读入上下文
```

---

## 加载与 API

- **索引**：仅解析各 skill 的 `SKILL.md` frontmatter（`name`、`description`），用于 `<available_skills>`。
- **Body**：加载某 skill 时返回 SKILL.md 正文（现有 `get_skill_full_content`）。
- **Resources**：新增 `get_skill_references_index()`、`get_skill_scripts_index()`，返回该 skill 下 references/scripts 的相对路径列表；skill 工具在返回中附带这些列表，由 agent 按需 read/bash。

---

## 工具链

| 工具 | 作用 |
|------|------|
| **init_skill** | 创建 skill 目录、SKILL.md 模板，可选 `--resources scripts,references,assets`、`--examples` |
| **quick_validate** | 校验 SKILL.md 存在、frontmatter、name 与目录名一致、命名规范与长度 |

---

## 实施阶段（建议）

1. **Phase 1**：`skills_loader` 增加 references/scripts 索引 API；skill 工具返回中追加资源列表说明；单测。
2. **Phase 2**：新增 `scripts/quick_validate.py`。
3. **Phase 3**：新增 `scripts/init_skill.py`。
4. **Phase 4（可选）**：SKILL.md 中引用 references 的写法约定或简单 linter。

详见 [完整设计](plans/2026-03-15-engineering-skills-design.md)。
