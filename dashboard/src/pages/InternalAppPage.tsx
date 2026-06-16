import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

const TITLES: Record<string, string> = {
  "/agents/the-super-app": "The Super App",
  "/agents/markup-app": "Markup App",
};

const APP_PATHS: Record<string, string> = {
  "/agents/the-super-app": "/internal-apps/the-super-app/",
  "/agents/markup-app": "/internal-apps/markup-app/",
};

const APP_SLUGS: Record<string, string> = {
  "/agents/the-super-app": "the-super-app",
  "/agents/markup-app": "markup-app",
};

export function InternalAppPage() {
  const { pathname, search } = useLocation();
  const title = TITLES[pathname] ?? "Agent App";
  const appPath = APP_PATHS[pathname];
  const slug = APP_SLUGS[pathname];
  const [buildVersion, setBuildVersion] = useState<number | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    fetch(`/internal-apps/${slug}/health`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.buildVersion === "number") {
          setBuildVersion(data.buildVersion);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const versionQuery = buildVersion ? `v=${buildVersion}` : "";
  const iframeSrc = appPath
    ? `${appPath}${search ? `${search}&${versionQuery}` : versionQuery ? `?${versionQuery}` : ""}`
    : null;

  if (!iframeSrc) {
    return (
      <div className="p-6 text-sm text-ink-600">
        Unknown internal app route.{" "}
        <Link to="/agents" className="font-medium text-brand-700 hover:text-brand-800">
          Back to agents
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4">
      <div className="flex items-center gap-4">
        <Link
          to="/agents"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>
        <h2 className="font-display text-xl font-semibold text-ink-900">{title}</h2>
      </div>

      <div className="brand-card min-h-0 flex-1 overflow-hidden rounded-[28px] bg-white">
        <iframe src={iframeSrc} className="h-full w-full border-0" title={title} />
      </div>
    </div>
  );
}
