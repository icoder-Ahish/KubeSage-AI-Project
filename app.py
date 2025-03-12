from fastapi import FastAPI, HTTPException, Query, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select, update, Index
from typing import Annotated, List, Dict
import subprocess
import shlex
from fastapi import File, UploadFile
from fastapi.responses import JSONResponse
import os, json
import uuid, ssl
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Schema
class Kubeconfs(SQLModel, table=True):

    __table_args__ = {'extend_existing': True}

    id: int | None = Field(default=None, primary_key=True)

    filename: str = Field(index=True)

    active: bool = Field(default=False, index=True)

    path: str | None = Field(default=None, index=True)

    cluster_name: str | None = Field(default=None, index=True)

    is_operator_installed: bool = Field(default=False, index=True)


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]



app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# CORS configuration to allow requests from your frontend (e.g., localhost:8005)
# origins = [
# "https://localhost:8005",
# "http://localhost:8005",
# # Add more allowed origins if necessary
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    #allow_origins=origins,  # Allow requests from specific origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
# Directory to store uploaded kubeconfig files
UPLOAD_DIR = "uploaded_kubeconfigs"

# Ensure the upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

def execute_command(command: str):
    print(command)
    try:
        args = shlex.split(command)
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        
        # Try to parse the output as JSON
        try:
            output = json.loads(result.stdout)
            return output
        except json.JSONDecodeError:
            # If parsing fails, return the raw output
            return {"stdout": result.stdout}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Command execution failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

def get_active_kubeconfig(session: Session) -> Kubeconfs:
    active_kubeconf = session.exec(select(Kubeconfs).where(Kubeconfs.active == True)).first()
    if not active_kubeconf:
        raise HTTPException(status_code=404, detail="No active kubeconfig found")
    return active_kubeconf


@app.put("/activate-kubeconfig/{filename}")
async def set_active_kubeconfig(filename: str, session: SessionDep):
    # Find the kubeconfig to activate
    kubeconf_to_activate = session.exec(select(Kubeconfs).where(Kubeconfs.filename == filename)).first()
    if not kubeconf_to_activate:
        raise HTTPException(status_code=404, detail=f"Kubeconfig '{filename}' not found")

    # Deactivate all kubeconfigs
    session.exec(update(Kubeconfs).values(active=False))

    # Activate the selected kubeconfig
    kubeconf_to_activate.active = True
    session.add(kubeconf_to_activate)
    session.commit()

    return JSONResponse(content={"message": f"Kubeconfig '{filename}' set as active"}, status_code=200)


@app.post("/upload_kubeconfig")
async def upload_kubeconfig(session: SessionDep, file: UploadFile = File(...)) -> Kubeconfs:
    try:
        # Generate a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Get cluster name
        command = f"kubectl config view --kubeconfig {file_path} --minify -o jsonpath='{{.clusters[0].name}}'"
        result = execute_command(command)
        cluster_name = result.get("stdout", "").strip()
        
        # Create a new Kubeconfs object
        new_kubeconf = Kubeconfs(
            filename=unique_filename,
            path=file_path,
            active=False,
            cluster_name=cluster_name
        )
        
        # Add to database
        session.add(new_kubeconf)
        session.commit()
        session.refresh(new_kubeconf)

        return new_kubeconf
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/install-operator")
async def install_operator(session: SessionDep):
    active_kubeconf = get_active_kubeconfig(session)
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

    return JSONResponse(content={"results": results, "operator_installed": success}, status_code=200)


@app.get("/get-namespaces")
async def get_namespaces(session: SessionDep):
    active_kubeconf = get_active_kubeconfig(session)
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

        return JSONResponse(content={"namespaces": namespaces}, status_code=200)
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching namespaces: {str(e)}")



@app.get("/get-cluster-names")
async def get_cluster_names(session: SessionDep):
    cluster_names = []
    errors = []

    # Query all Kubeconfs entries from the database
    kubeconfs = session.exec(select(Kubeconfs)).all()

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
            command = f"kubectl config view --kubeconfig {kubeconf.path} --minify -o jsonpath='{{.clusters[0].name}}'"
            try:
                result = execute_command(command)
                cluster_name = result.get("stdout", "").strip()
                
                if cluster_name:
                    cluster_names.append({
                        "filename": kubeconf.filename,
                        "cluster_name": cluster_name,
                        "active": kubeconf.active
                    })
                    # Update the database with the retrieved cluster name
                    kubeconf.cluster_name = cluster_name
                    session.add(kubeconf)
                else:
                    errors.append({"filename": kubeconf.filename, "error": "Unable to retrieve cluster name"})
            except HTTPException as e:
                errors.append({"filename": kubeconf.filename, "error": str(e.detail)})

    # Commit any changes made to the database
    session.commit()

    response: Dict[str, List] = {"cluster_names": cluster_names}
    if errors:
        response["errors"] = errors

    return JSONResponse(content=response, status_code=200)


