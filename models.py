from database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    
    # Relationship with notes
    notes = relationship("Notes", back_populates="owner", cascade="all, delete-orphan")

class Notes(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    owner = relationship("Users", back_populates="notes")
    bullet_points = relationship("BulletPoint", back_populates="note", cascade="all, delete-orphan")

class BulletPoint(Base):
    __tablename__ = "bullet_points"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed = Column(Boolean, default=False)
    note_id = Column(Integer, ForeignKey("notes.id"))
    
    # Relationships
    note = relationship("Notes", back_populates="bullet_points")
   
