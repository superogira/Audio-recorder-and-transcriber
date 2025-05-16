<?php
session_start();
$logged_in = $_SESSION['logged_in'] ?? false;
?>

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>รายการเสียงและข้อความที่บันทึกไว้</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
	<!-- Bootstrap Icons -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">

	<!-- Flatpickr -->
	<link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css" rel="stylesheet">
	<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
	<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        body { font-size: 1.1rem; }
        h2 { font-size: 2rem; }
      .badge-purple { background-color: #6f42c1; }
	  .container-99 {
		max-width: 99vw;
		margin: 0 auto;
	  }
    </style>
</head>
<body class="bg-light">
<div class="mb-3">
    <?php if ($logged_in): ?>
        <a href="logout.php" class="btn btn-outline-secondary">ออกจากระบบ</a>
    <?php else: ?>
        <a href="login.php" class="btn btn-outline-primary">เข้าสู่ระบบผู้ดูแล</a>
    <?php endif; ?>
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
              <input type="text" id="statFrom" class="form-control" placeholder="จากวันที่">
            </div>
            <div class="col-auto">
              <input type="text" id="statTo"   class="form-control" placeholder="ถึงวันที่">
            </div>
            <div class="col-auto">
              <button id="filterStatBtn" class="btn btn-outline-primary">กรอง</button>
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
              <button id="filterDurationBtn" class="btn btn-outline-success">กรอง</button>
            </div>
          </div>
          <canvas id="durationChart" height="100"></canvas>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container-fluid mt-5 px-5">
    <h2 class="mb-4">📻 รายการเสียงที่บันทึกและข้อความที่ถอดได้ จากการ Scan เฝ้าฟังในช่วงความถี่ 144-147 MHz</h2>

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
        <option value="Whisper">Whisper</option>
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
                    <th>ข้อความ</th>
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

<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>

<script>
flatpickr("#statFrom", { dateFormat: "Y-m-d" });
flatpickr("#statTo", { dateFormat: "Y-m-d" });
flatpickr("#durationFrom", { dateFormat: "Y-m-d" });
flatpickr("#durationTo", { dateFormat: "Y-m-d" });
flatpickr("#dateFrom", { dateFormat: "Y-m-d" });
flatpickr("#dateTo", { dateFormat: "Y-m-d" });


$(document).ready(function () {
    const table = $('#recordTable').DataTable({
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
		columnDefs: [
		  {
			targets: 0, // คอลัมน์ checkbox
			orderable: false
		  },
		{
		  targets: 6,
		  render: function (data) {
			if (data === "[ไม่สามารถถอดข้อความจากเสียงได้]") {
				return `<span class="badge bg-danger" data-bs-toggle="tooltip" title="เกิดข้อผิดพลาดในการประมวลผลเสียง">
						<i class="bi bi-x-circle-fill me-1"></i> ไม่สามารถถอดข้อความจากเสียงได้</span>`;
			}
			return data;
		  }
		},
		  {
			targets: 7, // คอลัมน์ระบบแปลงเสียง
			render: function (data) {
			  if (data === 'Azure AI Speech to Text') return '<span class="badge bg-primary" title="แปลงโดย Microsoft Azure AI Speech to Text"><i class="bi bi-cloud"></i> Azure</span>';
			  if (data === 'Whisper') return '<span class="badge bg-success" title="แปลงโดย OpenAI Whisper"><i class="bi bi-robot"></i> Whisper</span>';
			  if (data === 'Wav2Vec2') return '<span class="badge badge-purple" title="แปลงโดย Facebook Wav2Vec2"><i class="bi bi-soundwave"></i> Wav2Vec2</span>';
			  if (data === 'Google Cloud Speech-to-Text') return '<span class="badge bg-success" title="แปลงโดย Google Cloud Speech-to-Text"><i class="bi bi-soundwave"></i> Google Cloud</span>';
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
  if (source.includes("Whisper")) return 'rgba(255,193,7,0.6)';          // เหลือง
  if (source.includes("Wav2Vec2")) return 'rgba(108,117,125,0.6)';      // เทาเข้ม
  if (source.includes("ไม่ระบุ")) return 'rgba(108,117,125,0.4)';       // เทาอ่อน ✅
  return 'rgba(150,150,150,0.4)';  // default สำรอง
}

$('#filterStatBtn').on('click', loadStatChart);
loadStatChart(); // โหลดกราฟครั้งแรก


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
          backgroundColor: 'rgba(25, 135, 84, 0.2)',
          borderColor: 'rgba(25, 135, 84, 1)',
          borderWidth: 2,
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

$('#filterDurationBtn').on('click', loadDurationChart);
loadDurationChart(); // โหลดตอนเริ่มหน้า



</script>
</body>
</html>
