--
-- Validation: Fiscal Score Integration with Auction Data
-- 

-- Check total counts and linkage coverage
SELECT 
    (SELECT COUNT(*) FROM auctions)          AS total_auctions,
    (SELECT COUNT(*) FROM wsj_scores_daily)  AS total_fiscal_days,
    (SELECT COUNT(*) 
       FROM auction_with_wsj 
      WHERE wsj_fiscal_index <> 0)           AS auctions_with_fiscal_score,
    ROUND(
      100.0 * (
        SELECT COUNT(*) 
        FROM auction_with_wsj 
        WHERE wsj_fiscal_index <> 0
      ) / NULLIF((SELECT COUNT(*) FROM auctions), 0),
      2
    ) AS pct_auctions_with_scores;

-- Show a few recent joined records (sanity sample)
SELECT 
    a.auction_date,
    a.auction_format,
    a.bid_to_cover_ratio,
    w.wsj_fiscal_index
FROM auction_with_wsj w
JOIN auctions a ON a.auction_date = w.auction_date
ORDER BY a.auction_date DESC
LIMIT 10;

-- Detect possible date mismatches
SELECT 
    a.auction_date
FROM auctions a
LEFT JOIN wsj_scores_daily w ON a.auction_date = w.score_date
WHERE w.score_date IS NULL
ORDER BY a.auction_date DESC
LIMIT 10;

--quick null check summary
SELECT 
    COUNT(*) FILTER (WHERE wsj_fiscal_index IS NULL OR wsj_fiscal_index = 0) AS null_or_zero_index,
    COUNT(*) FILTER (WHERE bid_to_cover_ratio IS NULL) AS null_bid_to_cover
FROM auction_with_wsj;
