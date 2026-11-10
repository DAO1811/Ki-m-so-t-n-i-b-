"""Small software authenticator for exercising the real WebAuthn verifier.

These are generated test keys, never device exports or company credentials.
The authenticator emits ES256, CBOR attestation format ``none`` and signed
assertions in the same JSON shape returned by navigator.credentials.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass, field

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def unb64url(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass
class SoftwareAuthenticator:
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    private_key: object = field(
        default_factory=lambda: ec.generate_private_key(ec.SECP256R1())
    )

    @property
    def id(self):
        return b64url(self.credential_id)

    @property
    def public_key(self):
        numbers = self.private_key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    @staticmethod
    def _client_data(challenge, *, origin, ceremony_type, extra):
        data = {"type": ceremony_type, "challenge": challenge, "origin": origin}
        data.update(extra or {})
        return json.dumps(data, separators=(",", ":")).encode()

    @staticmethod
    def _auth_data(
        rp_id, *, counter, uv, up, backup_eligible, backed_up, attested=False
    ):
        flags = (
            (0x01 if up else 0)
            | (0x04 if uv else 0)
            | (0x08 if backup_eligible else 0)
            | (0x10 if backed_up else 0)
            | (0x40 if attested else 0)
        )
        return (
            hashlib.sha256(rp_id.encode()).digest()
            + bytes([flags])
            + counter.to_bytes(4, "big")
        )

    def registration(
        self,
        options,
        *,
        origin="http://localhost",
        rp_id="localhost",
        counter=0,
        uv=True,
        up=True,
        backup_eligible=False,
        backed_up=False,
        challenge=None,
        ceremony_type="webauthn.create",
        client_extra=None,
    ):
        client_data = self._client_data(
            challenge if challenge is not None else options["challenge"],
            origin=origin,
            ceremony_type=ceremony_type,
            extra=client_extra,
        )
        auth_data = self._auth_data(
            rp_id,
            counter=counter,
            uv=uv,
            up=up,
            backup_eligible=backup_eligible,
            backed_up=backed_up,
            attested=True,
        )
        auth_data += bytes(16) + len(self.credential_id).to_bytes(2, "big")
        auth_data += self.credential_id + self.public_key
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data),
                "attestationObject": b64url(
                    cbor2.dumps(
                        {
                            "fmt": "none",
                            "attStmt": {},
                            "authData": auth_data,
                        }
                    )
                ),
                "transports": ["internal"],
            },
        }

    def assertion(
        self,
        options,
        user_handle,
        *,
        origin="http://localhost",
        rp_id="localhost",
        counter=1,
        uv=True,
        up=True,
        backup_eligible=False,
        backed_up=False,
        challenge=None,
        ceremony_type="webauthn.get",
        client_extra=None,
        wrong_signature=False,
    ):
        client_data = self._client_data(
            challenge if challenge is not None else options["challenge"],
            origin=origin,
            ceremony_type=ceremony_type,
            extra=client_extra,
        )
        auth_data = self._auth_data(
            rp_id,
            counter=counter,
            uv=uv,
            up=up,
            backup_eligible=backup_eligible,
            backed_up=backed_up,
        )
        signing_key = (
            ec.generate_private_key(ec.SECP256R1())
            if wrong_signature
            else self.private_key
        )
        signature = signing_key.sign(
            auth_data + hashlib.sha256(client_data).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(signature),
                "userHandle": b64url(user_handle) if user_handle is not None else None,
            },
        }
