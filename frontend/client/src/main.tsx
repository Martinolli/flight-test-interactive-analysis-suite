import { trpc } from "@/lib/trpc";
import { UNAUTHED_ERR_MSG } from '@shared/const';
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { httpBatchLink, TRPCClientError } from "@trpc/client";
import { createRoot } from "react-dom/client";
import superjson from "superjson";
import App from "./App";
import { getLoginUrl } from "./const";
import "./index.css";

const queryClient = new QueryClient();

const maybeInstallAnalytics = () => {
  if (typeof document === "undefined") return;

  const endpoint = (import.meta.env.VITE_ANALYTICS_ENDPOINT as string | undefined) ?? "";
  const websiteId = (import.meta.env.VITE_ANALYTICS_WEBSITE_ID as string | undefined) ?? "";

  if (!endpoint || !websiteId) return;

  const normalizedEndpoint = endpoint.trim().replace(/\/+$/, "");
  if (!normalizedEndpoint) return;

  const src =
    normalizedEndpoint.startsWith("http://") || normalizedEndpoint.startsWith("https://")
      ? `${normalizedEndpoint}/umami`
      : normalizedEndpoint.startsWith("/")
        ? `${normalizedEndpoint}/umami`
        : `/${normalizedEndpoint}/umami`;

  const script = document.createElement("script");
  script.defer = true;
  script.src = src;
  script.setAttribute("data-website-id", websiteId);
  document.head.appendChild(script);
};

const redirectToLoginIfUnauthorized = (error: unknown) => {
  if (!(error instanceof TRPCClientError)) return;
  if (typeof window === "undefined") return;

  const isUnauthorized = error.message === UNAUTHED_ERR_MSG;

  if (!isUnauthorized) return;

  const loginUrl = getLoginUrl();
  if (!loginUrl) {
    console.warn(
      "[Auth] OAuth is not configured (missing VITE_OAUTH_PORTAL_URL/VITE_APP_ID); skipping redirect."
    );
    return;
  }

  window.location.href = loginUrl;
};

queryClient.getQueryCache().subscribe(event => {
  if (event.type === "updated" && event.action.type === "error") {
    const error = event.query.state.error;
    redirectToLoginIfUnauthorized(error);
    console.error("[API Query Error]", error);
  }
});

queryClient.getMutationCache().subscribe(event => {
  if (event.type === "updated" && event.action.type === "error") {
    const error = event.mutation.state.error;
    redirectToLoginIfUnauthorized(error);
    console.error("[API Mutation Error]", error);
  }
});

const trpcClient = trpc.createClient({
  links: [
    httpBatchLink({
      url: "/api/trpc",
      transformer: superjson,
      fetch(input, init) {
        return globalThis.fetch(input, {
          ...(init ?? {}),
          credentials: "include",
        });
      },
    }),
  ],
});

maybeInstallAnalytics();

createRoot(document.getElementById("root")!).render(
  <trpc.Provider client={trpcClient} queryClient={queryClient}>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </trpc.Provider>
);
