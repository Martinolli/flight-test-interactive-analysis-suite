// Import the backend adapter instead of tRPC
import { backendAdapter } from './backendAdapter';

// Export it as 'trpc' so existing code works without changes
export const trpc = backendAdapter;
