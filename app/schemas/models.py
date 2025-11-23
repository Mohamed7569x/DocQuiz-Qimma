import uuid
from sqlalchemy import *
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

Base = declarative_base()

class Content(Base):
    __tablename__ = "content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lang_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    href = Column(String, nullable=False)
    status = Column(Boolean, nullable=False, default=True)


class Page(Base):
    __tablename__ = "pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String, nullable=False, unique=True)
    page_title = Column(String, nullable=False)
    source_json = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    sections = relationship("Section", back_populates="page", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id"), nullable=False)
    title = Column(String, nullable=False)
    summary_json = Column(Text, nullable=True)     
    examples_json = Column(Text, nullable=True)
    page = relationship("Page", back_populates="sections")
    
class Url(Base):
    __tablename__ = "urls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lang= Column(String, nullable=False, unique=False)
    title= Column(String, nullable=False, unique=False)
    url = Column(String, nullable=False, unique=True)


class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    language = Column(String(50), nullable=False)
    level = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    
    
class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False)
    quiz = relationship("Quiz", back_populates="questions")
    topic = Column(String(100), nullable=True)
    q_type = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
       
class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(30))
    social = Column(String(255))
    language = Column(String(20))
    level = Column(String(20))
    topics = Column(JSON)
    score = Column(Integer)
    total = Column(Integer)
    per_topic = Column(JSON)
    wrong_questions = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
