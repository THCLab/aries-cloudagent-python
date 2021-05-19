from aries_cloudagent.aathcf.utils import run_standalone_async
from .base import BasePDS
from .api import encode
from .error import PDSError, PDSRecordNotFoundError

import json
import logging
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientConnectionError, ClientError
from aries_cloudagent.aathcf.credentials import assert_type, assert_type_or
import time


LOGGER = logging.getLogger(__name__)


def map_parsed_usage_policy(usage_policy, map_against):
    new_base = {}
    missing = {}
    for key, value in usage_policy.items():
        list_of_attrs = []
        possibilities = map_against["attr_entries"].get(key)
        if possibilities is None:
            missing[key] = "missing"
        else:
            for i in value:
                found = False
                for p in range(len(possibilities)):
                    if possibilities[p] == i["value"]:
                        found = True
                        list_of_attrs.append(str(p))
                if found == False:
                    if missing.get(key) == None:
                        missing[key] = {}
                    missing[key][i["value"]] = "missing"
            if list_of_attrs != []:
                new_base[key] = list_of_attrs
    return new_base, missing


async def unpack_response(response):
    result: str = await response.text()
    if response.status == 404:
        LOGGER.error("Error Own Your Data PDS %s", result)
        raise PDSRecordNotFoundError("Record not found in Own your data PDS", result)

    elif response.status != 200:
        LOGGER.error("Error Own Your Data PDS %s", result)
        raise PDSError("Error Own Your Data PDS", result)

    return result


def get_delimiter(parameter_count_in):
    if parameter_count_in == 0:
        return "?"
    else:
        return "&"


