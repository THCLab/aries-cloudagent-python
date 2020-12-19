from .api import load_string, save_string
from .base import *
from .error import PersonalDataStorageError, PersonalDataStorageNotFoundError
from .message_types import ExchangeDataB, ExchangeDataA
from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)
import logging

LOGGER = logging.getLogger(__name__)


class ExchangeDataAHandler(BaseHandler):
    """
    Stage first, this fires for the agent2, receive request to send data
    """

    async def handle(self, context: RequestContext, responder: BaseResponder):
        LOGGER.info("ExchangeDataAHandler called with context %s", context)
        assert isinstance(context.message, ExchangeDataA)
        payload_dri = context.message.payload_dri

        try:
            payload = await load_string(context, payload_dri)
            if payload == None:
                raise PersonalDataStorageNotFoundError
        except PersonalDataStorageNotFoundError as err:
            LOGGER.warning("TODO: ExchangeDataAHandler ProblemReport %s", err.roll_up)
            return

        response = ExchangeDataB(payload=payload, payload_dri=payload_dri)
        response.assign_thread_from(context.message)
        await responder.send_reply(response)


class ExchangeDataBHandler(BaseHandler):
    """
    Stage second, this fires for the agent1, the initiator
    """

    async def handle(self, context: RequestContext, responder: BaseResponder):
        LOGGER.info("ExchangeDataBHandler called with context %s", context)
        assert isinstance(context.message, ExchangeDataB)
        msg = context.message

        await responder.send_webhook(
            "pds/payload",
            {"dri": msg.payload_dri, "payload": msg.payload},
        )

        """
        try:
            payload_dri = await save_string(context, context.message.payload)
        except PersonalDataStorageError as err:
            raise err.roll_up

        if context.message.payload_dri:
            assert (
                context.message.payload_dri == payload_dri
            ), "dri's differ between agents!"
        """
