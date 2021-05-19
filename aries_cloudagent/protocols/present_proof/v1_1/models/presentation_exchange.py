"""Aries#0037 v1.0 presentation exchange information with non-secrets storage."""

from typing import Any

from marshmallow import fields, validate

from .....messaging.models.base_record import BaseExchangeRecord, BaseExchangeSchema
from .....messaging.valid import UUIDFour
from aries_cloudagent.aathcf.credentials import PresentationRequestSchema
from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.pdstorage_thcf.api import pds_load, pds_save, pds_save_a
from collections import OrderedDict


class THCFPresentationExchange(BaseExchangeRecord):
    """Represents an Aries#0037 v1.0 presentation exchange."""

    class Meta:
        """THCFPresentationExchange metadata."""

        schema_class = "THCFPresentationExchangeSchema"

    RECORD_TYPE = "presentation_exchange_thcf"
    RECORD_ID_NAME = "presentation_exchange_id"
    WEBHOOK_TOPIC = "present_proof"

    INITIATOR_SELF = "self"
    INITIATOR_EXTERNAL = "external"

    ROLE_PROVER = "prover"
    ROLE_VERIFIER = "verifier"

    STATE_PROPOSAL_SENT = "proposal_sent"
    STATE_PROPOSAL_RECEIVED = "proposal_received"
    STATE_REQUEST_SENT = "request_sent"
    STATE_REQUEST_RECEIVED = "request_received"
    STATE_PRESENTATION_DENIED = "presentation_denied"
    STATE_PRESENTATION_SENT = "presentation_sent"
    STATE_PRESENTATION_RECEIVED = "presentation_received"
    STATE_PRESENTATION_ACKED = "presentation_acked"
    STATE_ACKNOWLEDGED = "presentation_acknowledged"

    def __init__(
        self,
        *,
        presentation_exchange_id: str = None,
        connection_id: str = None,
        prover_public_did: str = None,
        thread_id: str = None,
        initiator: str = None,
        role: str = None,
        state: str = None,
        presentation_proposal: dict = None,
        presentation_request: dict = None,
        presentation_dri: str = None,
        acknowledgment_credential_dri: str = None,
        verified: str = None,
        auto_present: bool = False,
        requester_usage_policy=None,
        error_msg: str = None,
        trace: bool = False,
        **kwargs,
    ):
        """Initialize a new PresentationExchange."""
        super().__init__(presentation_exchange_id, state, trace=trace, **kwargs)
        self.connection_id = connection_id
        self.thread_id = thread_id
        self.initiator = initiator
        self.role = role
        self.state = state
        self.presentation_proposal = presentation_proposal
        self.presentation_request = presentation_request
        self.prover_public_did = prover_public_did
        self.presentation_dri = presentation_dri
        self.verified = verified
        self.auto_present = auto_present
        self.error_msg = error_msg
        self.trace = trace
        self.acknowledgment_credential_dri = None
        self.requester_usage_policy = requester_usage_policy

    @property
    def presentation_exchange_id(self) -> str:
        """Accessor for the ID associated with this exchange."""
        return self._id

    @property
    def record_value(self) -> dict:
        """Accessor for JSON record value generated for this presentation exchange."""
        return {
            prop: getattr(self, prop)
            for prop in (
                "connection_id",
                "thread_id",
                "initiator",
                "presentation_proposal",
                "presentation_request",
                "acknowledgment_credential_dri",
                "requester_usage_policy",
                "prover_public_did",
                "presentation_dri",
                "role",
                "state",
                "auto_present",
                "error_msg",
                "verified",
                "trace",
            )
        }

    @property
    def record_tags(self) -> dict:
        """Used to define tags with which record can be found."""
        return {
            prop: getattr(self, prop)
            for prop in (
                "connection_id",
                "thread_id",
                "initiator",
                "role",
                "state",
            )
        }

    @classmethod
    async def retrieve_by_connection_and_thread(
        cls, context: InjectionContext, connection_id: str, thread_id: str
    ):
        """Retrieve a credential exchange record by connection and thread ID."""
        cache_key = f"credential_exchange_ctidx::{connection_id}::{thread_id}"
        record_id = await cls.get_cached_key(context, cache_key)
        if record_id:
            record = await cls.retrieve_by_id(context, record_id)
        else:
            record = await cls.retrieve_by_tag_filter(
                context,
                {"thread_id": thread_id},
                {"connection_id": connection_id} if connection_id else None,
            )
            await cls.set_cached_key(context, cache_key, record._id)
        return record

    def __eq__(self, other: Any) -> bool:
        """Comparison between records."""
        return super().__eq__(other)

    async def verifier_ack_cred_pds_set(self, context, credential: OrderedDict):
        dri = await pds_save_a(context, credential, table="Acknowledgment")
        self.acknowledgment_credential_dri = dri

    async def ack_cred_pds_get(self, context):
        assert self.acknowledgment_credential_dri is not None
        credential = await pds_load(context, self.acknowledgment_credential)
        return credential

    async def presentation_pds_set(self, context, presentation):
        self.presentation_dri = await pds_save_a(
            context, presentation, table="Presentation"
        )

    async def presentation_pds_get(self, context):
        if self.presentation_dri is None:
            return None
        result = await pds_load(context, self.presentation_dri)
        return result


class THCFPresentationExchangeSchema(BaseExchangeSchema):
    """Schema for de/serialization of v1.0 presentation exchange records."""

    class Meta:
        """THCFPresentationExchangeSchema metadata."""

        model_class = THCFPresentationExchange

    presentation_exchange_id = fields.Str(
        required=False,
        description="Presentation exchange identifier",
        example=UUIDFour.EXAMPLE,  # typically a UUID4 but not necessarily
    )
    connection_id = fields.Str(
        required=False,
        description="Connection identifier",
        example=UUIDFour.EXAMPLE,  # typically a UUID4 but not necessarily
    )
    thread_id = fields.Str(
        required=False,
        description="Thread identifier",
        example=UUIDFour.EXAMPLE,  # typically a UUID4 but not necessarily
    )
    initiator = fields.Str(
        required=False,
        description="Present-proof exchange initiator: self or external",
        example=THCFPresentationExchange.INITIATOR_SELF,
        validate=validate.OneOf(["self", "external"]),
    )
    role = fields.Str(
        required=False,
        description="Present-proof exchange role: prover or verifier",
        example=THCFPresentationExchange.ROLE_PROVER,
        validate=validate.OneOf(["prover", "verifier"]),
    )
    state = fields.Str(
        required=False,
        description="Present-proof exchange state",
        example=THCFPresentationExchange.STATE_ACKNOWLEDGED,
    )
    presentation_proposal = fields.Dict(
        required=False, description="Serialized presentation proposal message"
    )
    presentation_request = fields.Nested(
        PresentationRequestSchema,
        required=False,
        description="presentation request (also known as proof request)",
    )
    verified = fields.Str(  # tag: must be a string
        required=False,
        description="Whether presentation is verified: true or false",
        example="true",
        validate=validate.OneOf(["true", "false"]),
    )
    auto_present = fields.Bool(
        required=False,
        description="Prover choice to auto-present proof as verifier requests",
        example=False,
    )
    error_msg = fields.Str(
        required=False, description="Error message", example="Invalid structure"
    )
    prover_public_did = fields.Str(required=False)
    acknowledgment_credential_dri = fields.Str(required=False)
    presentation_dri = fields.Str(required=False)