class OwnYourDataVault(BasePDS):
    def __init__(self):
        super().__init__()
        self.api_url = None
        self.token = {"expires_in": "-1000"}
        self.token_timestamp = 0
        self.preview_settings = {
            "oca_schema_namespace": "pds",
            "oca_schema_dri": "9bABtmHu628Ss4oHmyTU5gy7QB1VftngewTmh7wdmN1j",
        }

    async def get_usage_policy(self):
        if self.settings.get("usage_policy") is None:
            await self.update_token()

        return self.settings["usage_policy"]

    async def update_token(self):
        parsed_url = urlparse(self.settings.get("api_url"))
        self.api_url = "{url.scheme}://{url.netloc}".format(url=parsed_url)
        LOGGER.debug("API URL OYD %s", self.api_url)

        client_id = self.settings.get("client_id")
        client_secret = self.settings.get("client_secret")
        grant_type = self.settings.get("grant_type", "client_credentials")
        scope = self.settings.get("scope")

        if self.api_url is None:
            raise PDSError("Please configure the plugin, api_url is empty")
        if client_id is None:
            raise PDSError("Please configure the plugin, client_id is empty")
        if client_secret is None:
            raise PDSError("Please configure the plugin, client_secret is empty")

        async with ClientSession() as session:
            body = {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": grant_type,
            }
            if scope is not None:
                body["scope"] = scope
            result = await session.post(
                self.api_url + "/oauth/token",
                json=body,
            )
            result = await unpack_response(result)
            token = json.loads(result)
            self.token = token
            self.token_timestamp = time.time()
            LOGGER.info("update token: %s", self.token)

        """
        Download the usage policy

        """

        url = f"{self.api_url}/api/meta/usage"
        async with ClientSession() as session:
            result = await session.get(
                url,
                headers={"Authorization": "Bearer " + self.token["access_token"]},
            )
            result = await unpack_response(result)
            self.settings["usage_policy"] = result
            LOGGER.debug("Usage policy %s", self.settings["usage_policy"])

        """
        Upload usage_policy as oca_schema_chunk
        """

        async with ClientSession() as session:
            result = await session.post(
                "https://governance.ownyourdata.eu/api/usage-policy/parse",
                headers={"Authorization": "Bearer " + self.token["access_token"]},
                json={"ttl": self.settings["usage_policy"]},
            )
            result = await unpack_response(result)
            result = json.loads(result)
            result, err = map_parsed_usage_policy(result, cached_schema_to_map_against)
            await self.save(
                result,
                {"table": "tda.oca_chunks.H5F2YgEbXpSZjcNqAYevfGPFXSWUV1d2PnVg2ubkkKb"},
                addition_meta={"missing": err},
            )

    async def update_token_when_expired(self):
        time_elapsed = time.time() - (self.token_timestamp - 10)
        if time_elapsed > float(self.token["expires_in"]):
            await self.update_token()

    async def load(self, dri: str) -> dict:
        assert_type(dri, str)
        await self.update_token_when_expired()

        url = f"{self.api_url}/api/data/{dri}?p=dri&f=plain"
        async with ClientSession() as session:
            result = await session.get(
                url, headers={"Authorization": "Bearer " + self.token["access_token"]}
            )
            result = await unpack_response(result)
            result_dict: dict = json.loads(result)

        return result_dict

    async def link(self, source_dri, with_targets):
        await self.update_token_when_expired()
        body = {"source": source_dri, "targets": with_targets}
        async with ClientSession() as session:
            url = f"{self.api_url}/api/relation?p=dri"
            print("url", url, "body", body)

            response = await session.post(
                url,
                headers={"Authorization": "Bearer " + self.token["access_token"]},
                json=body,
            )
            await unpack_response(response)

    async def save(self, record, metadata: dict, *, addition_meta={}) -> str:
        """
        meta: {
            "table" - specifies the table name into which save the data
            "oca_schema_dri"
        }
        """
        assert_type_or(record, str, dict)
        assert_type(metadata, dict)
        await self.update_token_when_expired()

        table = self.settings.get("repo")
        table = table if table is not None else "dip.data"

        meta = metadata
        dri_value = None

        if isinstance(record, str):
            dri_value = encode(record)
        elif isinstance(record, dict):
            dri_value = encode(json.dumps(record))

        record = {
            "content": record,
            "dri": dri_value,
            "timestamp": int(round(time.time() * 1000)),  # current time in milliseconds
        }
        LOGGER.debug("OYD save record %s metadata %s", record, meta)

        if meta.get("table") is not None:
            table = f"{table}.{meta.get('table')}"

        body = {
            "content": record,
            "dri": dri_value,
            "table_name": table,
            "mime_type": "application/json",
        }
        if addition_meta:
            body.update(addition_meta)

        async with ClientSession() as session:
            url = f"{self.api_url}/api/data"
            response = await session.post(
                url,
                headers={"Authorization": "Bearer " + self.token["access_token"]},
                json=body,
            )
            result = await unpack_response(response)
            result = json.loads(result)
            LOGGER.debug("Result of POST request %s", result)

        return dri_value

    async def load_multiple(
        self, *, table: str = None, oca_schema_base_dri: str = None
    ):
        await self.update_token_when_expired()
        url = f"{self.api_url}/api/data"

        parameter_count = 0

        if table is not None:
            url = url + get_delimiter(parameter_count) + f"table=dip.data.{table}"
            parameter_count += 1
        if oca_schema_base_dri is not None:
            url = (
                url
                + get_delimiter(parameter_count)
                + f"schema_dri={oca_schema_base_dri}"
            )
            parameter_count += 1

        url = url + get_delimiter(parameter_count) + "f=plain"

        LOGGER.info("OYD LOAD TABLE url [ %s ]", url)
        async with ClientSession() as session:
            result = await session.get(
                url, headers={"Authorization": "Bearer " + self.token["access_token"]}
            )
            result = await unpack_response(result)
            LOGGER.debug("OYD LOAD TABLE result: [ %s ]", result)

        return result

    async def ping(self) -> [bool, str]:
        try:
            await self.update_token()
        except (ClientConnectionError, ClientError) as err:
            return [False, str(err)]
        except PDSError as err:
            return [False, str(err)]

        return [True, None]


