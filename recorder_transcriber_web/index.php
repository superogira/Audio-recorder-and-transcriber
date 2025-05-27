<?php
session_start();
$logged_in = $_SESSION['logged_in'] ?? false;
?>

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>รายการเสียงและข้อความที่บันทึกไว้</title>
	
	<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
	<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
	<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>

    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

	<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
	<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
	
	<script src="https://cdn.datatables.net/fixedheader/3.4.0/js/dataTables.fixedHeader.min.js"></script>
	

    <style>
        body { font-size: 1.1rem; }
        h2 { font-size: 2rem; }
      .badge-purple { background-color: #6f42c1; }
	  .container-99 {
		max-width: 99vw;
		margin: 0 auto;
	  }
	 
	.fixedHeader-floating {
	  background-color: #212529 !important;  /* same as .table-dark header */
	  color: #fff !important;
	}

	/* container ด้านล่าง สีเข้มหน่อย */
	#global-audio-container {
	  position: fixed;
	  bottom: 0; left: 0; right: 0;
	  background-color: #343a40; /* เข้มขึ้น */
	  padding: 0.5rem;
	  box-shadow: 0 -2px 6px rgba(0,0,0,0.3);
	  z-index: 1050;
	}

	/* audio element ให้เต็มความกว้าง */
	#globalPlayer {
	  width: 100%;
	  background-color: #fff;      /* พื้นหลังขาว เพื่อคอนทราสต์ */
	  border-radius: 4px;
	}

	/* สำหรับ Chrome/Edge/Safari: ให้ panel มีพื้นหลังขาวจริงๆ */
	#globalPlayer::-webkit-media-controls-panel,
	#globalPlayer::-webkit-media-controls-enclosure {
	  background-color: #fff !important;
	}

	/* ถ้าต้องการให้ปุ่มเป็นสีเข้มเห็นชัด (invert icons) */
	#globalPlayer::-webkit-media-controls-play-button,
	#globalPlayer::-webkit-media-controls-volume-slider {
	  filter: contrast(200%) !important;
	}

	/* Firefox (ทดลองดู ถ้ามันรองรับ) */
	#globalPlayer::-moz-media-controls {
	  background-color: #fff !important;
	}
	
    .custom-top-center-box {
        /* position: fixed; */
        top: 5%; /* หรือค่า px เช่น 20px */
        left: 50%;
        /* transform: translateX(-50%);
        z-index: 1050; */
        width: 90%; /* ความกว้าง responsive */
        max-width: 600px; /* ความกว้างสูงสุด */
        /* display: none;  ถ้าต้องการให้ซ่อนไว้ก่อนแล้วค่อยแสดงด้วย JS */
		  display: block;
		  margin-left: auto;
		  margin-right: auto;
    }
    </style>

	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
	<link rel="stylesheet"  href="https://cdn.datatables.net/fixedheader/3.4.0/css/fixedHeader.bootstrap5.min.css"/>
	<!-- Bootstrap Icons -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
	<!-- Flatpickr -->
	<link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css" rel="stylesheet">
  <!-- Font Awesome for icons -->
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet" />
</head>
<body class="bg-light">

<!--
<div class="mb-3 d-flex align-items-center">
  <?php if ($logged_in): ?>
    <a href="logout.php" class="btn btn-danger">ออกจากระบบ</a>
	<a href="manage_keywords.php" target="_blank" class="btn btn btn-primary">จัดการ Keywords</a>
  <?php else: ?>
    <a href="login.php" class="btn btn-outline-primary">เข้าสู่ระบบผู้ดูแล</a>
  <?php endif; ?>

  //กลุ่มนี้จะถูกดันไปฝั่งขวา
  <div class="ms-auto text-muted">
    จำนวนผู้ใช้ที่ออนไลน์ตอนนี้:
    <span id="onlineCount" class="fw-bold">–</span>
  </div>
</div>
-->

<div class="mb-3 d-flex align-items-center">
  <?php if ($logged_in): ?>
    <a href="logout.php" class="btn btn-danger">ออกจากระบบ</a>
    <a href="manage_keywords.php" target="_blank" class="btn btn-primary ms-2">จัดการ Keywords</a>
    <a href="manual_drive_transfer.php" target="_blank" class="btn btn-info ms-2"><i class="bi bi-google"></i> ย้ายไฟล์ไป Drive (Manual)</a>
	<a href="manual_drive_transfer_ajax.php" target="_blank" class="btn btn-info ms-2"><i class="bi bi-google"></i> ย้ายไฟล์ไป Drive (Manual แบบ AJAX)</a>
  <?php else: ?>
    <a href="login.php" class="btn btn-outline-primary">เข้าสู่ระบบผู้ดูแล</a>
  <?php endif; ?>
	<button id="toggleNotificationSound" class="btn btn-outline-secondary ms-3"><i class="bi bi-volume-up-fill"></i> <span>เปิดเสียงแจ้งเตือน</span></button>
	<button id="toggleAutoplayLatestAudio" class="btn btn-outline-secondary ms-2"><i class="bi bi-play-circle-fill"></i> <span>เปิดเล่นเสียงล่าสุดอัตโนมัติ</span></button>
  <!-- กลุ่มนี้จะถูกดันไปฝั่งขวา -->
  <div class="ms-auto text-muted">
    จำนวนผู้ใช้ที่ออนไลน์ตอนนี้:
    <span id="onlineCount" class="fw-bold">–</span>
	<a href="https://github.com/superogira/Audio-recorder-and-transcriber" target="_blank" class="btn btn-dark ms-2"><i class="bi bi-github"></i> ติดตาม Project</a>
  </div>
</div>

<!--<button class="btn btn-sm btn-outline-primary play-btn" data-src="http://e25wop.thddns.net:2255/stream.ogg"><i class="bi bi-play-circle"></i> เล่น</button>
<br> หากเล่นไม่ได้ สามารถไปฟังสดได้ที่ <a href="http://e25wop.thddns.net:2255/" target="_blank" >เว็บฟังสด </a>-->
<!--<div class="audioplayer"><audio controls="controls" preload="none"><source src="https://e25wop.thddns.net:2255/stream.ogg" type="application/ogg"></source></audio>
<br>If cannot play audio. Please reload page and press play again.</div>-->

<!--<button id="enableAlertSound" class="btn btn-sm btn-outline-secondary">
  เปิดเสียงแจ้งเตือน
</button>-->
<button id="enableAudio" class="btn btn-sm btn-outline-secondary">
  เปิดระบบเสียงแจ้งเตือนและการเล่นเสียงล่าสุด
</button>
<br><br>
    <div id="myCustomBox" class="custom-top-center-box">
        <div class="alert alert-success alert-dismissible fade show shadow-lg" role="alert">
            <h4 class="alert-heading">หากต้องการรับการสนับสนุน</h4>
            <hr>
			<p class="mb-0">สำหรับการบันทึกเสียงและถอดข้อความ ในย่านความถี่ไหนและช่วงเวลาอะไร</p>
			<p class="mb-0">สามารถติดต่อได้ที่ <a href="https://www.facebook.com/superogira" target="_blank" >Facebook</a></p>
        </div>
    </div>


