from typing import Any
from fastapi import APIRouter
from app.db import query_meta_summary
from app.schemas import MetaResponseOut

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta", response_model=MetaResponseOut)
def get_meta() -> dict[str, Any]:
    return query_meta_summary()
