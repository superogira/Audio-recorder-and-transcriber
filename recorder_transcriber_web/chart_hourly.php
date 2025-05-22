<?php
date_default_timezone_set('Asia/Bangkok');

require 'db_config.php';
header('Content-Type: application/json');

$dateFrom = $_GET['dateFrom'] ?? '';
$dateTo   = $_GET['dateTo']   ?? '';

$where = [];
$params = [];

if ($dateFrom && $dateTo) {
    // ถ้ามี dateFrom/dateTo ให้ใช้ช่วงนั้น (เริ่มต้น 00:00 ถึง 23:59)
    $where[]      = "created_at BETWEEN :from AND :to";
    $params[':from'] = $dateFrom . ' 00:00:00';
    $params[':to']   = $dateTo   . ' 23:59:59';
} else {
    // ไม่มี ให้ใช้ย้อนหลัง 7 วัน
    $where[] = "created_at >= DATE_SUB(NOW(), INTERVAL 168 HOUR)";
}

$whereSQL = 'WHERE ' . implode(' AND ', $where);

// กำหนดช่วงเวลา 7 วันล่าสุด
// สร้างอาเรย์ 168 ชั่วโมงย้อนหลังเสมอเพื่อ fill ค่าเป็น 0
// สร้างอาเรย์ช่วงเวลา (key = 'YYYY-mm-dd HH:00:00') ไล่ตั้งแต่ now-23h .. now
$now = new DateTime();
$intervals = $labels = [];

if ($dateFrom && $dateTo) {
    // แปลงเป็น DateTime
    $start = new DateTime($dateFrom);
    $end   = new DateTime($dateTo);
    // อยากให้รวมชั่วโมงสุดท้ายด้วย ให้เลื่อน end ไปอีกหนึ่งชั่วโมง
    $end->modify('+1 hour');

    // สร้างช่วงทุกๆ 1 ชั่วโมง
    $period = new DatePeriod(
        $start,
        new DateInterval('PT1H'),
        $end
    );

    foreach ($period as $dt) {
        $key           = $dt->format('Y-m-d H:00:00');
        $intervals[$key] = 0;
        $labels[]        = $dt->format('H:00');
    }
} else {
	// default = 7 วัน (168 ชม.) ย้อนหลัง
	for ($i = 168; $i >= 0; $i--) {
		$dt = (clone $now)->sub(new DateInterval("PT{$i}H"));
		$key = $dt->format('Y-m-d H:00:00');
		$intervals[$key] = 0;
		$labels[] = $dt->format('H:00');
	}
}
// ดึงผลรวม duration (วินาที) ตามชั่วโมง
$sql = "
  SELECT
    DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00') AS hour,
    SUM(duration)/60.0                          AS minutes
  FROM records
  $whereSQL
  GROUP BY hour
";
$stmt = $pdo->prepare($sql);
$stmt->execute($params);

foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $row) {
    if (isset($intervals[$row['hour']])) {
		// ปัดสองตำแหน่ง
        $intervals[$row['hour']] = round($row['minutes'], 2);
    }
}

// เตรียม data ส่งกลับ
echo json_encode([
    'labels' => $labels,
    'data'   => array_values($intervals)
]);
