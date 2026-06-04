import { useLocation, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function AgentIframePage() {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const url = searchParams.get("url");
  const name = searchParams.get("name") || "Agent App";

  if (!url) return <div className="p-6">No URL provided</div>;

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] w-full gap-4">
      <div className="flex items-center gap-4">
        <Link
          to="/agents"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>
        <h2 className="font-display text-xl font-semibold text-ink-900">{name}</h2>
      </div>
      
      <div className="flex-1 brand-card rounded-[28px] overflow-hidden bg-white">
        <iframe 
          src={url} 
          className="w-full h-full border-0" 
          title="Agent Interface"
        />
      </div>
    </div>
  );
}
