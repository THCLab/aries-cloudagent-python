"""Credential exchange admin routes."""

import json

from aiohttp import web
from aiohttp_apispec import (
    docs,
    match_info_schema,
    querystring_schema,
    request_schema,
    response_schema,
)
from json.decoder import JSONDecodeError
from marshmallow import fields, validate
import logging

from ....connections.models.connection_record import ConnectionRecord
from ....issuer.base import IssuerError
from ....ledger.error import LedgerError
from ....messaging.credential_definitions.util import CRED_DEF_TAGS
from ....messaging.models.base import BaseModelError, OpenAPISchema
from ....messaging.valid import (
    NATURAL_NUM,
    UUIDFour,
    UUID4,
)
from ....storage.error import StorageError, StorageNotFoundError
from ....wallet.base import BaseWallet
from ....holder.base import BaseHolder, HolderError
from ....issuer.base import BaseIssuer
from ....wallet.error import WalletError
from ....utils.outofband import serialize_outofband
from ....utils.tracing import trace_event, get_timer, AdminAPIMessageTracingSchema
from .messages.credential_issue import CredentialIssue
from aries_cloudagent.protocols.issue_credential.v1_1.messages.credential_request import (
    CredentialRequest,
)
from .models.credential_exchange import CredentialExchangeRecord


LOG = logging.getLogger(__name__).info


class RequestCredentialSchema(OpenAPISchema):
    credential_values = fields.Dict()
    credential_type = fields.Str(required=True)
    connection_id = fields.Str(required=True)


class IssueCredentialQuerySchema(OpenAPISchema):
    credential_exchange_id = fields.Str(required=False)


async def retrieve_connection(context, connection_id):
    try:
        connection_record: ConnectionRecord = await ConnectionRecord.retrieve_by_id(
            context, connection_id
        )
    except StorageNotFoundError as err:
        raise web.HTTPNotFound(
            reason="Couldnt find a connection_record through the connection_id"
        )
    except StorageError as err:
        raise web.HTTPInternalServerError(reason=err.roll_up)
    if not connection_record.is_ready:
        raise web.HTTPRequestTimeout(reason="Connection with this agent is not ready")

    return connection_record


async def retrieve_credential_exchange(context, credential_exchange_id):
    try:
        exchange_record: CredentialExchangeRecord = (
            await CredentialExchangeRecord.retrieve_by_id(
                context, credential_exchange_id
            )
        )
    except StorageNotFoundError as err:
        raise web.HTTPNotFound(
            reason="Couldnt find a exchange_record through the credential_exchange_id"
        )
    except StorageError as err:
        raise web.HTTPInternalServerError(reason=err.roll_up)

    return exchange_record


# TODO: Not connection record
async def create_credential(
    context, credential_request, connection_record, exception=web.HTTPError
) -> dict:
    """
    Args:
        credential_request - dictionary containing "credential_values" and
        "credential_type"
        exception - pass in exception if you are using this outside of routes
    """
    credential_type = credential_request.get("credential_type")
    credential_values = credential_request.get("credential_values")
    try:
        issuer: BaseIssuer = await context.inject(BaseIssuer)
        credential, _ = await issuer.create_credential(
            schema={
                "credential_type": credential_type,
            },
            credential_values=credential_values,
            credential_offer={},
            credential_request={
                "connection_record": connection_record,
            },
        )
    except IssuerError as err:
        raise exception(reason=err.roll_up)

    return json.loads(credential)


@docs(tags=["issue-credential"], summary="Issue credential ")
@querystring_schema(IssueCredentialQuerySchema())
async def issue_credential(request: web.BaseRequest):
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]

    credential_exchange_id = request.query.get("credential_exchange_id")
    exchange = await retrieve_credential_exchange(context, credential_exchange_id)
    connection = await retrieve_connection(context, exchange.connection_id)
    request = exchange.credential_request
    credential = await create_credential(context, request, connection)

    issue = CredentialIssue(credential=credential)
    issue.assign_thread_id(exchange.thread_id)
    await outbound_handler(issue, connection_id=connection.connection_id)

    exchange.state = CredentialExchangeRecord.STATE_ISSUED
    await exchange.save(context)

    return web.json_response(json.loads(credential))


@docs(tags=["issue-credential"], summary="Request Credential")
@request_schema(RequestCredentialSchema())
async def request_credential(request: web.BaseRequest):
    context = request.app["request_context"]
    outbound_handler = request.app["outbound_message_router"]

    body = await request.json()
    credential_type = body.get("credential_type")
    credential_values = body.get("credential_values")
    connection_id = body.get("connection_id")
    connection_record = await retrieve_connection(context, connection_id)

    request = {
        "credential_type": credential_type,
        "credential_values": credential_values,
    }
    issue = CredentialRequest(credential=request)
    await outbound_handler(issue, connection_id=connection_record.connection_id)

    assert issue._thread_id != None
    exchange = CredentialExchangeRecord(
        connection_id=connection_id,
        thread_id=issue._thread_id,
        initiator=CredentialExchangeRecord.INITIATOR_SELF,
        role=CredentialExchangeRecord.ROLE_HOLDER,
        state=CredentialExchangeRecord.STATE_REQUEST_SENT,
        credential_request=request,
    )

    exchange_id = await exchange.save(
        context, reason="Save record of agent credential exchange"
    )

    return web.json_response({"credential_exchange_id": exchange_id})


async def register(app: web.Application):
    """Register routes."""

    app.add_routes(
        [
            web.post("/issue-credential/send", issue_credential),
            web.post("/issue-credential/request", request_credential),
        ]
    )


def post_process_routes(app: web.Application):
    """Amend swagger API."""

    # Add top-level tags description
    if "tags" not in app._state["swagger_dict"]:
        app._state["swagger_dict"]["tags"] = []
    app._state["swagger_dict"]["tags"].append(
        {
            "name": "issue-credential",
            "description": "Credential issue, revocation",
            # "externalDocs": {"description": "Specification", "url": SPEC_URI},
        }
    )
