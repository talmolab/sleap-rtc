"""Tests for ``JobExecutor.run_inference``.

These tests verify that the worker streams the output ``predictions.slp``
file to the client over the RTC data channel before signalling
``INFERENCE_COMPLETE`` (Gap 1 of the prediction-streaming v1 design doc,
``2026-04-22-prediction-streaming-v1-design.md``).
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sleap_rtc.worker.job_executor import JobExecutor


def _make_process(returncode: int = 0):
    """Build a MagicMock subprocess whose stdout yields EOF immediately.

    ``run_inference`` uses ``async for raw_line in process.stdout:`` so
    ``process.stdout`` must be an async iterable.  A list yields its items
    then raises ``StopAsyncIteration``, matching real pipe EOF.
    """
    proc = MagicMock()
    proc.pid = 12345
    proc.returncode = returncode

    class _EmptyAsyncIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    proc.stdout = _EmptyAsyncIter()
    proc.wait = AsyncMock()
    return proc


@pytest.mark.asyncio
async def test_run_inference_streams_predictions_before_complete(tmp_path):
    """Worker must stream predictions via ``send_file`` before ``INFERENCE_COMPLETE``.

    Verifies the fix for Gap 1 — predictions must be streamed to the client,
    not merely referenced by a worker-side path.
    """
    predictions_path = tmp_path / "predictions.slp"
    predictions_path.write_bytes(b"fake slp content for test")

    channel = MagicMock()
    channel.readyState = "open"

    file_manager = MagicMock()
    file_manager.send_file = AsyncMock()

    worker = MagicMock()
    worker.file_manager = file_manager

    # Record call ordering across both send_file (async) and channel.send
    # (sync) using a shared counter on a wrapping container.
    call_order: list[str] = []

    async def _record_send_file(*args, **kwargs):
        call_order.append("send_file")

    file_manager.send_file.side_effect = _record_send_file

    def _record_channel_send(msg):
        call_order.append(f"channel.send:{msg}")

    channel.send = MagicMock(side_effect=_record_channel_send)

    executor = JobExecutor(worker=worker, capabilities=MagicMock())

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_make_process(returncode=0)),
    ):
        await executor.run_inference(
            channel,
            cmd=["true"],
            predictions_path=str(predictions_path),
        )

    # 1. send_file was awaited exactly once, with the channel and predictions path.
    file_manager.send_file.assert_awaited_once()
    send_file_args = file_manager.send_file.call_args
    assert send_file_args.args[0] is channel, (
        f"send_file must be called with the RTC channel as first arg; got "
        f"{send_file_args.args[0]!r}"
    )
    assert send_file_args.args[1] == str(predictions_path), (
        f"send_file must be called with the predictions path; got "
        f"{send_file_args.args[1]!r}"
    )

    # 2. INFERENCE_COMPLETE was sent.
    inf_complete_msgs = [
        entry
        for entry in call_order
        if entry.startswith("channel.send:INFERENCE_COMPLETE::")
    ]
    assert (
        len(inf_complete_msgs) == 1
    ), f"Exactly one INFERENCE_COMPLETE expected; call_order={call_order!r}"

    # 3. send_file was awaited BEFORE INFERENCE_COMPLETE was sent.
    send_file_idx = call_order.index("send_file")
    inf_complete_idx = call_order.index(inf_complete_msgs[0])
    assert send_file_idx < inf_complete_idx, (
        f"send_file must be awaited BEFORE INFERENCE_COMPLETE is sent; "
        f"call_order={call_order!r}"
    )

    # 4. INFERENCE_FAILED must NOT be sent on the happy path.
    assert not any(
        entry.startswith("channel.send:INFERENCE_FAILED::") for entry in call_order
    ), f"INFERENCE_FAILED must not be emitted on success; call_order={call_order!r}"


@pytest.mark.asyncio
async def test_run_inference_emits_failed_when_streaming_raises(tmp_path):
    """If ``send_file`` raises, the worker must send ``INFERENCE_FAILED`` and
    must NOT send ``INFERENCE_COMPLETE``.
    """
    predictions_path = tmp_path / "predictions.slp"
    predictions_path.write_bytes(b"fake slp content for test")

    channel = MagicMock()
    channel.readyState = "open"
    channel.send = MagicMock()

    file_manager = MagicMock()
    file_manager.send_file = AsyncMock(side_effect=RuntimeError("boom"))

    worker = MagicMock()
    worker.file_manager = file_manager

    executor = JobExecutor(worker=worker, capabilities=MagicMock())

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_make_process(returncode=0)),
    ):
        await executor.run_inference(
            channel,
            cmd=["true"],
            predictions_path=str(predictions_path),
        )

    sent = [c.args[0] for c in channel.send.call_args_list if c.args]
    assert any(
        isinstance(s, str) and s.startswith("INFERENCE_FAILED::") for s in sent
    ), f"Expected INFERENCE_FAILED after streaming failure; got {sent!r}"
    assert not any(
        isinstance(s, str) and s.startswith("INFERENCE_COMPLETE::") for s in sent
    ), f"INFERENCE_COMPLETE must not be sent after streaming failure; got {sent!r}"


@pytest.mark.asyncio
async def test_inference_failed_with_quote_in_error_is_valid_json(tmp_path):
    """When the worker emits INFERENCE_FAILED, the wire payload after the
    ``INFERENCE_FAILED::`` prefix must be valid JSON regardless of what
    characters appear in the interpolated error string. Real Python
    exception messages routinely contain ``"`` and ``\\``.
    """
    predictions_path = tmp_path / "predictions.slp"
    predictions_path.write_bytes(b"x")

    channel = MagicMock()
    channel.readyState = "open"
    channel.send = MagicMock()

    file_manager = MagicMock()
    # Force send_file to raise an exception whose str() contains a `"`.
    file_manager.send_file = AsyncMock(
        side_effect=RuntimeError('boom: file "/tmp/with quote".slp missing')
    )

    worker = MagicMock()
    worker.file_manager = file_manager
    executor = JobExecutor(worker=worker, capabilities=MagicMock())

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_make_process(returncode=0)),
    ):
        await executor.run_inference(
            channel,
            cmd=["true"],
            predictions_path=str(predictions_path),
        )

    failed_calls = [
        call.args[0]
        for call in channel.send.call_args_list
        if isinstance(call.args[0], str)
        and call.args[0].startswith("INFERENCE_FAILED::")
    ]
    assert (
        len(failed_calls) == 1
    ), f"Expected exactly one INFERENCE_FAILED; got {failed_calls!r}"

    payload_str = failed_calls[0].split("::", 1)[1]
    # MUST be parseable as JSON — this assertion is the whole point of the test.
    payload = json.loads(payload_str)
    assert "error" in payload
    assert "boom" in payload["error"]
    assert "with quote" in payload["error"]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "Windows reserves '\"' as an invalid filename character "
        '(NTFS / FAT disallow < > : " | ? * in filenames), so we cannot '
        "create a real file at this path on Windows. The fix being verified "
        "(json.dumps safety) is platform-independent and is exercised by the "
        "macOS and Linux runs."
    ),
)
@pytest.mark.asyncio
async def test_inference_complete_with_quote_in_path_is_valid_json(tmp_path):
    """Same property for INFERENCE_COMPLETE — the predictions_path field
    must round-trip through JSON even if the path contains ``"`` or ``\\``.
    """
    weird_path = tmp_path / 'has"quote.slp'
    weird_path.write_bytes(b"x")

    channel = MagicMock()
    channel.readyState = "open"
    channel.send = MagicMock()

    file_manager = MagicMock()
    file_manager.send_file = AsyncMock()

    worker = MagicMock()
    worker.file_manager = file_manager
    executor = JobExecutor(worker=worker, capabilities=MagicMock())

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_make_process(returncode=0)),
    ):
        await executor.run_inference(
            channel,
            cmd=["true"],
            predictions_path=str(weird_path),
        )

    complete_calls = [
        call.args[0]
        for call in channel.send.call_args_list
        if isinstance(call.args[0], str)
        and call.args[0].startswith("INFERENCE_COMPLETE::")
    ]
    assert len(complete_calls) == 1
    payload = json.loads(complete_calls[0].split("::", 1)[1])
    assert payload["predictions_path"] == str(weird_path)
