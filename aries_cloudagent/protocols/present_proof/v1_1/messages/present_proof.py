from marshmallow import fields
from .....messaging.agent_message import AgentMessage, AgentMessageSchema
from ..message_types import PRESENT_PROOF, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.present_proof.PresentProofHandler"


class PresentProof(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        schema_class = "PresentProofSchema"
        message_type = PRESENT_PROOF

    def __init__(
        self,
        _id: str = None,
        *,
        credential_presentation=None,
        prover_public_did=None,
        decision: bool = True,
        **kwargs,
    ):
        """Initialize credential issue object."""
        super().__init__(_id=_id, **kwargs)
        self.credential_presentation = credential_presentation
        self.prover_public_did = prover_public_did
        self.decision = decision


class PresentProofSchema(AgentMessageSchema):
    """Credential schema."""

    class Meta:
        """Credential schema metadata."""

        model_class = PresentProof

    credential_presentation = fields.Str(required=False)
    prover_public_did = fields.Str(required=False)
    decision = fields.Bool(required=True)
