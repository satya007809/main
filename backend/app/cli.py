"""Admin CLI: `python -m app.cli <command>`.

Commands:
  seed-playbooks            insert default playbooks (idempotent)
  create-user EMAIL NAME    create an admin user (prompts for password)
  purge-expired             delete cases past their retention period (schedule daily)
  gen-key                   print a new data-encryption key for BID_DATA_ENCRYPTION_KEY
"""
import getpass
import sys

from cryptography.fernet import Fernet

from .db import SessionLocal
from .main import init_db
from .models import User
from .routers.cases import purge_expired
from .security import hash_password


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "gen-key":
        print(Fernet.generate_key().decode())
        return 0
    init_db()
    db = SessionLocal()
    try:
        if cmd == "seed-playbooks":
            print("Playbooks seeded")
        elif cmd == "create-user":
            email, name = argv[1].lower(), " ".join(argv[2:])
            pw = getpass.getpass("Password (min 10 chars): ")
            if len(pw) < 10:
                print("Password too short")
                return 1
            db.add(User(email=email, full_name=name, password_hash=hash_password(pw), is_admin=True,
                        investigator_profile={"name": name}))
            db.commit()
            print("Created", email)
        elif cmd == "purge-expired":
            print("Purged", purge_expired(db), "case(s)")
        else:
            print(__doc__)
            return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
