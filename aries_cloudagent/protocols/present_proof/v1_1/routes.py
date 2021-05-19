"""Admin routes for presentations."""

from aries_cloudagent.pdstorage_thcf.own_your_data import OwnYourDataVault
from aries_cloudagent.aathcf.utils import run_standalone_async, build_context
import json

from aiohttp import web
from aiohttp_apispec import (
    docs,
    querystring_schema,
    request_schema,
)
from marshmallow import fields
from ....connections.models.connection_record import ConnectionRecord
from ....holder.base import BaseHolder, HolderError
from .models.presentation_exchange import THCFPresentationExchange
from ....messaging.models.openapi import OpenAPISchema
from aries_cloudagent.protocols.issue_credential.v1_1.utils import retrieve_connection
from .messages.request_proof import RequestProof
from .messages.present_proof import PresentProof
from .models.utils import retrieve_exchange
import logging
from aries_cloudagent.pdstorage_thcf.api import (
    load_multiple,
    pds_link_dri,
    pds_get_usage_policy_if_active_pds_supports_it,
)
from aries_cloudagent.holder.pds import CREDENTIALS_TABLE
from aries_cloudagent.pdstorage_thcf.error import PDSError
from aries_cloudagent.protocols.issue_credential.v1_1.routes import (
    routes_get_public_did,
)
from aries_cloudagent.issuer.base import BaseIssuer, IssuerError
from .messages.acknowledge_proof import AcknowledgeProof
from aiohttp import ClientSession, ClientTimeout

LOGGER = logging.getLogger(__name__)


class PresentationRequestAPISchema(OpenAPISchema):
    connection_id = fields.Str(required=True)
    requested_attributes = fields.List(fields.Str(required=True), required=True)
    issuer_did = fields.Str(required=False)
    schema_base_dri = fields.Str(required=True)


class PresentProofAPISchema(OpenAPISchema):
    exchange_record_id = fields.Str(required=True)
    credential_id = fields.Str(required=True)


class PresentProofRejectAPISchema(OpenAPISchema):
    exchange_record_id = fields.Str(required=True)


class RetrieveExchangeQuerySchema(OpenAPISchema):
    connection_id = fields.Str(required=False)
    thread_id = fields.Str(required=False)
    initiator = fields.Str(required=False)
    role = fields.Str(required=False)
    state = fields.Str(required=False)


class AcknowledgeProofSchema(OpenAPISchema):
    exchange_record_id = fields.Str(required=True)
    status = fields.Boolean(required=True)
    issuer_name = fields.Str(required=False)
    person_id = fields.Str(required=True)


@docs(tags=["present-proof"], summary="Sends a proof presentation")
@request_schema(PresentationRequestAPISchema())
async def request_presentation_endpoint(request: web.BaseRequest):
    """Request handler for sending a presentation."""
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]
    body = await request.json()

    connection_id = body.get("connection_id")
    await retrieve_connection(context, connection_id)  # throw exception if not found

    presentation_request = {
        "requested_attributes": body.get("requested_attributes"),
        "schema_base_dri": body.get("schema_base_dri"),
    }
    issuer_did = body.get("issuer_did")
    if issuer_did is not None:
        presentation_request["issuer_did"] = issuer_did

    usage_policy = await pds_get_usage_policy_if_active_pds_supports_it(context)
    message = RequestProof(
        presentation_request=presentation_request, usage_policy=usage_policy
    )
    await outbound_handler(message, connection_id=connection_id)

    exchange_record = THCFPresentationExchange(
        connection_id=connection_id,
        thread_id=message._thread_id,
        initiator=THCFPresentationExchange.INITIATOR_SELF,
        role=THCFPresentationExchange.ROLE_VERIFIER,
        state=THCFPresentationExchange.STATE_REQUEST_SENT,
        presentation_request=presentation_request,
    )

    LOGGER.debug("exchange_record %s", exchange_record)
    await exchange_record.save(context)

    return web.json_response(
        {
            "success": True,
            "message": "proof sent and exchange updated",
            "exchange_id": exchange_record._id,
            "thread_id": message._thread_id,
            "connection_id": connection_id,
        }
    )


