<?php
header('Content-Type: application/json');

function getFolderSize($dir) {
    $size = 0;
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir)) as $file) {
        if ($file->isFile()) {
            $size += $file->getSize();
        }
    }
    return $size;
}

$maxSize = 5 * 1024 * 1024 * 1024; // 5GB
$folder = __DIR__ . "/audio_files";

// เชื่อมต่อฐานข้อมูล
require 'db_config.php'; // สำหรับ $pdo

// ตรวจสอบขนาดโฟลเดอร์
while (getFolderSize($folder) > $maxSize) {
    // ดึง row ที่เก่าที่สุด
    $stmt = $pdo->query("SELECT * FROM records ORDER BY created_at ASC LIMIT 1");
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) break; // ถ้าไม่มีข้อมูลแล้ว ให้ออกจากลูป

    $filePath = $folder . "/" . $row['filename'];

    // ลบไฟล์
    if (file_exists($filePath)) {
        unlink($filePath);
    }

    // ลบข้อมูลในฐานข้อมูล
    $stmt = $pdo->prepare("DELETE FROM records WHERE id = ?");
    $stmt->execute([$row['id']]);
}

// ตรวจสอบไฟล์ถูกส่งมาหรือไม่
if (!isset($_FILES['audio']) || !isset($_POST['transcript'])) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'message' => 'Missing data']);
    exit;
}

$frequency = $_POST['frequency'] ?? '';
$station = $_POST['station'] ?? '';
$filename = basename($_FILES['audio']['name']);
$transcript = $_POST['transcript'] ?? '';
$duration = $_POST['duration'] ?? '';
$upload_dir = __DIR__ . '/audio_files/';
if (!is_dir($upload_dir)) mkdir($upload_dir, 0777, true);

// บันทึกไฟล์เสียง
$target_path = $upload_dir . $filename;
if (!move_uploaded_file($_FILES['audio']['tmp_name'], $target_path)) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => 'Upload failed']);
    exit;
}

$source = $_POST['source'] ?? 'unknown';  // หรือกำหนด default เป็น 'Azure'


// บันทึกลงฐานข้อมูล
$stmt = $pdo->prepare("INSERT INTO records (station, frequency, filename, transcript, source, duration, created_at) VALUES (?, ?, ?, ?, ?, ?, NOW())");
$stmt->execute([$station, $frequency, $filename, $transcript, $source, $duration]);

echo json_encode(['status' => 'ok']);
?>
