-- Estación climática del muestreo, notas de procedencia y tramo forzado. No destructiva.
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS season text CHECK (season IN ('seca', 'humeda'));
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS notes text;
ALTER TABLE measurement ADD COLUMN IF NOT EXISTS reach_forced boolean NOT NULL DEFAULT false;
