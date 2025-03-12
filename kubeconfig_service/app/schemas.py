from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class KubeconfigBase(BaseModel):
    filename: str
    original_filename: str
    cluster_name: Optional[str] = None
    context_name: Optional[str] = None
    active: bool = False
    is_operator_installed: bool = False

class KubeconfigResponse(KubeconfigBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class KubeconfigList(BaseModel):
    kubeconfigs: List[KubeconfigResponse]

class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    detail: str

class ClusterNameResponse(BaseModel):
    filename: str
    cluster_name: str
    active: bool
    operator_installed: bool

class ClusterNamesResponse(BaseModel):
    cluster_names: List[ClusterNameResponse]
    errors: Optional[List[dict]] = None
