from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session
from typing import Dict, List, Optional
import json

from app.database import get_session
from app.auth import get_current_user
from app.services import (
    run_k8sgpt_analysis,
    get_analysis_result,
    list_analysis_results,
    add_ai_backend,
    list_ai_backends,
    get_ai_backend,
    delete_ai_backend,
    set_default_ai_backend,
    get_available_analyzers
)
from app.schemas import (
    AnalysisRequest,
    AnalysisResultResponse,
    AnalysisResultsList,
    AIBackendConfigRequest,
    AIBackendConfigResponse,
    AIBackendsList,
    MessageResponse
)
from app.logger import logger

k8sgpt_router = APIRouter()

@k8sgpt_router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_cluster(
    analysis_request: AnalysisRequest,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Run K8sGPT analysis on the active Kubernetes cluster
    """
    user_id = current_user["id"]
    
    # Convert analysis_request to dict for parameter passing
    parameters = analysis_request.dict()
    
    # Run analysis
    analysis_result = await run_k8sgpt_analysis(
        user_id=user_id,
        parameters=parameters,
        session=session
    )
    
    # Parse the result for the response
    result_json = json.loads(analysis_result.result_json)
    parameters_json = json.loads(analysis_result.parameters)
    
    # Extract the items from the result
    items = []
    if isinstance(result_json, list):
        for item in result_json:
            items.append({
                "name": item.get("name", ""),
                "kind": item.get("kind", ""),
                "namespace": item.get("namespace", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "message": item.get("message", ""),
                "hint": item.get("hint", None),
                "explanation": item.get("explanation", None),
                "docs": item.get("docs", None)
            })
    
    return {
        "result_id": analysis_result.result_id,
        "cluster_name": analysis_result.cluster_name,
        "namespace": analysis_result.namespace,
        "items": items,
        "created_at": analysis_result.created_at,
        "parameters": parameters_json
    }

@k8sgpt_router.get("/analysis/{result_id}", response_model=AnalysisResultResponse)
async def get_analysis(
    result_id: str,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get a specific analysis result
    """
    user_id = current_user["id"]
    
    analysis_data = await get_analysis_result(
        user_id=user_id,
        result_id=result_id,
        session=session
    )
    
    # Extract the items from the result
    items = []
    result_json = analysis_data["result"]
    if isinstance(result_json, list):
        for item in result_json:
            items.append({
                "name": item.get("name", ""),
                "kind": item.get("kind", ""),
                "namespace": item.get("namespace", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "message": item.get("message", ""),
                "hint": item.get("hint", None),
                "explanation": item.get("explanation", None),
                "docs": item.get("docs", None)
            })
    
    return {
        "result_id": analysis_data["result_id"],
        "cluster_name": analysis_data["cluster_name"],
        "namespace": analysis_data["namespace"],
        "items": items,
        "created_at": analysis_data["created_at"],
        "parameters": analysis_data["parameters"]
    }

@k8sgpt_router.get("/analyses", response_model=AnalysisResultsList)
async def list_analyses(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    List analysis results for the user
    """
    user_id = current_user["id"]
    
    results = await list_analysis_results(
        user_id=user_id,
        session=session,
        limit=limit,
        offset=offset
    )
    
    # Transform results for the response
    transformed_results = []
    for result in results:
        # Get detailed result
        detailed_result = await get_analysis_result(
            user_id=user_id,
            result_id=result["result_id"],
            session=session
        )
        
        # Extract items
        items = []
        result_json = detailed_result["result"]
        if isinstance(result_json, list):
            for item in result_json:
                items.append({
                    "name": item.get("name", ""),
                    "kind": item.get("kind", ""),
                    "namespace": item.get("namespace", ""),
                    "status": item.get("status", ""),
                    "severity": item.get("severity", ""),
                    "message": item.get("message", ""),
                    "hint": item.get("hint", None),
                    "explanation": item.get("explanation", None),
                    "docs": item.get("docs", None)
                })
        
        transformed_results.append({
            "result_id": detailed_result["result_id"],
            "cluster_name": detailed_result["cluster_name"],
            "namespace": detailed_result["namespace"],
            "items": items,
            "created_at": detailed_result["created_at"],
            "parameters": detailed_result["parameters"]
        })
    
    return {"results": transformed_results}

@k8sgpt_router.post("/backends", response_model=AIBackendConfigResponse)
async def create_backend(
    backend_config: AIBackendConfigRequest,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Add or update an AI backend configuration
    """
    user_id = current_user["id"]
    
    backend = await add_ai_backend(
        user_id=user_id,
        backend_config=backend_config.dict(),
        session=session
    )
    
    return {
        "id": backend.id,
        "backend_name": backend.backend_name,
        "is_default": backend.is_default,
        "config": json.loads(backend.config_json),
        "created_at": backend.created_at,
        "updated_at": backend.updated_at
    }

@k8sgpt_router.get("/backends", response_model=AIBackendsList)
async def get_backends(
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    List AI backend configurations for the user
    """
    user_id = current_user["id"]
    
    backends = await list_ai_backends(
        user_id=user_id,
        session=session
    )
    
    return {"backends": backends}

@k8sgpt_router.get("/backends/{backend_name}", response_model=AIBackendConfigResponse)
async def get_backend(
    backend_name: str,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get a specific AI backend configuration
    """
    user_id = current_user["id"]
    
    backend = await get_ai_backend(
        user_id=user_id,
        backend_name=backend_name,
        session=session
    )
    
    return backend

@k8sgpt_router.delete("/backends/{backend_name}", response_model=MessageResponse)
async def remove_backend(
    backend_name: str,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete an AI backend configuration
    """
    user_id = current_user["id"]
    
    await delete_ai_backend(
        user_id=user_id,
        backend_name=backend_name,
        session=session
    )
    
    return {"message": f"Backend {backend_name} deleted successfully"}

@k8sgpt_router.put("/backends/{backend_name}/default", response_model=MessageResponse)
async def set_default_backend(
    backend_name: str,
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Set a backend as the default
    """
    user_id = current_user["id"]
    
    await set_default_ai_backend(
        user_id=user_id,
        backend_name=backend_name,
        session=session
    )
    
    return {"message": f"Backend {backend_name} set as default"}

@k8sgpt_router.get("/analyzers", response_model=List[str])
async def list_analyzers(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get available K8sGPT analyzers
    """
    user_id = current_user["id"]
    
    analyzers = await get_available_analyzers(user_id)
    
    return analyzers
