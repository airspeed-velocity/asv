from importlib_metadata import version as get_version

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
# needs_sphinx = '1.0'

intersphinx_mapping = {
    "python": (" https://docs.python.org/3/", None),
    "asv_runner": ("https://airspeed-velocity.github.io/asv_runner/", None),
}

extensions = [
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinxcontrib.katex",
    "sphinxcontrib.bibtex",
    "sphinx_collapse",
    "autoapi.extension",
]

autoapi_dirs = ["../../asv"]
autoapi_add_toc_entry = True
autoapi_keep_files = True
autoapi_ignore = ["*_version*", "*migrations*"]
autoapi_options = [
    "members",
    "undoc-members",
    "private-members",
    # "show-inheritance",
    "show-module-summary",
    "special-members",
    "imported-members",
]

bibtex_bibfiles = ["asv.bib"]
bibtex_default_style = "alpha"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The encoding of source files.
source_encoding = "utf-8-sig"

# The root toctree document.
root_doc = "index"

# General information about the project.
project = "airspeed velocity"
copyright = "2013--present, Michael Droettboom, Pauli Virtanen, asv Developers"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The full version, including alpha/beta/rc tags.
release: str = get_version("asv")
# The short X.Y.Z version.
version: str = ".".join(release.split(".")[:3])

# Warn about all references where the target cannot be found.
nitpicky = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "lightbulb"
pygments_dark_style = "one-dark"

# -- Options for HTML output ----------------------------------------------

html_theme = "furo"
html_favicon = "_static/swallow.ico"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/airspeed-velocity/asv/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "light_logo": "dark_logo.png",
    "dark_logo": "light_logo.png",
}
