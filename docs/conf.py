import os
import sys
sys.path.insert(0, os.path.abspath("../src"))

project   = "sentinel-core"
author    = "Sentinel Company"
release   = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

html_theme = "sphinx_rtd_theme"
