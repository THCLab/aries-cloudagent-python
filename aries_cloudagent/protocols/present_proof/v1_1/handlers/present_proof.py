from .....messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    HandlerException,
    RequestContext,
)
from aries_cloudagent.aathcf.utils import debug_handler
from aries_cloudagent.protocols.present_proof.v1_1.models.presentation_exchange import (
    THCFPresentationExchange,
)
from aries_cloudagent.protocols.present_proof.v1_1.messages.present_proof import (
    PresentProof,
)
from aries_cloudagent.verifier.base import BaseVerifier
from ..models.utils import retrieve_exchange_by_thread
import json
from collections import OrderedDict


class PresentProofHandler(BaseHandler):
    async def handle(self, context: RequestContext, responder: BaseResponder):
        debug_handler(self._logger.info, context, PresentProof)
        exchange: THCFPresentationExchange = await retrieve_exchange_by_thread(
            context,
            responder.connection_id,
            context.message._thread_id,
            HandlerException,
        )

        if exchange.role != exchange.ROLE_VERIFIER:
            raise HandlerException(reason="Invalid exchange role")
        if exchange.state != exchange.STATE_REQUEST_SENT:
            raise HandlerException(reason="Invalid exchange state")

        if context.message.decision:
            verifier: BaseVerifier = await context.inject(BaseVerifier)

            presentation = json.loads(
                context.message.credential_presentation, object_pairs_hook=OrderedDict
            )

            is_verified = await verifier.verify_presentation(
                presentation_request=exchange.presentation_request,
                presentation=presentation,
                schemas={},
                credential_definitions={},
                rev_reg_defs={},
                rev_reg_entries={},
            )

            if not is_verified:
                raise HandlerException(
                    f"Verifier couldn't verify the presentation {is_verified}"
                )

            await exchange.presentation_pds_set(context, presentation)
            exchange.verified = True
            exchange.prover_public_did = context.message.prover_public_did
            exchange.state = exchange.STATE_PRESENTATION_RECEIVED
        else:
            exchange.state = exchange.STATE_PRESENTATION_DENIED

        await exchange.save(context, reason="PresentationExchange updated")
        await responder.send_webhook(
            "present_proof",
            {
                "type": "present_proof",
                "exchange_record_id": exchange._id,
                "connection_id": responder.connection_id,
            },
        )
