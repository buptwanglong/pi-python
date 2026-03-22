Install basket-assistant globally via uv so the `basket` command reflects the latest local code.

Run this command from the project root:

```bash
uv tool install -e packages/basket-assistant --reinstall
```

After success, verify by running:

```bash
basket --version
```
