-- New companies (still active) by the month their ABN started, and how many are GST-registered.
SELECT date_trunc('month', abn_status_from)                  AS month,
       COUNT(*)                                              AS new_companies,
       SUM(CASE WHEN gst_status = 'ACT' THEN 1 ELSE 0 END)   AS gst_registered
FROM companies
WHERE abn_status = 'ACT'
  AND abn_status_from BETWEEN DATE '2023-01-01' AND DATE '2026-09-30'
GROUP BY 1
ORDER BY 1;
