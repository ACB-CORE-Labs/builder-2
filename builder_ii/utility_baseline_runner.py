try:
    from builder_ii_code_vault.utility_baseline_runner import run_utility_baseline
except ImportError:
    def run_utility_baseline(*args, **kwargs):
        raise RuntimeError('CodeVault is not installed. Please upgrade.')
