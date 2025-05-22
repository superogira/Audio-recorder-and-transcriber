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

$where = '1';
$params = [];

if (!empty($source)) {
    $where .= " AND source = :source";
    $params[':source'] = $source;
}

// ใน index.php คอลัมน์ใน DataTable คือ:
// 0: Checkbox
// 1: ID
// 2: วันที่/เวลา (created_at)
// 3: สถานีรับ / Callsign (station)
// 4: ความถี่ (MHz) (frequency)
// 5: ไฟล์เสียง (filename - หรืออาจจะเรียงตาม drive_url หรือ local_path)
// 6: ระยะเวลา (วินาที) (duration)
// 7: ข้อความ (transcript)
// 8: Note (tag/note)
// 9: ระบบแปลงเสียง (source)
// 10: จัดการ (actions)

/* $columns = ['id', 'created_at', 'filename', 'transcript', 'source', 'frequency', 'station', 'duration', 'note']; */

// Adjusted column mapping to match index.php
// Order of columns in JS: checkbox, id, created_at, station, frequency, audio, duration, transcript, tag, source, actions
$columns = [
    // 0 => ไม่ควร sort ตาม checkbox โดยตรง
    1 => 'id',
    2 => 'created_at',
    3 => 'station',
    4 => 'frequency',
    5 => 'filename', // หรือ 'local_path' ถ้าต้องการ sort ตาม path จริง
    6 => 'duration',
    7 => 'transcript',
    8 => 'note', // หรือ 'tag' ถ้าชื่อคอลัมน์ใน DB คือ tag
    9 => 'source',
    // 10 => ไม่ควร sort ตาม actions 
];
$orderBy = $columns[$orderCol] ?? 'created_at'; // $orderCol คือ index ที่ได้จาก DataTables


