from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Statuses ────────────────────────────────────────────────
class StatusBase(BaseModel):
    name: str
    description: Optional[str] = None

class StatusCreate(StatusBase): pass

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

class ContactCreate(ContactBase): pass

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

class LocationCreate(LocationBase): pass

class LocationOut(LocationBase):
    location_id:              int
    placeholder_container_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ── Containers ───────────────────────────────────────────────
class ContainerBase(BaseModel):
    category:       Optional[str]   = None
    container_type: Optional[str]   = None
    short_name:     str
    location_id:    Optional[int]   = None
    weight_kg:      Optional[float] = None
    width_cm:       Optional[float] = None
    depth_cm:       Optional[float] = None
    height_cm:      Optional[float] = None
    note:           Optional[str]   = None

class ContainerCreate(ContainerBase): pass

class ContainerOut(ContainerBase):
    container_id: int
    model_config  = ConfigDict(from_attributes=True)

class ContainerWithFixtures(ContainerOut):
    fixtures: List["FixtureOut"] = []


# ── Fixture Models ───────────────────────────────────────────
class FixtureModelBase(BaseModel):
    model_name:   str
    category:     Optional[str]   = None
    subcategory:  Optional[str]   = None
    manufacturer: Optional[str]   = None
    model:        Optional[str]   = None
    weight_kg:    Optional[float] = None
    width_cm:     Optional[float] = None
    depth_cm:     Optional[float] = None
    height_cm:    Optional[float] = None
    power_w:      Optional[float] = None
    description:  Optional[str]   = None
    preview_image:Optional[str]   = None

class FixtureModelCreate(FixtureModelBase): pass

class FixtureModelOut(FixtureModelBase):
    model_id:   int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Fixtures ─────────────────────────────────────────────────
class FixtureBase(BaseModel):
    short_name:   str
    model_id:     Optional[int] = None
    container_id: Optional[int] = None
    status_id:    Optional[int] = None
    note:         Optional[str] = None

class FixtureCreate(FixtureBase):
    quantity: int = 1  # convenience: creates N rows

class FixtureOut(FixtureBase):
    fixture_id: int
    # Flattened model fields for convenience (populated via joined query)
    model_name:   Optional[str]   = None
    category:     Optional[str]   = None
    subcategory:  Optional[str]   = None
    manufacturer: Optional[str]   = None
    model:        Optional[str]   = None
    weight_kg:    Optional[float] = None
    power_w:      Optional[float] = None
    model_config  = ConfigDict(from_attributes=True)

class FixtureWithModel(FixtureOut):
    fixture_model: Optional[FixtureModelOut] = None


# ── File attachments ─────────────────────────────────────────
class FileOut(BaseModel):
    file_id:       int
    filename:      str
    original_name: str
    mime_type:     Optional[str] = None
    size_bytes:    Optional[int] = None
    uploaded_at:   datetime
    note:          Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ── Loads ────────────────────────────────────────────────────
class LoadCreate(BaseModel):
    origin_location_id:      int
    destination_location_id: int
    event_id:                Optional[int] = None
    container_ids:           List[int]
    deselected_fixture_ids:  List[int] = []
    note:                    Optional[str] = None

class LoadOut(BaseModel):
    load_id:                 int
    created_at:              datetime
    origin_location_id:      Optional[int] = None
    destination_location_id: Optional[int] = None
    event_id:                Optional[int] = None
    status:                  str
    note:                    Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ── Load Manifest ────────────────────────────────────────────
class ManifestFixture(BaseModel):
    fixture_id:  int
    model_name:  str
    weight_kg:   Optional[float] = None
    included:    bool

class ManifestContainer(BaseModel):
    container_id: int
    short_name:   str
    tare_kg:      Optional[float] = None
    volume_m3:    Optional[float] = None
    fixtures:     List[ManifestFixture]

class LoadManifest(BaseModel):
    load_id:         int
    created_at:      datetime
    origin:          str
    destination:     str
    containers:      List[ManifestContainer]
    total_weight_kg: float
    total_volume_m3: float


# ── Status change ────────────────────────────────────────────
class StatusChangeRequest(BaseModel):
    entity_type:   str
    entity_id:     int
    new_status_id: int
    note:          Optional[str] = None
