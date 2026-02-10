// Import the backend adapter instead of tRPC
import { createTRPCReact } from "@trpc/react-query";

// Export it as 'trpc' so existing code works without changes

import type { AppRouter } from "../../../server/routers";

export const trpc = createTRPCReact<AppRouter>();
