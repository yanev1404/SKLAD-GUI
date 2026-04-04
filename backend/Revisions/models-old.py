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

    contact    = relationship("Contact", back_populates="locations")
    containers = relationship("Container", back_populates="location",
                              foreign_keys="Container.location_id")
    placeholder = relationship("Container",
                               foreign_keys=[placeholder_container_id])


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
    status_id      = Column(Integer, ForeignKey("statuses.status_id", ondelete="SET NULL"))
    note           = Column(Text)

    location = relationship("Location", back_populates="containers",
                            foreign_keys=[location_id])
    status   = relationship("Status")
    fixtures = relationship("Fixture", back_populates="container")


class Fixture(Base):
    __tablename__ = "fixtures"
    fixture_id   = Column(Integer, primary_key=True)
    category     = Column(String(64))
    subcategory  = Column(String(64))
    short_name   = Column(String(128), nullable=False)
    quantity     = Column(Integer, nullable=False, default=1)
    manufacturer = Column(String(128))
    model        = Column(String(128))
    weight_kg    = Column(Numeric(8, 2))
    power_w      = Column(Numeric(8, 2))
    container_id = Column(Integer, ForeignKey("containers.container_id", ondelete="SET NULL"))
    status_id    = Column(Integer, ForeignKey("statuses.status_id", ondelete="SET NULL"))
    note         = Column(Text)

    container = relationship("Container", back_populates="fixtures")
    status    = relationship("Status")


class Load(Base):
    __tablename__ = "loads"
    load_id                 = Column(Integer, primary_key=True)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    origin_location_id      = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    destination_location_id = Column(Integer, ForeignKey("locations.location_id", ondelete="SET NULL"))
    status                  = Column(String(32), nullable=False, default="completed")
    note                    = Column(Text)

    origin      = relationship("Location", foreign_keys=[origin_location_id])
    destination = relationship("Location", foreign_keys=[destination_location_id])
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
    load_id    = Column(Integer, ForeignKey("loads.load_id",    ondelete="CASCADE"), nullable=False)
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
