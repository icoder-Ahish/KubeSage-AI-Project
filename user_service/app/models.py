from sqlmodel import SQLModel, Field
from typing import Optional
import datetime
import uuid

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

class UserToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    expires_at: datetime.datetime
    is_revoked: bool = Field(default=False)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