<div class="container-fluid container-99 mt-5 px-5">
  <!-- row สำหรับกราฟทั้งสอง -->
  <div class="row">
    <!-- กราฟจำนวนไฟล์ -->
    <div class="col-12 col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-body">
          <h5 class="card-title">📈 สถิติไฟล์ที่บันทึก (จำนวนต่อวัน)</h5>
          <!-- Date picker + filter button ของกราฟนี้ -->
          <div class="row g-2 mb-3">
            <div class="col-auto">
              <input type="text" id="statFrom" class="form-control" placeholder="จากวันที่/เวลา">
            </div>
            <div class="col-auto">
              <input type="text" id="statTo"   class="form-control" placeholder="ถึงวันที่/เวลา">
            </div>
            <div class="col-auto">
              <button id="filterStatBtn" class="btn btn-outline-primary"><i class="bi bi-funnel"></i> กรอง</button>
            </div>
          </div>
          <canvas id="statChart" height="100"></canvas>
        </div>
      </div>
    </div>

    <!-- กราฟเวลารวม (duration) -->
    <div class="col-12 col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-body">
          <h5 class="card-title">🕒 เวลารวมที่บันทึกเสียง (วินาทีต่อวัน)</h5>
          <!-- Date picker + filter button ของกราฟนี้ -->
          <div class="row g-2 mb-3">
            <div class="col-auto">
              <input type="text" id="durationFrom" class="form-control" placeholder="จากวันที่">
            </div>
            <div class="col-auto">
              <input type="text" id="durationTo"   class="form-control" placeholder="ถึงวันที่">
            </div>
            <div class="col-auto">
              <button id="filterDurationBtn" class="btn btn-outline-warning"><i class="bi bi-funnel"></i> กรอง</button>
            </div>
          </div>
          <canvas id="durationChart" height="100"></canvas>
        </div>
      </div>
    </div>

  
	<!-- row ใหม่ สำหรับกราฟรายชั่วโมง -->
	  <div class="col-12 col-lg-6 mb-4">
		<div class="card h-100">
		  <div class="card-body">
			<h5 class="card-title">🕑 จำนวนนาทีการบันทึกเสียงที่ผ่านมาของแต่ละชั่วโมง (นาทีต่อชั่วโมง)</h5>
				<div class="row g-2 mb-3 align-items-end">
				  <div class="col-auto">
					<input type="text" id="hourlyFrom" class="form-control" placeholder="จากวันที่">
				  </div>
				  <div class="col-auto">
					<input type="text" id="hourlyTo"   class="form-control" placeholder="ถึงวันที่">
				  </div>
				  <div class="col-auto">
					<button id="filterHourlyBtn" class="btn btn-outline-primary"><i class="bi bi-funnel"></i> กรอง</button>
				  </div>
				</div>
			<canvas id="hourlyChart" height="100"></canvas>
		  </div>
		</div>
	  </div>
	
	<!-- row ใหม่ สำหรับกราฟ frequency -->
	  <div class="col-12 col-lg-6 mb-4">
		<div class="card h-100">
		  <div class="card-body">
			<h5 class="card-title">🎯 จำนวนการบันทึกของแต่ละความถี่</h5>
			<div class="row g-2 mb-3">
			  <div class="col-auto">
				<input type="text" id="freqFrom" class="form-control" placeholder="จากวันที่">
			  </div>
			  <div class="col-auto">
				<input type="text" id="freqTo"   class="form-control" placeholder="ถึงวันที่">
			  </div>
			  <div class="col-auto">
				<button id="filterFreqBtn" class="btn btn-outline-secondary"><i class="bi bi-funnel"></i> กรอง</button>
			  </div>
			</div>
			<canvas id="freqChart" height="100"></canvas>
		  </div>
		</div>
	  </div>
	  
	<!-- row ใหม่ สำหรับกราฟ Failed Transcripts -->
	  <div class="col-12 col-lg-6 mb-4">
		<div class="card h-100">
		  <div class="card-body">
			<h5 class="card-title">🚫 จำนวนรายการถอดข้อความล้มเหลว แยกตามระบบ</h5>
			<div class="row g-2 mb-3 align-items-end">
			  <div class="col-auto">
				<input type="text" id="failedFrom" class="form-control" placeholder="จากวันที่/เวลา">
			  </div>
			  <div class="col-auto">
				<input type="text" id="failedTo"   class="form-control" placeholder="ถึงวันที่/เวลา">
			  </div>
			  <div class="col-auto">
				<button id="filterFailedBtn" class="btn btn-outline-danger">
				  <i class="bi bi-funnel"></i> กรอง
				</button>
			  </div>
			</div>
			<canvas id="failedChart" height="100"></canvas>
		  </div>
		</div>
	  </div>
	  
	  <div class="col-12 col-lg-6 mb-4">
		<div class="card h-100">
		  <div class="card-body">
			<h5 class="card-title">⏱️ ระยะเวลารวมตามระบบแปลงเสียง (นาที)</h5>
			<div class="row g-2 mb-3 align-items-end">
			  <div class="col-auto">
				<input type="text" id="totalFrom" class="form-control" placeholder="จากวันที่/เวลา">
			  </div>
			  <div class="col-auto">
				<input type="text" id="totalTo"   class="form-control" placeholder="ถึงวันที่/เวลา">
			  </div>
			  <div class="col-auto">
				<button id="filterTotalBtn" class="btn btn-outline-secondary">
				  <i class="bi bi-funnel"></i> กรอง
				</button>
			  </div>
			</div>
			<canvas id="totalSourceChart" height="100"></canvas>
		  </div>
		</div>
	  </div>

	  
  </div>
</div>

<div class="container-fluid mt-5 px-5">
    <h2 class="mb-4">📻 รายการเสียงที่บันทึกและข้อความที่ถอดได้ จากการเฝ้าฟังในช่วงความถี่ต่าง ๆ</h2>

	<div class="row g-3 mb-3 align-items-end">
	  <div class="col-md-auto">
		<label for="dateFrom" class="form-label">จากวันที่:</label>
		<input type="text" id="dateFrom" class="form-control" placeholder="เลือกวันที่เริ่ม">
	  </div>
	  <div class="col-md-auto">
		<label for="dateTo" class="form-label">ถึงวันที่:</label>
		<input type="text" id="dateTo" class="form-control" placeholder="เลือกวันที่สิ้นสุด">
	  </div>
    <div class="col-md-auto">
      <label for="sourceFilter" class="form-label">ระบบแปลงเสียง:</label>
      <select id="sourceFilter" class="form-select">
        <option value="">ทั้งหมด</option>
        <option value="Azure AI Speech to Text">Azure AI Speech to Text</option>
		<option value="Google Cloud Speech-to-Text">Google Cloud Speech-to-Text</option>
		<option value="Speechmatics Speech-to-Text">Speechmatics Speech-to-Text</option>
      </select>
    </div>
	  <div class="col-md-auto">
		<button id="filterBtn" class="btn btn-primary">
		  <i class="bi bi-search"></i> กรอง
		</button>
		<button id="clearBtn" class="btn btn-outline-secondary">
		  <i class="bi bi-x-circle"></i> ล้าง
		</button>
	  </div>
	</div>

    <div class="table-responsive">
        <table id="recordTable" class="table table-bordered table-hover bg-white table-striped align-middle">
            <thead class="table-dark">
                <tr>
					<th><input type="checkbox" id="checkAll"></th>
                    <th>ID</th>
                    <th>วันที่/เวลา</th>
					<th>สถานีรับ / Callsign</th>
					<th>ความถี่ (MHz)</th>
                    <th>ไฟล์เสียง</th>
					<th>ระยะเวลา (วินาที)</th>
                    <th>ข้อความ</th>
					<th>Note</th>
					<th>ระบบแปลงเสียง</th>
                    <th>จัดการ</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
        <?php if ($logged_in): ?>
			<button id="bulkDelete" class="btn btn-danger mt-3">
			  <i class="bi bi-trash"></i> ลบรายการที่เลือก
			</button>
        <?php endif; ?>
    </div>
