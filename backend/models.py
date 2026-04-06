from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean,
    ForeignKey, TIMESTAMP, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Status(Base):
    __tablename__ = "statuses"
    status_id   = Column(Integer, primary_key=True)
    name        = Column(String(64), nullable=False, unique=True)
    description = Column(Text)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"
    contact_id = Column(Integer, primary_key=True)
    company    = Column(String(128))
    first_name = Column(String(64))
    last_name  = Column(String(64))
    phone      = Column(String(32))
    email      = Column(String(128))
    note       = Column(Text)
    locations  = relationship("Location", back_populates="contact")


class Location(Base):
    __tablename__ = "locations"
    location_id              = Column(Integer, primary_key=True)
    name                     = Column(String(128), nullable=False)
    type                     = Column(String(64))
    short_name               = Column(String(32), nullable=False, unique=True)
    address                  = Column(String(255))
    city                     = Column(String(64))
    contact_id               = Column(Integer, ForeignKey("contacts.contact_id", ondelete="SET NULL"))
    placeholder_container_id = Column(Integer, ForeignKey("containers.container_id", ondelete="SET NULL"))
    note                     = Column(Text)

    contact     = relationship("Contact", back_populates="locations")
    containers  = relationship("Container", back_populates="location",
                               foreign_keys="Container.location_id")
    placeholder = relationship("Container", foreign_keys=[placeholder_container_id])


class Container(Base):
    __tablename__ = "containers"
    container_id   = Column(Integer, primary_key=True)
    category       = Column(String(64))
    container_type = Column(String(64))
    short_name     = Column(String(64), nullable=False)
    location_id    = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    weight_kg      = Column(Numeric(8, 2))
    width_cm       = Column(Numeric(8, 2))
    depth_cm       = Column(Numeric(8, 2))
    height_cm      = Column(Numeric(8, 2))
    note           = Column(Text)

    location = relationship("Location", back_populates="containers",
                            foreign_keys=[location_id])
    fixtures = relationship("Fixture", back_populates="container")


class FixtureModel(Base):
    """Model/product specification — shared across many fixture units."""
    __tablename__ = "models"
    model_id      = Column(Integer, primary_key=True)
    model_name    = Column(String(128), nullable=False)
    category      = Column(String(64))
    subcategory   = Column(String(64))
    manufacturer  = Column(String(128))
    model         = Column(String(128))
    weight_kg     = Column(Numeric(8, 2))
    width_cm      = Column(Numeric(8, 2))
    depth_cm      = Column(Numeric(8, 2))
    height_cm     = Column(Numeric(8, 2))
    power_w       = Column(Numeric(8, 2))
    description   = Column(Text)
    preview_image = Column(String(255))   # filename in db/images/
    created_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())

    fixtures = relationship("Fixture", back_populates="fixture_model")
    files    = relationship("ModelFile", back_populates="model", cascade="all, delete-orphan")


class Fixture(Base):
    __tablename__ = "fixtures"
    fixture_id   = Column(Integer, primary_key=True)
    short_name   = Column(String(128), nullable=False)   # display/grouping name, independent of model
    model_id     = Column(Integer, ForeignKey("models.model_id", ondelete="SET NULL"))
    container_id = Column(Integer, ForeignKey("containers.container_id", ondelete="SET NULL"))
    status_id    = Column(Integer, ForeignKey("statuses.status_id",   ondelete="SET NULL"))
    note         = Column(Text)   # per-unit notes e.g. serial numbers

    fixture_model = relationship("FixtureModel", back_populates="fixtures")
    container     = relationship("Container",    back_populates="fixtures")
    status        = relationship("Status")
    files         = relationship("FixtureFile",  back_populates="fixture", cascade="all, delete-orphan")


class ModelFile(Base):
    __tablename__ = "model_files"
    file_id       = Column(Integer, primary_key=True)
    model_id      = Column(Integer, ForeignKey("models.model_id", ondelete="CASCADE"), nullable=False)
    filename      = Column(String(255), nullable=False)   # stored name (UUID-based)
    original_name = Column(String(255), nullable=False)   # original upload name
    mime_type     = Column(String(64))
    size_bytes    = Column(Integer)
    uploaded_at   = Column(TIMESTAMP(timezone=True), server_default=func.now())
    note          = Column(Text)

    model = relationship("FixtureModel", back_populates="files")


