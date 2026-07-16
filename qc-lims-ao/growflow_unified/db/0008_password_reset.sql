-- GrowFlow Unified — self-service password reset codes (forgot → reset flow).
-- Codes are bcrypt-hashed, single-use, time-limited. Touched only by the auth
-- endpoints via the admin/owner connection, so no RLS policy is required here.
CREATE TABLE IF NOT EXISTS password_reset_codes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  code_hash   TEXT NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL,
  used        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prc_user ON password_reset_codes(user_id);
