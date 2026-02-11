CREATE TABLE `data_points` (
	`id` int AUTO_INCREMENT NOT NULL,
	`flight_test_id` int NOT NULL,
	`parameter_id` int NOT NULL,
	`timestamp` timestamp NOT NULL,
	`value` text NOT NULL,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `data_points_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `flight_tests` (
	`id` int AUTO_INCREMENT NOT NULL,
	`name` varchar(255) NOT NULL,
	`description` text,
	`test_date` timestamp NOT NULL,
	`aircraft` varchar(255),
	`status` enum('draft','in_progress','completed','archived') NOT NULL DEFAULT 'draft',
	`created_by_id` int NOT NULL,
	`created_at` timestamp NOT NULL DEFAULT (now()),
	`updated_at` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `flight_tests_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `test_parameters` (
	`id` int AUTO_INCREMENT NOT NULL,
	`name` varchar(255) NOT NULL,
	`unit` varchar(50),
	`description` text,
	`parameter_type` varchar(100),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `test_parameters_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `data_points` ADD CONSTRAINT `data_points_flight_test_id_flight_tests_id_fk` FOREIGN KEY (`flight_test_id`) REFERENCES `flight_tests`(`id`) ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `data_points` ADD CONSTRAINT `data_points_parameter_id_test_parameters_id_fk` FOREIGN KEY (`parameter_id`) REFERENCES `test_parameters`(`id`) ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE `flight_tests` ADD CONSTRAINT `flight_tests_created_by_id_users_id_fk` FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE no action ON UPDATE no action;