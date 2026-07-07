"""opensrc source-fetcher API — fetch + browse any open-source package's real source."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import opensrc_service

router = APIRouter()


class FetchBody(BaseModel):
    pkg: str


def _guard(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except opensrc_service.OpensrcUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/status")
def status() -> dict:
    return {"available": opensrc_service.available()}


@router.post("/fetch")
def fetch(body: FetchBody) -> Any:
    return _guard(lambda: {"pkg": body.pkg, "path": opensrc_service.fetch(body.pkg)})


@router.get("/list")
def list_cached() -> Any:
    return _guard(opensrc_service.list_cached)


@router.get("/tree")
def tree(pkg: str) -> Any:
    return _guard(lambda: opensrc_service.tree(pkg))


@router.get("/file")
def file(pkg: str, path: str) -> Any:
    return _guard(lambda: opensrc_service.read(pkg, path))


@router.get("/search")
def search(pkg: str, q: str) -> Any:
    return _guard(lambda: opensrc_service.search(pkg, q))
