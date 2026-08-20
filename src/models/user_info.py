"""Pydantic models for user info in profile and submissions flows."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    personal_email: EmailStr
    team: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=500)


class SubmissionUserInfo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: EmailStr
    e_transfer_email: EmailStr
    address: str
    team: str
