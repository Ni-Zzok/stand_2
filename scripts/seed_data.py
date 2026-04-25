from __future__ import annotations

from app.db import Base, SessionLocal, engine
from app.repositories import Repository


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        repo = Repository(db)
        repo.clear_all()
        repo.seed_defaults()
        db.commit()
    print('Seed completed.')


if __name__ == '__main__':
    main()
