<?php
session_start();

// 1. ตรวจสอบการ Login
if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
    die("กรุณาเข้าสู่ระบบก่อน <a href='login.php'>เข้าสู่ระบบ</a>");
}

// 2. Include ไฟล์ที่จำเป็น (db_config, Google Client Library)
require 'db_config.php';
require_once __DIR__ . '/vendor/autoload.php'; // สำหรับ Google API Client

define('GOOGLE_APPLICATION_CREDENTIALS', __DIR__ . '/xxxxx-xxxxx-xxxxxxxxxx.json');
define('GOOGLE_DRIVE_FOLDER_ID', 'xxxxxxxxxxxxxxxxxxxx'); // แก้ไขตาม Folder ID ของคุณ

$upload_dir = __DIR__ . '/audio_files/';
$folder = $upload_dir;
$message = '';
$processed_files_count = 0;
$total_size_moved = 0;

// ฟังก์ชันที่ใช้ร่วมกัน (อาจจะย้ายไปไฟล์ helper ถ้าใช้หลายที่)
function getFolderSize($dir) {
    $size = 0;
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, RecursiveDirectoryIterator::SKIP_DOTS)) as $file) {
        if ($file->isFile()) {
            $size += $file->getSize();
        }
    }
    return $size;
}

function formatBytes($bytes, $precision = 2) {
    $units = ['B', 'KB', 'MB', 'GB', 'TB'];
    $bytes = max($bytes, 0);
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= (1 << (10 * $pow));
    return round($bytes, $precision) . ' ' . $units[$pow];
}

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

// 3. การจัดการ Action (เมื่อผู้ใช้กดปุ่ม "เริ่มการย้ายไฟล์")
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'move_files') {
    $files_to_move_count = isset($_POST['files_to_move']) ? intval($_POST['files_to_move']) : 0;
    $size_to_move_mb = isset($_POST['size_to_move_mb']) ? floatval($_POST['size_to_move_mb']) : 0; // ขนาดที่ต้องการย้าย (MB)
    $size_to_move_bytes = $size_to_move_mb * 1024 * 1024;

    if ($files_to_move_count <= 0 && $size_to_move_bytes <= 0) {
        $message = "<div class='alert alert-warning'>กรุณาระบุจำนวนไฟล์ หรือ ขนาดรวมที่ต้องการย้าย</div>";
    } else {
        $googleClient = getGoogleClient();
        if (!$googleClient) {
            $message = "<div class='alert alert-danger'>ไม่สามารถเชื่อมต่อ Google Client ได้ กรุณาตรวจสอบการตั้งค่า</div>";
        } else {
            $driveService = new Google_Service_Drive($googleClient);
            $moved_files_this_session = 0;
            $moved_size_this_session = 0;

            // ตั้งค่า PHP time limit เพิ่มขึ้นสำหรับ script นี้โดยเฉพาะ
            // อาจจะต้องปรับค่าตามความเหมาะสม หรือใช้วิธีอื่นถ้า script นานเกินไปมากๆ เช่น cron job
            set_time_limit(300); // 5 นาที (ปรับได้)

            $message .= "<div class='alert alert-info'>เริ่มกระบวนการย้ายไฟล์...</div>";

            // ลูปตามจำนวนไฟล์ หรือจนกว่าขนาดที่ย้ายจะถึงเป้าหมาย (เลือกอย่างใดอย่างหนึ่ง หรือทั้งสอง)
            // ในตัวอย่างนี้จะเน้นที่จำนวนไฟล์ก่อน
            for ($i = 0; $i < $files_to_move_count || ($size_to_move_bytes > 0 && $moved_size_this_session < $size_to_move_bytes) ; $i++) {
                if ($files_to_move_count > 0 && $moved_files_this_session >= $files_to_move_count) {
                    $message .= "<div class='alert alert-info'>ย้ายไฟล์ครบตามจำนวนที่ระบุแล้ว ({$moved_files_this_session} ไฟล์)</div>";
                    break; // ออกจาก loop ถ้าถึงจำนวนไฟล์ที่ต้องการแล้ว
                }
                if ($size_to_move_bytes > 0 && $moved_size_this_session >= $size_to_move_bytes) {
                    $message .= "<div class='alert alert-info'>ย้ายไฟล์ครบตามขนาดที่ระบุแล้ว (" . formatBytes($moved_size_this_session) . ")</div>";
                    break; // ออกจาก loop ถ้าถึงขนาดที่ต้องการแล้ว
                }


                $stmt = $pdo->query("SELECT * FROM records WHERE file_location_type = 'local' ORDER BY created_at ASC LIMIT 1");
                $row = $stmt->fetch(PDO::FETCH_ASSOC);

                if (!$row) {
                    $message .= "<div class='alert alert-warning'>ไม่พบไฟล์ที่อยู่ใน Local Server ที่สามารถย้ายได้อีกแล้ว</div>";
                    break;
                }

                $oldFilePath = $upload_dir . $row['filename'];
                $fileSize = file_exists($oldFilePath) ? filesize($oldFilePath) : 0;

                if (file_exists($oldFilePath)) {
                    error_log("[Manual Transfer] Attempting to move: {$row['filename']}");
                    $driveFileUrl = uploadToDrive($driveService, $oldFilePath, $row['filename']);

                    if ($driveFileUrl) {
                        $updateStmt = $pdo->prepare("UPDATE records SET drive_url = ?, local_path = NULL, file_location_type = 'drive' WHERE id = ?");
                        $updateStmt->execute([$driveFileUrl, $row['id']]);
                        unlink($oldFilePath);

                        $processed_files_count++;
                        $total_size_moved += $fileSize;
                        $moved_files_this_session++;
                        $moved_size_this_session += $fileSize;
                        $message .= "<div class='alert alert-success'>ย้ายไฟล์ '{$row['filename']}' (" . formatBytes($fileSize) . ") ไปยัง Google Drive สำเร็จ</div>";
                    } else {
                        $message .= "<div class='alert alert-danger'>ไม่สามารถย้ายไฟล์ '{$row['filename']}' ไปยัง Google Drive ได้ กรุณาตรวจสอบ Error Log</div>";
                        // อาจจะ break หรือ continue ขึ้นอยู่กับว่าต้องการให้หยุดเลยหรือไม่
                        // error_log("[Manual Transfer] Failed to move {$row['filename']} to Google Drive. File remains on local server.");
                        break; // หยุดถ้ามีปัญหา
                    }
                } else {
                    error_log("[Manual Transfer] File {$row['filename']} (ID: {$row['id']}) not found on local server. Marking as 'local_not_found'.");
                    $fixStmt = $pdo->prepare("UPDATE records SET local_path = 'FILE_NOT_FOUND', file_location_type = 'local_not_found' WHERE id = ? AND (drive_url IS NULL OR drive_url = '')");
                    $fixStmt->execute([$row['id']]);
                    $message .= "<div class='alert alert-warning'>ไฟล์ '{$row['filename']}' ไม่พบบนเซิร์ฟเวอร์ ถูกทำเครื่องหมายแล้ว</div>";
                    // ไม่นับเป็นการย้ายสำเร็จ และอาจจะต้องการให้ loop for ทำงานอีกครั้งเพื่อหาไฟล์อื่น (ลด i)
                    $i--; // ชดเชยรอบนี้ที่ไฟล์ไม่มีจริง
                }
                 // ป้องกันการวนซ้ำไม่รู้จบหากมีปัญหาบางอย่าง
                if ($i > $files_to_move_count + 10 && $files_to_move_count > 0) { // เพิ่ม buffer เล็กน้อย
                    $message .= "<div class='alert alert-danger'>มีการวนซ้ำมากเกินไป อาจมีปัญหาในการดึงไฟล์ กรุณาตรวจสอบ</div>";
                    break;
                }
            }
            if ($moved_files_this_session == 0 && $files_to_move_count > 0) {
                 $message .= "<div class='alert alert-info'>ไม่มีย้ายไฟล์ใดๆ ในรอบนี้ (อาจไม่มีไฟล์เหลือให้ย้าย หรือถึงจำนวนที่กำหนดแล้ว)</div>";
            }

        }
    }
}

