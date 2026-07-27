# Third-party notices

builder-II is licensed under the [MIT License](LICENSE). This file lists third-party software
builder-II integrates with, and clarifies what is and is not distributed as part of this
repository.

## Codename Goose

builder-II uses [Codename Goose](https://goose-docs.ai/) as its primary local execution-capable
agent runtime — see [`docs/GOOSE_CONVENTION_LAYER.md`](docs/GOOSE_CONVENTION_LAYER.md) and
[`docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md`](docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md)
for the integration design.

- **Project:** Codename Goose, part of the [Agentic AI Foundation](https://aaif.io/)
  (`aaif-goose/goose` on GitHub).
- **License:** Apache License 2.0, per Goose's own documentation and repository at the time of
  writing.
- **What builder-II ships:** No Goose source code or binary is vendored, embedded, compiled, or
  redistributed in this repository or in the `builder-ii` package. `builder_ii/tui`,
  `builder_ii/adapters/goose/`, and related modules contain only builder-II's own governance,
  projection, and convention-layer code that calls an independently installed `goose` executable
  as a subprocess.
- **How Goose is obtained:** `scripts/install-goose.sh` downloads and installs Goose directly from
  AAIF's own official release channel (`github.com/aaif-goose/goose/releases`), verified against a
  pinned SHA-256 checksum, onto the user's own machine, under the terms AAIF itself distributes it
  under. builder-II never re-hosts or re-packages that installer or binary.

Because builder-II does not distribute Goose's source or object code, Apache License 2.0's
redistribution conditions (§4 — including a copy of the license, a NOTICE file, and a statement of
changes) do not attach to builder-II's own repository or distribution. This section exists for
clarity, not because builder-II is redistributing Apache-licensed material.

## CodeVault

The commercial `builder-ii-code-vault` plugin (a separate, privately licensed repository — see the
[CodeVault section of `README.md`](README.md#codevault-paid-commercial-plugin-upgrade)) is not
covered by this repository's MIT license and is not referenced further here.

## Everything else

Python and Rust dependencies declared in `pyproject.toml` / `builder_ii_validation_rs/Cargo.toml`
each retain their own upstream licenses; this repository does not relicense them. This file will be
expanded if a formal licensing audit (see
[`docs/promotions/public_cut_over.md`](docs/promotions/public_cut_over.md)) identifies anything
further to disclose here before or after the open-source cut-over.
