from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    quiz_id: uuid.UUID


class JoinRunRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


class JoinRunResponse(BaseModel):
    run_id: uuid.UUID
    participant_id: uuid.UUID
    participant_token: str
    nickname: str


class SubmitAnswerRequest(BaseModel):
    selected_options: list[str] = Field(default_factory=list, max_length=12)


class ReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class TransitionRequest(BaseModel):
    action: str = Field(pattern="^(start|next|finish)$")
    expected_version: int = Field(ge=1)


class PublicOptionSchema(BaseModel):
    id: str
    text: str


class ResultOptionSchema(BaseModel):
    id: str
    text: str
    is_correct: bool


class LeaderboardEntry(BaseModel):
    participant_id: str
    nickname: str
    total_score: float
    total_time_ms: int
    rank: int


class ParticipantStateResponse(BaseModel):
    run_id: str
    stage: str
    substage: str
    question_index: int
    total_questions: int
    version: int
    server_time: datetime
    deadline_at: datetime | None
    copy_protection: bool
    question: dict | None = None
    results: dict | None = None
    self_score: float | None = None
    self_rank: int | None = None
    leaderboard: list[LeaderboardEntry] | None = None


class BroadcastStateResponse(BaseModel):
    run_id: str
    join_code: str
    stage: str
    substage: str
    question_index: int
    total_questions: int
    version: int
    server_time: datetime
    deadline_at: datetime | None
    participant_count: int
    question: dict | None = None
    results: dict | None = None
    leaderboard: list[LeaderboardEntry] | None = None


class HostStateResponse(BaseModel):
    run_id: str
    join_code: str
    broadcast_token: str
    stage: str
    substage: str
    question_index: int
    total_questions: int
    version: int
    server_time: datetime
    deadline_at: datetime | None
    participant_count: int
    answered_count: int
    current_question: dict | None = None
    stats: dict | None = None
    leaderboard: list[LeaderboardEntry] = Field(default_factory=list)
