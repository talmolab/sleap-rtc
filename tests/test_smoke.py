"""Smoke tests for the sleap-rtc package.

These tests verify that the installed package is structurally sound — all
subpackages importable, the CLI entry point reachable, and required data
files present. They are intentionally lightweight and fast (<5 s total).

Modeled after the CLI smoke test pattern used in SLEAP and sleap-nn
(tests/test_cli.py in each repo), using Click's CliRunner for in-process
invocation and plain imports for module-level checks.

The primary failure mode these tests guard against is a packaging bug
where subpackages or data files are missing from the published wheel
(as happened in v0.0.1, where sleap_rtc.worker was not included).
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from sleap_rtc.cli import cli


# ── Subpackage imports ────────────────────────────────────────────────────────


class TestSubpackageImports:
    """Each sleap_rtc subpackage must be importable without error.

    If any of these fail, the wheel is missing __init__.py files or the
    package was not correctly included in the distribution.
    """

    def test_import_worker(self):
        """sleap_rtc.worker must be importable."""
        import sleap_rtc.worker  # noqa: F401

    def test_import_worker_class(self):
        """RTCWorkerClient must be importable from sleap_rtc.worker."""
        from sleap_rtc.worker.worker_class import RTCWorkerClient  # noqa: F401

    def test_import_client(self):
        """sleap_rtc.client must be importable."""
        import sleap_rtc.client  # noqa: F401

    def test_import_client_class(self):
        """RTCClient must be importable from sleap_rtc.client."""
        from sleap_rtc.client.client_class import RTCClient  # noqa: F401

    def test_import_auth(self):
        """sleap_rtc.auth must be importable."""
        import sleap_rtc.auth  # noqa: F401

    def test_import_jobs(self):
        """sleap_rtc.jobs must be importable."""
        import sleap_rtc.jobs  # noqa: F401

    def test_import_gui(self):
        """sleap_rtc.gui must be importable."""
        import sleap_rtc.gui  # noqa: F401

    def test_import_tui(self):
        """sleap_rtc.tui must be importable."""
        import sleap_rtc.tui  # noqa: F401


# ── CLI entry point ───────────────────────────────────────────────────────────


class TestCLIEntryPoint:
    """The CLI entry point must be reachable and respond to --help."""

    def test_main_help(self):
        """sleap-rtc --help must exit 0 and list core commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "worker" in result.output
        assert "train" in result.output
        assert "track" in result.output
        assert "login" in result.output

    def test_worker_help(self):
        """sleap-rtc worker --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "--help"])
        assert result.exit_code == 0

    def test_train_help(self):
        """sleap-rtc train --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["train", "--help"])
        assert result.exit_code == 0

    def test_track_help(self):
        """sleap-rtc track --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["track", "--help"])
        assert result.exit_code == 0

    def test_key_help(self):
        """sleap-rtc key --help must exit 0 and list subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["key", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "revoke" in result.output
        assert "show" in result.output
        assert "use" in result.output

    def test_key_list_help(self):
        """sleap-rtc key list --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["key", "list", "--help"])
        assert result.exit_code == 0

    def test_key_create_help(self):
        """sleap-rtc key create --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["key", "create", "--help"])
        assert result.exit_code == 0

    def test_key_revoke_help(self):
        """sleap-rtc key revoke --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["key", "revoke", "--help"])
        assert result.exit_code == 0

    def test_key_use_help(self):
        """sleap-rtc key use --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["key", "use", "--help"])
        assert result.exit_code == 0

    def test_worker_account_key_option(self):
        """sleap-rtc worker --help must show --account-key option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "--help"])
        assert result.exit_code == 0
        assert "account-key" in result.output

    def test_room_set_default_help(self):
        """sleap-rtc room set-default --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["room", "set-default", "--help"])
        assert result.exit_code == 0


# ── Required data files ───────────────────────────────────────────────────────


class TestRequiredDataFiles:
    """Non-Python files that must be present in the installed package.

    The filesystem viewer server (fs_viewer_server.py) serves these HTML
    files at runtime using Path(__file__).parent / "static" / "...".
    If they are missing from the wheel the server returns HTTP 500.
    """

    def test_fs_viewer_html_present(self):
        """fs_viewer.html must be bundled with the package."""
        import sleap_rtc.client.fs_viewer_server as mod

        html_path = Path(mod.__file__).parent / "static" / "fs_viewer.html"
        assert html_path.exists(), (
            f"fs_viewer.html missing from installed package at {html_path}. "
            "Check the hatchling exclude config in pyproject.toml."
        )

    def test_fs_resolve_html_present(self):
        """fs_resolve.html must be bundled with the package."""
        import sleap_rtc.client.fs_viewer_server as mod

        html_path = Path(mod.__file__).parent / "static" / "fs_resolve.html"
        assert html_path.exists(), (
            f"fs_resolve.html missing from installed package at {html_path}. "
            "Check the hatchling exclude config in pyproject.toml."
        )


