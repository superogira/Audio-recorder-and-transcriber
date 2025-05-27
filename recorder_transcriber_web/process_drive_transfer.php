<?php
session_start();

// ป้องกันการเข้าถึงโดยตรง และตรวจสอบการ Login
if (php_sapi_name() !== 'cli' && (!isset($_SERVER['HTTP_X_REQUESTED_WITH']) || strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) !== 'xmlhttprequest') && !isset($_GET['files_to_move']) && !isset($_GET['size_to_move_mb'])) {
    // Allow direct access if it's through EventSource which doesn't send X-Requested-With
    // A better check might be specific query params if security is paramount
}

if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
    header('Content-Type: application/json'); // Ensure correct content type for error
    echo json_encode(['status' => 'error', 'message' => 'Unauthorized access. Please login.']);
    exit;
}

// ตั้งค่า Server-Sent Events headers
header('Content-Type: text/event-stream');
header('Cache-Control: no-cache');
header('Connection: keep-alive');
header("X-Accel-Buffering: no"); // สำหรับ Nginx

// ฟังก์ชันสำหรับส่งข้อมูล SSE
function send_sse_message($data) {
    echo "data: " . json_encode($data) . "\n\n";
    ob_flush();
    flush();
}

// Include ไฟล์ที่จำเป็น
require 'db_config.php';
require_once __DIR__ . '/vendor/autoload.php';

define('GOOGLE_APPLICATION_CREDENTIALS', __DIR__ . '/xxxxx-xxxxx-xxxxxxxxxx.json');
define('GOOGLE_DRIVE_FOLDER_ID', 'xxxxxxxxxxxxxxxxxxxx');

$upload_dir = __DIR__ . '/audio_files/';

// ฟังก์ชันที่ใช้ร่วมกัน (เหมือนใน manual_drive_transfer.php เดิม)
/* ...โค้ดเดิม... */
function formatBytes($bytes, $precision = 2) {
    $units = ['B', 'KB', 'MB', 'GB', 'TB'];
    $bytes = max($bytes, 0);
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= (1 << (10 * $pow));
    return round($bytes, $precision) . ' ' . $units[$pow];
}
/* ...โค้ดเดิม... */
function getGoogleClient() {
    $client = new Google_Client();
    $client->setApplicationName('PHP Drive Uploader Manual');
    $client->setScopes(Google_Service_Drive::DRIVE_FILE);
    try {
        $client->setAuthConfig(GOOGLE_APPLICATION_CREDENTIALS);
    } catch (Google\Exception $e) {
        error_log('Google Auth Config Exception: ' . $e->getMessage());
        return null; // หรือ throw exception
    }
    $client->setAccessType('offline');
    return $client;
}

{ /* ...โค้dเดิม, อาจจะต้องปรับให้มีการส่ง SSE message ภายในนี้ด้วยถ้าต้องการความละเอียดสูงมาก... */ }
function uploadToDrive($driveService, $filePath, $fileNameInDrive) {
    if (!file_exists($filePath)) {
        error_log("uploadToDrive: File not found at " . $filePath);
        return null;
    }
    $fileMetadata = new Google_Service_Drive_DriveFile([
        'name' => $fileNameInDrive,
        'parents' => [GOOGLE_DRIVE_FOLDER_ID]
    ]);
    $content = file_get_contents($filePath);
    if ($content === false) {
        error_log("uploadToDrive: Failed to read content from " . $filePath);
        return null;
    }
    try {
        $file = $driveService->files->create($fileMetadata, [
            'data' => $content,
            'mimeType' => mime_content_type($filePath) ?: 'application/octet-stream',
            'uploadType' => 'multipart',
            'fields' => 'id, webViewLink'
        ]);
        return $file ? $file->webViewLink : null;
    } catch (Google_Service_Exception $e) {
        $errors = $e->getErrors();
        $errorMessage = "Google Service Exception during upload: " . $e->getMessage();
        if (!empty($errors)) {
            $errorMessage .= " | Errors: " . json_encode($errors);
        }
        error_log($errorMessage);
        return null;
    } catch (Exception $e) {
        error_log("Generic error uploading to Drive: " . $e->getMessage());
        return null;
    }
}


// --- เริ่ม Logic การย้ายไฟล์ ---
$files_to_move_count_param = isset($_GET['files_to_move']) ? intval($_GET['files_to_move']) : 0;
$size_to_move_mb_param = isset($_GET['size_to_move_mb']) ? floatval($_GET['size_to_move_mb']) : 0;
$size_to_move_bytes_param = $size_to_move_mb_param * 1024 * 1024;

