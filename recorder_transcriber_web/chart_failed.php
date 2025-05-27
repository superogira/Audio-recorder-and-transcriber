<?php
require 'db_config.php';
header('Content-Type: application/json');

// รับพารามิเตอร์กรองวันที่
$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo   = $_GET['dateTo']   ?? '';

$where = ["transcript = '[ไม่สามารถถอดข้อความจากเสียงได้]'"];
$params = [];
/*
if ($dateFrom && $dateTo) {
    $where[]        = "created_at BETWEEN :from AND :to";
    $params[':from'] = $dateFrom . ' 00:00:00';
    $params[':to']   = $dateTo   . ' 23:59:59';
}
*/

if (!empty($_GET['dateFrom']) && !empty($_GET['dateTo'])) {
    // รับรูปแบบ "2025-05-18 14:30" มาจาก flatpickr ได้เลย
    $where[]        = "created_at BETWEEN :from AND :to";
    $params[':from'] = $_GET['dateFrom']; 
    $params[':to']   = $_GET['dateTo'];
}

$whereSQL = 'WHERE ' . implode(' AND ', $where);

// … เตรียม SQL, execute, ส่ง JSON กลับ …
// ดึงข้อมูลจำนวนแต่ละ source
$sql = "
  SELECT
    source,
    COUNT(*) AS cnt
  FROM records
  $whereSQL
  GROUP BY source
  ORDER BY cnt DESC
";
$stmt = $pdo->prepare($sql);
$stmt->execute($params);
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

// เตรียม labels และ data
$labels = [];
$data   = [];
foreach ($rows as $r) {
    $labels[] = $r['source'];
    $data[]   = (int)$r['cnt'];
}

echo json_encode([
    'labels' => $labels,
    'data'   => $data
]);
