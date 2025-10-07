-- validation.sql
-- run inside psql: \i validation.sql

\echo 'TABLE ROW COUNTS'
SELECT 'auctions' AS table, COUNT(*) AS rows FROM auctions
UNION ALL
SELECT 'securities', COUNT(*) FROM securities
UNION ALL
SELECT 'bidder_details', COUNT(*) FROM bidder_details
UNION ALL
SELECT 'data_updates', COUNT(*) FROM data_updates;

\echo 'ORPHAN CHECKS (should be empty)'
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

\echo 'BIDDER PERCENTAGES SUM (~100)'
SELECT auction_id,
       COALESCE(primary_dealer_percentage,0)
     + COALESCE(direct_bidder_percentage,0)
     + COALESCE(indirect_bidder_percentage,0) AS pct_sum
FROM bidder_details
ORDER BY auction_id DESC
LIMIT 15;

\echo 'BID-TO-COVER CHECK'
SELECT auction_id,
       total_accepted,
       bid_to_cover_ratio,
       ROUND(total_accepted * bid_to_cover_ratio, 2) AS approx_total_tendered
FROM auctions
WHERE total_accepted IS NOT NULL
ORDER BY auction_id DESC
LIMIT 15;

\echo 'LATEST COMPLETED AUCTIONS'
SELECT a.auction_id, a.auction_date, s.security_type, a.bid_to_cover_ratio
FROM auctions a
JOIN securities s USING (cusip)
WHERE a.bid_to_cover_ratio IS NOT NULL
ORDER BY a.auction_date DESC, a.auction_id DESC
LIMIT 10;

\echo 'AVG BID-TO-COVER BY SECURITY TYPE (last 90 days)'
SELECT s.security_type,
       ROUND(AVG(a.bid_to_cover_ratio), 3) AS avg_btc,
       COUNT(*) AS n
FROM auctions a JOIN securities s USING (cusip)
WHERE a.auction_date >= CURRENT_DATE - INTERVAL '90 days'
  AND a.bid_to_cover_ratio IS NOT NULL
GROUP BY s.security_type
ORDER BY n DESC;

\echo 'TOP 10 INDIRECT-HEAVY AUCTIONS'
SELECT a.auction_id, a.auction_date, s.security_type, b.indirect_bidder_percentage
FROM auctions a
JOIN securities s USING (cusip)
JOIN bidder_details b USING (auction_id)
WHERE b.indirect_bidder_percentage IS NOT NULL
ORDER BY b.indirect_bidder_percentage DESC
LIMIT 10;

\echo 'LAST DATA UPDATES'
SELECT update_id, update_timestamp, records_fetched, records_inserted, status
FROM data_updates
ORDER BY update_timestamp DESC
LIMIT 5;
