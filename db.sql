-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS 1crop_yield_prediction;

-- Switch to the created database
USE 1crop_yield_prediction;

-- Drop the table if it exists
DROP TABLE IF EXISTS `users`;

-- Create the user table with correct structure
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `email` VARCHAR(255) UNIQUE NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `address` TEXT,
    `registration_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);