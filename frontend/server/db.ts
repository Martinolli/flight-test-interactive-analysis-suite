import { eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { InsertUser, users } from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: ReturnType<typeof drizzle> | null = null;

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

// Flight Test Queries
export async function getFlightTests(userId: number) {
  const db = await getDb();
  if (!db) return [];
  
  const { flightTests } = await import("../drizzle/schema");
  const { eq, desc } = await import("drizzle-orm");
  
  return await db
    .select()
    .from(flightTests)
    .where(eq(flightTests.createdById, userId))
    .orderBy(desc(flightTests.createdAt));
}

export async function getFlightTestById(id: number, userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const { flightTests } = await import("../drizzle/schema");
  const { eq, and } = await import("drizzle-orm");
  
  const results = await db
    .select()
    .from(flightTests)
    .where(and(eq(flightTests.id, id), eq(flightTests.createdById, userId)))
    .limit(1);
  
  return results[0];
}

export async function createFlightTest(data: any, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const { flightTests } = await import("../drizzle/schema");
  
  const insertData = {
    ...data,
    createdById: userId,
  };
  
  const result = await db.insert(flightTests).values(insertData);
  return Number(result[0].insertId);
}

export async function updateFlightTest(id: number, data: any, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const { flightTests } = await import("../drizzle/schema");
  const { eq, and } = await import("drizzle-orm");
  
  await db
    .update(flightTests)
    .set(data)
    .where(and(eq(flightTests.id, id), eq(flightTests.createdById, userId)));
}

export async function deleteFlightTest(id: number, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const { flightTests } = await import("../drizzle/schema");
  const { eq, and } = await import("drizzle-orm");
  
  await db
    .delete(flightTests)
    .where(and(eq(flightTests.id, id), eq(flightTests.createdById, userId)));
}

// Parameter Queries
export async function getParameters() {
  const db = await getDb();
  if (!db) return [];
  
  const { testParameters } = await import("../drizzle/schema");
  
  return await db.select().from(testParameters);
}

export async function createParameter(data: any) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const { testParameters } = await import("../drizzle/schema");
  
  const result = await db.insert(testParameters).values(data);
  return Number(result[0].insertId);
}

// Data Point Queries
export async function getDataPoints(flightTestId: number, limit = 1000) {
  const db = await getDb();
  if (!db) return [];
  
  const { dataPoints, testParameters } = await import("../drizzle/schema");
  const { eq } = await import("drizzle-orm");
  
  return await db
    .select({
      id: dataPoints.id,
      timestamp: dataPoints.timestamp,
      value: dataPoints.value,
      parameterId: dataPoints.parameterId,
      parameterName: testParameters.name,
      parameterUnit: testParameters.unit,
    })
    .from(dataPoints)
    .leftJoin(testParameters, eq(dataPoints.parameterId, testParameters.id))
    .where(eq(dataPoints.flightTestId, flightTestId))
    .limit(limit);
}

export async function createDataPoints(points: any[]) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const { dataPoints } = await import("../drizzle/schema");
  
  // Insert in batches to avoid overwhelming the database
  const batchSize = 1000;
  for (let i = 0; i < points.length; i += batchSize) {
    const batch = points.slice(i, i + batchSize);
    await db.insert(dataPoints).values(batch);
  }
}
