from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.media import router as media_router
from app.routes.editorial import router as editorial_router
from app.routes.review import router as review_router
from app.routes.export import router as export_router
from app.routes.correction import router as correction_router

app = FastAPI(
    title="Midad AI Editorial Studio",
    description="Human-centered AI tools for educational media production.",
    version="0.6.0"
)

app.include_router(media_router)
app.include_router(editorial_router)
app.include_router(review_router)
app.include_router(export_router)
app.include_router(correction_router)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


@app.get("/")
def home():
    return FileResponse("templates/index.html")


@app.get("/api/health")
def health():
    return {"status": "healthy"}
