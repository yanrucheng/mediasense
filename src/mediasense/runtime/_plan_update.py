"""Bind one MCP update's cancellation and optional progress to synchronous Plan."""

from concurrent.futures import CancelledError
import logging

import anyio
from mcp.shared.exceptions import NoBackChannelError

from mediasense.plan._update_execution import UpdateCancelled, UpdateExecution


_LOGGER = logging.getLogger(__name__)


async def call_plan_update(runtime, context, dataset_ref, request, authority):
    cancelled_error = anyio.get_cancelled_exc_class()
    progress_available = True

    def check_cancelled():
        # AnyIO's supported worker-thread API observes the enclosing request
        # scope even though run_sync shields its waiter until the thread exits.
        try:
            anyio.from_thread.check_cancelled()
        except cancelled_error as error:
            raise UpdateCancelled() from error

    async def progress(event):
        nonlocal progress_available
        # A stalled/closed progress channel must not hold the update hostage.
        with anyio.move_on_after(0.25, shield=True) as emission:
            await context.session.report_progress(
                event["read_calls"],
                message=f"Plan update: {event['phase']}; finished Read calls: {event['read_calls']}.",
            )
        if emission.cancel_called:
            progress_available = False

    def observe(event):
        nonlocal progress_available
        if (
            not progress_available
            or context.meta is None
            or context.meta.get("progress_token") is None
        ):
            return
        try:
            anyio.from_thread.run(progress, event)
        except (
            cancelled_error,
            CancelledError,
            NoBackChannelError,
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            OSError,
        ):
            progress_available = False
            _LOGGER.debug("Plan progress channel is no longer available")

    request_id = request.get("request_id")
    _LOGGER.info(
        "Plan update RPC correlation: rpc_id=%r dataset_ref=%r request_id=%r",
        context.request_id,
        dataset_ref,
        request_id if isinstance(request_id, str) else None,
    )
    execution = UpdateExecution(check_cancelled=check_cancelled, observe=observe)
    return await anyio.to_thread.run_sync(
        lambda: runtime.call_tool(
            "mediasense.plan.work",
            dataset_ref=dataset_ref,
            request=request,
            authority=authority,
            plan_update_execution=execution,
        )
    )
