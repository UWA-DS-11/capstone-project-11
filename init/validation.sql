-- validation.sql  
-- run in psql: \i /validation.sql 

\echo 'INFO'
SELECT current_database() AS db, now() AT TIME ZONE 'utc' AS utc_time;

\echo '1) ROW COUNT'
SELECT 'auctions' AS table, COUNT(*) AS rows FROM auctions
UNION ALL SELECT 'securities', COUNT(*) FROM securities
UNION ALL SELECT 'bidder_details', COUNT(*) FROM bidder_details
UNION ALL SELECT 'data_updates', COUNT(*) FROM data_updates;

\echo '2) ORPHANS (should be empty)'
-- auctions without a matching security
SELECT a.auction_id, a.cusip
FROM auctions a LEFT JOIN securities s USING (cusip)
WHERE s.cusip IS NULL
LIMIT 10;

-- bidder rows without a matching auction
SELECT b.detail_id, b.auction_id
FROM bidder_details b LEFT JOIN auctions a USING (auction_id)
WHERE a.auction_id IS NULL
LIMIT 10;

\echo '3) NULL COVERAGE (important fields)'
SELECT 'bid_to_cover_ratio' AS col, COUNT(*) FILTER (WHERE bid_to_cover_ratio IS NULL) AS nulls FROM auctions
UNION ALL SELECT 'total_accepted', COUNT(*) FILTER (WHERE total_accepted IS NULL) FROM auctions
UNION ALL SELECT 'offering_amount', COUNT(*) FILTER (WHERE offering_amount IS NULL) FROM auctions
UNION ALL SELECT 'auction_date', COUNT(*) FILTER (WHERE auction_date IS NULL) FROM auctions;

\echo '4) VALUE BOUNDS'
-- yields non-negative; price in a reasonable band; btc positive and not absurd
SELECT auction_id, high_yield, price_per_100, bid_to_cover_ratio
FROM auctions
WHERE (high_yield < 0)
   OR (price_per_100 NOT BETWEEN 0 AND 200)
   OR (bid_to_cover_ratio IS NOT NULL AND (bid_to_cover_ratio <= 0 OR bid_to_cover_ratio > 10))
ORDER BY auction_id DESC
LIMIT 20;

\echo '5) BID-TO-COVER CONSISTENCY (approx)'
-- show where BTC exists; compute approx tendered = accepted * btc
SELECT auction_id,
       total_accepted,
       bid_to_cover_ratio,
       ROUND(total_accepted * bid_to_cover_ratio, 2) AS approx_total_tendered
FROM auctions
WHERE total_accepted IS NOT NULL AND bid_to_cover_ratio IS NOT NULL
ORDER BY auction_id DESC
LIMIT 20;

\echo '6) BID-TO-COVER RATIO CHECK'
SELECT auction_id,
       total_tendered,
       total_accepted,
       bid_to_cover_ratio,
       ROUND(total_tendered::numeric / NULLIF(total_accepted,0), 3) AS calc_btc,
       ROUND( (bid_to_cover_ratio - (total_tendered::numeric / NULLIF(total_accepted,0))), 3 ) AS diff
FROM auctions
WHERE total_tendered IS NOT NULL
  AND total_accepted IS NOT NULL
ORDER BY auction_date DESC
LIMIT 15;

\echo '7) COMPLETED VS PENDING AUCTIONS'
SELECT CASE WHEN a.bid_to_cover_ratio IS NULL THEN 'PENDING' ELSE 'RESULTS' END AS status,
       COUNT(*) AS n
FROM auctions a
GROUP BY 1
ORDER BY 2 DESC;

\echo '8) COVERAGE WINDOW (date range & recent count)'
SELECT MIN(auction_date) AS min_date,
       MAX(auction_date) AS max_date,
       COUNT(*) FILTER (WHERE auction_date >= CURRENT_DATE - INTERVAL '30 days') AS last_30d
FROM auctions;

\echo '9) AVG BID-TO-COVER BY SECURITY TYPE (last 90 days, completed)'
SELECT s.security_type,
       ROUND(AVG(a.bid_to_cover_ratio), 3) AS avg_btc,
       COUNT(*) AS n
FROM auctions a
JOIN securities s USING (cusip)
WHERE a.auction_date >= CURRENT_DATE - INTERVAL '90 days'
  AND a.bid_to_cover_ratio IS NOT NULL
GROUP BY s.security_type
ORDER BY n DESC;

\echo '10) TOP 10 INDIRECT-HEAVY AUCTIONS'
SELECT a.auction_id, a.auction_date, s.security_type, b.indirect_bidder_percentage
FROM auctions a
JOIN securities s USING (cusip)
JOIN bidder_details b USING (auction_id)
WHERE b.indirect_bidder_percentage IS NOT NULL
ORDER BY b.indirect_bidder_percentage DESC
LIMIT 10;

\echo '11) LAST DATA UPDATES'
SELECT update_id, update_timestamp, records_fetched, records_inserted, status
FROM data_updates
ORDER BY update_timestamp DESC
LIMIT 5;
