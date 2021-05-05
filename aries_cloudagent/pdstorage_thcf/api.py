from aries_cloudagent.aathcf.utils import build_context, run_standalone_async
from aries_cloudagent.aathcf.credentials import assert_type, assert_type_or
from aries_cloudagent.storage.error import StorageNotFoundError
from .base import BasePDS
from .error import PDSError, PDSNotFoundError, PDSRecordNotFoundError
from .models.saved_personal_storage import SavedPDS
import hashlib
import multihash
import logging
import multibase

from .models.table_that_matches_dris_with_pds import DriStorageMatchTable

import json
from collections import OrderedDict

LOGGER = logging.getLogger(__name__)


async def match_save_save_record_id(context, record_id, pds_name):
    match_table = DriStorageMatchTable(record_id, pds_name)
    record_id = await match_table.save(context)
    return record_id


async def match_table_query_id(context, id):
    try:
        match = await DriStorageMatchTable.retrieve_by_id(context, id)
    except StorageNotFoundError as err:
        LOGGER.error(
            f"table_that_matches_plugins_with_ids id that matches with None value\n",
            f"input id: {id}\n",
            f"ERROR: {err.roll_up}",
        )
        debug_all_records = await DriStorageMatchTable.query(context)
        LOGGER.error("All records in table: ", debug_all_records)
        raise PDSNotFoundError(err)

    return match


async def pds_get_active_name(context):
    try:
        active_pds = await SavedPDS.retrieve_active(context)
    except StorageNotFoundError as err:
        raise PDSNotFoundError(f"No active pds found {err.roll_up}")

    return active_pds.get_pds_name()


async def pds_get_by_name(context, name):
    pds: BasePDS = await context.inject(BasePDS, {"personal_storage_type": name})

    return pds


async def pds_get_active(context):
    active_pds_name = await pds_get_active_name(context)
    pds = await pds_get_by_name(context, active_pds_name)
    return pds


async def pds_load(context, id: str, *, with_meta: bool = False) -> dict:
    assert_type(id, str)

    match = await match_table_query_id(context, id)
    pds = await pds_get_by_name(context, match.pds_type)
    result = await pds.load(id)

    try:
        result["content"] = json.loads(result["content"], object_pairs_hook=OrderedDict)
    except json.JSONDecodeError:
        pass
    except TypeError:
        pass

    if with_meta:
        return result
    else:
        return result["content"]


async def pds_link_dri(context, dri, link_with_dris):
    if isinstance(link_with_dris, str):
        link_with_dris = [link_with_dris]
    elif isinstance(link_with_dris, list):
        pass
    else:
        raise TypeError("Expected: list or string")

    if __debug__:
        assert isinstance(link_with_dris, list)

    pds = await pds_get_active(context)
    if "link" in dir(pds):
        try:
            await pds.link(dri, link_with_dris)
        except PDSError as err:
            LOGGER.error(
                "source_dri: %s target_dris: %s error: %s",
                dri,
                link_with_dris,
                err.roll_up,
            )
            return False
    else:
        LOGGER.warning(
            "This is an own your data pds extension. current pds doesn't support this method"
        )
        return False
    return True


async def __test_pds_link():
    context = await build_context()
    await pds_link_dri(
        context,
        "zQmNaccqmcrPy93ehV8qEfkNf3ez6EQ94iBxzv3NrA25AXh",
        "zQmPBDRQpQxbYFvBc71HnvhnMGxzbTiCiWR47vCNUS2cGSa",
    )
    import random

    dri1 = await pds_save_a(context, "124inmjfa0dioq-0dq" + str(random.random()))
    dri2 = await pds_save_a(context, "1asdad24inmjfa0dioq-0dq" + str(random.random()))
    result = await pds_link_dri(context, dri1, dri2)
    assert result == True

    result = await pds_link_dri(context, "1wd1fc", "difhd908f")
    assert result == False

    context = await build_context("local")

    import random

    dri1 = await pds_save_a(context, "124inmjfa0dioq-0dq" + str(random.random()))
    dri2 = await pds_save_a(context, "1asdad24inmjfa0dioq-0dq" + str(random.random()))
    result = await pds_link_dri(context, dri1, dri2)
    assert result == False

    result = await pds_link_dri(context, "1wd1fc", "difhd908f")
    assert result == False


