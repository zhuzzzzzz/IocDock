"""Create the IOC state database. Run it once when the system is installed:

    python3 scripts/init_state_db.py [db_path]

Without db_path it creates settings.DEFAULT_DB_PATH. Run it as the user
that runs IocDock, so the database belongs to that user. An existing database is
left untouched, so running it again is harmless.

Exit code: 0 the database was created or is already there, 1 it could not be
created, 2 wrong arguments.

core.ioc opens the database when it is imported and fails if it is missing, so
this script imports only core.ioc_state."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import settings
from core.ioc_state import IocStateManager


def main(argv):
    if len(argv) > 2:
        print(f"usage: {argv[0]} [db_path]", file=sys.stderr)
        return 2
    path = os.path.abspath(argv[1] if len(argv) == 2 else settings.DEFAULT_DB_PATH)
    try:
        IocStateManager.initialize(path)
    except FileExistsError as e:
        # makedirs() raises it too, when a parent of the path is a file
        if not os.path.isfile(path):
            print(f"failed to create the state database {path}: {e}", file=sys.stderr)
            return 1
        print(f"state database already exists, left unchanged: {path}")
        return 0
    except Exception as e:
        print(f"failed to create the state database {path}: {e}", file=sys.stderr)
        return 1
    print(f"state database created: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
