import uuid

from pydantic import BaseModel, Field


class AiProposeRequest(BaseModel):
    quiz_id: uuid.UUID
    instruction: str = Field(min_length=3, max_length=2000)
    attachment_text: str = Field(default="", max_length=20000)


class AiDiffOperation(BaseModel):
    op: str = Field(pattern="^(add_question|update_question|update_explanation)$")
    question_index: int | None = None
    before: dict | None = None
    after: dict


class AiProposeResponse(BaseModel):
    quiz_id: uuid.UUID
    base_version: int
    operations: list[AiDiffOperation]


class AiApplyRequest(BaseModel):
    quiz_id: uuid.UUID
    base_version: int = Field(ge=1)
    operations: list[AiDiffOperation]
