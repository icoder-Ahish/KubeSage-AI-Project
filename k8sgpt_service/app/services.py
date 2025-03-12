import os
import json
import shlex
import subprocess
import uuid
import httpx
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select, update
from fastapi import HTTPException

from app.models import AnalysisResult, AIBackendConfig
from app.config import settings
from app.logger import logger
from app.cache import cache_get, cache_set

async def get_active_kubeconfig_path(user_id: int) -> Dict[str, Any]:
    """Get the active kubeconfig path from the kubeconfig service"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f"{settings.KUBECONFIG_SERVICE_URL}/kubeconfig/active",
                headers={"X-User-ID": str(user_id)}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting active kubeconfig: {response.text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Failed to get active kubeconfig: {response.text}"
                )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to kubeconfig service: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Kubeconfig service unavailable"
        )

def execute_command(command: str) -> Dict[str, Any]:
    """Execute a shell command and return the result"""
    logger.debug(f"Executing command: {command}")
    try:
        args = shlex.split(command)
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        
        try:
            output = json.loads(result.stdout)
            return output
        except json.JSONDecodeError:
            return {"stdout": result.stdout}
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Command execution failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

async def run_k8sgpt_analysis(
    user_id: int,
    parameters: Dict[str, Any],
    session: Session
) -> AnalysisResult:
    """Run K8sGPT analysis with the given parameters and return results"""
    # Get active kubeconfig
    active_kubeconfig = await get_active_kubeconfig_path(user_id)
    kubeconfig_path = active_kubeconfig["path"]
    cluster_name = active_kubeconfig["cluster_name"]
    
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail="Active kubeconfig file not found on disk")

    # Build k8sgpt analyze command
    command = "k8sgpt analyze"
    
    if parameters.get("backend"):
        command += f" --backend {parameters['backend']}"
    if parameters.get("custom_analysis"):
        command += " --custom-analysis"
    if parameters.get("custom_headers"):
        for header in parameters["custom_headers"]:
            command += f" --custom-headers {header}"
    if parameters.get("explain"):
        command += " --explain"
    if parameters.get("filter_analyzers"):
        for f in parameters["filter_analyzers"]:
            command += f" --filter {f}"
    if parameters.get("interactive"):
        command += " --interactive"
    if parameters.get("language") and parameters["language"] != "english":
        command += f" --language {parameters['language']}"
    if parameters.get("max_concurrency") and parameters["max_concurrency"] != 10:
        command += f" --max-concurrency {parameters['max_concurrency']}"
    if parameters.get("namespace"):
        command += f" --namespace {parameters['namespace']}"
    if parameters.get("no_cache"):
        command += " --no-cache"
    # Always use JSON output for structured data storage
    command += " --output json"
    if parameters.get("selector"):
        command += f" --selector {parameters['selector']}"
    if parameters.get("with_doc"):
        command += " --with-doc"
    
    # Add the active kubeconfig path
    command += f" --kubeconfig {kubeconfig_path}"

    try:
        # Execute the k8sgpt command
        result = execute_command(command)
        
        # Generate a unique ID for this analysis result
        result_id = str(uuid.uuid4())
        
        # Store the result in the database
        analysis_result = AnalysisResult(
            user_id=user_id,
            cluster_name=cluster_name,
            namespace=parameters.get("namespace"),
            result_id=result_id,
            result_json=json.dumps(result),
            parameters=json.dumps(parameters)
        )
        
        session.add(analysis_result)
        session.commit()
        session.refresh(analysis_result)
        
        # Cache the result
        cache_key = f"analysis_result:{result_id}"
        cache_set(user_id, cache_key, {
            "result_id": result_id,
            "result": result,
            "parameters": parameters
        })
        
        return analysis_result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error during k8sgpt analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during analysis: {str(e)}")

async def get_analysis_result(
    user_id: int,
    result_id: str,
    session: Session
) -> Dict[str, Any]:
    """Get a specific analysis result"""
    # Try to get from cache first
    cache_key = f"analysis_result:{result_id}"
    cached_result = cache_get(user_id, cache_key)
    if cached_result:
        return cached_result
    
    # If not in cache, get from database
    analysis_result = session.exec(
        select(AnalysisResult).where(
            AnalysisResult.user_id == user_id,
            AnalysisResult.result_id == result_id
        )
    ).first()
    
    if not analysis_result:
        raise HTTPException(status_code=404, detail=f"Analysis result {result_id} not found")
    
    result = {
        "result_id": analysis_result.result_id,
        "cluster_name": analysis_result.cluster_name,
        "namespace": analysis_result.namespace,
        "result": json.loads(analysis_result.result_json),
        "created_at": analysis_result.created_at,
        "parameters": json.loads(analysis_result.parameters)
    }
    
    # Update cache
    cache_set(user_id, cache_key, result)
    
    return result

async def list_analysis_results(
    user_id: int,
    session: Session,
    limit: int = 10,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List analysis results for a user"""
    analysis_results = session.exec(
        select(AnalysisResult)
        .where(AnalysisResult.user_id == user_id)
        .order_by(AnalysisResult.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    return [
        {
            "result_id": ar.result_id,
            "cluster_name": ar.cluster_name,
            "namespace": ar.namespace,
            "created_at": ar.created_at,
            "parameters": json.loads(ar.parameters)
        }
        for ar in analysis_results
    ]

async def add_ai_backend(
    user_id: int,
    backend_config: Dict[str, Any],
    session: Session
) -> AIBackendConfig:
    """Add or update an AI backend configuration"""
    backend_name = backend_config.pop("backend")
    is_default = backend_config.pop("is_default", False)
    
    # Check if this backend already exists for this user
    existing_backend = session.exec(
        select(AIBackendConfig).where(
            AIBackendConfig.user_id == user_id,
            AIBackendConfig.backend_name == backend_name
        )
    ).first()
    
    if existing_backend:
        # Update existing backend
        existing_backend.config_json = json.dumps(backend_config)
        existing_backend.is_default = is_default
        session.add(existing_backend)
    else:
        # Create new backend
        new_backend = AIBackendConfig(
            user_id=user_id,
            backend_name=backend_name,
            is_default=is_default,
            config_json=json.dumps(backend_config)
        )
        session.add(new_backend)
    
    # If this backend is set as default, update all others to non-default
    if is_default:
        session.exec(
            update(AIBackendConfig)
            .where(
                AIBackendConfig.user_id == user_id,
                AIBackendConfig.backend_name != backend_name
            )
            .values(is_default=False)
        )
    
    session.commit()
    
    # Re-fetch the backend to get updated values
    backend = session.exec(
        select(AIBackendConfig).where(
            AIBackendConfig.user_id == user_id,
            AIBackendConfig.backend_name == backend_name
        )
    ).first()
    
    return backend

async def list_ai_backends(
    user_id: int,
    session: Session
) -> List[Dict[str, Any]]:
    """List AI backends for a user"""
    backends = session.exec(
        select(AIBackendConfig)
        .where(AIBackendConfig.user_id == user_id)
        .order_by(AIBackendConfig.backend_name)
    ).all()
    
    return [
        {
            "id": backend.id,
            "backend_name": backend.backend_name,
            "is_default": backend.is_default,
            "config": json.loads(backend.config_json),
            "created_at": backend.created_at,
            "updated_at": backend.updated_at
        }
        for backend in backends
    ]

async def get_ai_backend(
    user_id: int,
    backend_name: str,
    session: Session
) -> Dict[str, Any]:
    """Get a specific AI backend configuration"""
    backend = session.exec(
        select(AIBackendConfig).where(
            AIBackendConfig.user_id == user_id,
            AIBackendConfig.backend_name == backend_name
        )
    ).first()
    
    if not backend:
        raise HTTPException(status_code=404, detail=f"AI backend {backend_name} not found")
    
    return {
        "id": backend.id,
        "backend_name": backend.backend_name,
        "is_default": backend.is_default,
        "config": json.loads(backend.config_json),
        "created_at": backend.created_at,
        "updated_at": backend.updated_at
    }

async def delete_ai_backend(
    user_id: int,
    backend_name: str,
    session: Session
) -> bool:
    """Delete an AI backend configuration"""
    backend = session.exec(
        select(AIBackendConfig).where(
            AIBackendConfig.user_id == user_id,
            AIBackendConfig.backend_name == backend_name
        )
    ).first()
    
    if not backend:
        raise HTTPException(status_code=404, detail=f"AI backend {backend_name} not found")
    
    session.delete(backend)
    session.commit()
    
    return True

async def set_default_ai_backend(
    user_id: int,
    backend_name: str,
    session: Session
) -> bool:
    """Set a backend as the default for a user"""
    backend = session.exec(
        select(AIBackendConfig).where(
            AIBackendConfig.user_id == user_id,
            AIBackendConfig.backend_name == backend_name
        )
    ).first()
    
    if not backend:
        raise HTTPException(status_code=404, detail=f"AI backend {backend_name} not found")
    
    # Set all backends to non-default
    session.exec(
        update(AIBackendConfig)
        .where(AIBackendConfig.user_id == user_id)
        .values(is_default=False)
    )
    
    # Set this backend as default
    backend.is_default = True
    session.add(backend)
    session.commit()
    
    return True

async def get_available_analyzers(user_id: int) -> List[str]:
    """Get a list of available k8sgpt analyzers"""
    # Get active kubeconfig
    active_kubeconfig = await get_active_kubeconfig_path(user_id)
    kubeconfig_path = active_kubeconfig["path"]
    
    command = f"k8sgpt filters list --kubeconfig {kubeconfig_path}"
    
    try:
        result = execute_command(command)
        if "stdout" in result:
            # Parse stdout to get analyzers list
            analyzers = [line.strip() for line in result["stdout"].split("\n") if line.strip()]
            return analyzers
        return []
    except Exception as e:
        logger.error(f"Error getting analyzers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting analyzers: {str(e)}")