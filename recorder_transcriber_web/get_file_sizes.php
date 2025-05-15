<?php
header('Content-Type: application/json');

if (!isset($_POST['files']) || !is_array($_POST['files'])) {
    echo json_encode(['success' => false]);
    exit;
}

$total = 0;
foreach ($_POST['files'] as $file) {
    $path = __DIR__ . '/audio_files/' . basename($file);
    if (file_exists($path)) {
        $total += filesize($path);
    }
}

echo json_encode(['success' => true, 'total_size' => $total]);