</div>

<!-- ปรับ CSS ตามชอบ ให้แสดง/ซ่อน หรือ fixed bottom bar -->
<div id="global-audio-container" style="display:none; position:fixed; bottom:0; left:0; right:0; background:#fff; padding:8px; box-shadow:0 -2px 6px rgba(0,0,0,0.1); z-index:1050;">
  <audio id="globalPlayer" controls style="width:100%;">
    Your browser doesn’t support HTML5 audio.
  </audio>
</div>

<!-- วางตรงไหนก็ได้ใน <body> แต่ซ่อนไว้ -->
<!-- <audio id="rowAlertSound" src="radio-tail.mp3" preload="auto"></audio> -->

<!-- เปลี่ยนเป็น container-fluid + fixed-bottom -->
<!-- col-12 บนมือถือ, col-md-8 บนแท็บเล็ต, col-lg-6 บนเดสก์ท็อป -->
<!-- audio เต็มความกว้างคอลัมน์ -->
<!--<div id="global-audio-container" class="container-fluid fixed-bottom bg-white p-2">
  <div class="row justify-content-center">
    
    <div class="col-12 col-md-8 col-lg-6">
      
      <audio id="globalPlayer" controls class="w-100">
        Your browser doesn’t support HTML5 audio.
      </audio>
    </div>
  </div>
</div> -->


<script>
	let globalContainer;
	let globalPlayer;
	let fadeTimeout;
	let table;   // declare in the outer scope
	  
	let lastMaxId = 0;
	
	let currentNotificationAudio = null; // Audio object ที่กำลังเล่นไฟล์เสียงล่าสุด
	let audioNotificationQueue = [];   // คิวสำหรับเก็บ URL ของไฟล์เสียงล่าสุดที่รอเล่น
	let isAutoplayLatestAudioPlaying = false; // สถานะว่ากำลังเล่นเสียงจากคิวหรือไม่
	
	// ฟังก์ชันสำหรับเล่นเสียงถัดไปในคิว
	function playNextInNotificationQueue() {
		if (audioNotificationQueue.length > 0) {
			isAutoplayLatestAudioPlaying = true;
			const nextAudioUrl = audioNotificationQueue.shift(); // ดึง URL แรกออกจากคิว
			
			// หยุด globalPlayer ถ้ากำลังเล่นอยู่ เพื่อไม่ให้เสียงซ้อนกัน
			if (globalPlayer && !globalPlayer.paused) {
				globalPlayer.pause();
				// globalPlayer.currentTime = 0; // อาจจะไม่จำเป็นต้อง reset เวลาของ globalPlayer
				console.log("หยุด globalPlayer ชั่วคราวเพื่อเล่นเสียงแจ้งเตือนล่าสุด");
			}

			if (currentNotificationAudio && typeof currentNotificationAudio.pause === 'function') {
				currentNotificationAudio.pause(); // หยุดเสียงที่อาจจะยังเล่นค้าง (กรณีที่ไม่ใช่จาก ended)
			}

			currentNotificationAudio = new Audio(nextAudioUrl);
			console.log(`[Queue] กำลังพยายามเล่น: ${nextAudioUrl}`);

			currentNotificationAudio.play().then(() => {
				console.log(`[Queue] ✅ เล่นไฟล์จากคิวสำเร็จ: ${nextAudioUrl}`);
			}).catch(error => {
				console.warn(`[Queue] ⚠️ ไม่สามารถเล่นไฟล์จากคิวอัตโนมัติ: ${nextAudioUrl}`, error);
				isAutoplayLatestAudioPlaying = false; // รีเซ็ตสถานะ
				playNextInNotificationQueue(); // พยายามเล่นไฟล์ถัดไปในคิว (ถ้ามี)
			});

			currentNotificationAudio.onended = function() {
				console.log(`[Queue] 🏁 ไฟล์เล่นจบ: ${nextAudioUrl}`);
				isAutoplayLatestAudioPlaying = false;
				playNextInNotificationQueue(); // เล่นไฟล์ถัดไปในคิวเมื่อไฟล์ปัจจุบันจบ
			};

			currentNotificationAudio.onerror = function() {
				console.error(`[Queue] ❌ เกิดข้อผิดพลาดในการเล่นไฟล์: ${nextAudioUrl}`);
				isAutoplayLatestAudioPlaying = false;
				playNextInNotificationQueue(); // พยายามเล่นไฟล์ถัดไปในคิว (ถ้ามี)
			};

		} else {
			isAutoplayLatestAudioPlaying = false; // ไม่มีอะไรในคิวแล้ว
			console.log("[Queue] คิวว่างเปล่า");
		}
	}
  
	// ฟังก์ชัน reload โดยไม่เปลี่ยนหน้า
	function reloadTableKeepSelection() {
		table.ajax.reload(null, false);
	}
	
  // อ่านค่าเริ่มต้น
  function initNotification() {
    $.getJSON('notification.php', function(res) {
      lastMaxId = res.max_id || 0;
    });
  }

  // ตรวจว่ามี row ใหม่หรือไม่
  function checkNewRows() {
	  
    // ดึงค่าล่าสุดจาก localStorage เผื่อมีการเปลี่ยนแปลงจาก tab อื่น (ถึงแม้จะไม่ค่อยเกิดขึ้นบ่อย)
    let isShortNotificationSoundEnabled = localStorage.getItem('notificationSoundEnabled') === 'true'; // สำหรับเสียงเตือนสั้นๆ
    let isAutoplayNewAudioEnabled = localStorage.getItem('autoplayLatestAudioEnabled') === 'true'; // สำหรับเล่นไฟล์เสียงล่าสุด

    $.getJSON('notification.php', function(res) {
      const newMax = res.max_id || 0;
      if (newMax > lastMaxId) {
        // มีรายการใหม่
        lastMaxId = newMax;
		const newAudioUrl = res.new_audio_url;
		const newFilename = res.new_filename || "ไฟล์ใหม่";
		
		// 1. เล่นเสียงแจ้งเตือนสั้นๆ (ถ้าเปิดไว้)
		if (isShortNotificationSoundEnabled) {
			try {
				const shortSound = new Audio('radio-tail.mp3'); // << ไฟล์เสียงแจ้งเตือนสั้นๆ
				shortSound.play().catch(error => { /* console.warn("Autoplay short sound blocked", error); */ });
			} catch (e) {
				console.error("เกิดข้อผิดพลาดในการสร้างหรือเล่นเสียง Error playing short notification sound:", e);
			}
		}

		// 2. เล่นไฟล์เสียงล่าสุดอัตโนมัติ (ถ้าเปิดไว้ และมี URL)
/* 		if (isAutoplayNewAudioEnabled && newAudioUrl) {
			try {
				// หยุดเสียงที่กำลังเล่นอยู่ (ถ้ามี)
				if (currentNotificationAudio && typeof currentNotificationAudio.pause === 'function') {
					currentNotificationAudio.pause();
					currentNotificationAudio.currentTime = 0;
				}
				currentNotificationAudio = new Audio(newAudioUrl);
				console.log(`กำลังพยายามเล่นไฟล์เสียงล่าสุดอัตโนมัติ: ${newAudioUrl}`);

				currentNotificationAudio.play().then(() => {
					console.log(`✅ เล่นไฟล์ "${newFilename}" อัตโนมัติสำเร็จ`);
					// เมื่อเล่นไฟล์ล่าสุดจบ อาจจะต้องการให้ player ปกติ (globalPlayer) กลับมาควบคุม
					// หรืออาจจะให้ currentNotificationAudio เล่นจนจบไปเลย
					// และอาจจะอัปเดต source ของ globalPlayer ให้เป็นไฟล์นี้ด้วยก็ได้
					// globalPlayer.src = newAudioUrl; // ถ้าต้องการให้ globalPlayer เล่นไฟล์นี้ต่อ
				}).catch(error => {
					console.warn(`ไม่สามารถเล่นไฟล์เสียง "${newFilename}" อัตโนมัติ:`, error);
					// ถ้า Autoplay ถูกบล็อก อาจจะแค่แสดง SweetAlert ปกติ
				});
			} catch (e) {
				console.error("เกิดข้อผิดพลาดในการสร้างหรือเล่นเสียงล่าสุดอัตโนมัติ:", e);
			}
		} */
		// 2. จัดการไฟล์เสียงล่าสุดอัตโนมัติ (ถ้าเปิดไว้ และมี URL)
		if (isAutoplayNewAudioEnabled && newAudioUrl) {
			console.log(`[Notification] ได้รับไฟล์ใหม่: ${newAudioUrl}`);
			audioNotificationQueue.push(newAudioUrl); // เพิ่ม URL ใหม่เข้าไปในคิว

			if (!isAutoplayLatestAudioPlaying) { // ถ้าไม่มีเสียงกำลังเล่นจากคิวอยู่
				playNextInNotificationQueue(); // เริ่มเล่นเสียงแรกในคิว
			} else {
				console.log(`[Notification] มีเสียงกำลังเล่นอยู่ เพิ่ม ${newAudioUrl} เข้าคิว (คิวมี ${audioNotificationQueue.length} รายการ)`);
			}
		}
		// --- สิ้นสุดส่วนเล่นเสียง ---
			
/* 		// --- เพิ่มส่วนเล่นเสียงแจ้งเตือน ---
		try {
			const notificationSound = new Audio('radio-tail.mp3'); // << แก้ไข path และชื่อไฟล์เสียงของคุณ
			notificationSound.play().catch(error => {
				// จัดการ error ที่อาจเกิดขึ้นจากการ block autoplay ของเบราว์เซอร์
				// console.warn("ไม่สามารถเล่นเสียงแจ้งเตือนอัตโนมัติ:", error);
				// อาจจะแสดงข้อความให้ผู้ใช้กดปุ่มเพื่อเปิดเสียง หากจำเป็น
			});
		} catch (e) {
			console.error("เกิดข้อผิดพลาดในการสร้างหรือเล่นเสียง:", e);
		}
		// --- สิ้นสุดส่วนเล่นเสียงแจ้งเตือน --- */
		
      // เล่นเสียงแจ้งเตือน
/*       document.getElementById('rowAlertSound').play().catch(e=>{
        console.warn('เสียงแจ้งเตือนถูกบล็อก:', e);
      }); */
	  
/* 		// --- ตรวจสอบการตั้งค่าก่อนเล่นเสียง ---
		if (isSoundCurrentlyEnabled) { // ตรวจสอบสถานะการเปิด/ปิดเสียง
			try {
				const notificationSound = new Audio('radio-tail.mp3'); // << แก้ไข path และชื่อไฟล์เสียงของคุณ
				notificationSound.play().catch(error => {
					// console.warn("ไม่สามารถเล่นเสียงแจ้งเตือนอัตโนมัติ:", error);
				});
			} catch (e) {
				console.error("เกิดข้อผิดพลาดในการสร้างหรือเล่นเสียง:", e);
			}
		}
		// --- สิ้นสุดส่วนเล่นเสียงแจ้งเตือน --- */
			
        // แสดง Popup ตรงกลาง
		Swal.fire({
		  toast: true,              // ใช้เป็น toast
		  position: 'top',          // กึ่งกลางด้านบน
		  icon: 'info',
		  background: 'rgba(240, 255, 235, 1)',
		  title: `มีรายการใหม่: ${newFilename}!`, // แสดงชื่อไฟล์ถ้ามี
		  text: 'มีไฟล์เสียงและข้อความใหม่ถูกบันทึก',
		  showConfirmButton: false, // ไม่มีปุ่มตกลง
		  timer: (isAutoplayNewAudioEnabled && newAudioUrl) ? 7000 : 3000, // แสดงนานขึ้นถ้ามีการพยายามเล่นเสียงเต็ม
		  timerProgressBar: false,    // แสดงแถบเวลา
		  customClass: {
			// popup: 'shadow-lg', 
			// หรือ class อื่นที่คุณต้องการ
		  }
		});

        // ถ้าอยากให้ DataTable รีโหลดข้อมูลด้วย
        $('#recordTable').DataTable().ajax.reload(null, false);
		reloadTableKeepSelection();
		
        // (ถ้ามี) รีโหลดกราฟต่าง ๆ ด้วย
        //loadStatChart();
        //loadDurationChart();
        //if (typeof loadFreqChart === 'function') loadFreqChart();
      }
    });
  }

  $(document).ready(function() {
    initNotification();
    // Poll ทุก 5 วินาที (ปรับตามต้องการ)
    setInterval(checkNewRows, 3000);
  });

