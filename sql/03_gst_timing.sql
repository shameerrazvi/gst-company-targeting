-- How soon after its ABN starts does a company register for GST?
-- Companies started Jan 2023 to Sep 2025 (so each has had 12+ months), GST-registered now.
WITH gst AS (
    SELECT date_diff('day', abn_status_from, gst_status_from) AS days
    FROM companies
    WHERE abn_status = 'ACT'
      AND gst_status = 'ACT'
      AND abn_status_from BETWEEN DATE '2023-01-01' AND DATE '2025-09-30'
),
points(days_after_abn) AS (VALUES (0), (7), (30), (60), (90), (180), (365))
SELECT p.days_after_abn,
       100.0 * AVG(CASE WHEN g.days <= p.days_after_abn THEN 1 ELSE 0 END) AS share_of_gst_registered_pct
FROM points p CROSS JOIN gst g
GROUP BY p.days_after_abn
ORDER BY p.days_after_abn;
