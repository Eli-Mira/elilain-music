"""Allow running as: python -m elilain_music.web"""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
