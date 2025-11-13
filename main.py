import os
from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Comic as ComicSchema

app = FastAPI(title="Comics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ComicCreate(ComicSchema):
    pass


class ComicResponse(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    rating: Optional[float] = None
    tags: Optional[List[str]] = None


def serialize_document(doc: dict) -> dict:
    out = doc.copy()
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    # Convert datetimes to isoformat
    for k in ("created_at", "updated_at"):
        if k in out and hasattr(out[k], "isoformat"):
            out[k] = out[k].isoformat()
    return out


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/api/comics", response_model=List[ComicResponse])
def list_comics(q: Optional[str] = Query(None, description="Search by title"),
                genre: Optional[str] = Query(None, description="Filter by genre"),
                limit: int = Query(24, ge=1, le=100, description="Max items to return")):
    """List comics with optional search and genre filters. If database is empty, seed a few examples."""
    if db is None:
        # Provide graceful fallback demo data if DB not configured
        sample = _demo_comics()
        return [ComicResponse(**c).model_dump() for c in sample[:limit]]

    # Seed if empty
    try:
        count = db["comic"].count_documents({})
        if count == 0:
            for c in _demo_comics():
                create_document("comic", c)
    except Exception:
        # If any error, continue without seeding
        pass

    filt: dict[str, Any] = {}
    if q:
        # Simple title regex search
        filt["title"] = {"$regex": q, "$options": "i"}
    if genre:
        filt["genre"] = genre

    docs = get_documents("comic", filt, limit)
    return [ComicResponse(**serialize_document(d)).model_dump() for d in docs]


@app.post("/api/comics", response_model=dict)
def create_comic(payload: ComicCreate):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    new_id = create_document("comic", payload)
    return {"id": new_id}


@app.get("/api/comics/{comic_id}", response_model=ComicResponse)
def get_comic(comic_id: str):
    if db is None:
        # fallback to demo search
        for c in _demo_comics():
            if c.get("id") == comic_id:
                return ComicResponse(**c)
        raise HTTPException(status_code=404, detail="Comic not found")
    try:
        doc = db["comic"].find_one({"_id": ObjectId(comic_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Comic not found")
        return ComicResponse(**serialize_document(doc))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid comic id")


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


def _demo_comics() -> List[dict]:
    return [
        {
            "id": "demo-1",
            "title": "Nova City: Neon Nights",
            "author": "A. Sterling",
            "genre": "Sci-Fi",
            "description": "A rogue courier races through a glowing mega-city to stop a sentient virus.",
            "cover_url": "https://images.unsplash.com/photo-1534088568595-a066f410bcda?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.8,
            "tags": ["cyberpunk", "action", "future"]
        },
        {
            "id": "demo-2",
            "title": "Arcane Academy",
            "author": "M. Kato",
            "genre": "Fantasy",
            "description": "A misfit mage uncovers a conspiracy at a floating academy of spells.",
            "cover_url": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.6,
            "tags": ["magic", "school", "adventure"]
        },
        {
            "id": "demo-3",
            "title": "Starlight Rangers",
            "author": "J. Vega",
            "genre": "Adventure",
            "description": "Five unlikely heroes chart the unknown between galaxies.",
            "cover_url": "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.7,
            "tags": ["space", "team", "epic"]
        },
        {
            "id": "demo-4",
            "title": "Crimson Streets",
            "author": "L. Noir",
            "genre": "Noir",
            "description": "A masked detective hunts the truth in rain-soaked alleys.",
            "cover_url": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.4,
            "tags": ["mystery", "crime", "vigilante"]
        }
    ]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
