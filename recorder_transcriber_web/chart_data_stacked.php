<?php
require 'db_config.php';

$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo = $_GET['dateTo'] ?? '';

if ($dateFrom && $dateTo) {
    $stmt = $pdo->prepare("
        SELECT DATE(created_at) AS date, source, COUNT(*) AS count
        FROM records
        WHERE DATE(created_at) BETWEEN :from AND :to
        GROUP BY date, source
        ORDER BY date ASC
    ");
    $stmt->execute([
        ':from' => $dateFrom,
        ':to' => $dateTo
    ]);
} else {
    $stmt = $pdo->prepare("
        SELECT DATE(created_at) AS date, source, COUNT(*) AS count
        FROM records
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY date, source
        ORDER BY date ASC
    ");
    $stmt->execute();
}

$data = $stmt->fetchAll(PDO::FETCH_ASSOC);

$grouped = [];
$sources = [];

foreach ($data as $row) {
    $date = $row['date'];
    $source = $row['source'] ?: 'ไม่ระบุ';  // แสดงชื่อ "ไม่ระบุ" หาก source เป็นค่าว่าง
    $count = (int)$row['count'];

    $sources[$source] = true;
    $grouped[$date][$source] = $count;
}

// เตรียม labels และ datasets
$labels = array_keys($grouped);
ksort($labels);
$sources = array_keys($sources);
$datasets = [];

foreach ($sources as $source) {
    $dataset = [
        'label' => $source,
        'data' => [],
    ];
    foreach ($labels as $date) {
        $dataset['data'][] = $grouped[$date][$source] ?? 0;
    }
    $datasets[] = $dataset;
}

echo json_encode([
    'labels' => $labels,
    'datasets' => $datasets
]);
