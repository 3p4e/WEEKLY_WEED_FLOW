-- GrowFlow Unified — account hierarchy (provisioning authority is enforced in the
-- API; see server/routers/auth.py). Adds the inter-department account marker.
--
-- Tiers (top → bottom):  admin → executive (C-level) → hod (head of department)
--                         → qp / qa / operator (staff). `cross_department` marks an
-- inter-department account (e.g. a team-leader/coordinator spanning departments).
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS cross_department BOOLEAN NOT NULL DEFAULT FALSE;
