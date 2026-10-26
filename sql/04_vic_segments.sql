-- Victorian region x industry segments of new leads, placed on a size-growth grid.
-- A segment needs 100+ new leads; the grid lines are the medians of size and growth.
WITH params AS (
    SELECT DATE '2025-10-01' AS recent_start, DATE '2026-09-30' AS recent_end,
           DATE '2024-10-01' AS prior_start,  DATE '2025-09-30' AS prior_end
),
leads AS (
    SELECT c.sa4, c.sector,
           c.abn_status_from BETWEEN p.recent_start AND p.recent_end AS is_recent,
           c.abn_status_from BETWEEN p.prior_start AND p.prior_end   AS is_prior
    FROM companies c CROSS JOIN params p
    WHERE c.abn_status = 'ACT' AND c.state = 'VIC'
      AND c.operating = 1 AND c.gst_status = 'ACT'
      AND c.sector <> 'Unclassified' AND c.sa4 <> 'Unmatched'
),
segments AS (
    SELECT sa4, sector,
           COUNT(*) FILTER (WHERE is_recent) AS new_leads,
           COUNT(*) FILTER (WHERE is_prior)  AS prior_leads
    FROM leads
    GROUP BY sa4, sector
    HAVING COUNT(*) FILTER (WHERE is_recent) >= 100
),
scored AS (
    SELECT *,
           100.0 * (new_leads / NULLIF(prior_leads, 0) - 1)      AS growth_pct
    FROM segments
),
cuts AS (
    SELECT quantile_cont(new_leads, 0.5) AS size_cut, quantile_cont(growth_pct, 0.5) AS growth_cut
    FROM scored
),
placed AS (
    SELECT s.*,
           CASE WHEN s.new_leads >= c.size_cut AND s.growth_pct >= c.growth_cut THEN 'Priority: large and growing'
                WHEN s.new_leads >= c.size_cut                                THEN 'Core: large, steady'
                WHEN s.growth_pct >= c.growth_cut                             THEN 'Emerging: small, growing'
                ELSE 'Monitor: small, steady' END AS quadrant
    FROM scored s CROSS JOIN cuts c
)
SELECT ROW_NUMBER() OVER (ORDER BY CASE quadrant WHEN 'Priority: large and growing' THEN 0
                                                 WHEN 'Core: large, steady' THEN 1
                                                 WHEN 'Emerging: small, growing' THEN 2 ELSE 3 END,
                                   new_leads DESC, sa4, sector) AS rank,
       sa4, sector, new_leads, prior_leads, growth_pct, quadrant
FROM placed
ORDER BY rank;
