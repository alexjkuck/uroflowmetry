#!/usr/bin/env python3
"""
Main entry point for Uroflowmetry Data Collection application
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from uroflow.data_collection_gui import DataCollectionGUI

#*******************************************************************
def main():
    """
    --------------------------------------------------------------------
    main()
    Main entry point for the application

    OUTPUTS
    None

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    app = DataCollectionGUI()
    app.run()
#*******************************************************************

if __name__ == "__main__":
    main()