class FixtureFile(Base):
    __tablename__ = "fixture_files"
    file_id       = Column(Integer, primary_key=True)
    fixture_id    = Column(Integer, ForeignKey("fixtures.fixture_id", ondelete="CASCADE"), nullable=False)
    filename      = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type     = Column(String(64))
    size_bytes    = Column(Integer)
    uploaded_at   = Column(TIMESTAMP(timezone=True), server_default=func.now())
    note          = Column(Text)

    fixture = relationship("Fixture", back_populates="files")


class Event(Base):
    __tablename__ = "events"
    event_id    = Column(Integer, primary_key=True)
    short_name  = Column(String(128), nullable=False)
    event_type  = Column(String(64))
    location_id = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    contact_id  = Column(Integer, ForeignKey("contacts.contact_id",   ondelete="SET NULL"))
    start_date  = Column(TIMESTAMP(timezone=True))
    end_date    = Column(TIMESTAMP(timezone=True))
    description = Column(Text)

    location = relationship("Location", foreign_keys=[location_id])
    contact  = relationship("Contact",  foreign_keys=[contact_id])


class Load(Base):
    __tablename__ = "loads"
    load_id                 = Column(Integer, primary_key=True)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    origin_location_id      = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    destination_location_id = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    status                  = Column(String(32), nullable=False, default="completed")
    event_id                = Column(Integer, ForeignKey("events.event_id", ondelete="SET NULL"))
    event_activated         = Column(Boolean, nullable=False, default=False)
    event_ended             = Column(Boolean, nullable=False, default=False)
    note                    = Column(Text)

    origin      = relationship("Location", foreign_keys=[origin_location_id])
    destination = relationship("Location", foreign_keys=[destination_location_id])
    event       = relationship("Event",    foreign_keys=[event_id])
    containers  = relationship("LoadContainer", back_populates="load", cascade="all, delete-orphan")
    fixtures    = relationship("LoadFixture",   back_populates="load", cascade="all, delete-orphan")
    log_entries = relationship("LoadLog",       back_populates="load", cascade="all, delete-orphan")


class LoadContainer(Base):
    __tablename__ = "load_containers"
    id           = Column(Integer, primary_key=True)
    load_id      = Column(Integer, ForeignKey("loads.load_id", ondelete="CASCADE"), nullable=False)
    container_id = Column(Integer, ForeignKey("containers.container_id", ondelete="CASCADE"), nullable=False)
    load      = relationship("Load",      back_populates="containers")
    container = relationship("Container")


class LoadFixture(Base):
    __tablename__ = "load_fixtures"
    id         = Column(Integer, primary_key=True)
    load_id    = Column(Integer, ForeignKey("loads.load_id",       ondelete="CASCADE"), nullable=False)
    fixture_id = Column(Integer, ForeignKey("fixtures.fixture_id", ondelete="CASCADE"), nullable=False)
    included   = Column(Boolean, nullable=False, default=True)
    load    = relationship("Load",    back_populates="fixtures")
    fixture = relationship("Fixture")


class LoadLog(Base):
    __tablename__ = "load_log"
    log_id    = Column(Integer, primary_key=True)
    load_id   = Column(Integer, ForeignKey("loads.load_id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
    action    = Column(String(64), nullable=False)
    note      = Column(Text)
    load = relationship("Load", back_populates="log_entries")


class StatusChangeLog(Base):
    __tablename__ = "status_change_log"
    log_id        = Column(Integer, primary_key=True)
    entity_type   = Column(String(16), nullable=False)
    entity_id     = Column(Integer, nullable=False)
    old_status_id = Column(Integer, ForeignKey("statuses.status_id", ondelete="SET NULL"))
    new_status_id = Column(Integer, ForeignKey("statuses.status_id", ondelete="SET NULL"))
    load_id       = Column(Integer, ForeignKey("loads.load_id", ondelete="SET NULL"))
    timestamp     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    note          = Column(Text)
    old_status = relationship("Status", foreign_keys=[old_status_id])
    new_status = relationship("Status", foreign_keys=[new_status_id])
