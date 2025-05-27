<?php
session_start();
require 'db_config.php';

// บันทึก session ปัจจุบัน
$sid = session_id();
$stmt = $pdo->prepare("
  REPLACE INTO online_users (session_id, last_activity)
  VALUES (:sid, NOW())
");
$stmt->execute([':sid' => $sid]);

// ลบ session เก่าที่ inactivity เกิน 2 นาที
$pdo->exec("
  DELETE FROM online_users
  WHERE last_activity < DATE_SUB(NOW(), INTERVAL 2 MINUTE)
");

// นับจำนวน session ที่ยัง active
$count = $pdo->query("SELECT COUNT(*) FROM online_users")
             ->fetchColumn();

// คืนค่าเป็น JSON
header('Content-Type: application/json');
echo json_encode(['online' => (int)$count]);
