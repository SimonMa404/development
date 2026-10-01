from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.layers import router as layers_router
from app.api.raster import router as raster_router
from app.api.vector import router as vector_router
from app.api.analysis import router as analysis_router
from app.core.config import settings

app = FastAPI(
    title="Urban Climate Tool API",
    version="0.1.0",
    description="Backend for climate adaptation geospatial analysis.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(layers_router, prefix="/api")
app.include_router(raster_router, prefix="/api")
app.include_router(vector_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Urban Climate Tool API"}
