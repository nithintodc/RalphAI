"""Resolve Multilogin password from .env without shell mangling special characters."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os


def multilogin_password() -> str:
    """
    Password for Multilogin API sign-in.

    Prefer ``MULTILOGIN_PASSWORD_B64`` (base64 of UTF-8 password) in .env so ``$`` and
    other shell metacharacters are not altered when ``run.sh`` sources the file.

    Encode locally::

        python -c "import base64; print(base64.b64encode(b'YOUR_PASSWORD').decode())"

    Falls back to plain ``MULTILOGIN_PASSWORD`` if B64 is unset.
    """
    b64 = os.getenv("MULTILOGIN_PASSWORD_B64", "").strip()
    if b64:
        try:
            return base64.b64decode(b64, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError(
                "MULTILOGIN_PASSWORD_B64 is not valid base64 UTF-8. "
                "Re-encode with: python -c \"import base64; print(base64.b64encode(b'...').decode())\""
            ) from exc
    return os.getenv("MULTILOGIN_PASSWORD", "").strip()


def multilogin_password_for_api() -> str:
    """
    Value to send in POST /user/signin ``password`` field.

    Multilogin X API expects MD5 hex of the UTF-8 password (web app uses plain text).
    See https://multilogin.com/help/en_US/getting-started-with-postman and
    https://documenter.getpostman.com/view/28533318/2s946h9Cv9

    Set ``MULTILOGIN_SIGNIN_PASSWORD_PLAIN=true`` only for legacy plain-password sign-in.
    """
    plain = multilogin_password()
    if not plain:
        return ""
    if os.getenv("MULTILOGIN_SIGNIN_PASSWORD_PLAIN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return plain
    return hashlib.md5(plain.encode("utf-8")).hexdigest()