# ── Dashboard smoke tests ─────────────────────────────────────────────────────


class TestDashboardJobSubmission:
    """Dashboard job submission UI elements must be present."""

    @pytest.fixture
    def app_js(self):
        return (Path(__file__).parent.parent / "dashboard" / "app.js").read_text()

    def test_submit_job_button_in_render_room_card(self, app_js):
        """renderRoomCard must include a Submit Job button calling openSubmitJobModal."""
        assert "openSubmitJobModal" in app_js
        assert "Submit Job" in app_js

    def test_open_submit_job_modal_method_defined(self, app_js):
        """openSubmitJobModal method must be defined on the app class."""
        assert "openSubmitJobModal(" in app_js

    @pytest.fixture
    def index_html(self):
        return (Path(__file__).parent.parent / "dashboard" / "index.html").read_text()

    def test_modal_wrapper_present(self, index_html):
        """submit-job-modal wrapper must exist."""
        assert 'id="submit-job-modal"' in index_html

    def test_all_four_views_present(self, index_html):
        """All four step/status views must exist inside the modal."""
        assert 'id="sj-step1"' in index_html
        assert 'id="sj-step2"' in index_html
        assert 'id="sj-step3"' in index_html
        assert 'id="sj-status"' in index_html

    def test_step_progress_indicator_present(self, index_html):
        """A step progress indicator showing 3 steps must exist."""
        assert 'sj-step-indicator' in index_html

    def test_worker_list_container_present(self, index_html):
        """Worker selection list container must exist in step 1."""
        assert 'id="sj-worker-list"' in index_html

    def test_config_dropzone_present(self, index_html):
        """Config YAML drop zone must exist in step 2."""
        assert 'id="sj-config-dropzone"' in index_html

    def test_file_browser_columns_present(self, index_html):
        """File browser columns container must exist in step 3."""
        assert 'id="sj-file-columns"' in index_html

    def test_status_label_present(self, index_html):
        """Status label element must exist in the status view."""
        assert 'id="sj-status-label"' in index_html

    def test_wandb_link_present(self, index_html):
        """WandB URL link must exist in the status view (hidden by default)."""
        assert 'id="sj-wandb-link"' in index_html

    def test_sj_render_worker_list_method_defined(self, app_js):
        """_sjRenderWorkerList method must be defined."""
        assert "_sjRenderWorkerList(" in app_js

    def test_sj_select_worker_method_defined(self, app_js):
        """sjSelectWorker method must be defined."""
        assert "sjSelectWorker(" in app_js

    def test_sj_worker_row_available_clickable(self, app_js):
        """Available workers must call sjSelectWorker on click."""
        assert "sjSelectWorker" in app_js
        assert "sj-worker-row" in app_js

    def test_sj_worker_specs_rendered(self, app_js):
        """Worker GPU specs (gpu_model, gpu_memory_mb, cuda_version, sleap_nn_version) must be read from properties."""
        assert "gpu_model" in app_js
        assert "gpu_memory_mb" in app_js
        assert "cuda_version" in app_js
        assert "sleap_nn_version" in app_js

    def test_sj_status_dot_classes(self, app_js):
        """Status dot must use idle/busy/maintenance CSS classes."""
        assert "sj-status-dot" in app_js
        assert "idle" in app_js
        assert "busy" in app_js

    # ── Task 5: YAML config upload ────────────────────────────────────────────

    def test_parse_training_config_method_defined(self, app_js):
        """parseTrainingConfig method must be defined."""
        assert "parseTrainingConfig(" in app_js

    def test_parse_training_config_reads_key_fields(self, app_js):
        """parseTrainingConfig must read batch_size, learning_rate, max_epochs, run_name."""
        assert "batch_size" in app_js
        assert "learning_rate" in app_js
        assert "max_epochs" in app_js
        assert "run_name" in app_js

    def test_dropzone_handler_wired(self, app_js):
        """Drop zone drag-and-drop handler must be implemented (_sjInitDropzone or inline)."""
        assert "sj-config-dropzone" in app_js
        assert "dragover" in app_js
        assert "drop" in app_js

    def test_config_content_stored(self, app_js):
        """Parsed YAML content must be stored as _sjConfigContent."""
        assert "_sjConfigContent" in app_js

    # ── Task 6: WebRTC signaling ──────────────────────────────────────────────

    def test_connect_to_worker_method_defined(self, app_js):
        """connectToWorker method must be defined."""
        assert "connectToWorker(" in app_js

    def test_disconnect_from_worker_method_defined(self, app_js):
        """disconnectFromWorker method must be defined."""
        assert "disconnectFromWorker(" in app_js

    def test_webrtc_offer_sent_with_client_role(self, app_js):
        """Offer message must include role: 'client' so worker skips auth challenge."""
        assert "role" in app_js
        assert "client" in app_js

    def test_datachannel_label_is_job(self, app_js):
        """Data channel must be created with label 'job'."""
        assert "createDataChannel" in app_js
        assert "'job'" in app_js or '"job"' in app_js

    def test_connect_timeout_handled(self, app_js):
        """connectToWorker must handle connection timeout."""
        assert "timeout" in app_js.lower() or "setTimeout" in app_js

    # ── Task 7: filesystem browser ────────────────────────────────────────────

    def test_send_fs_message_defined(self, app_js):
        """sendFsMessage method must be defined."""
        assert "sendFsMessage(" in app_js

    def test_init_file_browser_defined(self, app_js):
        """initFileBrowser method must be defined."""
        assert "initFileBrowser(" in app_js

    def test_render_column_defined(self, app_js):
        """renderColumn method must be defined."""
        assert "renderColumn(" in app_js

    def test_fs_protocol_messages_used(self, app_js):
        """FS_GET_MOUNTS and FS_LIST_DIR protocol strings must be sent."""
        assert "FS_GET_MOUNTS" in app_js
        assert "FS_LIST_DIR" in app_js

    def test_slp_file_selection_stored(self, app_js):
        """Selecting a .slp file must store path as _sjLabelsPath."""
        assert "_sjLabelsPath" in app_js
        assert ".slp" in app_js

    def test_step3_triggers_connect(self, app_js):
        """Entering step 3 must call connectToWorker."""
        assert "connectToWorker" in app_js

    # ── Task 8: job submission and status view ────────────────────────────────

    def test_submit_job_method_defined(self, app_js):
        """submitJob method must be defined."""
        assert "submitJob(" in app_js

    def test_submit_job_uses_job_submit_protocol(self, app_js):
        """submitJob must send JOB_SUBMIT message."""
        assert "JOB_SUBMIT" in app_js

    def test_submit_job_generates_job_id(self, app_js):
        """submitJob must generate a job_id (crypto.randomUUID)."""
        assert "randomUUID" in app_js

    def test_job_accepted_switches_to_status_view(self, app_js):
        """JOB_ACCEPTED handler must switch to status view."""
        assert "JOB_ACCEPTED" in app_js
        assert "sj-status" in app_js

    def test_job_rejected_shows_error(self, app_js):
        """JOB_REJECTED handler must show an error."""
        assert "JOB_REJECTED" in app_js

    def test_job_progress_handled(self, app_js):
        """JOB_PROGRESS handler must be present."""
        assert "JOB_PROGRESS" in app_js

    def test_job_complete_updates_status(self, app_js):
        """JOB_COMPLETE handler must update status label."""
        assert "JOB_COMPLETE" in app_js

    def test_job_failed_updates_status(self, app_js):
        """JOB_FAILED handler must update status label."""
        assert "JOB_FAILED" in app_js

    def test_wandb_link_shown_on_progress(self, app_js):
        """wandb_url in JOB_PROGRESS must reveal the WandB link element."""
        assert "wandb_url" in app_js
        assert "sj-wandb-link" in app_js

    # ── Task 9: smoke test and cleanup ────────────────────────────────────────

    def test_js_yaml_cdn_included(self, index_html):
        """js-yaml CDN script must be included in index.html for YAML parsing."""
        assert "js-yaml" in index_html

    def test_nav_tabs_present(self, index_html):
        """Core data-tab nav items (rooms, tokens, quickstart, about) must be present."""
        assert 'data-tab="rooms"' in index_html
        assert 'data-tab="tokens"' in index_html
        assert 'data-tab="quickstart"' in index_html
        assert 'data-tab="about"' in index_html
