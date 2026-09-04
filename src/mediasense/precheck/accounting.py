"""Durable, resumable accounting for PreCheck source discovery.

This module owns only Slice 1 orchestration. SQLite layout and source
fingerprinting remain private implementation details, not PreCheck-to-Plan
contracts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from uuid import uuid4

from ._accounting_sqlite import SQLiteAccounting
from ._accounting_types import (
    AccountedItem,
    ChangeKind,
    RecordedIssue,
    RemovedSource,
    WorkingRunStatus,
    WorkingRunSummary,
)
from ._fingerprint import (
    SourceChangedDuringRead,
    fingerprint_candidate as _fingerprint_candidate,
)
from .discovery import DiscoveryIssue, DiscoveryIssueCode, discover_source_events
from .source_attachment import (
    AttachmentState,
    SourceAttachment,
    SourceAttachmentError,
    SourceAttachmentProbe,
    SourceRebinding,
    SourceRebindRequired,
    new_reuse_domain,
    probe_source_attachment,
)


class AccountingStore:
    """Coordinate discovery with the minimal private SQLite working store."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self._database = SQLiteAccounting(self.database_path)

    def register_dataset(self, dataset_id: str) -> None:
        """Register only Dataset identity; source locations belong to runs."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database.initialize()
        self._database.register_dataset(dataset_id)

    def start_or_resume_run(
        self,
        dataset_id: str,
        source_root: Path,
        *,
        rebind_reason: str | None = None,
    ) -> str:
        """Create or resume a run with an explicit source attachment.

        A changed locator is accepted automatically only when the current root
        identity matches. Otherwise an explicit reason creates a new reuse
        domain so candidate fingerprints cannot authorize cross-root reuse.
        """

        probe = self._probe(source_root)
        self._database.dataset(dataset_id)
        existing = self._database.unfinished_run(dataset_id)
        if existing is not None:
            self._resume_attachment(existing, probe, rebind_reason=rebind_reason)
            return existing

        previous = self._database.latest_attachment(dataset_id)
        reuse_domain = new_reuse_domain()
        binding_reason = "initial"
        previous_attachment: SourceAttachment | None = None
        continuity: str | None = None
        expected_volume_identity = probe.volume_identity
        expected_root_identity = probe.root_identity
        identity_strength = probe.identity_strength
        reason = rebind_reason.strip() if rebind_reason else None
        if previous is not None:
            if _same_root_identity(previous, probe):
                reuse_domain = previous.reuse_domain
                binding_reason = "verified_existing_source"
                if probe.source_root != previous.source_root:
                    previous_attachment = previous
                    continuity = "verified_root_identity"
            elif probe.source_root == previous.source_root and reason is None:
                reuse_domain = previous.reuse_domain
                binding_reason = "awaiting_compatible_remount"
                expected_volume_identity = previous.volume_identity
                expected_root_identity = previous.root_identity
                identity_strength = previous.identity_strength
            elif reason:
                if probe.state is not AttachmentState.AVAILABLE:
                    raise SourceAttachmentError(
                        "cannot rebind to an unavailable source root"
                    )
                binding_reason = f"operator_confirmed:{reason}"
                previous_attachment = previous
                continuity = "operator_confirmed_unverified"
            else:
                raise SourceRebindRequired(
                    "Dataset source changed; provide rebind_reason to start a new run"
                )
        attachment = SourceAttachment(
            source_root=probe.source_root,
            volume_identity=expected_volume_identity,
            root_identity=expected_root_identity,
            identity_strength=identity_strength,
            reuse_domain=reuse_domain,
            binding_reason=binding_reason,
            capabilities=probe.capabilities,
        )
        run_id = uuid4().hex
        self._database.create_run(
            run_id,
            dataset_id,
            attachment,
            previous_attachment=previous_attachment,
            continuity=continuity,
        )
        return run_id

    def get_source_attachment(self, run_id: str) -> SourceAttachment:
        return self._database.active_attachment(run_id)

    def resume_run_attachment(
        self,
        run_id: str,
        source_root: Path,
        *,
        rebind_reason: str | None = None,
    ) -> SourceAttachment:
        """Revalidate one exact Run attachment without selecting or creating a Run."""

        self._database.load_run(run_id)
        self._resume_attachment(
            run_id,
            self._probe(source_root),
            rebind_reason=rebind_reason,
        )
        return self.get_source_attachment(run_id)

    def get_source_rebindings(self, run_id: str) -> tuple[SourceRebinding, ...]:
        return self._database.get_rebindings(run_id)

    def process_run(
        self,
        run_id: str,
        *,
        batch_size: int = 256,
        max_batches: int | None = None,
        should_continue: Callable[[], bool] | None = None,
        force_rescan: bool = False,
    ) -> WorkingRunSummary:
        """Process a run in durable batches and optionally pause after a limit.

        Re-entering this method for an unfinished run reuses already committed
        observations. The filesystem is enumerated again so additions before the
        checkpoint and changes during an interrupted scan are not hidden, while
        stable committed items are not re-fingerprinted.
        """

        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_batches is not None and max_batches < 1:
            raise ValueError("max_batches must be positive when provided")

        run = self._database.load_run(run_id)
        if (
            WorkingRunStatus(run["status"])
            in {
                WorkingRunStatus.COMPLETED,
                WorkingRunStatus.COMPLETED_WITH_ISSUES,
            }
            and not force_rescan
        ):
            return self.get_run_summary(run_id)

        attachment = self._database.active_attachment(run_id)
        probe = self._probe(attachment.source_root)
        if probe.state is not AttachmentState.AVAILABLE:
            self._database.block_run(
                run_id,
                attachment.source_root,
                DiscoveryIssueCode.ROOT_UNAVAILABLE,
            )
            return self.get_run_summary(run_id)

        if not _same_root_identity(attachment, probe):
            self._database.block_run(
                run_id,
                attachment.source_root,
                DiscoveryIssueCode.ROOT_UNAVAILABLE,
            )
            return self.get_run_summary(run_id)
        scan_generation = self._database.prepare_run(run_id, probe)

        pending = []
        batches = 0
        blocking_issue_code: DiscoveryIssueCode | None = None
        with self._database.connect() as lookup_connection:
            for event in discover_source_events(attachment.source_root):
                if isinstance(event, DiscoveryIssue) and event.blocked:
                    blocking_issue_code = event.code
                if self._database.event_is_committed(
                    lookup_connection,
                    run_id,
                    scan_generation,
                    event,
                ):
                    continue
                pending.append(event)
                if len(pending) < batch_size:
                    continue
                self._database.commit_batch(
                    run_id,
                    scan_generation,
                    pending,
                    _fingerprint_candidate,
                )
                pending.clear()
                batches += 1
                if should_continue is not None and not should_continue():
                    self._database.set_status(run_id, WorkingRunStatus.PAUSED)
                    return self.get_run_summary(run_id)
                if max_batches is not None and batches >= max_batches:
                    if blocking_issue_code is None:
                        self._database.set_status(run_id, WorkingRunStatus.PAUSED)
                    else:
                        self._database.set_status(
                            run_id,
                            WorkingRunStatus.BLOCKED,
                            blocked_reason=blocking_issue_code,
                        )
                    return self.get_run_summary(run_id)

        if pending:
            self._database.commit_batch(
                run_id,
                scan_generation,
                pending,
                _fingerprint_candidate,
            )
        if should_continue is not None and not should_continue():
            self._database.set_status(run_id, WorkingRunStatus.PAUSED)
            return self.get_run_summary(run_id)

        if blocking_issue_code is not None:
            self._database.set_status(
                run_id,
                WorkingRunStatus.BLOCKED,
                blocked_reason=blocking_issue_code,
            )
            return self.get_run_summary(run_id)

        self._database.finish_run(run_id, scan_generation)
        return self.get_run_summary(run_id)

    def get_run_summary(self, run_id: str) -> WorkingRunSummary:
        return self._database.get_run_summary(run_id)

    def get_run_items(self, run_id: str) -> tuple[AccountedItem, ...]:
        return self._database.get_run_items(run_id)

    def count_run_items(
        self,
        run_id: str,
        *,
        scope: str | None = None,
        kinds: Iterable[str] = (),
        require_source_revision: bool = False,
    ) -> int:
        return self._database.count_run_items(
            run_id,
            scope=scope,
            kinds=kinds,
            require_source_revision=require_source_revision,
        )

    def iter_run_items(
        self,
        run_id: str,
        *,
        page_size: int = 1_000,
    ) -> Iterator[AccountedItem]:
        return self._database.iter_run_items(run_id, page_size=page_size)

    def iter_scope_inventory_facts(
        self,
        run_id: str,
        *,
        page_size: int = 1_000,
    ) -> Iterator[dict[str, object]]:
        return self._database.iter_scope_inventory_facts(run_id, page_size=page_size)

    def apply_scope_selection(
        self,
        run_id: str,
        selection: Mapping[str, object],
        *,
        selection_digest: str,
    ) -> tuple[int, int]:
        return self._database.apply_scope_selection(
            run_id,
            selection,
            selection_digest=selection_digest,
        )

    def associated_paths(self, run_id: str, relative_path: Path) -> tuple[Path, ...]:
        return self._database.associated_paths(run_id, relative_path)

    def get_run_issues(self, run_id: str) -> tuple[RecordedIssue, ...]:
        return self._database.get_run_issues(run_id)

    def get_run_removals(self, run_id: str) -> tuple[RemovedSource, ...]:
        return self._database.get_run_removals(run_id)

    def _probe(self, source_root: Path) -> SourceAttachmentProbe:
        return probe_source_attachment(source_root, self.database_path.parent)

    def _resume_attachment(
        self,
        run_id: str,
        probe: SourceAttachmentProbe,
        *,
        rebind_reason: str | None,
    ) -> None:
        current = self._database.active_attachment(run_id)
        reason = rebind_reason.strip() if rebind_reason else None
        if probe.source_root == current.source_root:
            if probe.state is not AttachmentState.AVAILABLE:
                return
            if _same_root_identity(current, probe):
                return
            if current.root_identity is None:
                self._database.rebind_run(
                    run_id,
                    probe,
                    reuse_domain=current.reuse_domain,
                    reason="first available source observation",
                    continuity="first_available_observation",
                )
                return
            if reason is None:
                return
        if _same_root_identity(current, probe):
            self._database.rebind_run(
                run_id,
                probe,
                reuse_domain=current.reuse_domain,
                reason="verified root relocation",
                continuity="verified_root_identity",
            )
            return
        if reason is None:
            raise SourceRebindRequired(
                "source attachment changed; explicit rebind_reason is required"
            )
        if probe.state is not AttachmentState.AVAILABLE:
            raise SourceAttachmentError("cannot rebind to an unavailable source root")
        self._database.rebind_run(
            run_id,
            probe,
            reuse_domain=new_reuse_domain(),
            reason=reason,
            continuity="operator_confirmed_unverified",
        )


def _same_root_identity(
    existing: SourceAttachment,
    observed: SourceAttachmentProbe,
) -> bool:
    return (
        observed.state is AttachmentState.AVAILABLE
        and existing.root_identity is not None
        and existing.root_identity == observed.root_identity
    )


__all__ = [
    "AccountedItem",
    "AccountingStore",
    "ChangeKind",
    "RecordedIssue",
    "RemovedSource",
    "SourceChangedDuringRead",
    "SourceAttachment",
    "SourceAttachmentError",
    "SourceRebinding",
    "SourceRebindRequired",
    "WorkingRunStatus",
    "WorkingRunSummary",
]
