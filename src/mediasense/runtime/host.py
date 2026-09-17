"""Process-local host for Dataset resolution and Tool dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any

from mediasense.plan._update_execution import UpdateExecution

from .composition import DatasetRuntime, HostRequestError, tool_descriptors
from .config import ConfigurationError
from .dataset import DatasetOpenError, DatasetOpenTool, DatasetResolver


class RuntimeHost:
    """Keep opened Datasets explicit while sharing one composition policy."""

    def __init__(self, resolver: DatasetResolver | None = None) -> None:
        self.resolver = resolver or DatasetResolver()
        self.dataset_tool = DatasetOpenTool(self.resolver)
        self._datasets: dict[str, DatasetRuntime] = {}
        self._lock = Lock()

    def open_dataset(
        self, source_root: str, workspace: str | None = None
    ) -> dict[str, object]:
        try:
            opened, config, result = self.dataset_tool.open(source_root, workspace)
        except (DatasetOpenError, ConfigurationError) as error:
            code = (
                error.code
                if isinstance(error, DatasetOpenError)
                else "configuration_invalid"
            )
            result = {
                "outcome": "error",
                "error": {"code": code, "message": str(error)},
            }
            if isinstance(error, DatasetOpenError) and error.path is not None:
                result["path"] = str(error.path)
            return result
        dataset_ref = opened.manifest.dataset_ref
        try:
            runtime = DatasetRuntime(opened, config)
        except (OSError, RuntimeError, ValueError) as error:
            return {
                "outcome": "error",
                "path": str(opened.workspace),
                "error": {
                    "code": "runtime_initialization_failed",
                    "message": str(error) or type(error).__name__,
                },
            }
        with self._lock:
            self._datasets[dataset_ref] = runtime
        return result

    def call_tool(
        self,
        name: str,
        *,
        dataset_ref: str,
        request: Mapping[str, Any],
        authority: Mapping[str, Any] | None = None,
        plan_update_execution: UpdateExecution | None = None,
    ) -> dict[str, object]:
        if name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
            from .resources import contract_validator

            if not contract_validator(name).is_valid(request):
                return {
                    "error": {
                        "code": "invalid_request",
                        "message": "Invalid PreCheck request.",
                    }
                }
            if request["dataset_ref"] != dataset_ref:
                return {
                    "error": {
                        "code": "reference_not_in_dataset",
                        "message": "Conflicting Dataset references.",
                    }
                }
        with self._lock:
            runtime = self._datasets.get(dataset_ref)
        if runtime is None:
            if name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
                return {
                    "error": {
                        "code": "dataset_not_open",
                        "message": "Open this Dataset in the Host first.",
                    }
                }
            raise HostRequestError(
                "Dataset is not open in this Host process; call mediasense.dataset.open first."
            )
        if plan_update_execution is None:
            result = runtime.call(name, request, authority)
        else:
            result = runtime.call(
                name, request, authority, plan_update_execution=plan_update_execution
            )
        if name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
            contract_validator(name, str(request["action"])).validate(result)
        return result

    def apply_discrepancies(
        self, dataset_ref: str, run_ref: str
    ) -> list[dict[str, object]]:
        with self._lock:
            runtime = self._datasets[dataset_ref]
        values = []
        cursor = ""
        size = 0
        import json

        while True:
            page = runtime.apply_run.run_store.iter_metadata_discrepancies(
                run_ref,
                after_discrepancy_ref=cursor,
                limit=100,
            )
            if not page:
                return values
            size += len(json.dumps(page, ensure_ascii=False).encode())
            if size > 524288:
                raise HostRequestError(
                    "Client cannot display the complete Apply discrepancy disclosure",
                    code="confirmation_unavailable",
                )
            values.extend(page)
            cursor = str(page[-1]["discrepancy_ref"])

    def precheck_confirmation(
        self, dataset_ref: str, run_ref: str
    ) -> Mapping[str, Any] | None:
        with self._lock:
            runtime = self._datasets.get(dataset_ref)
        if runtime is None:
            return None
        try:
            record = runtime.precheck_run._store.get(run_ref)
        except KeyError as error:
            if error.args != (run_ref,):
                raise
            # Missing Runs are reported by normal Tool dispatch, not elicitation.
            return None
        if record["dataset_ref"] != dataset_ref or record["state"] != "paused":
            return None
        return record["confirmation"]

    @staticmethod
    def tools() -> tuple[dict[str, object], ...]:
        return tuple(item.to_value() for item in tool_descriptors())
