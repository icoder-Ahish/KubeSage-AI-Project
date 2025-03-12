from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# Common Response Models
class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    detail: str

# Analysis Models
class AnalysisRequest(BaseModel):
    anonymize: bool = Field(False, description="Anonymize data before sending it to the AI backend")
    backend: Optional[str] = Field(None, description="Backend AI provider")
    custom_analysis: bool = Field(False, description="Enable custom analyzers")
    custom_headers: Optional[List[str]] = Field(None, description="Custom Headers, <key>:<value>")
    explain: bool = Field(False, description="Explain the problem")
    filter_analyzers: Optional[List[str]] = Field(None, description="Filter for these analyzers")
    interactive: bool = Field(False, description="Enable interactive mode")
    language: str = Field("english", description="Language to use for AI")
    max_concurrency: int = Field(10, description="Maximum number of concurrent requests")
    namespace: Optional[str] = Field(None, description="Namespace to analyze")
    no_cache: bool = Field(False, description="Do not use cached data")
    output_format: str = Field("text", description="Output format (text, json)")
    selector: Optional[str] = Field(None, description="Label selector")
    with_doc: bool = Field(False, description="Give me the official documentation of the involved field")

class AnalysisResultItem(BaseModel):
    name: str
    kind: str
    namespace: str
    status: str
    severity: str
    message: str
    hint: Optional[str] = None
    explanation: Optional[str] = None
    docs: Optional[str] = None

class AnalysisResultResponse(BaseModel):
    result_id: str
    cluster_name: str
    namespace: Optional[str] = None
    items: List[AnalysisResultItem]
    created_at: datetime
    parameters: Dict[str, Any]

class AnalysisResultsList(BaseModel):
    results: List[AnalysisResultResponse]

# AI Backend Models
class AIBackendConfigRequest(BaseModel):
    backend: str = Field(..., description="Backend AI provider")
    baseurl: Optional[str] = Field(None, description="URL AI provider")
    compartmentId: Optional[str] = Field(None, description="Compartment ID for generative AI model (only for oci backend)")
    endpointname: Optional[str] = Field(None, description="Endpoint Name (only for amazonbedrock, amazonsagemaker backends)")
    engine: Optional[str] = Field(None, description="Azure AI deployment name (only for azureopenai backend)")
    maxtokens: int = Field(2048, description="Specify a maximum output length")
    model: str = Field("gpt-3.5-turbo", description="Backend AI model")
    organizationId: Optional[str] = Field(None, description="OpenAI or AzureOpenAI Organization ID")
    password: Optional[str] = Field(None, description="Backend AI password")
    providerId: Optional[str] = Field(None, description="Provider specific ID for e.g. project (only for googlevertexai backend)")
    providerRegion: Optional[str] = Field(None, description="Provider Region name (only for amazonbedrock, googlevertexai backend)")
    temperature: float = Field(0.7, description="The sampling temperature")
    topk: int = Field(50, description="Sampling Cutoff")
    topp: float = Field(0.5, description="Probability Cutoff")
    is_default: bool = Field(False, description="Set as default backend")

class AIBackendConfigResponse(BaseModel):
    id: int
    backend_name: str
    is_default: bool
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class AIBackendsList(BaseModel):
    backends: List[AIBackendConfigResponse]
