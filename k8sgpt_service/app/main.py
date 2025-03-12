from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import k8sgpt_router
from app.database import create_db_and_tables
from app.config import settings
from app.logger import logger

app = FastAPI(title="KubeSage K8sGPT Operations Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(k8sgpt_router, prefix="/k8sgpt", tags=["K8sGPT"])

@app.on_event("startup")
def on_startup():
    logger.info("Starting K8sGPT Operations Service")
    create_db_and_tables()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        ssl_keyfile=settings.ssl_keyfile,
        ssl_certfile=settings.ssl_certfile
    )
