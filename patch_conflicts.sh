#!/bin/bash
set -ex

# README.md: Keep HEAD (main)
git checkout --ours README.md

# docs/manual.md: Keep HEAD (main)
git checkout --ours docs/manual.md

# builder_ii/verification_profiles.py: Keep 93570e5 (theirs)
git checkout --theirs builder_ii/verification_profiles.py

# tests/test_context_pack.py: Keep 93570e5 (theirs)
git checkout --theirs tests/test_context_pack.py

# tests/test_profile_resolution.py: Keep 93570e5 (theirs)
git checkout --theirs tests/test_profile_resolution.py

# tests/test_runtime_governance_release_audit.py: Keep 93570e5 (theirs)
git checkout --theirs tests/test_runtime_governance_release_audit.py

# Add all resolved files to git
git add README.md docs/manual.md builder_ii/verification_profiles.py tests/test_context_pack.py tests/test_profile_resolution.py tests/test_runtime_governance_release_audit.py
git add builder_ii/cli/verification_cli.py builder_ii/config.py builder_ii/context.py builder_ii/goose_setup.py builder_ii/wizard_framework.py builder_ii/tui/app.py

