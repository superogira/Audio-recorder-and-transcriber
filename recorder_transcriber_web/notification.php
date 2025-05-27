<?php
/* require 'db_config.php';
header('Content-Type: application/json');

// ดึงค่า MAX(id) ปัจจุบัน
$stmt = $pdo->query("SELECT MAX(id) FROM records");
$maxId = (int)$stmt->fetchColumn();

echo json_encode(['max_id' => $maxId]); */

require 'db_config.php'; // สมมติว่าไฟล์นี้ใช้เชื่อมต่อ PDO

try {
    // ดึง ID สูงสุด และข้อมูลไฟล์ที่เกี่ยวข้อง
    $stmt = $pdo->query("
        SELECT 
            r.id AS max_id, 
            r.filename, 
            r.file_location_type, 
            r.drive_url,
            r.local_path 
        FROM records r
        WHERE r.id = (SELECT MAX(id) FROM records)
    ");
    $result = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($result) {
        $audio_url_to_play = null;
        if (!empty($result['drive_url']) && ($result['file_location_type'] === 'drive' || $result['file_location_type'] === 'archived')) {
            // ถ้าอยู่บน Drive ให้ใช้ drive_url
            $audio_url_to_play = $result['drive_url'];
        } elseif ($result['file_location_type'] === 'local' && !empty($result['local_path'])) {
            // ถ้าอยู่ local และมี local_path (สมมติว่า local_path เก็บแค่ชื่อไฟล์)
            // คุณต้องสร้าง URL เต็มที่เข้าถึงได้จาก client-side
            // ตัวอย่าง: ถ้า script อยู่ใน subfolder และ audio_files อยู่ระดับเดียวกับ index.php
            // $base_url = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http") . "://" . $_SERVER['HTTP_HOST'];
            // $script_dir = dirname($_SERVER['PHP_SELF']); // Path to the current script's directory
            // $audio_folder_path = realpath(__DIR__ . '/../audio_files'); // Path to audio_files relative to db_config.php
            // $relative_audio_path = str_replace($_SERVER['DOCUMENT_ROOT'], '', $audio_folder_path);
            // $audio_url_to_play = $base_url . $relative_audio_path . '/' . $result['local_path'];

            // วิธีที่ง่ายกว่า (ถ้า audio_files อยู่ใน path ที่ public):
            // สมมติว่า index.php อยู่ใน root และ audio_files ก็อยู่ใน root
             $audio_url_to_play = 'audio_files/' . rawurlencode($result['local_path']);
        }

        echo json_encode([
            'max_id' => (int)$result['max_id'],
            'new_audio_url' => $audio_url_to_play, // URL หรือ Path ของไฟล์เสียงล่าสุด
            'new_filename' => $result['filename'] // ชื่อไฟล์ (เผื่อใช้แสดง)
        ]);
    } else {
        echo json_encode(['max_id' => 0, 'new_audio_url' => null, 'new_filename' => null]);
    }

} catch (PDOException $e) {
    // ควรจะ log error จริงๆ แทนการ echo ออกไป
    // error_log("Database error in notification.php: " . $e->getMessage());
    echo json_encode(['max_id' => 0, 'error' => 'Database error', 'new_audio_url' => null, 'new_filename' => null]);
}
?>