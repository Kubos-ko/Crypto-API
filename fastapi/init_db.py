from database import engine
from schemas import Base

def init_db():
    print("Vytváram databázové tabuľky...")
    Base.metadata.create_all(bind=engine)
    print("Databázové tabuľky boli úspešne vytvorené!")

if __name__ == "__main__":
    init_db() 