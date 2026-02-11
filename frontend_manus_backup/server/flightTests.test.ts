import { describe, expect, it } from "vitest";
import { appRouter } from "./routers";
import type { TrpcContext } from "./_core/context";

type AuthenticatedUser = NonNullable<TrpcContext["user"]>;

function createAuthContext(): TrpcContext {
  const user: AuthenticatedUser = {
    id: 1,
    openId: "test-user",
    email: "test@example.com",
    name: "Test User",
    loginMethod: "manus",
    role: "user",
    createdAt: new Date(),
    updatedAt: new Date(),
    lastSignedIn: new Date(),
  };

  const ctx: TrpcContext = {
    user,
    req: {
      protocol: "https",
      headers: {},
    } as TrpcContext["req"],
    res: {} as TrpcContext["res"],
  };

  return ctx;
}

describe("flightTests procedures", () => {
  it("should list flight tests for authenticated user", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    const result = await caller.flightTests.list();

    expect(Array.isArray(result)).toBe(true);
  });

  it("should create a flight test", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    const testData = {
      name: "Test Flight",
      description: "Test Description",
      testDate: new Date(),
      aircraft: "Boeing 737",
      status: "draft" as const,
    };

    const result = await caller.flightTests.create(testData);

    expect(result).toHaveProperty("id");
    expect(typeof result.id).toBe("number");
  });

  it("should get flight test by id", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    // First create a test
    const createResult = await caller.flightTests.create({
      name: "Test Flight for Get",
      description: "Test",
      testDate: new Date(),
      aircraft: "Test Aircraft",
      status: "draft" as const,
    });

    // Then retrieve it
    const result = await caller.flightTests.getById({ id: createResult.id });

    expect(result).toBeDefined();
    expect(result?.name).toBe("Test Flight for Get");
  });

  it("should update a flight test", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    // Create a test
    const createResult = await caller.flightTests.create({
      name: "Test Flight for Update",
      description: "Original",
      testDate: new Date(),
      aircraft: "Test Aircraft",
      status: "draft" as const,
    });

    // Update it
    const updateResult = await caller.flightTests.update({
      id: createResult.id,
      description: "Updated Description",
      status: "completed" as const,
    });

    expect(updateResult.success).toBe(true);

    // Verify the update
    const updated = await caller.flightTests.getById({ id: createResult.id });
    expect(updated?.description).toBe("Updated Description");
    expect(updated?.status).toBe("completed");
  });

  it("should delete a flight test", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    // Create a test
    const createResult = await caller.flightTests.create({
      name: "Test Flight for Delete",
      description: "To be deleted",
      testDate: new Date(),
      aircraft: "Test Aircraft",
      status: "draft" as const,
    });

    // Delete it
    const deleteResult = await caller.flightTests.delete({ id: createResult.id });

    expect(deleteResult.success).toBe(true);

    // Verify it's deleted
    const deleted = await caller.flightTests.getById({ id: createResult.id });
    expect(deleted).toBeUndefined();
  });
});

describe("parameters procedures", () => {
  it("should list all parameters", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    const result = await caller.parameters.list();

    expect(Array.isArray(result)).toBe(true);
  });

  it("should create a parameter", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    const paramData = {
      name: "Altitude",
      unit: "ft",
      description: "Aircraft altitude",
      parameterType: "altitude",
    };

    const result = await caller.parameters.create(paramData);

    expect(result).toHaveProperty("id");
    expect(typeof result.id).toBe("number");
  });
});

describe("dataPoints procedures", () => {
  it("should get data points for a flight test", async () => {
    const ctx = createAuthContext();
    const caller = appRouter.createCaller(ctx);

    // Create a flight test first
    const flightTest = await caller.flightTests.create({
      name: "Test Flight for Data Points",
      description: "Test",
      testDate: new Date(),
      aircraft: "Test Aircraft",
      status: "draft" as const,
    });

    // Get data points (should be empty initially)
    const result = await caller.dataPoints.getByFlightTest({
      flightTestId: flightTest.id,
    });

    expect(Array.isArray(result)).toBe(true);
  });
});
