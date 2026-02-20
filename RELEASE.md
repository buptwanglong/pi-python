# 发布到 PyPI

本仓库是 monorepo，包含 5 个可独立发布到 PyPI 的包，**必须按依赖顺序**发布。

## 依赖顺序

1. **pi-ai** — 无内部 path 依赖  
2. **pi-tui** — 无内部 path 依赖  
3. **pi-agent** — 依赖 `pi-ai`  
4. **pi-trajectory** — 依赖 `pi-ai`、`pi-agent`  
5. **pi-coding-agent** — 依赖 `pi-ai`、`pi-agent`、`pi-trajectory`、`pi-tui`（可选）

发布顺序必须严格按上述顺序执行，否则依赖包未上传时后续包会构建或安装失败。

本地开发时各包通过 `path = "../..."` 引用；发布前需要把 path 依赖改成版本约束（如 `^0.1.0`），否则用户 `pip install` 会找不到依赖。

## 方式一：用脚本一键构建/发布（推荐）

```bash
# 安装依赖
pip install poetry twine

# 仅构建（生成各包 dist/ 下的 sdist 和 wheel）
./scripts/publish-to-pypi.sh

# 构建并上传到 PyPI
./scripts/publish-to-pypi.sh --upload
```

上传前需配置 PyPI 凭据（二选一）：

- **Token**：在 https://pypi.org/manage/account/token/ 创建，然后：
  ```bash
  export TWINE_USERNAME=__token__
  export TWINE_PASSWORD=pypi-xxxx
  ```
- 或使用 **用户名 + 密码**：`TWINE_USERNAME` / `TWINE_PASSWORD`

指定版本（否则用各包 `pyproject.toml` 里的 version，通常与 pi-ai 一致）：

```bash
VERSION=0.2.0 ./scripts/publish-to-pypi.sh --upload
```

脚本会：

1. 运行 `scripts/prepare_pypi_release.py`，把 path 依赖临时改成版本约束  
2. 按顺序在各包目录执行 `poetry build`（可选时再执行 `twine upload`）  
3. 运行 `prepare_pypi_release.py --restore` 恢复 `pyproject.toml`

## 方式二：手动步骤

1. **准备 release 依赖**（把 path 改成版本）  
   ```bash
   python3 scripts/prepare_pypi_release.py
   # 指定版本：python3 scripts/prepare_pypi_release.py --version 0.2.0
   ```

2. **按顺序构建并上传**  
   ```bash
   cd packages/pi-ai && poetry build && twine upload dist/* && cd ../..
   cd packages/pi-tui && poetry build && twine upload dist/* && cd ../..
   cd packages/pi-agent && poetry build && twine upload dist/* && cd ../..
   cd packages/pi-trajectory && poetry build && twine upload dist/* && cd ../..
   cd packages/pi-coding-agent && poetry build && twine upload dist/* && cd ../..
   ```

3. **恢复本地开发用的 path 依赖**  
   ```bash
   python3 scripts/prepare_pypi_release.py --restore
   ```

## 仅构建、不上传

- 用脚本：`./scripts/publish-to-pypi.sh`（不加 `--upload`）  
- 或先 `prepare_pypi_release.py`，再在各包下执行 `poetry build`，最后 `--restore`。

产物在各自 `packages/<pkg>/dist/` 下，可本地测试安装：

```bash
pip install packages/pi-coding-agent/dist/pi_coding_agent-0.1.0-py3-none-any.whl
```

## 测试网 PyPI（TestPyPI）

先发到 TestPyPI 验证再发正式 PyPI：

```bash
twine upload --repository testpypi packages/pi-ai/dist/*
# 安装测试：pip install -i https://test.pypi.org/simple/ pi-coding-agent
```

## 版本与兼容性

- 各包 `version` 建议保持一致（如 0.1.0），在各自 `pyproject.toml` 里改好再跑脚本。  
- 依赖约束使用 `^0.1.0`，与 [Poetry 的 caret 规则](https://python-poetry.org/docs/dependency-specification/) 一致，即兼容 `>=0.1.0,<0.2.0`。

## CI 示例（GitHub Actions）

可在 tag 推送时自动发布，例如：

```yaml
# .github/workflows/publish.yml
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry twine
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          VERSION=${GITHUB_REF#refs/tags/v} ./scripts/publish-to-pypi.sh --upload
```

注意：tag 名需与版本一致（如 `v0.1.0`），或从 tag 解析出 `VERSION` 再传给脚本。
