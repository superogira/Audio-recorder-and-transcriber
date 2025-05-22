-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:3306
-- Generation Time: May 22, 2025 at 10:07 PM
-- Server version: 10.11.11-MariaDB-0+deb12u1
-- PHP Version: 8.4.5

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `recorder_transcriber`
--

-- --------------------------------------------------------

--
-- Table structure for table `online_users`
--

CREATE TABLE `online_users` (
  `session_id` varchar(128) NOT NULL,
  `last_activity` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `records`
--

CREATE TABLE `records` (
  `id` int(11) NOT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `transcript` text DEFAULT NULL,
  `source` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `frequency` varchar(20) DEFAULT NULL,
  `station` varchar(50) DEFAULT NULL,
  `duration` float DEFAULT NULL,
  `note` varchar(255) DEFAULT NULL,
  `drive_url` varchar(512) DEFAULT NULL,
  `local_path` varchar(255) DEFAULT NULL,
  `file_location_type` enum('local','drive','archived') NOT NULL DEFAULT 'local'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `telegram_notifications_config`
--

CREATE TABLE `telegram_notifications_config` (
  `id` int(11) NOT NULL,
  `keyword` varchar(255) NOT NULL,
  `bot_token` varchar(255) NOT NULL,
  `chat_id` varchar(255) NOT NULL,
  `custom_message_prefix` text DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `online_users`
--
ALTER TABLE `online_users`
  ADD PRIMARY KEY (`session_id`);

--
-- Indexes for table `records`
--
ALTER TABLE `records`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `telegram_notifications_config`
--
ALTER TABLE `telegram_notifications_config`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_keyword_chat` (`keyword`,`chat_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `records`
--
ALTER TABLE `records`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

--
-- AUTO_INCREMENT for table `telegram_notifications_config`
--
ALTER TABLE `telegram_notifications_config`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
