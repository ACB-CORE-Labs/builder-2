class CodeVaultNotInstalledError(NotImplementedError):
    pass

try:
    import builder_ii_code_vault  # noqa: F401
    from builder_ii_code_vault.utility_baseline_runner import run_utility_baseline
except ImportError:
    def run_utility_baseline(*args, **kwargs):
        raise CodeVaultNotInstalledError("The CodeVault utility baseline requires the `builder-ii-code-vault` package.")
