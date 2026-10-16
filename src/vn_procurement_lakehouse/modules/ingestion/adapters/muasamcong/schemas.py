from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchPage(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )

    content: list[dict[str, Any]]

    total_pages: int = Field(alias="totalPages", ge=0)
    total_elements: int = Field(alias="totalElements", ge=0)

    page_size: int = Field(alias="pageSize", gt=0)
    current_page: int = Field(alias="currentPage", ge=0)

    first: bool
    last: bool


class SearchResponse(BaseModel):
    page: SearchPage
