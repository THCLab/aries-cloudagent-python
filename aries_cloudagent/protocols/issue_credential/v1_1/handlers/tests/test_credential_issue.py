import pytest
from asynctest import (
    mock as async_mock,
    TestCase as AsyncTestCase,
)

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import MockResponder
from aries_cloudagent.transport.inbound.receipt import MessageReceipt
from aries_cloudagent.protocols.issue_credential.v1_1.messages.credential_issue import (
    CredentialIssue,
)
from aries_cloudagent.protocols.issue_credential.v1_1.handlers.credential_issue import (
    CredentialIssueHandler,
)
from aries_cloudagent.storage.basic import BasicStorage
from aries_cloudagent.storage.base import BaseStorage
from aries_cloudagent.protocols.issue_credential.v1_1.models.credential_exchange import (
    CredentialExchangeRecord,
)
from aries_cloudagent.issuer.pds import PDSIssuer
from aries_cloudagent.wallet.basic import BasicWallet
from ...routes import create_credential
from aries_cloudagent.connections.models.connection_record import ConnectionRecord
from aries_cloudagent.issuer.base import BaseIssuer
from aries_cloudagent.holder.base import BaseHolder
from aries_cloudagent.holder.pds import PDSHolder
from aries_cloudagent.wallet.base import BaseWallet

credential_request = {
    "credential_type": "TEST",
    "credential_values": {"test": "one", "value": "two"},
}
connection_id = "1234"
thread_id = "1234"


class TestCredentialIssueHandler(AsyncTestCase):
    async def test_is_handler_saving_record(self):
        context = RequestContext()
        context.message_receipt = MessageReceipt()

        wallet = BasicWallet()
        storage = BasicStorage(wallet)
        issuer = PDSIssuer(wallet)
        holder = PDSHolder(context)
        context.injector.bind_instance(BaseWallet, wallet)
        context.injector.bind_instance(BaseStorage, storage)
        context.injector.bind_instance(BaseIssuer, issuer)
        context.injector.bind_instance(BaseHolder, holder)

        record = CredentialExchangeRecord(
            connection_id=connection_id,
            initiator=CredentialExchangeRecord.INITIATOR_SELF,
            role=CredentialExchangeRecord.ROLE_HOLDER,
            state=CredentialExchangeRecord.STATE_REQUEST_SENT,
            thread_id=thread_id,
            credential_request=credential_request,
        )
        await record.save(context)

        connection = ConnectionRecord(my_did="1234-mydid", their_did="1234-theirdid")
        credential = await create_credential(context, credential_request, connection)
        context.message: CredentialIssue = CredentialIssue(credential=credential)
        context.message.assign_thread_id(thread_id)
        context.connection_ready = True

        handler_inst = CredentialIssueHandler()
        responder = MockResponder()
        responder.connection_id = connection_id

        await handler_inst.handle(context, responder)
