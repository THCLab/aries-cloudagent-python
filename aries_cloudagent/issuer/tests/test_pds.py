import json

import pytest

from asynctest import TestCase as AsyncTestCase
from asynctest import mock as async_mock
from ...wallet.basic import BasicWallet
from ..pds import *
from ...aathcf.credentials import verify_proof


TEST_DID = "55GkHamhTU1ZbTbV2ab9DE"
SCHEMA_NAME = "resident"
SCHEMA_VERSION = "1.0"
SCHEMA_TXN = 1234
SCHEMA_ID = f"{TEST_DID}:2:{SCHEMA_NAME}:{SCHEMA_VERSION}"
CRED_DEF_ID = f"{TEST_DID}:3:CL:{SCHEMA_TXN}:default"

credential_test_schema = {
    "@context": [
        "https://www.w3.org/2018/credentials/v1",
        "https://www.schema.org",
    ],
    "type": [
        "VerifiableCredential",
        "@TODO should this be oca schema or what dri points to",
    ],
    "issuer": "1234",
    "issuanceDate": time_now(),
    "credentialSubject": {
        "id": "TODO: Did of subject",
        "ocaSchema": {
            "dri": "1234",
            "dataDri": "1234",
        },
    },
    "proof": {
        "type": "Ed25519Signature2018",
        "created": time_now(),
        "proofPurpose": "assertionMethod",
        "verificationMethod": "1234",
        "jws": "1234",
    },
}


def assert_that_contains(base: dict, to_verify: dict):
    # assert that contains at least values of base or more
    # and these least values are not NULL
    for key in base:
        assert to_verify[key] != None
        assert to_verify[key] != {}
        assert to_verify[key] != []


async def create_test_credential(issuer):
    test_cred = {
        "credentialSubject": {
            "id": "TODO: Did of subject",
            "ocaSchema": {
                "dri": "1234",
                "dataDri": "1234",
            },
            "first_name": "Karol",
        },
    }

    connection = ConnectionRecord(my_did="1234-my", their_did="1234-their")
    credential, _ = await issuer.create_credential(
        schema={"credential_type": "TestType"},
        credential_values=test_cred["credentialSubject"],
        credential_offer={},
        credential_request={"connection_record": connection},
    )
    credential_dict = json.loads(credential)

    assert credential_dict["credentialSubject"] == test_cred["credentialSubject"]

    return credential_dict


class TestPDSIssuer(AsyncTestCase):
    async def setUp(self):
        self.wallet = BasicWallet()
        self.issuer: PDSIssuer = PDSIssuer(self.wallet)
        assert self.issuer.wallet is self.wallet
        await self.wallet.create_public_did()

    async def test_create_credential(self):
        credential_dict = await create_test_credential(self.issuer)

        assert_that_contains(credential_test_schema, credential_dict)
        assert_that_contains(credential_test_schema["proof"], credential_dict["proof"])

        assert await verify_proof(self.wallet, credential_dict) == True
