from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class QuestionOption(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False


class ScoringSchema(BaseModel):
    mode: str = Field(default="all_or_nothing", pattern="^(all_or_nothing|per_item|by_correct_count|custom)$")
    base_points: float = Field(default=1000.0, ge=0.0, le=100000.0)
    min_points: float = Field(default=0.0, ge=-100000.0, le=100000.0)
    max_points: float = Field(default=1000.0, ge=0.0, le=100000.0)
    coeff_a: float | None = None
    coeff_b: float = 0.0
    coeff_c: float = 0.0
    coeff_d: float = 0.0
    custom_map: dict[int, float] = Field(default_factory=dict)
    speed_bonus_enabled: bool = False
    k_max: float = Field(default=1.0, ge=0.1, le=5.0)
    k_min: float = Field(default=0.5, ge=0.0, le=5.0)
    t0_seconds: float = Field(default=0.0, ge=0.0, le=300.0)


class QuestionItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=8000)
    explanation: str = Field(default="", max_length=8000)
    sandbox_html: str = Field(default="", max_length=16000)
    options: list[QuestionOption] = Field(min_length=2, max_length=12)
    duration_seconds: int = Field(default=30, ge=5, le=600)
    results_duration_seconds: int = Field(default=10, ge=0, le=300)
    auto_advance_question: bool = True
    auto_advance_results: bool = False
    scoring: ScoringSchema = Field(default_factory=ScoringSchema)


class VisibilityScreenRules(BaseModel):
    show_question_text: bool = True
    show_options: bool = True
    show_timer: bool = True
    show_explanation_on_results: bool = True
    show_correct_on_results: bool = True
    show_stats_on_results: bool = True
    show_leaderboard_on_results: bool = True


class QuizSettings(BaseModel):
    participant_rules: VisibilityScreenRules = Field(default_factory=VisibilityScreenRules)
    broadcast_rules: VisibilityScreenRules = Field(default_factory=VisibilityScreenRules)
    copy_protection: bool = False
    retention_days: int = Field(default=30, ge=1, le=365)


class QuizCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    questions: list[QuestionItem] = Field(default_factory=list, max_length=100)
    settings: QuizSettings = Field(default_factory=QuizSettings)


class QuizUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    questions: list[QuestionItem] | None = Field(default=None, max_length=100)
    settings: QuizSettings | None = None


class QuizResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    questions: list[dict]
    settings: dict
    version: int
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
