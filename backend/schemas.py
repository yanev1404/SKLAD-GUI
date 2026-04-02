from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Statuses ────────────────────────────────────────────────
class StatusBase(BaseModel):
    name: str
    description: Optional[str] = None

class StatusCreate(StatusBase):
    pass

class StatusOut(StatusBase):
    status_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Contacts ────────────────────────────────────────────────
class ContactBase(BaseModel):
    company:    Optional[str] = None
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    phone:      Optional[str] = None
    email:      Optional[str] = None
    note:       Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactOut(ContactBase):
    contact_id: int
    model_config = ConfigDict(from_attributes=True)


# ── Locations ───────────────────────────────────────────────
class LocationBase(BaseModel):
    name:       str
    type:       Optional[str] = None
    short_name: str
    address:    Optional[str] = None
    city:       Optional[str] = None
    contact_id: Optional[int] = None
    note:       Optional[str] = None

class LocationCreate(LocationBase):
    pass

class LocationOut(LocationBase):
    location_id:              int
    placeholder_container_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ── Containers ──────────────────────────────────────────────
class ContainerBase(BaseModel):
    category:       Optional[str]   = None
    container_type: Optional[str]   = None
    short_name:     str
    location_id:    Optional[int]   = None
    weight_kg:      Optional[float] = None
    width_cm:       Optional[float] = None
    depth_cm:       Optional[float] = None
    height_cm:      Optional[float] = None
    status_id:      Optional[int]   = None
    note:           Optional[str]   = None

class ContainerCreate(ContainerBase):
    pass

class ContainerOut(ContainerBase):
    container_id: int
    model_config  = ConfigDict(from_attributes=True)

class ContainerWithFixtures(ContainerOut):
    fixtures: List["FixtureOut"] = []


# ── Fixtures ────────────────────────────────────────────────
class FixtureBase(BaseModel):
    category:     Optional[str]   = None
    subcategory:  Optional[str]   = None
    short_name:   str
    quantity:     int             = 1
    manufacturer: Optional[str]   = None
    model:        Optional[str]   = None
    weight_kg:    Optional[float] = None
    power_w:      Optional[float] = None
    container_id: Optional[int]   = None
    status_id:    Optional[int]   = None
    note:         Optional[str]   = None

class FixtureCreate(FixtureBase):
    pass

class FixtureOut(FixtureBase):
    fixture_id: int
    model_config = ConfigDict(from_attributes=True)


# ── Loads ────────────────────────────────────────────────────
class LoadFixtureIn(BaseModel):
    fixture_id: int
    included:   bool = True

class LoadContainerIn(BaseModel):
    container_id: int

class LoadCreate(BaseModel):
    origin_location_id:      int
    destination_location_id: int
    container_ids:           List[int]
    deselected_fixture_ids:  List[int] = []   # fixtures to leave behind
    note:                    Optional[str] = None

class LoadOut(BaseModel):
    load_id:                 int
    created_at:              datetime
    origin_location_id:      Optional[int]
    destination_location_id: Optional[int]
    status:                  str
    note:                    Optional[str]
    model_config = ConfigDict(from_attributes=True)


# ── Load Manifest (report) ───────────────────────────────────
class ManifestFixture(BaseModel):
    fixture_id:   int
    short_name:   str
    quantity:     int
    weight_kg:    Optional[float]
    included:     bool

class ManifestContainer(BaseModel):
    container_id: int
    short_name:   str
    tare_kg:      Optional[float]
    volume_m3:    Optional[float]
    fixtures:     List[ManifestFixture]

class LoadManifest(BaseModel):
    load_id:          int
    created_at:       datetime
    origin:           str
    destination:      str
    containers:       List[ManifestContainer]
    total_weight_kg:  float
    total_volume_m3:  float


# ── Status change (manual) ───────────────────────────────────
class StatusChangeRequest(BaseModel):
    entity_type: str   # 'fixture' or 'container'
    entity_id:   int
    new_status_id: int
    note:        Optional[str] = None
