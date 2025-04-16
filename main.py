from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, status
from database import SessionLocal, engine
import auth
import notes
from sqlalchemy.orm import Session
import models
from auth import get_current_user
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

origins = [
    'http://localhost:5173',
    'https://accounts.google.com',
    'https://www.googleapis.com',
    'https://gemnotes.netlify.app'
]

app.add_middleware(CORSMiddleware,
                   allow_origins=origins,
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"],
                   expose_headers=["*"]
                   )



app.include_router(auth.router)
app.include_router(notes.router)
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[models.Users, Depends(get_current_user)]

@app.get("/",status_code=status.HTTP_200_OK)
async def user(user: user_dependency):
    if(user is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"User": user}  