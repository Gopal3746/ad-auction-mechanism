CREATE OR REPLACE VIEW v_mechanism_kpis AS
SELECT
    mechanism,
    COUNT(*) AS auction_count,
    SUM(CASE WHEN is_filled THEN 1 ELSE 0 END) AS filled_auctions,
    AVG(CASE WHEN is_filled THEN 1.0 ELSE 0.0 END) AS fill_rate,
    AVG(seller_revenue) AS revenue_per_auction,
    AVG(CASE WHEN is_filled THEN seller_revenue END) AS revenue_per_filled_auction,
    MEDIAN(seller_revenue) AS median_revenue_per_auction,
    QUANTILE_CONT(seller_revenue, 0.95) AS p95_revenue_per_auction,
    AVG(bid_spread) AS avg_bid_spread,
    AVG(top_bid_gap) AS avg_top_bid_gap,
    AVG(auction_depth) AS avg_auction_depth,
    AVG(mean_shading_ratio) AS avg_shading_ratio,
    AVG(winner_surplus) AS avg_winner_surplus
FROM fact_auction_outcomes
WHERE split = 'evaluation'
GROUP BY mechanism;

CREATE OR REPLACE VIEW v_daily_fill_rate AS
SELECT
    CAST(event_timestamp AS DATE) AS event_date,
    mechanism,
    COUNT(*) AS auctions,
    AVG(CASE WHEN is_filled THEN 1.0 ELSE 0.0 END) AS fill_rate,
    AVG(seller_revenue) AS revenue_per_auction
FROM fact_auction_outcomes
WHERE split = 'evaluation'
GROUP BY 1, 2
ORDER BY 1, 2;

CREATE OR REPLACE VIEW v_bid_shading_by_depth AS
SELECT
    mechanism,
    auction_depth,
    COUNT(*) AS auctions,
    AVG(mean_shading_ratio) AS avg_shading_ratio,
    AVG(seller_revenue) AS revenue_per_auction
FROM fact_auction_outcomes
WHERE split = 'evaluation'
GROUP BY 1, 2
ORDER BY 1, 2;

CREATE OR REPLACE VIEW v_auction_depth_distribution AS
SELECT
    auction_depth,
    COUNT(DISTINCT auction_id) AS auction_count
FROM fact_auction_outcomes
WHERE split = 'evaluation'
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE VIEW v_placement_mechanism_kpis AS
SELECT
    p.placement_name,
    a.mechanism,
    COUNT(*) AS auctions,
    AVG(CASE WHEN a.is_filled THEN 1.0 ELSE 0.0 END) AS fill_rate,
    AVG(a.seller_revenue) AS revenue_per_auction,
    AVG(a.bid_spread) AS avg_bid_spread,
    AVG(a.winner_surplus) AS avg_winner_surplus
FROM fact_auction_outcomes a
JOIN dim_placement p USING (placement_id)
WHERE a.split = 'evaluation'
GROUP BY 1, 2
ORDER BY 1, 2;
