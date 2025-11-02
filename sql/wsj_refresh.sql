-- wsj_refresh.sql  (aggregate raw → daily, safe to re-run)
INSERT INTO wsj_scores_daily(score_date, fiscal_index)
SELECT
  score_date,
  ROUND(AVG(fiscal_index)::NUMERIC, 4) AS fiscal_index
FROM stg_wsj_scores_raw
GROUP BY score_date
ON CONFLICT (score_date) DO UPDATE
SET fiscal_index = EXCLUDED.fiscal_index;
