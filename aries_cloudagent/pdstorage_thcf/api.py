from .base import BasePersonalDataStorage
from .error import PersonalDataStorageNotFoundError
from ..messaging.request_context import RequestContext
from .models.saved_personal_storage import SavedPersonalStorage
import hashlib
import multihash
import logging
import multibase
from aries_cloudagent.storage.error import StorageNotFoundError
from .models.table_that_matches_dris_with_pds import DriStorageMatchTable
from aries_cloudagent.aathcf.credentials import assert_type

LOGGER = logging.getLogger(__name__)


async def load_string(context: RequestContext, id: str) -> str:
    assert_type(id, str)
    # plugin = table_that_matches_plugins_with_ids.get(id, None)
    try:
        match = await DriStorageMatchTable.retrieve_by_id(context, id)
    except StorageNotFoundError as err:
        LOGGER.info(
            f"""table_that_matches_plugins_with_ids has an id that matches with None value 
                input id: {id}
                plugin: {match}
                ERROR: {err.roll_up}
            """
        )
        raise PersonalDataStorageNotFoundError(err)

    pds: BasePersonalDataStorage = await context.inject(
        BasePersonalDataStorage, {"personal_storage_type": match.pds_type}
    )
    result = await pds.load(id)

    return result


async def save_string(context: RequestContext, payload: str, metadata="{}") -> str:
    assert_type(id, str)

    try:
        active_pds = await SavedPersonalStorage.retrieve_active(context)
    except StorageNotFoundError as err:
        raise PersonalDataStorageNotFoundError(f"No active pds found {err.roll_up}")

    pds: BasePersonalDataStorage = await context.inject(
        BasePersonalDataStorage, {"personal_storage_type": active_pds.get_pds_name()}
    )
    payload_id = await pds.save(payload, metadata)

    match_table = DriStorageMatchTable(payload_id, active_pds.get_pds_name())
    payload_id = await match_table.save(context)

    return payload_id


def encode(data: str) -> str:
    hash_object = hashlib.sha256()
    hash_object.update(bytes(data, "utf-8"))
    multi = multihash.encode(hash_object.digest(), "sha2-256")
    result = multibase.encode("base58btc", multi)

    return result.decode("utf-8")