@docs(tags=["present-proof"], summary="Send a credential presentation")
@request_schema(PresentProofAPISchema())
async def present_proof_endpoint(request: web.BaseRequest):
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]

    body = await request.json()
    exchange_record_id = body.get("exchange_record_id")
    credential_id = body.get("credential_id")

    exchange = await retrieve_exchange(context, exchange_record_id, web.HTTPNotFound)

    if exchange.role != exchange.ROLE_PROVER:
        raise web.HTTPBadRequest(reason="Invalid exchange role")
    if exchange.state != exchange.STATE_REQUEST_RECEIVED:
        raise web.HTTPBadRequest(reason="Invalid exchange state")

    connection_record: ConnectionRecord = await retrieve_connection(
        context, exchange.connection_id
    )

    try:
        holder: BaseHolder = await context.inject(BaseHolder)
        requested_credentials = {"credential_id": credential_id}
        presentation = await holder.create_presentation(
            presentation_request=exchange.presentation_request,
            requested_credentials=requested_credentials,
            schemas={},
            credential_definitions={},
        )
    except HolderError as err:
        raise web.HTTPInternalServerError(reason=err.roll_up)

    public_did = await routes_get_public_did(context)
    message = PresentProof(
        credential_presentation=presentation, prover_public_did=public_did
    )
    message.assign_thread_id(exchange.thread_id)
    await outbound_handler(message, connection_id=connection_record.connection_id)

    exchange.state = exchange.STATE_PRESENTATION_SENT
    await exchange.presentation_pds_set(context, json.loads(presentation))
    await exchange.save(context)

    return web.json_response(
        {
            "success": True,
            "message": "proof sent and exchange updated",
            "exchange_id": exchange._id,
        }
    )


@docs(tags=["present-proof"], summary="Reject a present proof request")
@request_schema(PresentProofRejectAPISchema())
async def present_proof_reject_endpoint(request: web.BaseRequest):
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]
    body = await request.json()
    exchange_record_id = body.get("exchange_record_id")

    exchange = await retrieve_exchange(context, exchange_record_id, web.HTTPNotFound)

    if exchange.role != exchange.ROLE_PROVER:
        raise web.HTTPBadRequest(reason="Invalid exchange role")
    if exchange.state != exchange.STATE_REQUEST_RECEIVED:
        raise web.HTTPBadRequest(reason="Invalid exchange state")

    connection_record: ConnectionRecord = await retrieve_connection(
        context, exchange.connection_id
    )

    message = PresentProof(decision=False)
    message.assign_thread_id(exchange.thread_id)
    await outbound_handler(message, connection_id=connection_record.connection_id)

    exchange.state = exchange.STATE_PRESENTATION_DENIED
    await exchange.save(context)

    return web.json_response({"exchange_id": exchange._id})


@docs(tags=["present-proof"], summary="retrieve exchange record")
@querystring_schema(AcknowledgeProofSchema())
async def acknowledge_proof(request: web.BaseRequest):
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]
    query = request.query

    exchange: THCFPresentationExchange = await retrieve_exchange(
        context, query["exchange_record_id"], web.HTTPNotFound
    )

    if exchange.role != exchange.ROLE_VERIFIER:
        raise web.HTTPBadRequest(reason="Invalid exchange role")
    if exchange.state != exchange.STATE_PRESENTATION_RECEIVED:
        raise web.HTTPBadRequest(reason="Invalid exchange state")

    connection_record: ConnectionRecord = await retrieve_connection(
        context, exchange.connection_id
    )

    try:
        issuer: BaseIssuer = await context.inject(BaseIssuer)
        credential = await issuer.create_credential_ex(
            credential_values={
                "oca_data": {
                    "verified": str(query.get("status")),
                    "presentation_dri": exchange.presentation_dri,
                    "person_id": query.get("person_id"),
                    "issuer_name": query.get("issuer_name")
                    if query.get("issuer_name") is not None
                    else context.settings.get("default_label"),
                },
                "oca_schema_dri": "dL37iDvZBXE4Jj8G94CcFYU48T6Nk3Ak1usjSgnPE8K1",
            },
            credential_type="ProofAcknowledgment",
            subject_public_did=exchange.prover_public_did,
        )
    except IssuerError as err:
        raise web.HTTPInternalServerError(
            reason=f"Error occured while creating a credential {err.roll_up}"
        )

    message = AcknowledgeProof(credential=credential)
    message.assign_thread_id(exchange.thread_id)
    await outbound_handler(message, connection_id=connection_record.connection_id)

    exchange.state = exchange.STATE_ACKNOWLEDGED
    await exchange.verifier_ack_cred_pds_set(context, credential)
    await pds_link_dri(
        context, exchange.presentation_dri, exchange.acknowledgment_credential_dri
    )
    await exchange.save(context)
    return web.json_response(
        {
            "success": True,
            "message": "ack sent and exchange record updated",
            "exchange_record_id": exchange._id,
            "ack_credential_dri": exchange.acknowledgment_credential_dri,
        }
    )


async def verify_usage_policy(controller_usage_policy, subject_usage_policy):
    timeout = ClientTimeout(total=15)
    async with ClientSession(timeout=timeout) as session:
        result = await session.post(
            "https://governance.ownyourdata.eu/api/usage-policy/match",
            json={
                "data-subject": subject_usage_policy,
                "data-controller": controller_usage_policy,
            },
        )
        result = await result.text()
        result = json.loads(result)

        if result["code"] == 0:
            return True, result["message"]
        return False, result["error"]


