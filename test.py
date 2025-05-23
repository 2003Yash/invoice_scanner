from typing import List, Optional, Union
from pydantic import BaseModel
from enum import Enum

Enums for type validation,
class OperatorType(str, Enum):
    EQUALS = "="
    CONTAINS = "in"
    NOT_CONTAINS = "not in"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    NOT_EQUALS = "!="

class ConditionType(str, Enum):
    OR = "OR"  # Only OR remains

Condition model,
class Condition(BaseModel):
    type: ConditionType  # Only OR now
    field_key: str
    field_label: str
    operator: OperatorType
    value: Union[str, List[str]]

User entity,
class UserEntity(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

Role entity,
class RoleEntity(BaseModel):
    id: str
    role_id: Optional[str] = None
    role_name: Optional[str] = None

class AssignedTo(BaseModel):
    users: List[UserEntity] = []
    roles: List[RoleEntity] = []

Conditions model (only OR now),
class Conditions(BaseModel):
    OR: List[Condition] = []

Bucket input base model,
class BucketBase(BaseModel):
    solution_object_id: Optional[str] = None  # Newly added field
    bucket_name: str
    is_active: bool = True
    keywords: List[str] = []
    domains: List[str] = []
    assigned_to: AssignedTo

Bucket create model,
class BucketCreate(BucketBase):
    conditions: Conditions

Bucket update model,
class BucketUpdate(BucketBase):
    id: Optional[int] = None
    conditions: Conditions

Bucket response model,
class Bucket(BucketBase):
    bucket_id: str
    conditions: Conditions








------------------------------------------------------------------------------
{
  "solution_object_id": "sol-12345",
  "bucket_name": "Important Leads",
  "is_active": true,
  "keywords": ["sales", "marketing", "leads"],
  "domains": ["example.com", "sales.org"],
  "assigned_to": {
    "users": [
      {
        "id": "user-001",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com"
      },
      {
        "id": "user-002",
        "first_name": "Bob",
        "last_name": "Brown",
        "email": "bob@example.com"
      }
    ],
    "roles": [
      {
        "id": "role-101",
        "role_id": "sales-rep",
        "role_name": "Sales Representative"
      }
    ]
  },
  "conditions": {
    "OR": [
      {
        "type": "OR",
        "field_key": "industry",
        "field_label": "Industry",
        "operator": "in",
        "value": ["Technology", "Healthcare"]
      },
      {
        "type": "OR",
        "field_key": "revenue",
        "field_label": "Annual Revenue",
        "operator": ">",
        "value": "1000000"
      }
    ]
  }
}

