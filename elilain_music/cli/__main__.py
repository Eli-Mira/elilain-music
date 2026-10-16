"""Allow running as: python -m elilain_music.cli down <url>"""

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