def test_format():
    base = {
        "sick": [{"ns": "...", "value": "No"}],
        "allergies": [{"ns": "...", "value": "Yes"}],
        "seriousReaction": [
            {"ns": "...", "value": "Yes"},
            {"ns": "...", "value": "Don't Know"},
        ],
        "test_not_existent": [{"ns": "...", "value": "Yes"}],
        "test_not_existent_value": [{"ns": "...", "value": "CoolValue"}],
    }
    schema = {
        "@context": "https://odca.tech/overlays/v1",
        "type": "spec/overlay/entry/1.0",
        "issued_by": "",
        "role": "",
        "purpose": "",
        "schema_base": "hl:afW1EfhWNh76BL3FUV8mniQAU4jRAb6Q6vxuCpLy5Nf6",
        "language": "en_US",
        "attr_entries": {
            "sick": ["Yes", "No", "Don't Know"],
            "allergies": ["Yes", "No", "Don't Know"],
            "seriousReaction": ["Yes", "No", "Don't Know"],
            "healthProblem": ["Yes", "No", "Don't Know"],
            "immuneSystemProblem": ["Yes", "No", "Don't Know"],
            "radiationTreatments": ["Yes", "No", "Don't Know"],
            "nervousSystemProblem": ["Yes", "No", "Don't Know"],
            "bloodProducts": ["Yes", "No", "Don't Know"],
            "pregnant": ["Yes", "No", "Don't Know"],
            "recentVaccinations": ["Yes", "No", "Don't Know"],
            "additionalDataRequest": ["Yes", "No"],
            "immunizationRecordCard": ["Yes", "No"],
            "test_not_existent_value": ["Yes", "No"],
        },
    }

    result, err = map_parsed_usage_policy(base, schema)
    assert err["test_not_existent"] == "missing"
    assert err["test_not_existent_value"]["CoolValue"] == "missing"
    assert result == {
        "sick": ["1"],
        "allergies": ["0"],
        "seriousReaction": ["0", "2"],
    }


cached_schema_to_map_against = {
    "@context": "https://odca.tech/overlays/v1",
    "type": "spec/overlay/entry/1.0",
    "issued_by": "",
    "role": "",
    "purpose": "",
    "schema_base": "hl:8gkUPenRUXU15qrUZufoeLriqxqNMAtmUqRJCC8ajULr",
    "language": "en_US",
    "attr_entries": {
        "data": [
            "AnyData",
            "Activity",
            "Anonymized",
            "AudiovisualActivity",
            "Computer",
            "Content",
            "Demographic",
            "Derived",
            "EarthObservation",
            "Meteorology",
            "MeteorologicMeasurement",
            "MeteorologicForecast",
            "MeteorologicCurrent",
            "MeteorologicHistoric",
            "MeteorologicRaster",
            "Geophysics",
            "GeophysicsSeismology",
            "GeophysicsMagneticField",
            "GeophysicsGravimetry",
            "Financial",
            "Government",
            "Health",
            "Diabetes",
            "Sensor",
            "InsulinPump",
            "Interactive",
            "Judicial",
            "Location",
            "Navigation",
            "Online",
            "OnlineActivity",
            "Physical",
            "PhysicalActivity",
            "Political",
            "Preference",
            "Profile",
            "Purchase",
            "Social",
            "State",
            "Statistical",
            "TelecomActivity",
            "UniqueId",
        ],
        "purpose": [
            "AnyPurpose",
            "Account",
            "Admin",
            "Arts",
            "Browsing",
            "Charity",
            "Communicate",
            "Current",
            "Custom",
            "Delivery",
            "Develop",
            "Downloads",
            "Education",
            "Feedback",
            "Finmgt",
            "Gambling",
            "Gaming",
            "Government",
            "Health",
            "Historical",
            "Login",
            "Marketing",
            "MeteorologicalService",
            "News",
            "Payment",
            "Sales",
            "Search",
            "State",
            "Tailoring",
            "Telemarketing",
        ],
        "processing": [
            "AnyProcessing",
            "Aggregate",
            "Analyze",
            "Anonymize",
            "Collect",
            "Copy",
            "Derive",
            "Move",
            "Query",
            "Transfer",
        ],
        "recipient": [
            "AnyRecipient",
            "Ours",
            "Delivery",
            "Same",
            "OtherRecipient",
            "Unrelated",
            "Public",
        ],
        "location": [
            "AnyLocation",
            "OurServers",
            "ThirdParty",
            "EU",
            "EULike",
            "ThirdCountries",
        ],
        "duration": [
            "AnyDuration",
            "StatedPurpose",
            "LegalRequirement",
            "BusinessPractices",
            "Indefinitely",
        ],
    },
}


