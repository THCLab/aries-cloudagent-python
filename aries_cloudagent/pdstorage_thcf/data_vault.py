from .base import BasePersonalDataStorage
from .error import PDSNotFoundError
from aiohttp import ClientSession, FormData, ClientConnectionError
import json
import logging

LOGGER = logging.getLogger(__name__)

API_ENDPOINT = "/api/v1/files"


class DataVault(BasePersonalDataStorage):
    def __init__(self):
        super().__init__()
        self.preview_settings = {
            "oca_schema_namespace": "pds",
            "oca_schema_dri": "ejHFuhg2v1ZrL5uQrHe3Arcxy62GWNakjTwL38swC9RB",
        }
        self.settings = {}
        # self.settings = {"api_url": "https://data-vault.argo.colossi.network"}

    async def load(self, id: str) -> str:
        """
        Returns: None on record not found
        """
        url = f"{self.settings['api_url']}{API_ENDPOINT}/{id}"
        LOGGER.info(
            f"""DataVault.load: 
                url: {url}
                id: {id}
                settings: {self.settings}
            """
        )

        async with ClientSession() as session:
            response = await session.get(url)
            response_text = await response.text()
            LOGGER.info("Response %s", response_text)

        # seek errors
        try:
            response_json = json.loads(response_text)
            if "errors" in response_json:
                return None
        except json.JSONDecodeError:
            LOGGER.warning("Error found in data_vault load %s", response_text)
            pass

        return response_text

    async def save(self, record: str, metadata: str) -> str:
        data = FormData()
        data.add_field("file", record, filename="data", content_type="application/json")
        url = f"{self.settings['api_url']}{API_ENDPOINT}"
        LOGGER.info(
            f"""DataVault.save:
                url: {url}
                id: {id}
                settings: {self.settings}
            """
        )

        async with ClientSession() as session:
            response = await session.post(url=url, data=data)
            response_text = await response.text()
            response_json = json.loads(response_text)

        return response_json["content_dri"]

    async def load_multiple(
        self, *, table: str = None, oca_schema_base_dri: str = None
    ) -> str:

        assert not "Load multiple not supported by active PDS"

    async def ping(self) -> [bool, str]:
        """
        Returns: true if we connected at all, false if service is not responding.
                 and additional info about the failure
        """
        try:
            await self.load("ping")
        except ClientConnectionError as err:
            return [False, str(err)]

        return [True, None]
