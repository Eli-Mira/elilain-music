"""GUI entry point — `python -m elilain_music.gui`."""

import sys

from .qml import main

if __name__ == "__main__":
    sys.exit(main())
