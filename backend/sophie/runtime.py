"""One shared Sophie runtime for CLI and later HTTP/evaluation wrappers."""

from .backend import CanonicalBackend
from .llm import ModelClient, OpenAIResponsesClient, ResponsesProposalSource
from .policy import EmptyProposalSource, PolicyRuntime


class SophieRuntime(PolicyRuntime):
    def __init__(
        self,
        backend: CanonicalBackend,
        *,
        model_client: ModelClient | None = None,
        offline: bool = False,
    ):
        if offline and model_client is not None:
            raise ValueError("offline and model_client cannot both be set")
        source = (
            EmptyProposalSource()
            if offline
            else ResponsesProposalSource(
                backend,
                model_client or OpenAIResponsesClient(),
            )
        )
        super().__init__(backend, source, identity_intro=True)

    def create_conversation(self, sandbox_id: str) -> str:
        fixture = self.backend.fixture_info(sandbox_id)
        conversation_id = super().create_conversation(sandbox_id)
        seed = fixture["seed"]
        lead_id = seed.get("lead_id")
        if not lead_id:
            return conversation_id
        snapshot = self.backend.snapshot(sandbox_id)
        lead = next((row for row in snapshot["leads"] if row["id"] == lead_id), None)
        if lead is None:
            raise RuntimeError("fixture lead is missing")
        state = self.get_state(sandbox_id, conversation_id)
        state.lead_id = lead_id
        for field in ("first_name", "last_name", "email", "phone"):
            if lead[field]:
                setattr(state.confirmed_contact, field, lead[field])
                state.contact_confirmation[field] = "confirmed"
        tour_id = seed.get("tour_id")
        if tour_id and any(
            row["id"] == tour_id and row["status"] == "booked"
            for row in snapshot["tours"]
        ):
            state.verified_tour_ids.append(tour_id)
        with self.backend._connection() as conn:
            conn.execute(
                "UPDATE conversations SET state_json=? WHERE sandbox_id=? AND id=?",
                (state.model_dump_json(), sandbox_id, conversation_id),
            )
        return conversation_id
