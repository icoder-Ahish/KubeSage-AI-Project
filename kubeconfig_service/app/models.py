from sqlmodel import SQLModel, Field
from typing import Optional
import datetime

class Kubeconf(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    original_filename: str = Field(default="")
    user_id: int = Field(index=True)
    active: bool = Field(default=False, index=True)
    path: str = Field()
    cluster_name: Optional[str] = Field(default=None, index=True)
    context_name: Optional[str] = Field(default=None, index=True)
    is_operator_installed: bool = Field(default=False, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
