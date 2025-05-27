<?php
header('Content-Type: application/json');

/* function sendTelegramMessage($botToken, $chatId, $message) {
    $url = "https://api.telegram.org/" . $botToken . "/sendMessage";
    $post_fields = [
        'chat_id' => $chatId,
        'text' => $message,
        'parse_mode' => 'HTML'
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_HTTPHEADER, ["Content-Type:multipart/form-data"]);
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $post_fields);
    $output = curl_exec($ch);
    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpcode == 200) {
        // error_log("Telegram notification sent successfully to chat_id: " . $chatId);
        return true;
    } else {
        // error_log("Failed to send Telegram notification to chat_id: " . $chatId . ". HTTP Code: " . $httpcode . " Response: " . $output);
        return false;
    }
} */

function sendTelegramNotification($botToken, $chatId, $message, $audioFilePath = null, $audioFilename = null, $audioDuration = null) {
    $post_fields = [
        'chat_id' => $chatId,
        'parse_mode' => 'HTML'
    ];

    if ($audioFilePath && file_exists($audioFilePath)) {
        $url = "https://api.telegram.org/" . $botToken . "/sendAudio";
        $post_fields['audio'] = new CURLFile(realpath($audioFilePath));
        $post_fields['caption'] = $message; // ข้อความจะกลายเป็น caption ของไฟล์เสียง
        if ($audioDuration) {
            $post_fields['duration'] = intval($audioDuration);
        }
        if ($audioFilename) {
            // อาจจะใช้ชื่อไฟล์เป็น title ของ audio track ได้ ถ้าต้องการ
            // $post_fields['title'] = pathinfo($audioFilename, PATHINFO_FILENAME);
        }
    } else {
        $url = "https://api.telegram.org/" . $botToken . "/sendMessage";
        $post_fields['text'] = $message;
    }

    $ch = curl_init();
    // ไม่จำเป็นต้องตั้ง HTTPHEADER Content-Type:multipart/form-data อีก เพราะ CURLFile จะจัดการให้เมื่อมีไฟล์
    // แต่ถ้าไม่มีไฟล์ การส่งแบบ multipart ก็ยังใช้ได้สำหรับ sendMessage
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $post_fields);
    // หาก Server ของคุณมีปัญหา SSL certificate validation ให้ลอง uncomment บรรทัดด้านล่าง (ไม่แนะนำสำหรับ production)
    // curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
    // curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, 0);

    $output = curl_exec($ch);
    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error_msg = curl_error($ch); // ดึงข้อความ error จาก cURL
    curl_close($ch);

    if ($httpcode == 200) {
        // error_log("Telegram notification sent successfully to chat_id: " . $chatId . ($audioFilePath ? " with audio." : "."));
        return true;
    } else {
        // error_log("Failed to send Telegram notification to chat_id: " . $chatId . ". HTTP Code: " . $httpcode . " Response: " . $output . " cURL Error: " . $error_msg);
        return false;
    }
}

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

$maxFolderSize = 5 * 1024 * 1024 * 1024; // 5 GB
$folder = $upload_dir;


// ถ้าโฟลเดอร์ vendor อยู่ในระดับเดียวกับ upload.php
//require_once __DIR__ . '/vendor/autoload.php';

// หรือถ้าอยู่ในตำแหน่งอื่น ก็ระบุ path ให้ถูกต้อง
// require_once '/path/to/your/project/vendor/autoload.php';

// --- เพิ่มการตั้งค่า Google API Client ---
// ถ้าโฟลเดอร์ vendor อยู่ในระดับเดียวกับ upload.php
require_once __DIR__ . '/vendor/autoload.php'; // ถ้าใช้ Composer

define('GOOGLE_APPLICATION_CREDENTIALS', __DIR__ . '/xxxxx-xxxxx-xxxxxxxxxx.json'); // << แก้ไข path ให้ถูกต้อง
define('GOOGLE_DRIVE_FOLDER_ID', 'xxxxxxxxxxxxxxxxxxxx'); // << แก้ไขเป็น ID ของโฟลเดอร์ใน Google Drive

function getGoogleClient() {
    $client = new Google_Client();
    $client->setApplicationName('PHP Drive Uploader');
    $client->setScopes(Google_Service_Drive::DRIVE_FILE); // หรือ Google_Service_Drive::DRIVE ถ้าต้องการจัดการ metadata มากขึ้น
    $client->setAuthConfig(GOOGLE_APPLICATION_CREDENTIALS);
    $client->setAccessType('offline');
    // $client->setPrompt('select_account consent'); // อาจจะไม่จำเป็นสำหรับ service account
    return $client;
}

