<?php
require 'db_config.php';
header('Content-Type: application/json');

$id  = $_POST['id']  ?? '';
$note = $_POST['note'] ?? '';
if (!$id) {
  echo json_encode(['success'=>false,'error'=>'Missing id']); exit;
}

$stmt = $pdo->prepare("UPDATE records SET note = :note WHERE id = :id");
$res  = $stmt->execute([':note'=>$note,':id'=>$id]);

echo json_encode(['success'=> $res]);
