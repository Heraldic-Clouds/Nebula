"""Enforce append-only financial/usage/audit records and immutable rate amounts."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION nebula_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Nebula facts are append-only; post a compensating entry'; END; $$""")
    for table in ["ledger", "usage", "audit"]:
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION nebula_append_only()")
    op.execute("""CREATE FUNCTION nebula_fixed_rates() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF (NEW.cpu, NEW.ram, NEW.storage, NEW.public_ip, NEW.created_at, NEW.id)
          IS DISTINCT FROM (OLD.cpu, OLD.ram, OLD.storage, OLD.public_ip, OLD.created_at, OLD.id)
        THEN RAISE EXCEPTION 'Create a new rate version instead of editing amounts'; END IF;
        RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER fixed_rates BEFORE UPDATE ON rates FOR EACH ROW EXECUTE FUNCTION nebula_fixed_rates()")


def downgrade():
    op.execute("DROP TRIGGER fixed_rates ON rates")
    op.execute("DROP FUNCTION nebula_fixed_rates()")
    for table in ["ledger", "usage", "audit"]:
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION nebula_append_only()")
