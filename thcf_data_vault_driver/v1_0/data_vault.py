from aries_cloudagent.pdstorage_thcf.base import PersonalDataStorage
from aries_cloudagent.pdstorage_thcf.error import (
    PDSNotFoundError,
)
from aiohttp import ClientSession, FormData
from aries_cloudagent.config.injection_context import InjectionContext

DATA_VAULT = "http://ocadatavault/api/v1/files"


class THCFDataVault(PersonalDataStorage):
    def __init__(self):
        super().__init__()
        self.settings = {"no_configuration_needed": "yes"}

    async def load(self, id: str) -> str:
        """
        Returns: None on record not found
        """
        url = DATA_VAULT + "/" + id
        print("URL: ", url)

        async with ClientSession() as session:
            result = await session.get(url)
            result = await result.text()
            print(result)

        return result

    async def save(self, record: str) -> str:
        data = FormData()
        data.add_field("file", record, filename="data", content_type="application/json")

        result = None
        async with ClientSession() as session:
            result = await session.post(url=DATA_VAULT, data=data)
            result = await result.text()
            print(result)

        return result