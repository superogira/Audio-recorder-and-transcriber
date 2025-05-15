<?php
$host = 'localhost';
$dbname = 'xxxxxx';
$user = 'xxxxxx';
$pass = 'xxxxxx';

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8mb4", $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    die("❌ ไม่สามารถเชื่อมต่อฐานข้อมูล: " . $e->getMessage());
}
