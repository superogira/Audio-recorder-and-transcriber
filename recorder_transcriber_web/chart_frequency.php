<?php
require 'db_config.php';

$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo   = $_GET['dateTo']   ?? '';

$whereDate = '';
$params    = [];
if ($dateFrom && $dateTo) {
    $whereDate = "WHERE DATE(created_at) BETWEEN :from AND :to";
    $params = [
        ':from' => $dateFrom,
        ':to'   => $dateTo
    ];
}

$sql = "
    SELECT
      CASE
        WHEN frequency REGEXP '^[0-9]+(\\.[0-9]+)?$'
          THEN FORMAT(CAST(frequency AS DECIMAL(12,4)), 4)
        ELSE 'อื่น ๆ / ไม่ได้ระบุ'
      END AS freq_label,
      COUNT(*) AS cnt
    FROM records
    $whereDate
    GROUP BY freq_label
    ORDER BY cnt DESC
";

$stmt = $pdo->prepare($sql);
$stmt->execute($params);

$data = $stmt->fetchAll(PDO::FETCH_ASSOC);
$labels = array_column($data, 'freq_label');
$values = array_column($data, 'cnt');

echo json_encode([
  'labels' => $labels,
  'data'   => $values
]);
