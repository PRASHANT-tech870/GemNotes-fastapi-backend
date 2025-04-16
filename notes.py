from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Notes, BulletPoint, Users
from auth import get_current_user
from datetime import datetime
from pydantic import BaseModel
from google import genai
import re

# Initialize Gemini client
GEMINI_API_KEY = "AIzaSyCMEPSK6GFQiZm48zO5dgE1QaoGYmcfQGw"
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

router = APIRouter(
    prefix="/notes",
    tags=["notes"]
)

# Pydantic models for request/response
class BulletPointBase(BaseModel):
    content: str
    completed: Optional[bool] = False

class BulletPointCreate(BulletPointBase):
    enhance: Optional[bool] = False
    enhancement_type: Optional[str] = "explain"  # explain, example, code

class BulletPointResponse(BulletPointBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class NoteBase(BaseModel):
    title: str

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = None

class NoteResponse(NoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    bullet_points: List[BulletPointResponse] = []
    
    class Config:
        orm_mode = True

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

# Function to format code in the response
def format_code_blocks(text):
    # Check if the text contains code
    if "```" in text:
        return text  # It's already formatted
    
    # Check for common code patterns
    code_patterns = [
        r'(import\s+[\w\.]+)',
        r'(from\s+[\w\.]+\s+import\s+[\w\.\,\s]+)',
        r'(\w+\s*=\s*[\w\(\)\{\}\[\]\'\"\:\,\s]+)',
        r'(def\s+\w+\s*\([^\)]*\)\s*:)',
        r'(class\s+\w+\s*(\([^\)]*\))?\s*:)',
        r'(if\s+[^:]+:)',
        r'(for\s+[^:]+:)',
        r'(while\s+[^:]+:)'
    ]
    
    for pattern in code_patterns:
        if re.search(pattern, text):
            # Wrap the entire text in code block if it looks like code
            return f"```python\n{text}\n```"
    
    return text

# Function to enhance content using Gemini
def enhance_with_gemini(content: str, enhancement_type: str) -> str:
    prompt_map = {
        "explain": f"Explain this in 1-2 simple sentences only: {content}",
        "example": f"Give just 1 short example to understand this better: {content}",
        "code": f"Give only a very short code snippet (if possible) for this, and explain it in 1 sentence max: {content}"
    }
    
    prompt = prompt_map.get(enhancement_type, prompt_map["explain"])
    
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        
        response_text = response.text.strip()
        
        # Format the response appropriately based on the enhancement type
        if enhancement_type == "code":
            response_text = format_code_blocks(response_text)
        
        formatted_response = f"**{content}**\n\n{response_text}"
        return formatted_response
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return content  # Return original content if enhancement fails

# CRUD operations for Notes
@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(note: NoteCreate, user: user_dependency, db: db_dependency):
    db_note = Notes(
        title=note.title,
        user_id=user["id"]
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

@router.get("/", response_model=List[NoteResponse])
async def get_notes(user: user_dependency, db: db_dependency):
    notes = db.query(Notes).filter(Notes.user_id == user["id"]).all()
    return notes

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: int, user: user_dependency, db: db_dependency):
    note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note

@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: int, note_update: NoteUpdate, user: user_dependency, db: db_dependency):
    db_note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if db_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    if note_update.title is not None:
        db_note.title = note_update.title
    
    db_note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_note)
    return db_note

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, user: user_dependency, db: db_dependency):
    db_note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if db_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    db.delete(db_note)
    db.commit()
    return {"detail": "Note deleted successfully"}

# CRUD operations for Bullet Points
@router.post("/{note_id}/bullet-points", response_model=BulletPointResponse, status_code=status.HTTP_201_CREATED)
async def create_bullet_point(note_id: int, bullet_point: BulletPointCreate, user: user_dependency, db: db_dependency):
    # Verify note exists and belongs to user
    note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    content = bullet_point.content
    
    # Check if content should be enhanced with Gemini
    if bullet_point.enhance:
        content = enhance_with_gemini(content, bullet_point.enhancement_type)
    
    db_bullet_point = BulletPoint(
        content=content,
        completed=bullet_point.completed,
        note_id=note_id
    )
    db.add(db_bullet_point)
    db.commit()
    db.refresh(db_bullet_point)
    return db_bullet_point

@router.get("/{note_id}/bullet-points", response_model=List[BulletPointResponse])
async def get_bullet_points(note_id: int, user: user_dependency, db: db_dependency):
    # Verify note exists and belongs to user
    note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    bullet_points = db.query(BulletPoint).filter(BulletPoint.note_id == note_id).all()
    return bullet_points

@router.put("/{note_id}/bullet-points/{bullet_id}", response_model=BulletPointResponse)
async def update_bullet_point(
    note_id: int, 
    bullet_id: int, 
    bullet_point: BulletPointBase, 
    user: user_dependency, 
    db: db_dependency
):
    # Verify note exists and belongs to user
    note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    db_bullet = db.query(BulletPoint).filter(BulletPoint.id == bullet_id, BulletPoint.note_id == note_id).first()
    if db_bullet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bullet point not found")
    
    db_bullet.content = bullet_point.content
    db_bullet.completed = bullet_point.completed
    db_bullet.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_bullet)
    return db_bullet

@router.delete("/{note_id}/bullet-points/{bullet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bullet_point(note_id: int, bullet_id: int, user: user_dependency, db: db_dependency):
    # Verify note exists and belongs to user
    note = db.query(Notes).filter(Notes.id == note_id, Notes.user_id == user["id"]).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    db_bullet = db.query(BulletPoint).filter(BulletPoint.id == bullet_id, BulletPoint.note_id == note_id).first()
    if db_bullet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bullet point not found")
    
    db.delete(db_bullet)
    db.commit()
    return {"detail": "Bullet point deleted successfully"} 