if ($files_to_move_count_param <= 0 && $size_to_move_bytes_param <= 0) {
    send_sse_message(['status' => 'error', 'message' => 'ไม่ได้ระบุจำนวนไฟล์ หรือ ขนาดรวมที่ต้องการย้าย', 'icon' => 'exclamation-triangle-fill', 'type' => 'danger']);
    exit;
}

$googleClient = getGoogleClient();
if (!$googleClient) {
    send_sse_message(['status' => 'error', 'message' => 'ไม่สามารถเชื่อมต่อ Google Client ได้', 'icon' => 'exclamation-triangle-fill', 'type' => 'danger']);
    exit;
}
$driveService = new Google_Service_Drive($googleClient);

// ตั้งค่า PHP time limit ให้ยาวนานขึ้น
set_time_limit(0); // ไม่จำกัดเวลา (ระวังการใช้งานจริง ควรมีกลไกป้องกันที่ดีกว่านี้)
ignore_user_abort(true); // ให้ script ทำงานต่อแม้ user จะปิด browser (แต่ SSE อาจจะหยุด)

send_sse_message(['status' => 'info', 'message' => 'เริ่มกระบวนการย้ายไฟล์...', 'icon' => 'hourglass-split', 'type' => 'info']);

$processed_files_count = 0;
$total_size_moved_bytes = 0;
$files_actually_processed_in_loop = 0; // สำหรับป้องกัน infinite loop

// Loop ย้ายไฟล์
// เงื่อนไขการหยุด loop:
// 1. ย้ายครบตามจำนวนไฟล์ที่กำหนด (ถ้ามีการกำหนด files_to_move_count_param)
// 2. ย้ายครบตามขนาดที่กำหนด (ถ้ามีการกำหนด size_to_move_bytes_param)
// 3. ไม่มีไฟล์เหลือให้ย้าย
// 4. เกิดข้อผิดพลาดร้ายแรง

$loop_limit = $files_to_move_count_param > 0 ? $files_to_move_count_param + 20 : 500; // เพิ่ม buffer หรือ limit สูงสุดถ้าไม่ได้ระบุจำนวนไฟล์

