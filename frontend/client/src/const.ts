export { COOKIE_NAME, ONE_YEAR_MS } from "@shared/const";

// Generate login URL at runtime so redirect URI reflects the current origin.
export const getLoginUrl = () => {
  const oauthPortalUrlRaw = import.meta.env.VITE_OAUTH_PORTAL_URL;
  const appId = import.meta.env.VITE_APP_ID;
  if (!oauthPortalUrlRaw || !appId) return null;

  const oauthPortalUrl = oauthPortalUrlRaw.trim();
  if (!oauthPortalUrl) return null;
  if (oauthPortalUrl === "undefined" || oauthPortalUrl === "null") return null;
  const redirectUri = `${window.location.origin}/api/oauth/callback`;
  const state = btoa(redirectUri);

  const normalizedBaseUrl =
    oauthPortalUrl.startsWith("http://") || oauthPortalUrl.startsWith("https://")
      ? oauthPortalUrl
      : oauthPortalUrl.startsWith("//")
        ? `https:${oauthPortalUrl}`
        : oauthPortalUrl.startsWith("/")
          ? new URL(oauthPortalUrl, window.location.origin).toString()
          : `http://${oauthPortalUrl}`;

  let url: URL;
  try {
    url = new URL("/app-auth", normalizedBaseUrl);
  } catch {
    return null;
  }

  url.searchParams.set("appId", appId);
  url.searchParams.set("redirectUri", redirectUri);
  url.searchParams.set("state", state);
  url.searchParams.set("type", "signIn");

  return url.toString();
};