function uploadToDrive($service, $filePath, $fileNameInDrive) {
    $fileMetadata = new Google_Service_Drive_DriveFile([
        'name' => $fileNameInDrive,
        'parents' => [GOOGLE_DRIVE_FOLDER_ID] // ระบุ Parent folder ID
		//'mimeType' => mime_content_type($filePath)
    ]);
    $content = file_get_contents($filePath);
	error_log("Attempting to create file on Drive. Name: " . $fileNameInDrive . ", Parent: " . GOOGLE_DRIVE_FOLDER_ID);
    try {
        $file = $service->files->create($fileMetadata, [
            'data' => $content,
            //'mimeType' => mime_content_type($filePath), // หรือระบุ mime type ที่ถูกต้อง
            'uploadType' => 'multipart'
            //'fields' => 'id, webViewLink' // ขอ id และ webViewLink กลับมา
        ]);
		if ($file && $file->id) { // ตรวจสอบว่าได้ file object และ id กลับมา
             error_log("File created on Drive. ID: " . $file->id);
             // ถ้าต้องการ webViewLink อาจจะต้องเรียก get เพิ่มเติมถ้าไม่ได้ระบุใน fields
             $fileWithLink = $service->files->get($file->id, ['fields' => 'webViewLink']);
             return $fileWithLink ? $fileWithLink->webViewLink : null;
        } else {
            error_log("Drive API create call did not return a valid file object or ID.");
            return null;
        }
        // return $file->getId(); // คืนค่า ID ของไฟล์ใน Drive
        return $file->webViewLink; // คืนค่า URL สำหรับดูไฟล์
    } catch (Google_Service_Exception $e) { // ดักจับ Exception ของ Google โดยเฉพาะ
        $errors = $e->getErrors();
        $errorMessage = "Google Service Exception: " . $e->getMessage();
        if (!empty($errors)) {
            $errorMessage .= " | Errors: " . json_encode($errors);
        }
        error_log($errorMessage);
        return null;
    } catch (Exception $e) {
        // จัดการ error, อาจจะ log ไว้
        error_log("Error uploading to Drive: " . $e->getMessage());
        return null;
    }
}

// เชื่อมต่อฐานข้อมูล
require 'db_config.php'; // สำหรับ $pdo

// ตรวจสอบขนาดโฟลเดอร์ และเคลียร์โฟลเดอร์เก่าเมื่อเต็ม
/* while (getFolderSize($folder) > $maxSize) {
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
} */

