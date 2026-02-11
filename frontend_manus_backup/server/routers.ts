import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, protectedProcedure, router } from "./_core/trpc";

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),

  flightTests: router({
    list: protectedProcedure.query(async ({ ctx }) => {
      const { getFlightTests } = await import("./db");
      return await getFlightTests(ctx.user.id);
    }),
    
    getById: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null && "id" in val && typeof val.id === "number") {
          return val as { id: number };
        }
        throw new Error("Invalid input: expected { id: number }");
      })
      .query(async ({ ctx, input }) => {
        const { getFlightTestById } = await import("./db");
        return await getFlightTestById(input.id, ctx.user.id);
      }),
    
    create: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null) {
          return val as any;
        }
        throw new Error("Invalid input");
      })
      .mutation(async ({ ctx, input }) => {
        const { createFlightTest } = await import("./db");
        const id = await createFlightTest(input, ctx.user.id);
        return { id };
      }),
    
    update: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null && "id" in val && typeof val.id === "number") {
          return val as { id: number; [key: string]: any };
        }
        throw new Error("Invalid input: expected { id: number, ... }");
      })
      .mutation(async ({ ctx, input }) => {
        const { id, ...data } = input;
        const { updateFlightTest } = await import("./db");
        await updateFlightTest(id, data, ctx.user.id);
        return { success: true };
      }),
    
    delete: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null && "id" in val && typeof val.id === "number") {
          return val as { id: number };
        }
        throw new Error("Invalid input: expected { id: number }");
      })
      .mutation(async ({ ctx, input }) => {
        const { deleteFlightTest } = await import("./db");
        await deleteFlightTest(input.id, ctx.user.id);
        return { success: true };
      }),
  }),
  
  parameters: router({
    list: publicProcedure.query(async () => {
      const { getParameters } = await import("./db");
      return await getParameters();
    }),
    
    create: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null) {
          return val as any;
        }
        throw new Error("Invalid input");
      })
      .mutation(async ({ input }) => {
        const { createParameter } = await import("./db");
        const id = await createParameter(input);
        return { id };
      }),
  }),
  
  dataPoints: router({
    getByFlightTest: protectedProcedure
      .input((val: unknown) => {
        if (typeof val === "object" && val !== null && "flightTestId" in val && typeof val.flightTestId === "number") {
          return val as { flightTestId: number; limit?: number };
        }
        throw new Error("Invalid input: expected { flightTestId: number }");
      })
      .query(async ({ input }) => {
        const { getDataPoints } = await import("./db");
        return await getDataPoints(input.flightTestId, input.limit);
      }),
  }),
});

export type AppRouter = typeof appRouter;
