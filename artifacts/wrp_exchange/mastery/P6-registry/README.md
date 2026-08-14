# Mastery P6.1 — Backend registry + doctor

Inventory + health for WRP backends already landed in #148.
**Not** S4 promotion. **Not** S3 enablement. M1 defaults must doctor ok.

## Commands

```bash
uv run builder-wrp backends
uv run builder-wrp doctor-backends
uv run pytest tests/test_wrp_backend_registry.py -q
```
