<?php
require 'db_config.php';

$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo = $_GET['dateTo'] ?? '';

if ($dateFrom && $dateTo) {
    $stmt = $pdo->prepare("
        SELECT DATE(created_at) AS day, ROUND(SUM(duration), 0) AS total_seconds
        FROM records
        WHERE DATE(created_at) BETWEEN :dateFrom AND :dateTo
        GROUP BY day
        ORDER BY day ASC
    ");
    $stmt->execute([
        ':dateFrom' => $dateFrom,
        ':dateTo' => $dateTo
    ]);
} else {
    // ค่า default: 30 วันล่าสุด
    $stmt = $pdo->prepare("
        SELECT DATE(created_at) AS day, ROUND(SUM(duration), 0) AS total_seconds
        FROM records
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY day
        ORDER BY day ASC
    ");
    $stmt->execute();
}

$data = $stmt->fetchAll(PDO::FETCH_ASSOC);

$labels = [];
$values = [];

foreach ($data as $row) {
    $labels[] = $row['day'];
    $values[] = $row['total_seconds'];
}

echo json_encode([
    'labels' => $labels,
    'data' => $values
]);
