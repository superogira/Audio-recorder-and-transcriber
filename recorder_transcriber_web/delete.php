<?php
header('Content-Type: application/json');

session_start();
if (!($_SESSION['logged_in'] ?? false)) {
    echo json_encode(['success' => false, 'error' => 'คุณต้องเข้าสู่ระบบก่อน']);
    exit;
}

// ตั้งค่าการเชื่อมต่อ
require 'db_config.php'; // สำหรับ $pdo

$id = $_POST['id'] ?? null;
$filename = $_POST['filename'] ?? null;

if (!$id || !$filename) {
    echo json_encode(["success" => false, "error" => "Missing data"]);
    exit;
}

// ลบ record
$stmt = $pdo->prepare("DELETE FROM records WHERE id = ?");
if (!$stmt->execute([$id])) {
    echo json_encode(["success" => false, "error" => "Delete DB failed"]);
    exit;
}

// ลบไฟล์เสียง
$file_path = __DIR__ . "/audio_files/" . basename($filename);
if (file_exists($file_path)) {
    unlink($file_path);
}

if (isset($_POST['ids']) && is_array($_POST['ids'])) {
    $ids = $_POST['ids'];
    $files = $_POST['files'];

    foreach ($ids as $i => $id) {
        $filename = basename($files[$i]);
        $filePath = __DIR__ . '/audio_files/' . $filename;

        // ลบไฟล์
        if (file_exists($filePath)) unlink($filePath);

        // ลบจาก DB
        $stmt = $pdo->prepare("DELETE FROM records WHERE id = ?");
        $stmt->execute([$id]);
    }

    echo json_encode(['success' => true]);
    exit;
}

echo json_encode(["success" => true]);
