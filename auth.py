from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status,APIRouter
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from database import SessionLocal
from models import Users
from sqlalchemy.orm import Session
from starlette import status
from jose import JWTError, jwt
from pydantic import BaseModel
import uuid

import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests



router = APIRouter(
    prefix="/auth",
    tags=["auth"]   
)

SECRET_KEY = "a1b2c3d4e5f6g7h8feafiueafuafe7q6378qn4u3qr8q3nfqeiuhf98huo23fi9j0k"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 100

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")

class CreateUserRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    
class GoogleAuthRequest(BaseModel):
    token: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def authenticate_user(username: str, password: str, db  ):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    create_user_model = Users(
        username=create_user_request.username,
        hashed_password=bcrypt_context.hash(create_user_request.password)
    )

    db.add(create_user_model)
    db.commit()


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm,Depends()],
                                 db:db_dependency):
    
    user = authenticate_user(form_data.username, form_data.password,db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.username,user.id,timedelta(minutes=20))

    return {"access_token": token, "token_type": "bearer"}


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id}
    expires = datetime.now() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str,Depends(oauth2_bearer)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        if username is None or user_id is None:
            raise credentials_exception
        return {"username": username, "id": user_id}
    except JWTError:
        raise credentials_exception
    

@router.post("/google", response_model=Token)
async def google_login(google_data: GoogleAuthRequest, db: db_dependency):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            google_data.token, google_requests.Request(), 
            "219445210127-m2l1od9935os0qkugrlo2afq9nf2ene2.apps.googleusercontent.com")  # Same client ID as frontend
        
        # Extract user info from token
        email = idinfo['email']
        
        # Check if user exists
        user = db.query(Users).filter(Users.username == email).first()
        
        # If user doesn't exist, create one
        if not user:
            user = Users(
                username=email,
                hashed_password=bcrypt_context.hash(str(uuid.uuid4()))  # Random secure password
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Generate JWT token for the user
        token = create_access_token(user.username, user.id, timedelta(minutes=20))
        
        return {"access_token": token, "token_type": "bearer"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/google-signup")
async def google_signup(google_data: GoogleAuthRequest, db: db_dependency):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            google_data.token, google_requests.Request(), 
            "219445210127-m2l1od9935os0qkugrlo2afq9nf2ene2.apps.googleusercontent.com")  # Same client ID as frontend
        
        # Extract user info from token
        email = idinfo['email']
        
        # Check if user already exists
        existing_user = db.query(Users).filter(Users.username == email).first()
        if existing_user:
            return {"message": "User already exists. Please login."}
        
        # Create new user
        new_user = Users(
            username=email,
            hashed_password=bcrypt_context.hash(str(uuid.uuid4()))  # Random secure password
        )
        db.add(new_user)
        db.commit()
        
        return {"message": "User created successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process Google signup: {str(e)}",
        )
