# Parked

Good ideas that are out of scope right now. Each entry: date, where it came from, and why it
waits.

- **2026-09-29, V2 plan: FedRAMP 20x KSI mapping file.** The KSI definitions are now verified from
  the primary FedRAMP source (SPEC_NOTES §4). The mapping file stays in V2 unless the owner pulls
  it into the MVP with an ADR.
- **2026-09-29, M0 setup: run gitleaks in `make check`.** It runs in CI only today because
  gitleaks is not installed locally. It could be added once gitleaks is installed.
- **2026-09-29, M0 setup: `uv audit`.** uv 0.12.9 has `uv audit`, which could replace pip-audit and
  its dependencies. pip-audit is the planned tool, so this waits for an owner decision.
