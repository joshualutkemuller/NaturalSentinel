"""add pg_document provenance columns

Revision ID: 79cb2d858edf
Revises: e054cbada3f2
Create Date: 2026-04-13 20:56:56.445039

Phase P0.4 — Promote source_url, domain, and jurisdiction to
first-class columns on ns_documents so "find all docs from sec.gov"
is a B-tree index hit rather than a JSON-extract scan.

- ``source_url`` (NOT NULL, default "") — canonical provenance URL
- ``domain``      (nullable)            — RegulatoryDomain value or NULL
- ``jurisdiction``(NOT NULL, default "federal") — Jurisdiction value

All three get B-tree indexes. Existing rows are backfilled with the
column defaults; the app-level write path starts populating real
values immediately so only already-ingested-before-this-migration
rows carry the placeholder.
"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "79cb2d858edf"
down_revision = "e054cbada3f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ns_documents",
        sa.Column(
            "source_url",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "ns_documents",
        sa.Column(
            "domain",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )
    op.add_column(
        "ns_documents",
        sa.Column(
            "jurisdiction",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="federal",
        ),
    )
    op.create_index(
        op.f("ix_ns_documents_domain"), "ns_documents", ["domain"], unique=False
    )
    op.create_index(
        op.f("ix_ns_documents_jurisdiction"),
        "ns_documents",
        ["jurisdiction"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ns_documents_source_url"),
        "ns_documents",
        ["source_url"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_ns_documents_source_url"), table_name="ns_documents")
    op.drop_index(op.f("ix_ns_documents_jurisdiction"), table_name="ns_documents")
    op.drop_index(op.f("ix_ns_documents_domain"), table_name="ns_documents")
    op.drop_column("ns_documents", "jurisdiction")
    op.drop_column("ns_documents", "domain")
    op.drop_column("ns_documents", "source_url")
