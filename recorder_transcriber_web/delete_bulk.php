<?php
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

if (!isset($_POST['ids']) || !isset($_POST['files'])) {
    echo json_encode(['success' => false, 'error' => 'Missing parameters']);
    exit;
}

$ids = $_POST['ids'];
$files = $_POST['files'];

if (!is_array($ids) || !is_array($files) || count($ids) !== count($files)) {
    echo json_encode(['success' => false, 'error' => 'Invalid data']);
    exit;
}

session_start();
if (!($_SESSION['logged_in'] ?? false)) {
    echo json_encode(['success' => false, 'error' => 'คุณต้องเข้าสู่ระบบก่อน']);
    exit;
}


try {
    require 'db_config.php'; // สำหรับ $pdo

    $pdo->beginTransaction();

    foreach ($ids as $i => $id) {
        $filename = basename($files[$i]); // ป้องกัน path injection
        $filePath = __DIR__ . "/audio_files/" . $filename;

        if (file_exists($filePath)) {
            unlink($filePath);
        }

        $stmt = $pdo->prepare("DELETE FROM records WHERE id = ?");
        $stmt->execute([$id]);
    }

    $pdo->commit();

    echo json_encode(['success' => true]);
} catch (Exception $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