// ดึงขนาดโฟลเดอร์ปัจจุบัน
$currentLocalFolderSize = getFolderSize($folder);

?>
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>จัดการย้ายไฟล์ไป Google Drive</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .container { max-width: 800px; }
    </style>
</head>
<body>
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h1><i class="bi bi-google"></i> จัดการย้ายไฟล์ไป Google Drive (Manual)</h1>
            <div>
                <a href="index.php" class="btn btn-outline-secondary"><i class="bi bi-arrow-left-circle"></i> กลับหน้าหลัก</a>
                <a href="logout.php" class="btn btn-outline-danger">ออกจากระบบ</a>
            </div>
        </div>

        <?php if ($message) echo $message; ?>

        <div class="card mb-4">
            <div class="card-body">
                <h5 class="card-title">สถานะโฟลเดอร์ Local ปัจจุบัน</h5>
                <p>ขนาดรวมของไฟล์ในโฟลเดอร์ <code>audio_files/</code>: <strong><?php echo formatBytes($currentLocalFolderSize); ?></strong></p>
                <?php
                $stmt_local_count = $pdo->query("SELECT COUNT(*) FROM records WHERE file_location_type = 'local'");
                $local_files_db_count = $stmt_local_count->fetchColumn();
                ?>
                <p>จำนวนไฟล์ที่ระบุว่าอยู่ 'local' ในฐานข้อมูล: <strong><?php echo $local_files_db_count; ?> ไฟล์</strong></p>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                เริ่มการย้ายไฟล์
            </div>
            <div class="card-body">
                <form action="manual_drive_transfer.php" method="POST">
                    <input type="hidden" name="action" value="move_files">
                    <div class="mb-3">
                        <label for="files_to_move" class="form-label">จำนวนไฟล์ที่ต้องการย้าย (ไฟล์ที่เก่าที่สุดก่อน):</label>
                        <input type="number" class="form-control" id="files_to_move" name="files_to_move" min="0" placeholder="เช่น 100">
                    </div>
                    <div class="mb-3">
                        <label for="size_to_move_mb" class="form-label">หรือ ขนาดรวมสูงสุดที่ต้องการย้าย (MB):</label>
                        <input type="number" step="any" class="form-control" id="size_to_move_mb" name="size_to_move_mb" min="0" placeholder="เช่น 500 (สำหรับ 500MB)">
                        <small class="form-text text-muted">ระบบจะพยายามย้ายไฟล์จนกว่าจะถึงจำนวนไฟล์หรือขนาดที่ระบุ (อย่างใดอย่างหนึ่งถึงก่อน)</small>
                    </div>
                    <button type="submit" class="btn btn-primary w-100"><i class="bi bi-cloud-upload"></i> เริ่มการย้ายไฟล์ไป Google Drive</button>
                </form>
            </div>
            <?php if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($processed_files_count > 0 || $total_size_moved > 0)): ?>
            <div class="card-footer">
                <strong>ผลลัพธ์การย้ายรอบนี้:</strong>
                <p>จำนวนไฟล์ที่ย้ายสำเร็จ: <?php echo $processed_files_count; ?> ไฟล์</p>
                <p>ขนาดรวมที่ย้ายสำเร็จ: <?php echo formatBytes($total_size_moved); ?></p>
            </div>
            <?php endif; ?>
        </div>
    </div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
