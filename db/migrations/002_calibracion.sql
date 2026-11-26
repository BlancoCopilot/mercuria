-- Covariable congelada de cada medición (calibración del modelo). No destructiva.
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS covariate_u double precision;
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS calibrated_at timestamptz;
