# Every target runs through uv against the committed uv.lock. `make check` is CI minus the
# integration, commit-hygiene and security jobs (those need network or the push range).

UV_RUN := uv run --frozen

.PHONY: setup check lint type test schemas integration demo release-dry

setup:
	uv sync --locked
	git config core.hooksPath scripts/hooks

check: lint type test schemas

lint:
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .

type:
	$(UV_RUN) mypy --strict src scripts

test:
	$(UV_RUN) pytest -m "not integration" --cov=src --cov-fail-under=85

schemas:
	$(UV_RUN) python scripts/validate_outputs.py

# pytest exits 5 when it collects nothing. Until M2 adds the first sandbox test that is the
# expected state; say so loudly instead of passing silently. Remove this allowance in M2.
integration:
	@$(UV_RUN) pytest -m integration --force-enable-socket; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "make integration: NO integration tests exist yet (first ones arrive in M2)"; exit 0; fi; \
	exit $$rc

demo:
	@echo "make demo: the SUCCESS TEST demo is built in M5 (see docs/PROGRESS.md); nothing ran" >&2
	@exit 1

release-dry:
	rm -rf dist
	uv build --no-sources
	uv export --frozen --no-dev --format cyclonedx1.5 --output-file dist/controlproof.cdx.json > /dev/null
	ls -l dist
