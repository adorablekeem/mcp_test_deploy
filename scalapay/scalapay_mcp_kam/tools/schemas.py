from typing import Any, List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class CreatePresentationArgs(BaseModel):
    title: str = Field(..., min_length=1, description='"title" (string) is required.')


class GetPresentationArgs(BaseModel):
    presentation_id: str = Field(
        ..., min_length=1, alias="presentationId", description='"presentationId" (string) is required.'
    )
    fields: Optional[str] = None


class BatchUpdatePresentationArgs(BaseModel):
    presentation_id: str = Field(
        ..., min_length=1, alias="presentationId", description='"presentationId" (string) is required.'
    )
    requests: List[Any] = Field(..., min_items=1, description='"requests" (array) is required.')
    write_control: Optional[Any] = Field(default=None, alias="writeControl")


class GetPageArgs(BaseModel):
    presentation_id: str = Field(
        ..., min_length=1, alias="presentationId", description='"presentationId" (string) is required.'
    )
    page_object_id: str = Field(
        ..., min_length=1, alias="pageObjectId", description='"pageObjectId" (string) is required.'
    )


class SummarizePresentationArgs(BaseModel):
    presentation_id: str = Field(
        ..., min_length=1, alias="presentationId", description='"presentationId" (string) is required.'
    )
    include_notes: Optional[bool] = Field(default=False, alias="include_notes")
