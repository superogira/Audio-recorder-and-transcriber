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

$upload_dir = __DIR__ . '/audio_files/';
if (!is_dir($upload_dir)) mkdir($upload_dir, 0755, true);

$maxSize = 5 * 1024 * 1024 * 1024; // 5 GB
$folder = $upload_dir;

// เชื่อมต่อฐานข้อมูล
require 'db_config.php'; // สำหรับ $pdo

// ตรวจสอบขนาดโฟลเดอร์ และเคลียร์โฟลเดอร์เก่าเมื่อเต็ม
while (getFolderSize($folder) > $maxSize) {
	// ดึง row ที่เก่าที่สุด
    $stmt = $pdo->query("SELECT * FROM records ORDER BY created_at ASC LIMIT 1");
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$row) break; // ถ้าไม่มีข้อมูลแล้ว ให้ออกจากลูป

	// ลบไฟล์
    $oldFile = $upload_dir . $row['filename'];
    if (file_exists($oldFile)) unlink($oldFile);

	// ลบข้อมูลในฐานข้อมูล
    $stmt = $pdo->prepare("DELETE FROM records WHERE id = ?");
    $stmt->execute([$row['id']]);
}

// ตรวจสอบไฟล์และข้อมูลที่ส่งมา
if (!isset($_FILES['audio']) || $_FILES['audio']['error'] !== UPLOAD_ERR_OK || !isset($_POST['transcript'])) {
    http_response_code(400);
    echo json_encode(['status'=>'error','message'=>'Missing or invalid upload data']);
    exit;
}

// --- เช็คขนาดไฟล์ ไม่เกิน 5 MB ---
$maxSize = 5 * 1024 * 1024;  // 5 MB
if ($_FILES['audio']['size'] > $maxSize) {
    http_response_code(413);
    echo json_encode([
        'status'  => 'error',
        'message' => 'ไฟล์ใหญ่เกิน 5 MB ไม่สามารถอัพโหลดได้'
    ]);
    exit;
}

// 1. ตรวจนามสกุล
$origName = $_FILES['audio']['name'];
$ext = strtolower(pathinfo($origName, PATHINFO_EXTENSION));
$allowed_ext = ['wav'];
if (!in_array($ext, $allowed_ext)) {
    http_response_code(415);
    echo json_encode(['status'=>'error','message'=>"Unsupported file extension .{$ext}"]);
    exit;
}

// 2. ตรวจ MIME type
$finfo = new finfo(FILEINFO_MIME_TYPE);
$mime  = $finfo->file($_FILES['audio']['tmp_name']);
$allowed_mime = ['audio/wav','audio/x-wav'];
if (!in_array($mime, $allowed_mime)) {
    http_response_code(415);
    echo json_encode(['status'=>'error','message'=>"Unsupported MIME type {$mime}"]);
    exit;
}

// 3. sanitize ชื่อไฟล์
$base = pathinfo($origName, PATHINFO_FILENAME);
$base = preg_replace('/[^A-Za-z0-9_\-]/', '_', $base); // เหลือแค่ a–z, A–Z,0–9,_,-

// เตรียมชื่อไฟล์สุดท้าย
$filename = "{$base}.{$ext}";
$target   = $upload_dir . $filename;

// 4. ป้องกัน overwrite
if (file_exists($target)) {
    $filename = sprintf("%s_%s.%s",
        $base,
        date('Ymd_His'),  // หรือใช้ uniqid()
        $ext
    );
    $target = $upload_dir . $filename;
}

// เก็บข้อมูลอื่นๆ
$frequency  = $_POST['frequency'] ?? '';
$station    = $_POST['station']   ?? '';
$transcript = $_POST['transcript'];
$duration   = $_POST['duration']   ?? '';
$source     = $_POST['source']     ?? 'unknown';

// ย้ายไฟล์ขึ้นเซิร์ฟเวอร์
if (!move_uploaded_file($_FILES['audio']['tmp_name'], $target)) {
    http_response_code(500);
    echo json_encode(['status'=>'error','message'=>'Upload failed']);
    exit;
}

// บันทึกลงฐานข้อมูล
$stmt = $pdo->prepare("
    INSERT INTO records (station, frequency, filename, transcript, source, duration, created_at)
    VALUES (?,?,?,?,?,?,NOW())
");
$stmt->execute([
    $station,
    $frequency,
    $filename,
    $transcript,
    $source,
    $duration
]);

echo json_encode(['status'=>'ok','filename'=>$filename]);
?>