async def pds_load_string(context, id: str, *, with_meta: bool = False) -> str:
    assert_type(id, str)

    match = await match_table_query_id(context, id)
    pds = await pds_get_by_name(context, match.pds_type)
    result = await pds.load(id)

    if with_meta:
        return result
    else:
        return result["content"]


async def pds_save(context, payload, metadata: str = "{}") -> str:
    assert_type_or(payload, str, dict)
    assert_type(metadata, str)

    active_pds_name = await pds_get_active_name(context)
    pds = await pds_get_by_name(context, active_pds_name)
    payload_id = await pds.save(payload, json.loads(metadata))
    payload_id = await match_save_save_record_id(context, payload_id, active_pds_name)

    return payload_id


async def pds_save_a(
    context, payload, *, oca_schema_dri: str = None, table: str = None
) -> str:
    assert_type_or(payload, str, dict)

    meta = {"table": table, "oca_schema_dri": oca_schema_dri}
    active_pds_name = await pds_get_active_name(context)
    pds = await pds_get_by_name(context, active_pds_name)
    payload_id = await pds.save(payload, meta)
    payload_id = await match_save_save_record_id(context, payload_id, active_pds_name)

    return payload_id


async def load_multiple(context, *, table: str = None, oca_schema_base_dri=None):
    """ Load multiple records, if oca_schema_base_dri is a list then returns a dictionary"""
    pds = await pds_get_active(context)
    if isinstance(oca_schema_base_dri, list):
        result = {}
        for dri in oca_schema_base_dri:
            result[dri] = await pds.load_multiple(table=table, oca_schema_base_dri=dri)
            result[dri] = json.loads(result[dri])
        return result

    else:
        result = await pds.load_multiple(
            table=table, oca_schema_base_dri=oca_schema_base_dri
        )
        result = json.loads(result)
        return result


async def delete_record(context, id: str) -> str:
    assert_type(id, str)

    match = await match_table_query_id(context, id)
    pds = await pds_get_by_name(context, match.pds_type)
    result = await pds.delete(id)

    return result


async def pds_get_usage_policy_if_active_pds_supports_it(context):
    active_pds_name = await pds_get_active_name(context)
    if active_pds_name[0] != "own_your_data":
        return None

    pds = await pds_get_by_name(context, active_pds_name)
    result = await pds.get_usage_policy()

    return result


def encode(data: str) -> str:
    assert_type(data, str)
    hash_object = hashlib.sha256()
    hash_object.update(bytes(data, "utf-8"))
    multi = multihash.encode(hash_object.digest(), "sha2-256")
    result = multibase.encode("base58btc", multi)

    return result.decode("utf-8")


async def pds_oca_data_format_save(context, data):
    ids_of_saved_schemas = {}
    for oca_schema_base_dri in data:
        if oca_schema_base_dri.startswith("DRI:"):
            payload_id = await pds_save_a(
                context,
                data[oca_schema_base_dri],
                oca_schema_dri=oca_schema_base_dri[4:],
            )
            ids_of_saved_schemas[oca_schema_base_dri] = payload_id
        else:
            ids_of_saved_schemas[
                oca_schema_base_dri
            ] = "Invalid format, DRIs should start with 'DRI:'"

    return ids_of_saved_schemas


async def pds_oca_data_format_serialize_item_recursive(context, key, val):
    new_val = val
    if isinstance(val, dict):
        new_val = await pds_oca_data_format_serialize_dict_recursive(context, val)
    elif val.startswith("DRI:"):
        new_val = await pds_load(context, val[4:])
        new_val = await pds_oca_data_format_serialize_dict_recursive(context, new_val)
    return new_val


async def pds_oca_data_format_serialize_dict_recursive(context, dct):
    new_dict = {}
    for k, v in dct.items():
        new_dict[k] = await pds_oca_data_format_serialize_item_recursive(context, k, v)
    return new_dict


run_standalone_async(__name__, __test_pds_link)
