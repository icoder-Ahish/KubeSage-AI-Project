from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, update
from typing import List, Dict, Optional
import os, uuid, json, subprocess, shlex

from app.database import get_session
from app.models import Kubeconf
from app.schemas import (
    KubeconfigResponse, 
    KubeconfigList, 
    MessageResponse, 
    ClusterNamesResponse
)
from app.auth import get_current_user
from app.config import settings
from app.logger import logger

kubeconfig_router = APIRouter()

def execute_command(command: str):
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

def get_active_kubeconfig(session: Session, user_id: int) -> Kubeconf:
    """Get the active kubeconfig for a user"""
    active_kubeconf = session.exec(
        select(Kubeconf).where(
            Kubeconf.user_id == user_id, 
            Kubeconf.active == True
        )
    ).first()
    
    if not active_kubeconf:
        raise HTTPException(status_code=404, detail="No active kubeconfig found")
    
    return active_kubeconf

@kubeconfig_router.post("/upload", response_model=KubeconfigResponse, status_code=201)
async def upload_kubeconfig(
    file: UploadFile = File(...), 
    session: Session = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    try:
        # Generate a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Get cluster name
        command = f"kubectl config view --kubeconfig {file_path} --minify -o jsonpath='{{.clusters[0].name}}'"
        result = execute_command(command)
        cluster_name = result.get("stdout", "").strip()
        
        # Get context name
        command = f"kubectl config view --kubeconfig {file_path} --minify -o jsonpath='{{.contexts[0].name}}'"
        result = execute_command(command)
        context_name = result.get("stdout", "").strip()
        
        # Create a new Kubeconf object
        new_kubeconf = Kubeconf(
            filename=unique_filename,
            original_filename=file.filename,
            user_id=current_user["id"],
            path=file_path,
            active=False,
            cluster_name=cluster_name,
            context_name=context_name
        )
        
        # Add to database
        session.add(new_kubeconf)
        session.commit()
        session.refresh(new_kubeconf)
        
        logger.info(f"User {current_user['id']} uploaded kubeconfig: {unique_filename}")
        return new_kubeconf
    except Exception as e:
            logger.error(f"Error uploading kubeconfig: {str(e)}")
            raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@kubeconfig_router.put("/activate/{filename}")
async def set_active_kubeconfig(
        filename: str, 
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        # Find the kubeconfig to activate
        kubeconf_to_activate = session.exec(
            select(Kubeconf).where(
                Kubeconf.filename == filename,
                Kubeconf.user_id == current_user["id"]
            )
        ).first()
    
        if not kubeconf_to_activate:
            raise HTTPException(status_code=404, detail=f"Kubeconfig '{filename}' not found")

        # Deactivate all kubeconfigs for this user
        session.exec(
            update(Kubeconf)
            .where(Kubeconf.user_id == current_user["id"])
            .values(active=False)
        )

        # Activate the selected kubeconfig
        kubeconf_to_activate.active = True
        session.add(kubeconf_to_activate)
        session.commit()
    
        logger.info(f"User {current_user['id']} activated kubeconfig: {filename}")
        return JSONResponse(content={"message": f"Kubeconfig '{filename}' set as active"}, status_code=200)

@kubeconfig_router.get("/list", response_model=KubeconfigList)
async def list_kubeconfigs(
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        kubeconfigs = session.exec(
            select(Kubeconf)
            .where(Kubeconf.user_id == current_user["id"])
            .order_by(Kubeconf.created_at.desc())
        ).all()
    
        return {"kubeconfigs": kubeconfigs}

@kubeconfig_router.get("/clusters", response_model=ClusterNamesResponse)
async def get_cluster_names(
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        cluster_names = []
        errors = []

        # Query all Kubeconfs entries for the current user
        kubeconfs = session.exec(
            select(Kubeconf).where(Kubeconf.user_id == current_user["id"])
        ).all()

        for kubeconf in kubeconfs:
            if kubeconf.cluster_name:
                cluster_names.append({
                    "filename": kubeconf.filename,
                    "cluster_name": kubeconf.cluster_name,
                    "active": kubeconf.active,
                    "operator_installed": kubeconf.is_operator_installed,
                })
            else:
                # If cluster_name is not available in the database, try to retrieve it
                try:
                    if not os.path.exists(kubeconf.path):
                        errors.append({
                            "filename": kubeconf.filename, 
                            "error": "Kubeconfig file not found on disk"
                        })
                        continue
                    
                    command = f"kubectl config view --kubeconfig {kubeconf.path} --minify -o jsonpath='{{.clusters[0].name}}'"
                    result = execute_command(command)
                    cluster_name = result.get("stdout", "").strip()
                
                    if cluster_name:
                        cluster_names.append({
                            "filename": kubeconf.filename,
                            "cluster_name": cluster_name,
                            "active": kubeconf.active,
                            "operator_installed": kubeconf.is_operator_installed
                        })
                        # Update the database with the retrieved cluster name
                        kubeconf.cluster_name = cluster_name
                        session.add(kubeconf)
                    else:
                        errors.append({
                            "filename": kubeconf.filename, 
                            "error": "Unable to retrieve cluster name"
                        })
                except HTTPException as e:
                    errors.append({
                        "filename": kubeconf.filename, 
                        "error": str(e.detail)
                    })

        # Commit any changes made to the database
        session.commit()

        response: Dict[str, List] = {"cluster_names": cluster_names}
        if errors:
            response["errors"] = errors

        return response

@kubeconfig_router.delete("/remove")
async def remove_kubeconfig(
        filename: str = Query(..., description="Filename of the kubeconfig to remove"),
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        # Check if the file exists in the database and belongs to the current user
        kubeconf = session.exec(
            select(Kubeconf).where(
                Kubeconf.filename == filename,
                Kubeconf.user_id == current_user["id"]
            )
        ).first()
    
        if not kubeconf:
            raise HTTPException(status_code=404, detail=f"Kubeconfig '{filename}' not found or does not belong to you")

        file_path = kubeconf.path
    
        # Check if the file exists on disk
        if not os.path.exists(file_path):
            # If file doesn't exist on disk but exists in DB, we should still remove the DB entry
            session.delete(kubeconf)
            session.commit()
            logger.info(f"User {current_user['id']} removed kubeconfig {filename} from database (file not found)")
            return JSONResponse(content={
                "message": f"Kubeconfig '{filename}' removed from database. File was not found on disk."
            }, status_code=200)
    
        try:
            # Remove the file from disk
            os.remove(file_path)
        
            # Remove the entry from the database
            session.delete(kubeconf)
            session.commit()
        
            logger.info(f"User {current_user['id']} removed kubeconfig {filename}")
            return JSONResponse(content={
                "message": f"Kubeconfig '{filename}' successfully removed from disk and database"
            }, status_code=200)
        except Exception as e:
            # If an error occurs, rollback the database transaction
            session.rollback()
            logger.error(f"Error removing kubeconfig: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error removing kubeconfig: {str(e)}")

@kubeconfig_router.post("/install-operator")
async def install_operator(
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        active_kubeconf = get_active_kubeconfig(session, current_user["id"])
        kubeconfig_path = active_kubeconf.path

        if not os.path.exists(kubeconfig_path):
            raise HTTPException(status_code=404, detail="Active kubeconfig file not found on disk")

        commands = [
            f"helm repo add k8sgpt https://charts.k8sgpt.ai/ --kubeconfig {kubeconfig_path}",
            f"helm repo update --kubeconfig {kubeconfig_path}",
            f"helm install release k8sgpt/k8sgpt-operator -n k8sgpt-operator-system --create-namespace --kubeconfig {kubeconfig_path}"
        ]

        results = []
        success = True
        for command in commands:
            try:
                result = execute_command(command)
                results.append({"command": command, "result": result})
            except HTTPException as e:
                results.append({"command": command, "error": str(e.detail)})
                success = False
                break  # Stop execution if a command fails

        if success:
            active_kubeconf.is_operator_installed = True
            session.add(active_kubeconf)
            session.commit()
            logger.info(f"User {current_user['id']} installed operator on cluster {active_kubeconf.cluster_name}")

        return JSONResponse(
            content={"results": results, "operator_installed": success}, 
            status_code=200
        )

@kubeconfig_router.get("/namespaces")
async def get_namespaces(
        session: Session = Depends(get_session),
        current_user: Dict = Depends(get_current_user)
):
        active_kubeconf = get_active_kubeconfig(session, current_user["id"])
        kubeconfig_path = active_kubeconf.path

        if not os.path.exists(kubeconfig_path):
            raise HTTPException(status_code=404, detail="Active kubeconfig file not found on disk")

        command = f"kubectl get namespaces -o jsonpath='{{.items[*].metadata.name}}' --kubeconfig {kubeconfig_path}"

        try:
            result = execute_command(command)
        
            # Check if result is a dictionary with 'stdout' key
            if isinstance(result, dict) and 'stdout' in result:
                namespaces = result['stdout'].strip().split()
            else:
                # If result is not in the expected format, raise an exception
                raise ValueError("Unexpected result format from execute_command")

            logger.info(f"User {current_user['id']} retrieved namespaces from cluster {active_kubeconf.cluster_name}")
            return JSONResponse(content={"namespaces": namespaces}, status_code=200)
        except HTTPException as he:
            # Re-raise HTTP exceptions
            raise he
        except Exception as e:
            logger.error(f"Error fetching namespaces: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error fetching namespaces: {str(e)}")
