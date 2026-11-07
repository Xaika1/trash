import asyncio
import hashlib
import hmac
import secrets


def make_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def check_hash(password, stored):
    salt, digest = stored.split("$")
    new_digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(new_digest.hex(), digest)


async def hash_password(password):
    return await asyncio.to_thread(make_hash, password)


async def verify_password(password, stored):
    return await asyncio.to_thread(check_hash, password, stored)