// ตรวจสอบขนาดโฟลเดอร์ และจัดการไฟล์เก่าเมื่อเต็ม
$currentFolderSize = getFolderSize($folder);
if ($currentFolderSize > $maxFolderSize) { // เปลี่ยนจาก while เป็น if ก็พอ เพราะเราจะเช็คก่อนอัปโหลดไฟล์ใหม่
    $googleClient = getGoogleClient();
    $driveService = new Google_Service_Drive($googleClient);

    // คำนวณพื้นที่ที่ต้องเคลียร์ (อาจจะไม่จำเป็นต้องเป๊ะๆ แค่เคลียร์ไฟล์เก่าออกจนกว่าจะมีที่พอ)
    // $spaceToClear = $currentFolderSize - $maxSize + $_FILES['audio']['size']; // ประมาณการพื้นที่ที่ต้องการ

    // ดึงรายการไฟล์ที่เก่าที่สุดมาจัดการ
    // เปลี่ยน logic เป็นการวนลูปจนกว่าขนาดโฟลเดอร์จะน้อยกว่า maxSize
    while (getFolderSize($folder) > $maxFolderSize) {
        //$stmt = $pdo->query("SELECT * FROM records WHERE drive_url IS NULL OR drive_url = '' ORDER BY created_at ASC LIMIT 1"); // ดึงเฉพาะไฟล์ที่ยังไม่ได้ย้าย
		//$stmt = $pdo->query("SELECT * FROM records WHERE (drive_url IS NULL OR drive_url = '') AND (local_path IS NOT NULL AND local_path != 'FILE_NOT_FOUND') ORDER BY created_at ASC LIMIT 1");
		$stmt = $pdo->query("SELECT * FROM records WHERE file_location_type = 'local' ORDER BY created_at ASC LIMIT 1");
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            // ไม่มีไฟล์ที่ยังไม่ได้ย้ายไป Drive แต่ขนาดโฟลเดอร์ยังคงเกิน
            // อาจจะต้องมี logic เพิ่มเติม เช่น แจ้งเตือน admin หรือหยุดการอัปโหลดชั่วคราว
            error_log("Folder size still exceeds limit, but no local files found to move to Drive.");
            // คุณอาจจะเลือกที่จะลบไฟล์ที่เก่าที่สุดที่อยู่บน Drive ออก (ถ้าจำเป็นจริงๆ และมี logic ที่ซับซ้อนขึ้น)
            // หรือ แจ้ง error กลับไปให้ผู้ใช้ว่าไม่สามารถอัปโหลดได้ชั่วคราว
            // ในที่นี้จะ break ออกจาก loop ไปก่อน
            break;
        }

        $oldFilePath = $upload_dir . $row['filename'];

        if (file_exists($oldFilePath)) {
            $fileNameInDrive = $row['filename']; // หรือจะตั้งชื่อใหม่ใน Drive ก็ได้
            $driveFileUrl = uploadToDrive($driveService, $oldFilePath, $fileNameInDrive);

            if ($driveFileUrl) {
                // อัปเดตฐานข้อมูลด้วย Google Drive URL
                $updateStmt = $pdo->prepare("UPDATE records SET drive_url = ?, local_path = NULL, file_location_type = 'drive' WHERE id = ?"); // เก็บ drive_url และล้าง local_path (ถ้ามี)
                $updateStmt->execute([$driveFileUrl, $row['id']]);

                // ลบไฟล์ออกจากเซิร์ฟเวอร์หลังจากอัปโหลดสำเร็จ
                unlink($oldFilePath);
                error_log("Moved {$row['filename']} to Google Drive and deleted from local server.");
            } else {
                // ถ้าอัปโหลดไป Drive ไม่สำเร็จ อาจจะยังไม่ลบไฟล์ หรือ log error ไว้
                error_log("Failed to move {$row['filename']} to Google Drive. File remains on local server.");
                // อาจจะต้อง break loop เพื่อป้องกันการวนซ้ำไฟล์เดิมที่ไม่สำเร็จ
                break;
            }
        } else {
            // ไฟล์ไม่มีใน local server แต่ยังมี record ใน DB (อาจจะเกิดจากความผิดพลาดก่อนหน้า)
            // อาจจะแค่ update record ว่าไฟล์หายไป หรือลบ record นั้นทิ้ง
            error_log("File {$row['filename']} not found on local server for record ID {$row['id']}. Skipping move.");
            // พิจารณาอัปเดต record ใน DB เพื่อไม่ให้ถูกเลือกมาอีก
            //$fixStmt = $pdo->prepare("UPDATE records SET local_path = 'FILE_NOT_FOUND' WHERE id = ?"); // ตัวอย่างการ mark
			$fixStmt = $pdo->prepare("UPDATE records SET local_path = 'FILE_NOT_FOUND', file_location_type = 'local_not_found' WHERE id = ? AND (drive_url IS NULL OR drive_url = '')"); // เพิ่ม file_location_type
            $fixStmt->execute([$row['id']]);
			// ลดขนาดโฟลเดอร์จำลอง (ถ้าไฟล์นี้ถูกนับรวมใน getFolderSize โดยอิงจาก DB)
			// หรือถ้า getFolderSize นับจากไฟล์จริง ก็ไม่ต้องทำอะไรเพิ่มตรงนี้
			// แต่ควรให้ loop ไปต่อเพื่อเคลียร์ไฟล์อื่น
			error_log("Marked record ID {$row['id']} as FILE_NOT_FOUND. Continuing to next file if folder still full.");
			continue; // <--- เพิ่มบรรทัดนี้ เพื่อให้ไปเริ่มรอบใหม่ของ while loop และ query ไฟล์ถัดไป
        }
    }
}

// ตรวจสอบไฟล์และข้อมูลที่ส่งมา
if (!isset($_FILES['audio']) || $_FILES['audio']['error'] !== UPLOAD_ERR_OK || !isset($_POST['transcript'])) {
    http_response_code(400);
    echo json_encode(['status'=>'error','message'=>'Missing or invalid upload data']);
    exit;
}

