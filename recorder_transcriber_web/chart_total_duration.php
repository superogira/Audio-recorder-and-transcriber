<?php
require 'db_config.php';  // เชื่อมต่อฐานข้อมูล
header('Content-Type: application/json');

$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo   = $_GET['dateTo']   ?? '';

$where = [];
$params = [];

// ถ้ามีเลือกช่วงวัน+เวลา ให้กรองตามนั้น
if ($dateFrom && $dateTo) {
    $where[]       = "created_at BETWEEN :from AND :to";
    $params[':from'] = $dateFrom . ':00'; // ถ้า Flatpickr ส่ง Y-m-d H:i
    $params[':to']   = $dateTo   . ':59';
} else {
    // default ย้อนหลัง 30 วัน
    $where[] = "created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
}

$whereSQL = 'WHERE ' . implode(' AND ', $where);

// ดึงข้อมูลรวม duration ตาม source
//SUM(duration) AS total_duration
$sql = "
    SELECT
      source,
      SUM(duration) / 60.0 AS total_minutes
    FROM records
    $whereSQL
    GROUP BY source
    ORDER BY total_minutes DESC
";
$stmt = $pdo->prepare($sql);
$stmt->execute($params);

$labels = [];
$data   = [];
foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $row) {
    $labels[] = $row['source'];
    //$data[]   = (float)$row['total_duration'];
	$data[]   = round((float)$row['total_minutes'], 2);
}

echo json_encode([
    'labels' => $labels,
    'data'   => $data
]);
