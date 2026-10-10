from sqlmodel import SQLModel, Session, create_engine
from .config import settings
from .models import Household

engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})

def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if not s.get(Household, 1):
            s.add(Household(id=1)); s.commit()

def get_session():
    with Session(engine) as s:
        yield s
