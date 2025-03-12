from sqlmodel import SQLModel, Field
from typing import Optional
import datetime
import uuid

class AnalysisResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    cluster_name: str = Field(index=True)
    namespace: Optional[str] = Field(default=None, index=True)
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    result_json: str = Field(default="")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    parameters: str = Field(default="{}")  # JSON string of parameters used

class AIBackendConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    backend_name: str = Field(index=True)
    is_default: bool = Field(default=False, index=True)
    config_json: str = Field(default="{}")  # JSON string of backend configuration
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    
    class Config:
        # Define a unique constraint on user_id and backend_name
        table_args = {
            "UniqueConstraint": ("user_id", "backend_name")
        }
