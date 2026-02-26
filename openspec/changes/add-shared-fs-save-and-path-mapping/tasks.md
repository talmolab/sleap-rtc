# Tasks: add-shared-fs-save-and-path-mapping

## Phase 1 — Config layer (no GUI dependencies)

1. Add `PathMapping` dataclass to `config.py` with `local: str` and `worker: str` fields.
2. Add `get_path_mappings() -> list[PathMapping]` to `Config` — reads `[[path_mappings]]`
   from loaded TOML data.
3. Add `save_path_mapping(local: str, worker: str)` to `Config` — appends to
   `~/.sleap-rtc/config.toml` using `tomli-w`; skips duplicates.
4. Add `remove_path_mapping(local: str, worker: str)` to `Config` — rewrites the
   TOML file without the matching entry; warns if not found.
5. Add `translate_path(local_path: str) -> str | None` helper to `Config` — finds
   the longest matching `local` prefix and returns the translated worker path, or
   `None` if no mapping matches.
6. Write unit tests for all five config methods in `tests/test_config_path_mappings.py`.

## Phase 2 — CLI subcommands

7. Add `sleap-rtc config` command group to `cli.py`.
8. Add `add-path-mapping --local <path> --worker <path>` subcommand.
9. Add `remove-path-mapping --local <path> --worker <path>` subcommand.
10. Add `list-path-mappings` subcommand.
11. Write CLI tests in `tests/test_cli_config.py`.

## Phase 3 — SlpPathDialog: save-to-folder buttons

12. Add `save_fn: Callable[[str], None] | None = None` parameter to
    `SlpPathDialog.__init__` (mirrors existing `convert_fn`).
13. Thread `save_fn` through `run_presubmission_checks` → `check_video_paths` →
    `SlpPathDialog` (same pattern as `convert_fn`).
14. Wire `save_fn=lambda p: labels.save(p)` in SLEAP's `LearningDialog.dialog.py`
    (both repos: `scratch/repos/sleap` and `repos/sleap`).
15. Add top section to `SlpPathDialog._setup_ui`:
    - Horizontal `QFrame` separator
    - "Save as .slp to folder..." button (shown when `save_fn is not None`)
    - "Save as .pkg.slp to folder..." button (shown when `convert_fn is not None`)
16. Implement `_on_save_slp_clicked` and `_on_save_pkg_slp_clicked` — open
    `QFileDialog.getExistingDirectory`, call respective fn, show status label.
17. Write widget tests for save button visibility and click behaviour.

## Phase 4 — SlpPathDialog: auto-fill and save-mapping prompt

18. On `SlpPathDialog.__init__`, call `config.translate_path(local_path)` and
    pre-populate `self._path_edit` if a mapping is found.
19. On Continue, compare `dirname(local_path)` and `dirname(worker_path)`:
    - If they differ and no existing mapping covers this pair, show the
      save-mapping prompt (`QDialog` with Save / Skip buttons).
    - On Save: call `config.save_path_mapping(local_dir, worker_dir)`.
20. Write tests for auto-fill logic and the save-mapping prompt.

## Phase 5 — PathResolutionDialog: save-mapping prompt for videos

21. After `PathResolutionDialog` returns resolved video path mappings, iterate
    each pair and extract directory prefixes.
22. For each new prefix pair not already in config, show the save-mapping prompt.
23. Write tests for video path mapping prompt.

## Validation

- `openspec validate add-shared-fs-save-and-path-mapping --strict`
- All new tests pass: `pytest tests/test_config_path_mappings.py tests/test_cli_config.py`
- Manual E2E: open plain `.slp` → save to shared mount → browse → continue →
  save mapping → reopen and verify auto-fill