@docs(tags=["present-proof"], summary="retrieve exchange record")
@querystring_schema(RetrieveExchangeQuerySchema())
async def retrieve_credential_exchange_api(request: web.BaseRequest):
    context = request.app["request_context"]

    records = await THCFPresentationExchange.query(context, tag_filter=request.query)
    usage_policy = await pds_get_usage_policy_if_active_pds_supports_it(context)

    result = []
    for i in records:
        serialize = i.serialize()
        if i.presentation_dri is not None:
            serialize["presentation"] = await i.presentation_pds_get(context)
        if usage_policy and i.requester_usage_policy:
            serialize["usage_policies_match"], _ = await verify_usage_policy(
                i.requester_usage_policy, usage_policy
            )
        result.append(serialize)

    """
    Download credentials
    """

    try:
        credentials = await load_multiple(context, table=CREDENTIALS_TABLE)
    except json.JSONDecodeError:
        LOGGER.warn(
            "Error parsing credentials, perhaps there are no credentials in store %s",
        )
        credentials = {}
    except PDSError as err:
        LOGGER.warn("PDSError %s", err.roll_up)
        credentials = {}

    """
    Match the credential requests with credentials in the possesion of the agent
    in this case we check if both issuer_did and oca_schema_dri are correct
    """

    for rec in result:
        rec["list_of_matching_credentials"] = []
        for cred in credentials:
            try:
                cred_content = json.loads(cred["content"])
            except (json.JSONDecodeError, TypeError):
                cred_content = cred["content"]

            record_base_dri = rec["presentation_request"].get(
                "schema_base_dri", "INVALIDA"
            )
            cred_base_dri = cred_content["credentialSubject"].get(
                "oca_schema_dri", "INVALIDC"
            )
            if record_base_dri == cred_base_dri:
                rec["list_of_matching_credentials"].append(cred["dri"])

    return web.json_response({"success": True, "result": result})


async def register(app: web.Application):
    """Register routes."""

    app.add_routes(
        [
            web.post(
                "/present-proof/request",
                request_presentation_endpoint,
            ),
            web.post(
                "/present-proof/present",
                present_proof_endpoint,
            ),
            web.post(
                "/present-proof/reject",
                present_proof_reject_endpoint,
            ),
            web.post(
                "/present-proof/acknowledge",
                acknowledge_proof,
            ),
            web.get(
                "/present-proof/exchange/record",
                retrieve_credential_exchange_api,
                allow_head=False,
            ),
        ]
    )


def post_process_routes(app: web.Application):
    """Amend swagger API."""

    # Add top-level tags description
    if "tags" not in app._state["swagger_dict"]:
        app._state["swagger_dict"]["tags"] = []
    app._state["swagger_dict"]["tags"].append(
        {
            "name": "present-proof",
            "description": "Proof presentation",
            "externalDocs": {"description": "Specification"},
        }
    )


async def test_usage_policy():
    {
        "local, default": {},
        "own_your_data, dip21.demo@gmail.com": {
            "api_url": "https://data-vault.eu",
            "client_id": "QXw8w203kibmQYdXRHiS1lrtxy-o7rmdwILqAF2RnWI",
            "client_secret": "4CbCqomFaqaMbpMyASpaRlKc2IDJnKvddsgtf2M5Ss0",
            "grant_type": "client_credentials",
            "scope": None,
        },
    }

    {
        "own_your_data, ": {
            "api_url": "https://sc.dip-clinic.data-container.net",
            "client_id": "af34d25dc21d5ee5ad0a8da9d035954dac0a286b7fce2028222657e76c89b406",
            "client_secret": "3563ca90d9a6be2387849c2253f565ba68a58bd77f83404ffeb77727a019d7ab",
            "grant_type": "client_credentials",
            "scope": "admin",
        },
        "local, default": {},
    }
    context = await build_context()
    vault_1 = OwnYourDataVault()
    vault_1.settings["client_id"] = "QXw8w203kibmQYdXRHiS1lrtxy-o7rmdwILqAF2RnWI"
    vault_1.settings["client_secret"] = "4CbCqomFaqaMbpMyASpaRlKc2IDJnKvddsgtf2M5Ss0"
    vault_1.settings["api_url"] = "https://data-vault.eu"
    usage_vault_1 = await vault_1.get_usage_policy()

    vault_2 = OwnYourDataVault()
    vault_2.settings[
        "client_id"
    ] = "af34d25dc21d5ee5ad0a8da9d035954dac0a286b7fce2028222657e76c89b406"
    vault_2.settings[
        "client_secret"
    ] = "3563ca90d9a6be2387849c2253f565ba68a58bd77f83404ffeb77727a019d7ab"
    vault_2.settings["api_url"] = "https://sc.dip-clinic.data-container.net"
    vault_2.settings["scope"] = "admin"
    usage_vault_2 = await vault_2.get_usage_policy()

    usage, msg = await verify_usage_policy(usage_vault_2, usage_vault_1)
    print(usage, msg)


run_standalone_async(__name__, test_usage_policy)