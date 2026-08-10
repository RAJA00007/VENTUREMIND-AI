from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    account_type: Optional[str] = "personal"
    company: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    email: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    account_type: str
    company_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
