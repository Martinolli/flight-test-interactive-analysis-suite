import { int, mysqlEnum, mysqlTable, text, timestamp, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * Flight test table - stores metadata about each flight test
 */
export const flightTests = mysqlTable("flight_tests", {
  id: int("id").autoincrement().primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  description: text("description"),
  testDate: timestamp("test_date").notNull(),
  aircraft: varchar("aircraft", { length: 255 }),
  status: mysqlEnum("status", ["draft", "in_progress", "completed", "archived"]).default("draft").notNull(),
  createdById: int("created_by_id").notNull().references(() => users.id),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
});

export type FlightTest = typeof flightTests.$inferSelect;
export type InsertFlightTest = typeof flightTests.$inferInsert;

/**
 * Test parameters table - stores parameter definitions (e.g., altitude, speed, temperature)
 */
export const testParameters = mysqlTable("test_parameters", {
  id: int("id").autoincrement().primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  unit: varchar("unit", { length: 50 }),
  description: text("description"),
  parameterType: varchar("parameter_type", { length: 100 }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export type TestParameter = typeof testParameters.$inferSelect;
export type InsertTestParameter = typeof testParameters.$inferInsert;

/**
 * Data points table - stores time-series data for each parameter in a flight test
 */
export const dataPoints = mysqlTable("data_points", {
  id: int("id").autoincrement().primaryKey(),
  flightTestId: int("flight_test_id").notNull().references(() => flightTests.id, { onDelete: "cascade" }),
  parameterId: int("parameter_id").notNull().references(() => testParameters.id),
  timestamp: timestamp("timestamp").notNull(),
  value: text("value").notNull(), // Stored as text to handle various numeric formats
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export type DataPoint = typeof dataPoints.$inferSelect;
export type InsertDataPoint = typeof dataPoints.$inferInsert;