// --- เช็คขนาดไฟล์ ไม่เกิน 5 MB ---
$maxUploadFileSize = 5 * 1024 * 1024;  // 5 MB
if ($_FILES['audio']['size'] > $maxUploadFileSize) {
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
$allowed_ext = ['mp3','wav'];
if (!in_array($ext, $allowed_ext)) {
    http_response_code(415);
    echo json_encode(['status'=>'error','message'=>"Unsupported file extension .{$ext}"]);
    exit;
}

// 2. ตรวจ MIME type
$finfo = new finfo(FILEINFO_MIME_TYPE);
$mime  = $finfo->file($_FILES['audio']['tmp_name']);
$allowed_mime = ['audio/mpeg','audio/wav','audio/x-wav'];
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
/* $stmt = $pdo->prepare("
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
]); */
// แก้ไข SQL INSERT ให้รองรับ local_path หรือ file_location_type
$stmt = $pdo->prepare("
    INSERT INTO records (station, frequency, filename, transcript, source, duration, created_at, local_path, file_location_type)
    VALUES (?,?,?,?,?,?,NOW(),?,?)
"); // เพิ่ม local_path ชั่วคราว
$stmt->execute([
    $station,
    $frequency,
    $filename, // ชื่อไฟล์ที่เก็บใน local
    $transcript,
    $source,
    $duration,
    $filename, // หรือ $target ถ้าต้องการ path เต็มใน local_path
	'local'
]);

$lastInsertId = $pdo->lastInsertId();
// --- ตรวจสอบ Keyword และส่ง Telegram จากฐานข้อมูล ---
$trimmedTranscript = trim($transcript);

if (!empty($trimmedTranscript)) {
	$configStmt = $pdo->prepare("SELECT keyword, bot_token, chat_id, custom_message_prefix, except_keywords FROM telegram_notifications_config WHERE is_active = TRUE"); // เพิ่ม except_keywords
	$configStmt->execute();
	$notificationConfigs = $configStmt->fetchAll(PDO::FETCH_ASSOC);

    foreach ($notificationConfigs as $config) {
		$triggerNotification = false;
		
		// 1. ตรวจสอบว่า Keyword หลักอยู่ใน Transcript หรือไม่ (case-insensitive)
		if (stripos($trimmedTranscript, $config['keyword']) !== false) {
			$triggerNotification = true; // ตั้งค่าเริ่มต้นว่าให้ส่ง

			// 2. ตรวจสอบ "คำที่ยกเว้น" (ถ้ามี)
			if (!empty($config['except_keywords'])) {
				$exceptions = [];
				// สมมติว่าเก็บเป็น JSON array ใน DB
				$decoded_exceptions = json_decode($config['except_keywords'], true);
				if (is_array($decoded_exceptions)) {
					$exceptions = $decoded_exceptions;
				} else {
					// ถ้าเก็บเป็นสตริงคั่นด้วยจุลภาค (หรือรูปแบบอื่นที่ json_decode ไม่ได้)
					// ให้ explode หรือ preg_split ตามรูปแบบที่คุณใช้
					$exceptions = array_map('trim', explode(',', $config['except_keywords']));
				}

				if (!empty($exceptions)) {
					foreach ($exceptions as $except_phrase) {
						if (!empty($except_phrase) && stripos($trimmedTranscript, $except_phrase) !== false) {
							// ถ้าพบคำที่ยกเว้นใดๆ ใน Transcript
							$triggerNotification = false; // ไม่ต้องส่งแจ้งเตือน
							error_log("Notification for keyword '{$config['keyword']}' skipped due to exception phrase: '{$except_phrase}' in transcript: '{$trimmedTranscript}'");
							break; // ออกจาก loop ของ except_keywords ได้เลย
						}
					}
				}
			}
		}

		if ($triggerNotification) {
			$captionText = ""; // ข้อความที่จะใช้เป็น caption หรือ text message
			if (!empty($config['custom_message_prefix'])) {
				$captionText .= htmlspecialchars($config['custom_message_prefix']) . "\n\n";
			} else {
				$captionText .= "⚠️ <b>แจ้งเตือน Keyword!</b> ⚠️\n\n";
			}

			$captionText .= "<b>Keyword พบ:</b> " . htmlspecialchars($config['keyword']) . "\n";
			$captionText .= "<b>ข้อความ:</b> " . htmlspecialchars($trimmedTranscript) . "\n";
			$captionText .= "<b>ไฟล์:</b> " . htmlspecialchars($filename) . "\n";
			$captionText .= "<b>สถานี:</b> " . htmlspecialchars($station) . "\n";
			$captionText .= "<b>ความถี่:</b> " . htmlspecialchars($frequency) . "\n";
			// $captionText .= "<b>ลิงก์:</b> https://yourwebsite.com/view_record.php?id=" . $lastInsertId . "\n";

			// ส่งการแจ้งเตือนพร้อมไฟล์เสียง
			// $target คือ path เต็มของไฟล์เสียงที่อัปโหลดและบันทึกไว้บนเซิร์ฟเวอร์
			// $filename คือชื่อไฟล์
			// $duration คือระยะเวลาของไฟล์เสียง (ควรเป็น integer)
			sendTelegramNotification(
				$config['bot_token'],
				$config['chat_id'],
				$captionText,
				$target, // Path ไปยังไฟล์เสียง
				$filename, // ชื่อไฟล์ (สำหรับ metadata ถ้า API รองรับ)
				$duration  // ระยะเวลาไฟล์เสียง (เป็นวินาที)
			);
		}
    }
}
// --- สิ้นสุดส่วน Telegram ---

echo json_encode(['status'=>'ok','filename'=>$filename, 'record_id' => $lastInsertId]);

?>
