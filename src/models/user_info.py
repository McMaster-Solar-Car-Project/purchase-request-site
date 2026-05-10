"""Pydantic models for user info in profile and submissions flows."""

from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: EmailStr
    personal_email: EmailStr
    team: str
    address: str
    current_password: str = ""
    new_password: str = ""
    confirm_password: str = ""


class SubmissionUserInfo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: EmailStr
    e_transfer_email: EmailStr
    address: str
    team: str
    signature: str
