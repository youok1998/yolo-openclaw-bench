from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///./bench.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    job_id = Column(String, primary_key=True, index=True)
    status = Column(String, index=True, default="queued")
    progress = Column(Integer, default=0)
    payload_json = Column(Text)
    result_json = Column(Text, nullable=True)
    message = Column(Text, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)