for ($i = 0; $i < $loop_limit; $i++) {
     $should_stop_by_count = ($files_to_move_count_param > 0 && $processed_files_count >= $files_to_move_count_param);
     $should_stop_by_size = ($size_to_move_bytes_param > 0 && $total_size_moved_bytes >= $size_to_move_bytes_param);

     if ($should_stop_by_count && $should_stop_by_size) { // ถ้ากำหนดทั้งสองอย่าง และถึงทั้งคู่
          send_sse_message(['status' => 'info', 'message' => 'ย้ายไฟล์ครบตามจำนวนและขนาดที่ระบุแล้ว', 'icon' => 'check-circle-fill', 'type' => 'success']);
          break;
     }
      if ($files_to_move_count_param > 0 && $should_stop_by_count && $size_to_move_bytes_param <=0) { // ถึงจำนวนไฟล์ และไม่ได้กำหนดขนาด
         send_sse_message(['status' => 'info', 'message' => "ย้ายไฟล์ครบตามจำนวนที่ระบุแล้ว ({$processed_files_count} ไฟล์)", 'icon' => 'check-circle-fill', 'type' => 'success']);
         break;
     }
     if ($size_to_move_bytes_param > 0 && $should_stop_by_size && $files_to_move_count_param <=0) { // ถึงขนาด และไม่ได้กำหนดจำนวนไฟล์
         send_sse_message(['status' => 'info', 'message' => "ย้ายไฟล์ครบตามขนาดที่ระบุแล้ว (" . formatBytes($total_size_moved_bytes) . ")", 'icon' => 'check-circle-fill', 'type' => 'success']);
         break;
     }


    $stmt = $pdo->query("SELECT id, filename FROM records WHERE file_location_type = 'local' ORDER BY created_at ASC LIMIT 1");
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) {
        send_sse_message(['status' => 'no_files', 'message' => 'ไม่พบไฟล์ที่อยู่ใน Local Server ที่สามารถย้ายได้อีกแล้ว', 'icon' => 'info-circle-fill', 'type' => 'info']);
        break;
    }

    $oldFilePath = $upload_dir . $row['filename'];
    $fileSize = file_exists($oldFilePath) ? filesize($oldFilePath) : 0;
     $files_actually_processed_in_loop++;

    if (file_exists($oldFilePath)) {
        send_sse_message(['status' => 'progress_detail', 'message' => "กำลังพยายามย้ายไฟล์: {$row['filename']} (" . formatBytes($fileSize) . ")", 'icon' => 'arrow-repeat', 'type' => 'primary']);
        $driveFileUrl = uploadToDrive($driveService, $oldFilePath, $row['filename']);

        if ($driveFileUrl) {
            $updateStmt = $pdo->prepare("UPDATE records SET drive_url = ?, local_path = NULL, file_location_type = 'drive' WHERE id = ?");
            $updateStmt->execute([$driveFileUrl, $row['id']]);
            if (file_exists($oldFilePath)) unlink($oldFilePath); // ตรวจสอบอีกครั้งก่อน unlink

            $processed_files_count++;
            $total_size_moved_bytes += $fileSize;
            send_sse_message([
                'status' => 'progress',
                'message' => "ย้ายไฟล์ '{$row['filename']}' สำเร็จ!",
                'icon' => 'check-lg',
                'type' => 'success',
                'moved_files_count' => $processed_files_count,
                'moved_size_this_session_bytes' => $total_size_moved_bytes,
                'total_size_to_move_bytes' => $size_to_move_bytes_param // ส่งค่านี้ไปให้ JS คำนวณ progress bar ถ้าใช้ขนาด
             ]);
        } else {
            send_sse_message(['status' => 'error_file', 'message' => "ไม่สามารถย้ายไฟล์ '{$row['filename']}' ได้ (โปรดตรวจสอบ Error Log ของ Server)", 'icon' => 'x-circle-fill', 'type' => 'danger']);
            // อาจจะ break หรือ continue ขึ้นอยู่กับนโยบาย
            // break; // หยุดถ้ามีปัญหา
        }
    } else {
        error_log("[Manual SSE Transfer] File {$row['filename']} (ID: {$row['id']}) not found. Marking as 'local_not_found'.");
        $fixStmt = $pdo->prepare("UPDATE records SET local_path = 'FILE_NOT_FOUND', file_location_type = 'local_not_found' WHERE id = ? AND (drive_url IS NULL OR drive_url = '')");
        $fixStmt->execute([$row['id']]);
        send_sse_message(['status' => 'warning_file', 'message' => "ไฟล์ '{$row['filename']}' ไม่พบบนเซิร์ฟเวอร์ (ถูกทำเครื่องหมายแล้ว)", 'icon' => 'exclamation-triangle', 'type' => 'warning']);
    }

    // หน่วงเวลาเล็กน้อย (ถ้าต้องการ) เพื่อไม่ให้ Server ทำงานหนักเกินไป หรือเพื่อให้ Client มีเวลา update UI
    usleep(100000); // 0.1 วินาที
}

 if ($files_actually_processed_in_loop === 0 && $i === 0) { // ถ้าวน loop แรกแล้วไม่เจอไฟล์เลย
      send_sse_message(['status' => 'no_files', 'message' => 'ไม่พบไฟล์ที่อยู่ใน Local Server ที่สามารถย้ายได้', 'icon' => 'info-circle-fill', 'type' => 'info']);
 } else if ($processed_files_count > 0) {
     send_sse_message(['status' => 'completed', 'message' => "กระบวนการย้ายไฟล์เสร็จสิ้น ย้ายไป {$processed_files_count} ไฟล์, ขนาดรวม " . formatBytes($total_size_moved_bytes) . ".", 'icon' => 'check-circle-fill', 'type' => 'success']);
 } else if ($files_to_move_count_param > 0 && $processed_files_count < $files_to_move_count_param && $files_actually_processed_in_loop >= $loop_limit) {
      send_sse_message(['status' => 'info', 'message' => 'ถึงขีดจำกัดการวนลูปแต่ยังย้ายไฟล์ไม่ครบตามจำนวนที่ระบุ อาจไม่มีไฟล์เหลือหรือเกิดปัญหา', 'icon' => 'info-circle-fill', 'type' => 'info']);
 } else if ($processed_files_count == 0 && $files_actually_processed_in_loop > 0){
      send_sse_message(['status' => 'info', 'message' => 'ไม่มีไฟล์ใดถูกย้ายในรอบนี้ (อาจจะเกิดข้อผิดพลาดกับไฟล์ที่พยายามย้าย)', 'icon' => 'info-circle-fill', 'type' => 'warning']);
 }


// ปิดการเชื่อมต่อ SSE โดยปริยายเมื่อ script จบ
exit;
?>
