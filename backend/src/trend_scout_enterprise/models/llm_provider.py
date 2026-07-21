from sqlalchemy import Boolean, Column, Float, Integer, String, Text

from trend_scout_enterprise.core.database import Base


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    base_url = Column(Text, nullable=False)
    api_key_encrypted = Column(Text)
    model = Column(String(255), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    is_default = Column(Boolean, default=False)
