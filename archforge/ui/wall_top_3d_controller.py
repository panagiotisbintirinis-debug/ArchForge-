from __future__ import annotations

from typing import Optional, Sequence

from archforge.core.wall_top_handles import wall_top_handle_payload
from archforge.core.wall_top_transaction import WallTopEndpointTransaction


class WallTop3DController:
    """View-facing controller for semantic wall-top direct manipulation.

    The WebGL layer owns only pointer/raycast presentation. This controller owns the
    transient interaction transaction and derives handle payloads from the authoritative
    Document. Committed edits still flow through WallTopEndpointTransaction ->
    SetWallTopEndpoint -> CommandStack -> Document.
    """

    def __init__(self, doc, stack):
        self.doc = doc
        self.stack = stack
        self._transaction: Optional[WallTopEndpointTransaction] = None

    @property
    def active(self) -> bool:
        return self._transaction is not None

    def handles(self, selection: Optional[Sequence[str]] = None):
        selection = self.doc.selection if selection is None else selection
        if self._transaction is None:
            return wall_top_handle_payload(self.doc, selection)
        return wall_top_handle_payload(
            self.doc,
            selection,
            preview_endpoint=self._transaction.endpoint,
            preview_height=self._transaction.preview_height,
        )

    def begin(self, wall_id: str, endpoint: str) -> None:
        if self._transaction is not None:
            raise RuntimeError("wall-top drag already active")
        if wall_id not in self.doc.selection:
            raise ValueError("wall-top handle must belong to the current selection")
        self._transaction = WallTopEndpointTransaction(
            self.doc, self.stack, wall_id, endpoint
        )

    def update_from_ray(self, ray_origin, ray_direction) -> float:
        if self._transaction is None:
            raise RuntimeError("no wall-top drag is active")
        return self._transaction.update_from_ray(ray_origin, ray_direction)

    def finish(self) -> bool:
        if self._transaction is None:
            return False
        tx = self._transaction
        self._transaction = None
        return tx.commit()

    def cancel(self) -> None:
        if self._transaction is None:
            return
        tx = self._transaction
        self._transaction = None
        tx.cancel()

    def rebind(self, doc, stack) -> None:
        self.cancel()
        self.doc = doc
        self.stack = stack
