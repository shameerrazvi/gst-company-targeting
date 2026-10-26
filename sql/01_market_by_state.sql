-- Market size and new companies by state.
-- "New" = active companies whose ABN started in the window (Oct 2025 to Sep 2026),
-- compared with the 12 months before. A lead is an operating company registered for GST.
WITH params AS (
    SELECT DATE '2025-10-01' AS recent_start, DATE '2026-09-30' AS recent_end,
           DATE '2024-10-01' AS prior_start,  DATE '2025-09-30' AS prior_end
),
active AS (
    SELECT c.*,
           c.abn_status_from BETWEEN p.recent_start AND p.recent_end AS is_recent,
           c.abn_status_from BETWEEN p.prior_start AND p.prior_end   AS is_prior,
           c.operating = 1 AND c.gst_status = 'ACT'                  AS is_lead
    FROM companies c CROSS JOIN params p
    WHERE c.abn_status = 'ACT'
)
SELECT state,
       COUNT(*)                                                    AS active_companies,
       100.0 * AVG(CASE WHEN gst_status = 'ACT' THEN 1 ELSE 0 END) AS gst_registered_pct,
       COUNT(*) FILTER (WHERE is_recent)                           AS new_last_12m,
       COUNT(*) FILTER (WHERE is_prior)                            AS new_prior_12m,
       COUNT(*) FILTER (WHERE is_recent AND is_lead)               AS leads_last_12m,
       100.0 * (COUNT(*) FILTER (WHERE is_recent)
                / COUNT(*) FILTER (WHERE is_prior) - 1)            AS growth_pct
FROM active
WHERE state <> 'Unknown'
GROUP BY state
ORDER BY active_companies DESC;
