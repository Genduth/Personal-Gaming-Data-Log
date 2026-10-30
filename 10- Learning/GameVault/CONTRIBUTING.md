# Contributing

Create focused changes and keep provider adapters isolated under `src/gamevault/services`. Database changes require a new numbered migration; do not edit a migration after it has been released. Preserve the stable column names exposed by the `powerbi` schema, or update the TMDL model in the same change.

Before opening a pull request, run:

```bash
ruff check .
pytest
```

Never commit API keys, account tokens, raw personal exports or database dumps. Tests and screenshots must use clearly labelled demonstration data.