/* flatpickr("#statFrom", { dateFormat: "Y-m-d" });
flatpickr("#statTo", { dateFormat: "Y-m-d" }); */

flatpickr('#statFrom', {
  enableTime: true,
  time_24hr:  true,
  dateFormat: 'Y-m-d H:i'
});
flatpickr('#statTo', {
  enableTime: true,
  time_24hr:  true,
  dateFormat: 'Y-m-d H:i'
});

flatpickr("#durationFrom", { dateFormat: "Y-m-d" });
flatpickr("#durationTo", { dateFormat: "Y-m-d" });
flatpickr("#dateFrom", { dateFormat: "Y-m-d" });
flatpickr("#dateTo", { dateFormat: "Y-m-d" });
flatpickr("#freqFrom", { dateFormat: "Y-m-d" });
flatpickr("#freqTo",   { dateFormat: "Y-m-d" });



$(document).ready(function () {
	  // ย้าย listener ทั้งหมดมาไว้ในนี้เลย เพื่อให้ globalPlayer/Container มองเห็นได้
	  globalContainer = $('#global-audio-container');
	  globalPlayer    = $('#globalPlayer')[0];
	
    table = $('#recordTable').DataTable({
        serverSide: true,
        processing: true,
        ajax: {
            url: 'data.php',
            type: 'POST',
            data: function (d) {
                d.dateFrom = $('#dateFrom').val();
                d.dateTo = $('#dateTo').val();
				d.source = $('#sourceFilter').val();
            }
        },
        pageLength: 100,
        order: [[2, 'desc']],
		fixedHeader: true,
		columnDefs: [
		  {
			targets: 0, // คอลัมน์ checkbox
			orderable: false
		  },
		  {
			targets: 6,      // zero-based index ของคอลัมน์ duration
			render: sec => sec
		  },
		{
		  targets: 7,
		  render: function (data) {
			if (data === "[ไม่สามารถถอดข้อความจากเสียงได้]") {
				return `<span class="badge bg-danger" data-bs-toggle="tooltip" title="เกิดข้อผิดพลาดในการประมวลผลเสียง">
						<i class="bi bi-x-circle-fill me-1"></i> ไม่สามารถถอดข้อความจากเสียงได้</span>`;
			}
			return data;
		  }
		},
		  {
			targets: 8,      // ตำแหน่งคอลัมน์ Tag
			orderable: false,
			data: null,
			render: (data, type, row) => {
			  // data คือค่า row[9] ที่เป็น <span class="row-tag">…</span>
			  return row[8];
			}
		  },
		  {
			targets: 9, // คอลัมน์ระบบแปลงเสียง
			render: function (data) {
			  if (data === 'Azure AI Speech to Text') return '<span class="badge bg-primary" title="แปลงโดย Microsoft Azure AI Speech to Text"><i class="bi bi-cloud"></i> Azure</span>';
			  if (data === 'Google Cloud Speech-to-Text') return '<span class="badge bg-success" title="แปลงโดย Google Cloud Speech-to-Text"><i class="bi bi-soundwave"></i> Google Cloud</span>';
			  if (data === 'Speechmatics Speech-to-Text') return '<span class="badge bg-info" title="แปลงโดย Speechmatics Speech-to-Text"><i class="bi bi-soundwave"></i> Speechmatics</span>';
			  if (data === 'Whisper') return '<span class="badge bg-success" title="แปลงโดย OpenAI Whisper"><i class="bi bi-robot"></i> Whisper</span>';
			  if (data === 'Wav2Vec2') return '<span class="badge badge-purple" title="แปลงโดย Facebook Wav2Vec2"><i class="bi bi-soundwave"></i> Wav2Vec2</span>';
			  return data;
			}
		  }
		],
        language: {
            search: "ค้นหา:",
            lengthMenu: "แสดง _MENU_ รายการ",
            zeroRecords: "ไม่พบข้อมูล",
            info: "แสดง _START_ ถึง _END_ จาก _TOTAL_ รายการ",
            infoEmpty: "ไม่มีข้อมูล",
            infoFiltered: "(กรองจากทั้งหมด _MAX_ รายการ)",
            paginate: {
                first: "หน้าแรก",
                last: "หน้าสุดท้าย",
                next: "ถัดไป",
                previous: "ก่อนหน้า"
            }
        }
    });
	


  
/*   table.on('draw', function() {
    const $firstPlay = table.$('tbody .play-btn').first();
    if (!$firstPlay.length) return;
    const src = $firstPlay.data('src');
    globalPlayer.src = src;
    globalPlayer.currentTime = 0;
    globalPlayer.play().catch(err => {
      console.warn('Autoplay blocked:', err);
    });
    globalContainer.fadeIn(200);
  }); */
  


  
  // ฟังก์ชันช่วยซ่อน player
  function hidePlayer() {
    globalContainer.fadeOut(500);
  }
  
  // เมื่อผู้ใช้กด pause (หรือเสียงหยุดกลางคัน) ให้ตั้ง timer
  globalPlayer.addEventListener('pause', () => {
    // ถ้าเกิด pause จาก ended จะมี event pause ด้วย แต่ ended จะซ่อนทันทีก่อน
    clearTimeout(fadeTimeout);
    fadeTimeout = setTimeout(() => {
      if (globalPlayer.paused) {
        hidePlayer();
      }
    }, 10000); // 10 วินาทีหลัง pause จะซ่อน
  });
  
  // เมื่อเริ่มเล่นใหม่ ให้ยกเลิก timer และโชว์ player ถ้ามันซ่อนอยู่
  globalPlayer.addEventListener('play', () => {
    clearTimeout(fadeTimeout);
    if (!globalContainer.is(':visible')) {
      globalContainer.fadeIn(200);
    }
  });
  
  // เมื่อคลิกปุ่มเล่นในตาราง
  //$('#recordTable tbody').on('click', '.play-btn', function() {
  $(document).on('click', '.play-btn', function() {
	  
/*     const newSrc = $(this).data('src');
    if (!newSrc) return;
	
	// ตรวจสอบว่า URL ที่จะเล่นเป็น URL เดียวกับที่ globalPlayer มีอยู่หรือไม่
    // การใช้ new URL(...).pathname อาจจะช่วยให้การเปรียบเทียบ src แม่นยำขึ้น
    // หาก src อาจจะมี query parameters หรือ fragment ที่แตกต่างกัน
    let currentSrcPath = "";
    try {
        currentSrcPath = globalPlayer.src ? new URL(globalPlayer.src).pathname : "";
    } catch (e) {
        currentSrcPath = globalPlayer.src || ""; // Fallback if URL parsing fails
    }

    let newSrcPath = "";
    try {
        newSrcPath = new URL(newSrc, window.location.href).pathname; // Resolve newSrc relative to current page
    } catch (e) {
        newSrcPath = newSrc; // Fallback
    }


    if (currentSrcPath.endsWith(newSrcPath)) { // ถ้าเป็นไฟล์เสียงเดียวกัน
        if (globalPlayer.paused) {
            globalPlayer.play(); // ถ้า Pause อยู่ ให้เล่นต่อ
        } else {
            globalPlayer.pause(); // ถ้ากำลังเล่นอยู่ ให้ Pause
        }
    } else {
        // ถ้าเป็นไฟล์ใหม่ หรือ URL ไม่ตรงกัน (เช่น กรณีกดเล่นจากแถวอื่น)
        globalPlayer.src = newSrc;
        globalPlayer.currentTime = 0; // เริ่มเล่นไฟล์ใหม่ตั้งแต่ต้น
        globalPlayer.play().catch(error => {
            console.warn("Autoplay for new source was blocked:", error);
            // อาจจะต้องมี UI ให้ผู้ใช้กด play เองอีกครั้งถ้า autoplay ถูก block
        });
    } */
	
    const src = $(this).data('src');
    if (!src) return;

    // ถ้า player กำลังเล่นไฟล์เดิมอยู่
    if (globalPlayer.src.endsWith(src) && !globalPlayer.paused) {
      // ให้หยุดหรือเล่นต่อกลับได้ (toggle)
      globalPlayer.pause();
    } else if (globalPlayer.src.endsWith(src) && globalPlayer.paused) {
      // ถ้าเป็นไฟล์เดิม และกำลัง pause อยู่ ให้เล่นต่อ
      globalPlayer.play();
    } else {
      // โหลดไฟล์ใหม่
      globalPlayer.src = src;
      globalPlayer.currentTime = 0;
      globalPlayer.play();
    }

    // แสดงตัว player bar ถ้ายังซ่อนอยู่
    if (!globalContainer.is(':visible')) {
      globalContainer.fadeIn(300);
    }
  });

  // (option) ให้กดปุ่ม hide ได้ หรือซ่อนอัตโนมัติเม้ือจบ
  globalPlayer.addEventListener('ended', () => {
    globalContainer.fadeOut(500);
  });
	

	  // 3) เก็บ ID ของแถวที่ถูกติ๊ก
	  const selectedIds = new Set();
	  $('#recordTable tbody').on('change', '.row-checkbox', function() {
		const id = $(this).val();
		if (this.checked) selectedIds.add(id);
		else              selectedIds.delete(id);
	  });

	  // 4) ฟังก์ชัน reload โดยไม่เปลี่ยนหน้า
/* 	  function reloadTableKeepSelection() {
		table.ajax.reload(null, false);
	  } */

	  // 5) เมื่อ DataTable วาดเสร็จ (draw) ให้กู้คืน checkbox และอัปเดต checkAll
	  // เมื่อ DataTable โหลด/รี-วาดเสร็จ
	  table.on('draw', function() {
		// กู้คืนการติ๊ก
		table.$('.row-checkbox').each(function() {
		  $(this).prop('checked', selectedIds.has($(this).val()));
		});
		// อัปเดต “เลือกทั้งหมด” ตามสถานะ
		const all = table.$('.row-checkbox').length > 0;
		const noneUnchecked = table.$('.row-checkbox:not(:checked)').length === 0;
		$('#checkAll').prop('checked', all && noneUnchecked);
	  });

    $('#filterBtn').on('click', function () {
        table.ajax.reload();
    });

    $('#clearBtn').on('click', function () {
        $('#dateFrom').val('');
        $('#dateTo').val('');
		$('#sourceFilter').val('');
        table.ajax.reload();
    });

    <?php if ($logged_in): ?>
    $(document).on('click', '.delete-btn', function () {
        const id = $(this).data('id');
        const filename = $(this).data('file');

        Swal.fire({
            title: 'คุณแน่ใจหรือไม่?',
            text: `ต้องการลบไฟล์ "${filename}" หรือไม่?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'ใช่, ลบเลย!',
            cancelButtonText: 'ยกเลิก'
        }).then((result) => {
            if (result.isConfirmed) {
                $.post("delete.php", { id, filename }, function (res) {
                    if (res.success) {
                        //$('#row-' + id).fadeOut();
						table.ajax.reload(null, false); // รีโหลดเฉพาะแถว ไม่รีหน้า
                        Swal.fire('ลบแล้ว!', '', 'success');
                    } else {
                        Swal.fire('ผิดพลาด!', res.error, 'error');
                    }
                }, "json");
            }
        });
    });
    <?php endif; ?>

    $('#checkAll').on('click', function () {
        $('.row-checkbox').prop('checked', this.checked);
    });

    $('#bulkDelete').on('click', function () {
        const ids = [];
        const files = [];

        $('.row-checkbox:checked').each(function () {
            ids.push($(this).val());
            files.push($(this).data('file'));
        });

        if (ids.length === 0) {
            Swal.fire('กรุณาเลือกไฟล์ที่ต้องการลบ');
            return;
        }

        $.post("get_file_sizes.php", { files }, function (res) {
            if (!res.success) {
                Swal.fire('ไม่สามารถอ่านขนาดไฟล์ได้');
                return;
            }

            const sizeMB = (res.total_size / (1024 * 1024)).toFixed(2);

            Swal.fire({
                title: `ลบ ${ids.length} รายการ?`,
                html: `ขนาดรวมไฟล์ที่จะลบ: <b>${sizeMB} MB</b>`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'ลบเลย',
                cancelButtonText: 'ยกเลิก',
            }).then((result) => {
                if (result.isConfirmed) {
                    $.post("delete_bulk.php", { ids, files }, function (res) {
                        if (res.success) {
                            //ids.forEach(id => $('#row-' + id).fadeOut());
							Swal.fire('ลบเรียบร้อย', '', 'success');
							table.ajax.reload(null, false); // รีโหลดข้อมูลหน้าเดิม
                        } else {
                            Swal.fire('ผิดพลาด!', res.error, 'error');
                        }
                    }, "json");
                }
            });
        }, "json");
    });
	
	const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
	tooltipTriggerList.forEach(function (tooltipTriggerEl) {
	  new bootstrap.Tooltip(tooltipTriggerEl);
	});
	
    const notificationSoundEnabledKey = 'notificationSoundEnabled';
    let isNotificationSoundEnabled = localStorage.getItem(notificationSoundEnabledKey) === 'true'; // Default to false if not set

    const $toggleSoundBtn = $('#toggleNotificationSound');
    const $toggleSoundIcon = $toggleSoundBtn.find('i');
    const $toggleSoundText = $toggleSoundBtn.find('span');

    function updateSoundButtonUI() {
        if (isNotificationSoundEnabled) {
            $toggleSoundIcon.removeClass('bi-volume-mute-fill').addClass('bi-volume-up-fill');
            $toggleSoundText.text('เปิดเสียงแจ้งเตือนแล้ว');
            $toggleSoundBtn.removeClass('btn-outline-secondary').addClass('btn-success');
        } else {
            $toggleSoundIcon.removeClass('bi-volume-up-fill').addClass('bi-volume-mute-fill');
            $toggleSoundText.text('ปิดเสียงแจ้งเตือนแล้ว');
            $toggleSoundBtn.removeClass('btn-success').addClass('btn-outline-secondary');
        }
    }

    // ตั้งค่า UI ของปุ่มเมื่อโหลดหน้า
    updateSoundButtonUI();

    $toggleSoundBtn.on('click', function() {
        isNotificationSoundEnabled = !isNotificationSoundEnabled;
        localStorage.setItem(notificationSoundEnabledKey, isNotificationSoundEnabled);
        updateSoundButtonUI();
        if (isNotificationSoundEnabled) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: 'เปิดเสียงแจ้งเตือนแล้ว',
                showConfirmButton: false,
                timer: 1500
            });
        } else {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'info',
                title: 'ปิดเสียงแจ้งเตือนแล้ว',
                showConfirmButton: false,
                timer: 1500
            });
        }
    });
	
    const autoplayLatestAudioEnabledKey = 'autoplayLatestAudioEnabled';
    let isAutoplayLatestAudioEnabled = localStorage.getItem(autoplayLatestAudioEnabledKey) === 'true'; // Default to false

    const $toggleAutoplayBtn = $('#toggleAutoplayLatestAudio');
    const $toggleAutoplayIcon = $toggleAutoplayBtn.find('i');
    const $toggleAutoplayText = $toggleAutoplayBtn.find('span');

    function updateAutoplayLatestAudioButtonUI() {
        if (isAutoplayLatestAudioEnabled) {
            $toggleAutoplayIcon.removeClass('bi-stop-circle-fill').addClass('bi-play-circle-fill');
            $toggleAutoplayText.text('เปิดเล่นเสียงล่าสุดอัตโนมัติแล้ว');
            $toggleAutoplayBtn.removeClass('btn-outline-secondary').addClass('btn-success');
        } else {
            $toggleAutoplayIcon.removeClass('bi-play-circle-fill').addClass('bi-stop-circle-fill');
            $toggleAutoplayText.text('ปิดเล่นเสียงล่าสุดอัตโนมัติแล้ว');
            $toggleAutoplayBtn.removeClass('btn-success').addClass('btn-outline-secondary');
        }
    }

    // ตั้งค่า UI ของปุ่มเมื่อโหลดหน้า
    updateAutoplayLatestAudioButtonUI();

   $('#toggleAutoplayLatestAudio').on('click', function() {
        isAutoplayLatestAudioEnabled = !isAutoplayLatestAudioEnabled;
        localStorage.setItem(autoplayLatestAudioEnabledKey, isAutoplayLatestAudioEnabled);
        updateAutoplayLatestAudioButtonUI();
        if (isAutoplayLatestAudioEnabled) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: 'เปิดเล่นเสียงล่าสุดอัตโนมัติแล้ว',
                showConfirmButton: false,
                timer: 1500
            });
            // หากเปิดใช้งาน และมี globalPlayer ที่กำลังเล่นไฟล์อื่นอยู่ อาจจะต้องการให้หยุด
            // หรือปล่อยให้ user จัดการเอง
        } else {	
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'info',
                title: 'ปิดเล่นเสียงล่าสุดอัตโนมัติแล้ว',
                showConfirmButton: false,
                timer: 1500
            });
            // หากปิดใช้งาน และมี currentNotificationAudio กำลังเล่นอยู่ ให้หยุด
			if (!isAutoplayLatestAudioEnabled) { // ถ้าเพิ่งปิดการเล่นอัตโนมัติ
				audioNotificationQueue = []; // ล้างคิว
				if (currentNotificationAudio && typeof currentNotificationAudio.pause === 'function' && isAutoplayLatestAudioPlaying) {
					currentNotificationAudio.pause();
					currentNotificationAudio.currentTime = 0;
					isAutoplayLatestAudioPlaying = false;
					console.log("หยุดเล่นเสียงล่าสุดอัตโนมัติและล้างคิว (เนื่องจากผู้ใช้ปิดฟีเจอร์)");
				}
			}
        }
    });

});

// เมื่อดับเบิลคลิกที่ cell ของคอลัมน์ Tag
$('#recordTable').on('click', 'td:nth-child(9)', function(){
  // td:nth-child(10) คือคอลัมน์ที่ 9 (1-based index)
  
/*   const $td = $(this);
  const $span = $td.find('.row-tag');
  const old = $span.text();
  // สร้าง input แทน span
  const $input = $(`<input type="text" class="form-control form-control-sm" value="${old}">`);
  $span.replaceWith($input);
  $input.focus(); */
  
	const $td = $(this);
	const old = $td.text().trim();
	$td.html(`<input class="form-control" value="${old}">`);
	const $input = $td.find('input').focus();

  // เมื่อกด Enter หรือ focusout ให้ save
  $input.on('keydown', function(e){
    if (e.key==='Enter') saveNote();
  }).on('blur', saveNote);

  function saveNote(){
    const val = $input.val().trim();
    const data = table.row($td.closest('tr')).data();
    const id   = data[1]; // col index 1 = ID
	
/*   Fix 2: Grab the DataTable instance on the fly
	//If you don’t want a global variable, inside saveTag() you can always do:
	// find the table element and get its DataTable API object
  const table = $('#recordTable').DataTable();
  const tr    = $input.closest('tr');
  const data  = table.row(tr).data(); */
  
    $.post('update_note.php', { id, note: val }, function(res){
      if (res.success) {
        // ใส่กลับเป็น span ใหม่
        $input.replaceWith(`<span class="row-tag">${val}</span>`);
      } else {
        alert('Error: '+res.error);
        $input.replaceWith(`<span class="row-tag">${old}</span>`);
      }
    },'json');
  }
});


$(document).on('click', '.unauth', function (e) {
    e.preventDefault();
    Swal.fire({
        icon: 'info',
        title: 'กรุณาเข้าสู่ระบบ',
        text: 'คุณต้องเข้าสู่ระบบก่อนจึงจะสามารถลบรายการได้',
        confirmButtonText: 'ตกลง'
    });
});

let statChart =null;
function loadStatChart() {
  const from = $('#statFrom').val();
  const to = $('#statTo').val();

  $.getJSON("chart_data_stacked.php", { dateFrom: from, dateTo: to }, function (res) {
    const ctx = document.getElementById('statChart').getContext('2d');

    if (window.statChart && typeof window.statChart.destroy === 'function') {
		window.statChart.destroy();
	}
    window.statChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: res.datasets.map(ds => ({
          ...ds,
          backgroundColor: getColor(ds.label)
        }))
      },
      options: {
        responsive: true,
        plugins: {
          tooltip: { mode: 'index', intersect: false },
          title: { display: true, text: 'จำนวนไฟล์ที่บันทึก แยกตามระบบแปลงเสียง' },
          legend: { position: 'top' }
        },
        scales: {
          x: { stacked: true },
          y: {
            stacked: true,
            beginAtZero: true,
            title: { display: true, text: 'จำนวนไฟล์' },
            ticks: { precision: 0 }
          }
        }
      }
    });
  });
}

function getColor(source) {
  if (source.includes("Azure")) return 'rgba(13,110,253,0.6)';         // น้ำเงิน
  if (source.includes("Google")) return 'rgba(25,135,84,0.6)';         // เขียว
  if (source.includes("Speechmatics")) return 'rgba(13,202,240,0.6)';        // น้ำเงิน
  if (source.includes("Whisper")) return 'rgba(255,193,7,0.6)';          // เหลือง
  if (source.includes("Wav2Vec2")) return 'rgba(108,117,125,0.6)';      // เทาเข้ม
  if (source.includes("ไม่ระบุ")) return 'rgba(108,117,125,0.4)';       // เทาอ่อน ✅
  return 'rgba(150,150,150,0.4)';  // default สำรอง
}

$('#filterStatBtn').on('click', loadStatChart);
loadStatChart(); // โหลดกราฟครั้งแรก

$(document).ready(function() {
  // (option) reload อัตโนมัติทุก 5 นาที
  setInterval(loadStatChart, 5 * 60 * 1000);
});


let durationChart;
function loadDurationChart() {
  const from = $('#durationFrom').val();
  const to = $('#durationTo').val();

  $.getJSON("chart_duration.php", { dateFrom: from, dateTo: to }, function (res) {
    const ctx = document.getElementById('durationChart').getContext('2d');

    // ถ้ามีกราฟเก่า ลบทิ้งก่อน
    if (durationChart) {
      durationChart.destroy();
    }

    durationChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'จำนวนวินาทีรวมที่อัดเสียงต่อวัน',
          data: res.data,
          backgroundColor: 'rgba(255,128,0,0.6)',
          /* borderColor: 'rgba(255,193,7,1)',
          borderWidth: 2, */
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'วินาที'
            }
          }
        }
      }
    });
  });
}

$(document).ready(function() {
  // (option) reload อัตโนมัติทุก 5 นาที
  setInterval(loadDurationChart, 5 * 60 * 1000);
});


let hourlyChart = null;
function loadHourlyChart() {
  const from = $('#hourlyFrom').val();
  const to   = $('#hourlyTo').val();

  $.getJSON('chart_hourly.php', { dateFrom: from, dateTo: to }, function(res) {
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    if (hourlyChart) hourlyChart.destroy();

    hourlyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'นาทีที่บันทึกต่อชั่วโมง',
          data: res.data,
          backgroundColor: 'rgba(13,110,253,0.6)',
          borderColor:     'rgba(13,110,253,1)',
          borderWidth:     1
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: 'ช่วงเวลาแต่ละชั่วโมง' } },
          y: {
            beginAtZero: true,
            title: { display: true, text: 'นาที' },
            ticks: { precision: 0 }
          }
        }
      }
    });
  });
}

$(document).ready(function() {
  // init flatpickr
  flatpickr('#hourlyFrom', { dateFormat: 'Y-m-d' });
  flatpickr('#hourlyTo',   { dateFormat: 'Y-m-d' });

  // filter button
  $('#filterHourlyBtn').on('click', loadHourlyChart);

  // initial load
  loadHourlyChart();

  // (option) reload อัตโนมัติทุก 5 นาที
  setInterval(loadHourlyChart, 5 * 60 * 1000);
});


let freqChart = null;
function loadFreqChart() {
  const from = $('#freqFrom').val();
  const to   = $('#freqTo').val();

  $.getJSON("chart_frequency.php", { dateFrom: from, dateTo: to }, function(res) {
    const ctx = document.getElementById("freqChart").getContext("2d");
    if (freqChart) freqChart.destroy();

    freqChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: res.labels,
        datasets: [{
          label: "จำนวนการบันทึก ตามความถี่",
          data: res.data,
          backgroundColor: res.labels.map(l =>
            l === "อื่น ๆ / ไม่ได้ระบุ" ? "rgba(108,117,125,0.6)" : "rgba(13,110,253,0.6)"
          )
/*           borderColor: res.labels.map(l =>
            l === "อื่น ๆ / ไม่ได้ระบุ" ? "rgba(108,117,125,1)" : "rgba(13,110,253,1)"
          ),
          borderWidth: 1 */
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "ความถี่ (MHz)" } },
          y: {
            beginAtZero: true,
            title: { display: true, text: "จำนวนการบันทึก" },
            ticks: { precision: 0 }
          }
        }
      }
    });
  });
}

$(document).ready(function() {
  flatpickr("#freqFrom", { dateFormat: "Y-m-d" });
  flatpickr("#freqTo",   { dateFormat: "Y-m-d" });

  $('#filterFreqBtn').on('click', loadFreqChart);
  loadFreqChart();  // initial load
  
  // (option) reload อัตโนมัติทุก 5 นาที
  setInterval(loadFreqChart, 5 * 60 * 1000);
});


$('#filterDurationBtn').on('click', loadDurationChart);
loadDurationChart(); // โหลดตอนเริ่มหน้า

let failedChart = null;

function loadFailedChart() {
  const from = $('#failedFrom').val();
  const to   = $('#failedTo').val();

  $.getJSON('chart_failed.php', { dateFrom: from, dateTo: to }, function(res) {
    const ctx = document.getElementById('failedChart').getContext('2d');
    if (failedChart) failedChart.destroy();

    failedChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'จำนวนถอดข้อความล้มเหลว',
          data: res.data,
          backgroundColor: 'rgba(220,53,69,0.6)'   // สีแดง bootstrap
          //borderColor:     'rgba(220,53,69,1)',
          //borderWidth:     1
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: 'ระบบแปลงเสียง' } },
          y: {
            beginAtZero: true,
            title: { display: true, text: 'จำนวนรายการ' },
            ticks: { precision: 0 }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: { mode: 'index', intersect: false }
        }
      }
    });
  });
}

$(document).ready(function() {
  // init Flatpickr
  //flatpickr('#failedFrom', { dateFormat: 'Y-m-d' });
  //flatpickr('#failedTo',   { dateFormat: 'Y-m-d' });
	flatpickr('#failedFrom', {
	  enableTime: true,
	  time_24hr:  true,
	  dateFormat: 'Y-m-d H:i'
	});
	flatpickr('#failedTo', {
	  enableTime: true,
	  time_24hr:  true,
	  dateFormat: 'Y-m-d H:i'
	});

  // filter button
  $('#filterFailedBtn').on('click', loadFailedChart);

  // initial load
  loadFailedChart();

  // (option) reload ทุก 5 นาที
  setInterval(loadFailedChart, 5 * 60 * 1000);
});


const colorMap = {
  "อื่น ๆ / ไม่ได้ระบุ": "rgba(108,117,125,0.6)",
  "Azure AI Speech to Text": "rgba(13,110,253,0.6)",
  "Google Cloud Speech-to-Text": "rgba(25,135,84,0.6)",
  "Speechmatics Speech-to-Text": "rgba(13,202,240,0.6)"
};
// default ถ้าไม่ match key ใดๆ
const defaultColor = "rgba(108,117,125,0.6)";

// ตัวแปรเก็บ Chart object
let totalSourceChart = null;

// ฟังก์ชันโหลดข้อมูลแล้ววาดกราฟ
function loadTotalSourceChart() {
  const from = $('#totalFrom').val();
  const to   = $('#totalTo').val();

  $.getJSON('chart_total_duration.php', { dateFrom: from, dateTo: to }, function(res) {
    const ctx = document.getElementById('totalSourceChart').getContext('2d');
    if (totalSourceChart) {
      totalSourceChart.destroy();
    }
    totalSourceChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'ระยะเวลารวม (นาที)',
          data: res.data,
          //backgroundColor: 'rgba(0,255,0,0.6)'
		  backgroundColor: res.labels.map(l => colorMap[l] || defaultColor)
/* 		  backgroundColor: res.labels.map(l =>
            l === "อื่น ๆ / ไม่ได้ระบุ" ? "rgba(108,117,125,0.6)" :
			l === "Azure AI Speech to Text" ? "rgba(13,110,253,0.6)" :
			l === "Google Cloud Speech-to-Text" ? "rgba(25,135,84,0.6)" :
			l === "Speechmatics Speech-to-Text" ? "rgba(13,202,240,0.6)" :
			"rgba(13,110,253,0.6)" // else
          ) */
          //borderColor:     'rgba(108,117,125,1)',
          //borderWidth:     1
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: 'ระบบแปลงเสียง' } },
          y: {
            beginAtZero: true,
            title: { display: true, text: 'นาที' },
            ticks: { precision: 0 }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  });
}

$(document).ready(function() {
  // init Flatpickr แบบวัน-เวลา
  flatpickr('#totalFrom', {
    enableTime: true,
    time_24hr:  true,
    dateFormat: 'Y-m-d H:i'
  });
  flatpickr('#totalTo', {
    enableTime: true,
    time_24hr:  true,
    dateFormat: 'Y-m-d H:i'
  });

  // เมื่อกดกรอง
  $('#filterTotalBtn').on('click', loadTotalSourceChart);

  // โหลดครั้งแรก
  loadTotalSourceChart();

  // (option) อัปเดตอัตโนมัติทุก 5 นาที
  setInterval(loadTotalSourceChart, 5 * 60 * 1000);
});




function updateOnlineCount() {
  $.getJSON('online.php', function(res) {
    $('#onlineCount').text(res.online);
  });
}

// เรียกครั้งแรกแล้วให้ refresh ทุก 20 วินาที
updateOnlineCount();
setInterval(updateOnlineCount, 20000);

/* $('#enableAudio').on('click', () => {
  globalPlayer.muted = true;
  globalPlayer.play()
    .then(()=> {
      globalPlayer.pause();
      globalPlayer.muted = false;
      console.log('Autoplay unlocked');
    })
    .catch(err=> console.warn('Cannot unlock autoplay:', err));
}); */

/* $('#enableAlertSound').on('click', () => {
  const snd = document.getElementById('rowAlertSound');
  snd.muted = true;
  snd.play().then(()=> {
    snd.pause();
    snd.muted = false;
    console.log('ปลดล็อคเสียงแจ้งเตือนแล้ว');
  });
}); */

/* $('#enableAlertSound').on('click', () => {
  const snd = document.getElementById('rowAlertSound');
  if (snd) { // ตรวจสอบว่า snd ไม่ใช่ null
    snd.muted = true;
    snd.play().then(()=> {
      snd.pause();
      snd.muted = false;
      console.log('ปลดล็อคเสียงแจ้งเตือนแล้ว');
    }).catch(error => {
      console.warn('Error playing sound for unlocking:', error);
    });
  } else {
    console.error('ไม่พบ Element เสียงที่มี ID "rowAlertSound"');
    // อาจจะแจ้งเตือนผู้ใช้ หรือทำอย่างอื่น
    Swal.fire({
        icon: 'error',
        title: 'เกิดข้อผิดพลาด',
        text: 'ไม่พบองค์ประกอบเสียงสำหรับแจ้งเตือน กรุณาติดต่อผู้ดูแลระบบ'
    });
  }
}); */

$('#enableAudio').on('click', () => {
  globalPlayer.muted = true;
  globalPlayer.play()
    .then(()=> {
      globalPlayer.pause();
      globalPlayer.muted = false;
      console.log('Autoplay unlocked');
    })
    .catch(err=> console.warn('Cannot unlock autoplay:', err));
});

</script>
</body>
</html>