if (!empty($search)) {
    //$where .= " AND (transcript LIKE :search OR filename LIKE :search)";
	$where .= " AND (transcript LIKE :search OR filename LIKE :search OR station LIKE :search OR frequency LIKE :search OR note LIKE :search)";
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

if (!empty($source)) { // Use the renamed variable
    $where .= " AND source = :source"; // Use the renamed variable
    $params[':source'] = $source; // Use the renamed variable
}

//$sql = "SELECT * FROM records WHERE $where ORDER BY $orderBy $orderDir LIMIT :start, :length";
//$countSql = "SELECT COUNT(*) FROM records WHERE $where";

// Include file_location_type and drive_url in the SELECT statement
$sql = "SELECT id, created_at, filename, transcript, source, frequency, station, duration, note, file_location_type, drive_url, local_path FROM records WHERE $where ORDER BY $orderBy $orderDir LIMIT :start, :length";
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

//$totalCount = $pdo->query("SELECT COUNT(*) FROM records")->fetchColumn();
$totalCountStmt = $pdo->query("SELECT COUNT(*) FROM records"); // Prepare and execute for total count
$recordsTotal = $totalCountStmt->fetchColumn();

echo json_encode([
    "draw" => intval($draw),
    //"recordsTotal" => $totalCount,
	"recordsTotal" => $recordsTotal,
    "recordsFiltered" => $recordsFiltered,
/*     "data" => array_map(function($r) use ($loggedIn) {
        $file = htmlspecialchars($r['filename']);
        $audio = "<audio controls preload='none'><source src='audio_files/$file' type='audio/wav'>ไม่รองรับ</audio>";
        $download = "<br><a href='audio_files/$file' download>📥 ดาวน์โหลด</a>";
        return [
			'<input type="checkbox" class="row-checkbox" value="'.$r['id'].'" data-file="'.htmlspecialchars($r['filename']).'">',
            $r['id'],
            $r['created_at'],
            $audio . $download,
            nl2br(htmlspecialchars($r['transcript'])),
            //'<button class="btn btn-sm btn-danger delete-btn" data-id="'.$r['id'].'" data-file="'.htmlspecialchars($r['filename']).'">🗑 ลบ</button>'
			'<button class="btn btn-sm btn-danger delete-btn" data-id="'.$r['id'].'" data-file="'.htmlspecialchars($r['filename']).'">'.'<i class="bi bi-trash-fill"></i> ลบ</button>'
        ];
    }, $data) */

		"data" => array_map(function($r) use ($loggedIn) {
			//$file = htmlspecialchars($r['filename']);
			$filename = htmlspecialchars($r['filename'] ?? 'N/A'); // Ensure filename exists
			$audioHtml = '';
			$downloadLink = '';
			//$audio = "<audio controls preload='none'><source src='audio_files/$file' type='audio/wav'>ไม่รองรับ</audio>";
			//$audio = '<button class="btn btn-sm btn-outline-primary play-btn" data-src="audio_files/'.$file.'"><i class="bi bi-play-circle"></i> เล่น</button>';
			//$download = "<br><a href='audio_files/$file' download>📥 ดาวน์โหลด</a>";

			// Check if the file is on Google Drive or still local
			if (!empty($r['drive_url']) && ($r['file_location_type'] === 'drive' || $r['file_location_type'] === 'archived')) {
				// File is on Google Drive
				$audioSrc = htmlspecialchars($r['drive_url']);
				// For Google Drive, the play button might directly open the link,
				// or you might need a different way to embed/play if direct embedding is an issue.
				// The download link will also be the drive_url.
				//$audioHtml = '<a href="'.$audioSrc.'" target="_blank" class="btn btn-sm btn-outline-success play-gdrive-btn"><i class="bi bi-google"></i> เล่น (Drive)</a>'
				$audioHtml = '<a href="'.$audioSrc.'" target="_blank" class="btn btn-sm btn-outline-success play-gdrive-btn"><i class="fab fa-google-drive"></i> เล่น & ดาวน์โหลด (Drive)</a>';
				//$downloadLink = '<br><a href="'.$audioSrc.'" target="_blank">📥 ดาวน์โหลด (Drive)</a>';
				$downloadLink = '';
			} elseif ($r['local_path'] === 'FILE_NOT_FOUND') {
				$audioHtml = '<span class="badge bg-warning text-dark">ไฟล์ไม่พบ (Local)</span>';
				$downloadLink = '';
			} else {
				// File is local (or assumed local if no drive_url and type is 'local')
				$localFile = 'audio_files/' . $filename;
				$audioHtml = '<button class="btn btn-sm btn-outline-primary play-btn" data-src="'.$localFile.'"><i class="bi bi-play-circle"></i> เล่น</button>';
				$downloadLink = "<br><a href='".$localFile."' download>📥 ดาวน์โหลด</a>";
			}

			//$checkbox = '<input type="checkbox" class="row-checkbox" value="'.$r['id'].'" data-file="'.$file.'">';

/* 			$deleteBtn = $loggedIn
				? '<button class="btn btn-sm btn-danger delete-btn" data-id="'.$r['id'].'" data-file="'.$file.'"><i class="bi bi-trash-fill"></i> ลบ</button>'
				: '<button class="btn btn-sm btn-secondary unauth"><i class="bi bi-lock-fill"></i> ลบ</button>'; */

			$checkbox = '<input type="checkbox" class="row-checkbox" value="'.$r['id'].'" data-file="'.$filename.'">';

			$deleteBtn = $loggedIn
				? '<button class="btn btn-sm btn-danger delete-btn" data-id="'.$r['id'].'" data-file="'.$filename.'"><i class="bi bi-trash-fill"></i> ลบ</button>'
				: '<button class="btn btn-sm btn-secondary unauth"><i class="bi bi-lock-fill"></i> ลบ</button>';

			return [
				$checkbox,
				$r['id'],
				$r['created_at'],
				$r['station'],
				$r['frequency'],
				//$audio . $download,
				$audioHtml . $downloadLink, // Combined audio play and download
				//number_format((float)($r['duration'] ?? 0), 2),
				number_format((float)$r['duration'], 2),
				//nl2br(htmlspecialchars($r['transcript'] ?? '')),
				nl2br(htmlspecialchars($r['transcript'])),
				'<span class="row-tag">'.htmlspecialchars($r['note'] ?? '').'</span>',
				htmlspecialchars($r['source'] ?? '-'),
				$deleteBtn
			];
		}, $data)
	
]);
