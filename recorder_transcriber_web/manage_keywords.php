<?php
session_start();

// 1. ตรวจสอบการ Login
if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
    // ถ้ายังไม่ได้ Login ให้ redirect ไปหน้า login หรือแสดงข้อความ
    // header('Location: login.php'); // แก้ไข 'login.php' เป็นหน้า login ของคุณ
    die("กรุณาเข้าสู่ระบบก่อน <a href='login.php'>เข้าสู่ระบบ</a>"); // หรือแสดงข้อความพร้อมลิงก์
}

// 2. เชื่อมต่อฐานข้อมูล
require 'db_config.php'; // ไฟล์เชื่อมต่อ PDO

// 3. การจัดการ Actions (เพิ่ม, แก้ไข, ลบ)
$action = $_POST['action'] ?? $_GET['action'] ?? '';
$id = $_POST['id'] ?? $_GET['id'] ?? null;
$message = ''; // สำหรับแสดงผลการดำเนินการ

try {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $keyword = trim($_POST['keyword'] ?? '');
		$except_keywords_input = trim($_POST['except_keywords'] ?? '');
		$except_keywords_to_db = !empty($except_keywords_input) ? $except_keywords_input : null;
        $bot_token = trim($_POST['bot_token'] ?? '');
        $chat_id = trim($_POST['chat_id'] ?? '');
        $custom_message_prefix = trim($_POST['custom_message_prefix'] ?? '');
        $is_active = isset($_POST['is_active']) ? 1 : 0;

        if ($action === 'add' || $action === 'edit') {
            // --- ตรวจสอบ Input พื้นฐาน ---
            if (empty($keyword) || empty($bot_token) || empty($chat_id)) {
                $message = "<div class='alert alert-danger'>Keyword, Bot Token, และ Chat ID ห้ามว่าง</div>";
            } else {
                if ($action === 'add') {
                    $stmt = $pdo->prepare("INSERT INTO telegram_notifications_config (keyword, bot_token, chat_id, custom_message_prefix, is_active, except_keywords) VALUES (?, ?, ?, ?, ?, ?)");
                    if ($stmt->execute([$keyword, $bot_token, $chat_id, $custom_message_prefix, $is_active, $except_keywords_to_db])) {
                        $message = "<div class='alert alert-success'>เพิ่ม Keyword สำเร็จ</div>";
                    } else {
                        $message = "<div class='alert alert-danger'>เกิดข้อผิดพลาดในการเพิ่ม Keyword: " . $stmt->errorInfo()[2] . "</div>";
                    }
                } elseif ($action === 'edit' && $id) {
                    $stmt = $pdo->prepare("UPDATE telegram_notifications_config SET keyword = ?, bot_token = ?, chat_id = ?, custom_message_prefix = ?, is_active = ?, except_keywords = ? WHERE id = ?");
                    if ($stmt->execute([$keyword, $bot_token, $chat_id, $custom_message_prefix, $is_active, $except_keywords_to_db, $id])) {
                        $message = "<div class='alert alert-success'>แก้ไข Keyword สำเร็จ</div>";
                    } else {
                        $message = "<div class='alert alert-danger'>เกิดข้อผิดพลาดในการแก้ไข Keyword: " . $stmt->errorInfo()[2] . "</div>";
                    }
                }
            }
        }
    } elseif ($action === 'delete' && $id) {
        // --- การลบ ---
        // เพื่อความปลอดภัย อาจจะมี confirm ก่อนลบจริง ในตัวอย่างนี้ลบเลย
        $stmt = $pdo->prepare("DELETE FROM telegram_notifications_config WHERE id = ?");
        if ($stmt->execute([$id])) {
            $message = "<div class='alert alert-success'>ลบ Keyword สำเร็จ</div>";
        } else {
            $message = "<div class='alert alert-danger'>เกิดข้อผิดพลาดในการลบ Keyword: " . $stmt->errorInfo()[2] . "</div>";
        }
        // Redirect กลับมาหน้าเดิมเพื่อไม่ให้ URL ค้าง action=delete
        header("Location: manage_keywords.php?message=" . urlencode(strip_tags($message)));
        exit;
    } elseif ($action === 'edit_form' && $id) {
        // --- ดึงข้อมูลมาแสดงในฟอร์มแก้ไข ---
        $stmt = $pdo->prepare("SELECT * FROM telegram_notifications_config WHERE id = ?");
        $stmt->execute([$id]);
        $edit_data = $stmt->fetch(PDO::FETCH_ASSOC);
        if (!$edit_data) {
            $message = "<div class='alert alert-danger'>ไม่พบข้อมูล Keyword ที่ต้องการแก้ไข</div>";
            $action = ''; // กลับไปหน้าแสดงรายการ
        }
    }
} catch (PDOException $e) {
    $message = "<div class='alert alert-danger'>Database Error: " . $e->getMessage() . "</div>";
}