@app.delete("/remove-kubeconfig")
async def remove_kubeconfig(
    session: SessionDep,
    filename: str = Query(..., description="Filename of the kubeconfig to remove")
):
    # Check if the file exists in the database
    kubeconf = session.exec(select(Kubeconfs).where(Kubeconfs.filename == filename)).first()
    if not kubeconf:
        raise HTTPException(status_code=404, detail=f"Kubeconfig '{filename}' not found in database")

    file_path = kubeconf.path
    
    # Check if the file exists on disk
    if not os.path.exists(file_path):
        # If file doesn't exist on disk but exists in DB, we should still remove the DB entry
        session.delete(kubeconf)
        session.commit()
        return JSONResponse(content={
            "message": f"Kubeconfig '{filename}' removed from database. File was not found on disk."
        }, status_code=200)
    
    try:
        # Remove the file from disk
        os.remove(file_path)
        
        # Remove the entry from the database
        session.delete(kubeconf)
        session.commit()
        
        return JSONResponse(content={
            "message": f"Kubeconfig '{filename}' successfully removed from disk and database"
        }, status_code=200)
    except Exception as e:
        # If an error occurs, rollback the database transaction
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing kubeconfig: {str(e)}")

@app.get("/analyze")
async def analyze(
    session: SessionDep,
    anonymize: bool = Query(False, description="Anonymize data before sending it to the AI backend"),
    backend: str = Query(None, description="Backend AI provider"),
    custom_analysis: bool = Query(False, description="Enable custom analyzers"),
    custom_headers: List[str] = Query(None, description="Custom Headers, <key>:<value>"),
    explain: bool = Query(False, description="Explain the problem"),
    filter: List[str] = Query(None, description="Filter for these analyzers"),
    interactive: bool = Query(False, description="Enable interactive mode"),
    language: str = Query("english", description="Language to use for AI"),
    max_concurrency: int = Query(10, description="Maximum number of concurrent requests"),
    namespace: str = Query(None, description="Namespace to analyze"),
    no_cache: bool = Query(False, description="Do not use cached data"),
    output: str = Query("text", description="Output format (text, json)"),
    selector: str = Query(None, description="Label selector"),
    with_doc: bool = Query(False, description="Give me the official documentation of the involved field"),
    config: str = Query(None, description="Default config file"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    # Get the active kubeconfig
    active_kubeconf = get_active_kubeconfig(session)
    kubeconfig_path = active_kubeconf.path

    command = "k8sgpt analyze"
    
    if anonymize:
        command += " --anonymize"
    if backend:
        command += f" --backend {backend}"
    if custom_analysis:
        command += " --custom-analysis"
    if custom_headers:
        for header in custom_headers:
            command += f" --custom-headers {header}"
    if explain:
        command += " --explain"
    if filter:
        for f in filter:
            command += f" --filter {f}"
    if interactive:
        command += " --interactive"
    if language != "english":
        command += f" --language {language}"
    if max_concurrency != 10:
        command += f" --max-concurrency {max_concurrency}"
    if namespace:
        command += f" --namespace {namespace}"
    if no_cache:
        command += " --no-cache"
    if output != "text":
        command += f" --output {output}"
    if selector:
        command += f" --selector {selector}"
    if with_doc:
        command += " --with-doc"
    if config:
        command += f" --config {config}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    # Add the active kubeconfig path
    command += f" --kubeconfig {kubeconfig_path}"

    try:
        result = execute_command(command + " --output=json")
        return JSONResponse(content=result, status_code=200)
    except HTTPException as e:
        return JSONResponse(content={"error": str(e.detail)}, status_code=e.status_code)


@app.post("/auth/add")
async def auth_add(
    backend: str = Query("openai", description="Backend AI provider"),
    baseurl: str = Query(None, description="URL AI provider"),
    compartmentId: str = Query(None, description="Compartment ID for generative AI model (only for oci backend)"),
    endpointname: str = Query(None, description="Endpoint Name (only for amazonbedrock, amazonsagemaker backends)"),
    engine: str = Query(None, description="Azure AI deployment name (only for azureopenai backend)"),
    maxtokens: int = Query(2048, description="Specify a maximum output length"),
    model: str = Query("gpt-3.5-turbo", description="Backend AI model"),
    organizationId: str = Query(None, description="OpenAI or AzureOpenAI Organization ID"),
    password: str = Query(None, description="Backend AI password"),
    providerId: str = Query(None, description="Provider specific ID for e.g. project (only for googlevertexai backend)"),
    providerRegion: str = Query(None, description="Provider Region name (only for amazonbedrock, googlevertexai backend)"),
    temperature: float = Query(0.7, description="The sampling temperature"),
    topk: int = Query(50, description="Sampling Cutoff"),
    topp: float = Query(0.5, description="Probability Cutoff"),
    config: str = Query(None, description="Default config file"),
    kubeconfig: str = Query(None, description="Path to a kubeconfig"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    command = f"k8sgpt auth add --backend {backend}"
    
    if baseurl:
        command += f" --baseurl {baseurl}"
    if compartmentId:
        command += f" --compartmentId {compartmentId}"
    if endpointname:
        command += f" --endpointname {endpointname}"
    if engine:
        command += f" --engine {engine}"
    if maxtokens != 2048:
        command += f" --maxtokens {maxtokens}"
    if model != "gpt-3.5-turbo":
        command += f" --model {model}"
    if organizationId:
        command += f" --organizationId {organizationId}"
    if password:
        command += f" --password {password}"
    if providerId:
        command += f" --providerId {providerId}"
    if providerRegion:
        command += f" --providerRegion {providerRegion}"
    if temperature != 0.7:
        command += f" --temperature {temperature}"
    if topk != 50:
        command += f" --topk {topk}"
    if topp != 0.5:
        command += f" --topp {topp}"
    if config:
        command += f" --config {config}"
    if kubeconfig:
        command += f" --kubeconfig {kubeconfig}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    return execute_command(command)

@app.post("/auth/default")
async def auth_default(
    provider: str = Query(..., description="The name of the provider to set as default"),
    config: str = Query(None, description="Default config file"),
    kubeconfig: str = Query(None, description="Path to a kubeconfig"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    command = f"k8sgpt auth default --provider {provider}"
    
    if config:
        command += f" --config {config}"
    if kubeconfig:
        command += f" --kubeconfig {kubeconfig}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    return execute_command(command)

@app.get("/auth/list")
async def auth_list(
    details: bool = Query(False, description="Print active provider configuration details"),
    config: str = Query(None, description="Default config file"),
    kubeconfig: str = Query(None, description="Path to a kubeconfig"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    command = "k8sgpt auth list"
    
    if details:
        command += " --details"
    if config:
        command += f" --config {config}"
    if kubeconfig:
        command += f" --kubeconfig {kubeconfig}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    return execute_command(command)



@app.delete("/auth/remove")
async def auth_remove(
    backends: List[str] = Query(..., description="Backend AI providers to remove"),
    config: str = Query(None, description="Default config file"),
    kubeconfig: str = Query(None, description="Path to a kubeconfig"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    backends_str = ",".join(backends)
    command = f"k8sgpt auth remove --backends {backends_str}"
    
    if config:
        command += f" --config {config}"
    if kubeconfig:
        command += f" --kubeconfig {kubeconfig}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    return execute_command(command)

@app.put("/auth/update")
async def auth_update(
    backend: str = Query(..., description="Update backend AI provider"),
    baseurl: str = Query(None, description="Update URL AI provider"),
    engine: str = Query(None, description="Update Azure AI deployment name"),
    model: str = Query(None, description="Update backend AI model"),
    organizationId: str = Query(None, description="Update OpenAI or Azure organization Id"),
    password: str = Query(None, description="Update backend AI password"),
    temperature: float = Query(None, description="The sampling temperature"),
    config: str = Query(None, description="Default config file"),
    kubeconfig: str = Query(None, description="Path to a kubeconfig"),
    kubecontext: str = Query(None, description="Kubernetes context to use")
):
    command = f"k8sgpt auth update --backend {backend}"
    
    if baseurl:
        command += f" --baseurl {baseurl}"
    if engine:
        command += f" --engine {engine}"
    if model:
        command += f" --model {model}"
    if organizationId:
        command += f" --organizationId {organizationId}"
    if password:
        command += f" --password {password}"
    if temperature is not None:
        command += f" --temperature {temperature}"
    if config:
        command += f" --config {config}"
    if kubeconfig:
        command += f" --kubeconfig {kubeconfig}"
    if kubecontext:
        command += f" --kubecontext {kubecontext}"
    
    return execute_command(command)


@app.get("/cache/{action}")
async def cache(action: str):
    return execute_command(f"k8sgpt cache {action}")

@app.get("/filters/{action}")
async def filters(action: str):
    return execute_command(f"k8sgpt filters {action}")

@app.get("/generate/{backend}")
async def generate(backend: str):
    return execute_command(f"k8sgpt generate {backend}")

@app.get("/integration/{action}")
async def integration(action: str):
    return execute_command(f"k8sgpt integration {action}")

@app.get("/serve")
async def serve():
    return execute_command("k8sgpt serve")

@app.get("/version")
async def version():
    return execute_command("k8sgpt version")

if __name__ == '__main__':
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )