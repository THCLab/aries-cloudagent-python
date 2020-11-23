from aries_cloudagent.storage.error import StorageError, StorageNotFoundError
from aiohttp import web
from aries_cloudagent.connections.models.connection_record import ConnectionRecord
from aries_cloudagent.protocols.issue_credential.v1_1.models.credential_exchange import (
    CredentialExchangeRecord,
)
from aries_cloudagent.issuer.base import BaseIssuer, IssuerError
import json


async def retrieve_connection(context, connection_id):
    """
    Retrieve ConnectionRecord and handle exceptions.

    Raises AioHTTP exceptions so only should be used in routes.py.
    """
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
        raise web.HTTPRequestTimeout(reason=f"Connection {connection_id} not ready")

    return connection_record


async def retrieve_credential_exchange(context, credential_exchange_id):
    """
    Retrieve Credential Exchange Record and handle exceptions.

    Raises AioHTTP exceptions so only should be used in routes.py.
    """
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
    Create Credential utility wrapper which handles exceptions

    optionally you can pass

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