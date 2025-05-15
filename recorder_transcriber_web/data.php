<?php
session_start();

require 'db_config.php';

$loggedIn = $_SESSION['logged_in'] ?? false;

$draw = $_POST['draw'] ?? 1;
$start = $_POST['start'] ?? 0;
$length = $_POST['length'] ?? 100;
$search = $_POST['search']['value'] ?? '';
$orderCol = $_POST['order'][0]['column'] ?? 1;
$orderDir = $_POST['order'][0]['dir'] ?? 'desc';
$dateFrom = $_POST['dateFrom'] ?? '';
$dateTo = $_POST['dateTo'] ?? '';

$source = $_POST['source'] ?? '';
if (!empty($source)) {
    $where .= " AND source = :source";
    $params[':source'] = $source;
}

$columns = ['id', 'created_at', 'filename', 'transcript', 'source', 'frequency', 'station'];
$orderBy = $columns[$orderCol] ?? 'created_at';

$where = '1';
$params = [];

if (!empty($search)) {
    $where .= " AND (transcript LIKE :search OR filename LIKE :search)";
    $params[':search'] = "%$search%";
}

if (!empty($dateFrom) && !empty($dateTo)) {
    $where .= " AND DATE(created_at) BETWEEN :dateFrom AND :dateTo";
    $params[':dateFrom'] = $dateFrom;
    $params[':dateTo'] = $dateTo;
} elseif (!empty($dateFrom)) {
    $where .= " AND DATE(created_at) >= :dateFrom";
    $params[':dateFrom'] = $dateFrom;
} elseif (!empty($dateTo)) {
    $where .= " AND DATE(created_at) <= :dateTo";
    $params[':dateTo'] = $dateTo;
}

$sql = "SELECT * FROM records WHERE $where ORDER BY $orderBy $orderDir LIMIT :start, :length";
$countSql = "SELECT COUNT(*) FROM records WHERE $where";

$stmt = $pdo->prepare($sql);
$countStmt = $pdo->prepare($countSql);

foreach ($params as $key => $val) {
    $stmt->bindValue($key, $val);
    $countStmt->bindValue($key, $val);
}

$stmt->bindValue(':start', (int)$start, PDO::PARAM_INT);
$stmt->bindValue(':length', (int)$length, PDO::PARAM_INT);

$stmt->execute();
$data = $stmt->fetchAll(PDO::FETCH_ASSOC);
$countStmt->execute();
$recordsFiltered = $countStmt->fetchColumn();

$totalCount = $pdo->query("SELECT COUNT(*) FROM records")->fetchColumn();

echo json_encode([
    "draw" => intval($draw),
    "recordsTotal" => $totalCount,
    "recordsFiltered" => $recordsFiltered,

		"data" => array_map(function($r) use ($loggedIn) {
			$file = htmlspecialchars($r['filename']);
			$audio = "<audio controls preload='none'><source src='audio_files/$file' type='audio/wav'>ไม่รองรับ</audio>";
			$download = "<br><a href='audio_files/$file' download>📥 ดาวน์โหลด</a>";

			$checkbox = '<input type="checkbox" class="row-checkbox" value="'.$r['id'].'" data-file="'.$file.'">';

			$deleteBtn = $loggedIn
				? '<button class="btn btn-sm btn-danger delete-btn" data-id="'.$r['id'].'" data-file="'.$file.'"><i class="bi bi-trash-fill"></i> ลบ</button>'
				: '<button class="btn btn-sm btn-secondary unauth"><i class="bi bi-lock-fill"></i> ลบ</button>';

			return [
				$checkbox,
				$r['id'],
				$r['created_at'],
				$r['station'],
				$r['frequency'],
				$audio . $download,
				nl2br(htmlspecialchars($r['transcript'])),
				htmlspecialchars($r['source'] ?? '-'),
				$deleteBtn
			];
		}, $data)
	
]);