def test_format_2():
    schema = cached_schema_to_map_against
    base = {
        "duration": [
            {
                "ns": "http://www.specialprivacy.eu/vocabs/duration#",
                "value": "LegalRequirement",
            }
        ],
        "data": [
            {"ns": "http://www.specialprivacy.eu/vocabs/data#", "value": "Profile"}
        ],
        "purpose": [
            {"ns": "http://www.specialprivacy.eu/vocabs/purposes#", "value": "Health"}
        ],
        "recipient": [
            {"ns": "http://www.specialprivacy.eu/vocabs/recipients#", "value": "Ours"}
        ],
        "processing": [
            {
                "ns": "http://www.specialprivacy.eu/vocabs/processing#",
                "value": "Aggregate",
            },
            {
                "ns": "http://www.specialprivacy.eu/vocabs/processing#",
                "value": "Analyze",
            },
            {
                "ns": "http://www.specialprivacy.eu/vocabs/processing#",
                "value": "Collect",
            },
            {"ns": "http://www.specialprivacy.eu/vocabs/processing#", "value": "Copy"},
            {"ns": "http://www.specialprivacy.eu/vocabs/processing#", "value": "Move"},
            {"ns": "http://www.specialprivacy.eu/vocabs/processing#", "value": "Query"},
            {
                "ns": "http://www.specialprivacy.eu/vocabs/processing#",
                "value": "Transfer",
            },
        ],
        "location": [
            {"ns": "http://www.specialprivacy.eu/vocabs/locations#", "value": "EU"}
        ],
    }
    result, err = map_parsed_usage_policy(base, schema)

    assert err == {}
    assert result == {
        "data": ["35"],
        "purpose": ["18"],
        "processing": ["1", "2", "4", "5", "7", "8", "9"],
        "recipient": ["1"],
        "location": ["3"],
        "duration": ["2"],
    }, result


async def test_link(vault: OwnYourDataVault):
    dri1 = "zQmWK8aKAna7XgsEoWHwnqyDcHTyb9WFqXAQ5uMb7qRqm6s"
    dri2 = "zQmNYBW44DdSisoacg4bfe6gNpmemXicBuKDmgEFMmHAQFf"
    assert dri1 != dri2
    res1 = await vault.load(dri1)
    res2 = await vault.load(dri2)
    print("First:", res1)
    print("Second:", res2)
    await vault.link(dri1, [dri2])


async def test_usage_policy_parse():
    vault = OwnYourDataVault()
    #  lgicmntlfmqlguhalz
    vault.settings["client_id"] = "gVQJTSabNK8DxNzu3PeGWQwBtXSb2Iv7FgYlbzBEbfg"
    vault.settings["client_secret"] = "9yBmtiyO2YwhtHA9btSrYensVZZ9DLNY1Vq5D-EjxwQ"
    vault.settings["api_url"] = "https://data-vault.eu"
    await test_link(vault)
    await vault.update_token()
    # result = await vault.load_multiple()
    # print(result)

    # test_format()
    # test_format_2()


run_standalone_async(__name__, test_usage_policy_parse)
