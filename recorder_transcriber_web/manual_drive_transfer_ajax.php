<?php
session_start();

if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
    die("กรุณาเข้าสู่ระบบก่อน <a href='login.php'>เข้าสู่ระบบ</a>");
}

require 'db_config.php'; // สำหรับดึงข้อมูลบางอย่าง เช่น ขนาดโฟลเดอร์

$upload_dir = __DIR__ . '/audio_files/';
$folder = $upload_dir;

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

$currentLocalFolderSize = getFolderSize($folder);
$stmt_local_count = $pdo->query("SELECT COUNT(*) FROM records WHERE file_location_type = 'local'");
$local_files_db_count = $stmt_local_count->fetchColumn();
?>
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>จัดการย้ายไฟล์ไป Google Drive (Manual - AJAX)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .container { max-width: 800px; }
        #progress-log {
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid #ccc;
            padding: 10px;
            margin-top: 15px;
            background-color: #f8f9fa;
        }
        #progress-log p { margin-bottom: 0.5rem; }
    </style>
</head>
<body>
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h1><i class="bi bi-google"></i> จัดการย้ายไฟล์ไป Google Drive (AJAX)</h1>
            <div>
                <a href="index.php" class="btn btn-outline-secondary"><i class="bi bi-arrow-left-circle"></i> กลับหน้าหลัก</a>
                <a href="logout.php" class="btn btn-outline-danger">ออกจากระบบ</a>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-body">
                <h5 class="card-title">สถานะโฟลเดอร์ Local ปัจจุบัน</h5>
                <p>ขนาดรวมของไฟล์ในโฟลเดอร์ <code>audio_files/</code>: <strong><?php echo formatBytes($currentLocalFolderSize); ?></strong></p>
                <p>จำนวนไฟล์ที่ระบุว่าอยู่ 'local' ในฐานข้อมูล: <strong><?php echo $local_files_db_count; ?> ไฟล์</strong></p>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                เริ่มการย้ายไฟล์
            </div>
            <div class="card-body">
                <form id="moveFilesForm">
                    <div class="mb-3">
                        <label for="files_to_move" class="form-label">จำนวนไฟล์ที่ต้องการย้าย (ไฟล์ที่เก่าที่สุดก่อน):</label>
                        <input type="number" class="form-control" id="files_to_move" name="files_to_move" min="0" placeholder="เช่น 100">
                    </div>
                    <div class="mb-3">
                        <label for="size_to_move_mb" class="form-label">หรือ ขนาดรวมสูงสุดที่ต้องการย้าย (MB):</label>
                        <input type="number" step="any" class="form-control" id="size_to_move_mb" name="size_to_move_mb" min="0" placeholder="เช่น 500 (สำหรับ 500MB)">
                        <small class="form-text text-muted">ระบบจะพยายามย้ายไฟล์จนกว่าจะถึงจำนวนไฟล์หรือขนาดที่ระบุ (อย่างใดอย่างหนึ่งถึงก่อน หรือทั้งสองอย่าง)</small>
                    </div>
                    <button type="submit" class="btn btn-primary w-100" id="startMoveBtn"><i class="bi bi-cloud-upload"></i> เริ่มการย้ายไฟล์ไป Google Drive</button>
                </form>
                <div id="progress-log" class="d-none">
                    <h5><i class="bi bi-activity"></i> สถานะการทำงาน:</h5>
                    <div id="log-messages"></div>
                    <div class="progress mt-2 d-none" id="progressBarContainer">
                        <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
$(document).ready(function() {
    $('#moveFilesForm').on('submit', function(e) {
        e.preventDefault();
        const filesToMove = $('#files_to_move').val();
        const sizeToMoveMb = $('#size_to_move_mb').val();

        if ((!filesToMove || filesToMove <= 0) && (!sizeToMoveMb || sizeToMoveMb <= 0)) {
            alert('กรุณาระบุจำนวนไฟล์ หรือ ขนาดรวมที่ต้องการย้าย');
            return;
        }

        $('#startMoveBtn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> กำลังประมวลผล...');
        $('#progress-log').removeClass('d-none');
        $('#log-messages').html(''); // Clear previous logs
        $('#progressBarContainer').removeClass('d-none');
        $('#progressBar').css('width', '0%').attr('aria-valuenow', 0).text('0%');


        const params = new URLSearchParams();
        if (filesToMove && filesToMove > 0) {
            params.append('files_to_move', filesToMove);
        }
        if (sizeToMoveMb && sizeToMoveMb > 0) {
            params.append('size_to_move_mb', sizeToMoveMb);
        }

        // ใช้ EventSource (Server-Sent Events)
        const eventSource = new EventSource('process_drive_transfer.php?' + params.toString());
         let totalFilesToProcess = parseInt(filesToMove) || 0; // หากระบุจำนวนไฟล์ จะใช้เป็นตัวนับ progress
         let filesProcessed = 0;

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            let logHtml = `<p class="text-${data.type || 'muted'}">`;
            if(data.icon) logHtml += `<i class="bi bi-${data.icon} me-1"></i>`;
            logHtml += `[${new Date().toLocaleTimeString()}] ${data.message}</p>`;
            $('#log-messages').append(logHtml);
            $('#progress-log').scrollTop($('#progress-log')[0].scrollHeight); // Auto-scroll

             if (data.status === 'progress') {
                 filesProcessed++;
                 if (totalFilesToProcess > 0) {
                     const percentage = Math.min(100, Math.round((filesProcessed / totalFilesToProcess) * 100));
                     $('#progressBar').css('width', percentage + '%').attr('aria-valuenow', percentage).text(percentage + '%');
                 } else if (data.total_size_to_move_bytes && data.moved_size_this_session_bytes) {
                     // ถ้าใช้ขนาดเป็นตัวนับ progress (ซับซ้อนกว่าเล็กน้อย เพราะขนาดไฟล์ไม่เท่ากัน)
                     const percentage = Math.min(100, Math.round((data.moved_size_this_session_bytes / data.total_size_to_move_bytes) * 100));
                      $('#progressBar').css('width', percentage + '%').attr('aria-valuenow', percentage).text(percentage + '%');
                 }
             }


            if (data.status === 'completed' || data.status === 'error' || data.status === 'no_files') {
                eventSource.close();
                $('#startMoveBtn').prop('disabled', false).html('<i class="bi bi-cloud-upload"></i> เริ่มการย้ายไฟล์ไป Google Drive');
                 if (data.status === 'completed') {
                     $('#progressBar').css('width', '100%').attr('aria-valuenow', 100).text('100%').removeClass('progress-bar-animated').addClass('bg-success');
                 } else if (data.status === 'error') {
                      $('#progressBar').removeClass('progress-bar-animated').addClass('bg-danger');
                 }
                // อาจจะมีการ reload ข้อมูลสถานะโฟลเดอร์
                setTimeout(function() { window.location.reload(); }, 3000); // Reload หน้าเพื่อดูสถานะล่าสุด
            }
        };

        eventSource.onerror = function(err) {
            $('#log-messages').append('<p class="text-danger">เกิดข้อผิดพลาดในการเชื่อมต่อกับเซิร์ฟเวอร์ (SSE Error)</p>');
            $('#startMoveBtn').prop('disabled', false).html('<i class="bi bi-cloud-upload"></i> เริ่มการย้ายไฟล์ไป Google Drive');
            eventSource.close();
        };
    });
});
</script>
</body>
</html>
