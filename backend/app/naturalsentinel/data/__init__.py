"""Data files for NaturalSentinel — NOT code.

This package holds data that used to live in ``.py`` files (large
hardcoded mapping dicts, sample fixtures, builtin process definitions)
and is now stored as YAML / JSON / Markdown so it can be edited without
a code review.

Layout::

    data/
    ├── mappings/   — YAML files for sector/domain/state mappings
    ├── processes/  — Markdown files for builtin process definitions
    └── samples/    — JSON fixtures for tests and sample mode

The loader API lives here at the package level::

    from app.naturalsentinel.data import load_mapping, load_process, load_samples

Phase R creates this package as a scaffold. Phase P1.2 will actually
populate ``mappings/`` with the five mapping YAMLs and migrate
``state_domains.py``, ``fetchers/__init__.py``, and
``fetchers/live/federal_register.py`` to read from them. Phase R extras
will relocate builtin process ``.md`` files and the ``sample_data.py``
fixtures here.
"""
