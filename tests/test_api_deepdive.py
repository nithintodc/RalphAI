import asyncio

from fastapi import HTTPException

from api.main import post_deepdive


def test_deepdive_requires_zip_upload():
    try:
        asyncio.run(post_deepdive(operator_id="SSM", zip_files=None))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Upload at least one DeepDive zip file."
    else:
        raise AssertionError("Expected HTTPException for missing zip uploads.")
