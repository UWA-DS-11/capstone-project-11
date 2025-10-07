-- wsj_setup.sql  
BEGIN;

-- raw staging: allow duplicates, keep history
CREATE TABLE IF NOT EXISTS stg_wsj_scores_raw (
  row_id       BIGSERIAL PRIMARY KEY,
  score_date   DATE        NOT NULL,
  fiscal_index NUMERIC(12,6) NOT NULL
);

-- daily aggregation target: one row per day
CREATE TABLE IF NOT EXISTS wsj_scores_daily (
  score_date   DATE PRIMARY KEY,
  fiscal_index NUMERIC(12,4) NOT NULL
);

CREATE INDEX IF NOT EXISTS wsj_scores_daily_date_idx
  ON wsj_scores_daily(score_date);

-- auction ↔ fiscal index join (latest score on or before the auction)
CREATE OR REPLACE VIEW auction_with_wsj AS
SELECT
  a.auction_date,
  a.auction_format,
  a.bid_to_cover_ratio,
  s.fiscal_index AS wsj_fiscal_index
FROM auctions a
LEFT JOIN LATERAL (
  SELECT fiscal_index
  FROM wsj_scores_daily
  WHERE score_date <= a.auction_date
  ORDER BY score_date DESC
  LIMIT 1
) s ON TRUE;

COMMIT;