// แสดงข้อความจาก URL (ถ้ามีการ redirect มาจากการลบ)
if (isset($_GET['message'])) {
    $message = "<div class='alert alert-info'>" . htmlspecialchars($_GET['message']) . "</div>";
}


// 4. ดึงข้อมูลทั้งหมดมาแสดง
$keywords_list = [];
try {
    $stmt = $pdo->query("SELECT * FROM telegram_notifications_config ORDER BY keyword ASC");
    $keywords_list = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    $message .= "<div class='alert alert-danger'>ไม่สามารถดึงรายการ Keywords ได้: " . $e->getMessage() . "</div>";
}

?>
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>จัดการ Keywords แจ้งเตือน Telegram</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .container { max-width: 960px; }
        .table th, .table td { vertical-align: middle; }
        .form-check-input { transform: scale(1.2); }
    </style>
</head>
<body>
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h1>จัดการ Keywords แจ้งเตือน Telegram</h1>
            <a href="logout.php" class="btn btn-outline-danger">ออกจากระบบ</a>  </div>

        <?php if ($message) echo $message; ?>

        <?php if ($action === 'edit_form' && isset($edit_data) && $edit_data): ?>
            <h2><i class="bi bi-pencil-square"></i> แก้ไข Keyword (ID: <?php echo htmlspecialchars($edit_data['id']); ?>)</h2>
            <form action="manage_keywords.php" method="POST" class="mb-4 p-3 border rounded bg-light">
                <input type="hidden" name="action" value="edit">
                <input type="hidden" name="id" value="<?php echo htmlspecialchars($edit_data['id']); ?>">
                <div class="mb-3">
                    <label for="edit_keyword" class="form-label">Keyword <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="edit_keyword" name="keyword" value="<?php echo htmlspecialchars($edit_data['keyword']); ?>" required>
                </div>
				<div class="mb-3">
					<label for="edit_except_keywords" class="form-label">คำ/วลีที่ยกเว้น หากเจอร่วมกับ Keyword ที่กำหนด ก็ไม่ต้องส่งแจ้งเตือน (ถ้ามีหลายคำ ให้คั่นด้วยจุลภาค )</label>
					<textarea class="form-control" id="edit_except_keywords" name="except_keywords" rows="2" placeholder="เช่น ไม่ต้องส่ง,ยกเว้นคำนี้"><?php echo htmlspecialchars($edit_data['except_keywords'] ?? ''); ?></textarea>
				</div>
                <div class="mb-3">
                    <label for="edit_bot_token" class="form-label">Bot Token <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="edit_bot_token" name="bot_token" value="<?php echo htmlspecialchars($edit_data['bot_token']); ?>" required>
                </div>
                <div class="mb-3">
                    <label for="edit_chat_id" class="form-label">Chat ID <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="edit_chat_id" name="chat_id" value="<?php echo htmlspecialchars($edit_data['chat_id']); ?>" required>
                </div>
                <div class="mb-3">
                    <label for="edit_custom_message_prefix" class="form-label">Custom Message Prefix (ถ้ามี)</label>
                    <textarea class="form-control" id="edit_custom_message_prefix" name="custom_message_prefix" rows="2"><?php echo htmlspecialchars($edit_data['custom_message_prefix']); ?></textarea>
                </div>
                <div class="mb-3 form-check">
                    <input type="checkbox" class="form-check-input" id="edit_is_active" name="is_active" value="1" <?php echo $edit_data['is_active'] ? 'checked' : ''; ?>>
                    <label class="form-check-label" for="edit_is_active">เปิดใช้งาน</label>
                </div>
                <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> บันทึกการแก้ไข</button>
                <a href="manage_keywords.php" class="btn btn-secondary">ยกเลิก</a>
            </form>
        <?php else: ?>
            <h2><i class="bi bi-plus-circle-fill"></i> เพิ่ม Keyword ใหม่</h2>
            <form action="manage_keywords.php" method="POST" class="mb-4 p-3 border rounded bg-light">
                <input type="hidden" name="action" value="add">
                <div class="mb-3">
                    <label for="add_keyword" class="form-label">Keyword <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="add_keyword" name="keyword" required>
                </div>
				<div class="mb-3">
					<label for="add_except_keywords" class="form-label">คำ/วลีที่ยกเว้น หากเจอร่วมกับ Keyword ที่กำหนด ก็ไม่ต้องส่งแจ้งเตือน (ถ้ามีหลายคำ ให้คั่นด้วยจุลภาค )</label>
					<textarea class="form-control" id="add_except_keywords" name="except_keywords" rows="2" placeholder="เช่น ไม่ต้องส่ง,ยกเว้นคำนี้"></textarea>
				</div>
                <div class="mb-3">
                    <label for="add_bot_token" class="form-label">Bot Token <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="add_bot_token" name="bot_token" required>
                </div>
                <div class="mb-3">
                    <label for="add_chat_id" class="form-label">Chat ID <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="add_chat_id" name="chat_id" required>
                </div>
                <div class="mb-3">
                    <label for="add_custom_message_prefix" class="form-label">Custom Message Prefix (ถ้ามี)</label>
                    <textarea class="form-control" id="add_custom_message_prefix" name="custom_message_prefix" rows="2"></textarea>
                </div>
                <div class="mb-3 form-check">
                    <input type="checkbox" class="form-check-input" id="add_is_active" name="is_active" value="1" checked>
                    <label class="form-check-label" for="add_is_active">เปิดใช้งาน</label>
                </div>
                <button type="submit" class="btn btn-success"><i class="bi bi-plus-lg"></i> เพิ่ม Keyword</button>
            </form>
        <?php endif; ?>

        <hr>

        <h2><i class="bi bi-list-ul"></i> รายการ Keywords ทั้งหมด</h2>
        <?php if (empty($keywords_list) && empty($message)): ?>
            <div class="alert alert-info">ยังไม่มีข้อมูล Keyword</div>
        <?php elseif (!empty($keywords_list)): ?>
            <div class="table-responsive">
                <table class="table table-striped table-hover table-bordered">
                    <thead class="table-dark">
                        <tr>
                            <th>ID</th>
                            <th>Keyword</th>
							<th>คำที่ยกเว้น</th>
                            <th>Bot Token</th>
                            <th>Chat ID</th>
                            <th>Prefix</th>
                            <th>สถานะ</th>
                            <th>จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($keywords_list as $item): ?>
                            <tr>
                                <td><?php echo htmlspecialchars($item['id']); ?></td>
                                <td><?php echo htmlspecialchars($item['keyword']); ?></td>
								<td>
									<?php
									// สมมติว่าเก็บเป็น JSON array หรือ สตริงคั่นด้วยจุลภาค
									$exceptions = $item['except_keywords'] ?? '';
									if (!empty($exceptions)) {
										// ถ้าเป็น JSON array
										$decoded_exceptions = json_decode($exceptions, true);
										if (is_array($decoded_exceptions)) {
											echo htmlspecialchars(implode(', ', $decoded_exceptions));
										} else {
											// ถ้าเป็นสตริงคั่นด้วยจุลภาค หรือ JSON ที่ decode ไม่ได้
											echo htmlspecialchars($exceptions);
										}
									} else {
										echo '-';
									}
									?>
								</td>
                                <td><?php echo htmlspecialchars($item['bot_token']); // แสดง Bot Token แค่บางส่วน ?></td>
                                <td><?php echo htmlspecialchars($item['chat_id']); ?></td>
                                <td><?php echo nl2br(htmlspecialchars($item['custom_message_prefix'])); ?></td>
                                <td>
                                    <?php if ($item['is_active']): ?>
                                        <span class="badge bg-success">เปิดใช้งาน</span>
                                    <?php else: ?>
                                        <span class="badge bg-secondary">ปิดใช้งาน</span>
                                    <?php endif; ?>
                                </td>
                                <td>
                                    <a href="manage_keywords.php?action=edit_form&id=<?php echo $item['id']; ?>" class="btn btn-sm btn-warning" title="แก้ไข">
                                        <i class="bi bi-pencil"></i>
                                    </a>
                                    <a href="manage_keywords.php?action=delete&id=<?php echo $item['id']; ?>" class="btn btn-sm btn-danger" title="ลบ" onclick="return confirm('คุณแน่ใจหรือไม่ว่าต้องการลบ Keyword นี้?');">
                                        <i class="bi bi-trash"></i>
                                    </a>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>