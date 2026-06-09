import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  RefreshCw,
  Save,
  Link2,
  Unlink,
} from "lucide-react";
import {
  OperatorMappingVenn,
  type VennSegment,
} from "../components/OperatorMappingVenn";

type OperatorRow = {
  operator_name: string;
  doordash_email: string;
  multilogin_profile_id: string;
  multilogin_profile_name: string;
  match_method: string;
  mapped: boolean;
};

type ProfileOption = {
  profile_id: string;
  profile_name: string;
  folder_id?: string;
};

type MappingPayload = {
  path?: string;
  json_path?: string;
  csv_path?: string;
  mapping?: {
    operators?: OperatorRow[];
    unmatched_profiles?: ProfileOption[];
    stats?: Record<string, number>;
    synced_at?: string;
    updated_at?: string;
  };
  venn?: {
    counts: { only_airtable: number; in_both: number; only_multilogin: number };
    only_airtable: OperatorRow[];
    in_both: OperatorRow[];
    only_multilogin: ProfileOption[];
  };
  profiles?: ProfileOption[];
};

function parseApiError(body: string, status: number): string {
  const trimmed = body.trim();
  if (!trimmed) return `Request failed (HTTP ${status})`;
  try {
    const parsed = JSON.parse(trimmed) as { detail?: string };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON
  }
  return trimmed;
}

export function OperatorProfileMappingPage() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [operators, setOperators] = useState<OperatorRow[]>([]);
  const [unmatchedProfiles, setUnmatchedProfiles] = useState<ProfileOption[]>([]);
  const [profileOptions, setProfileOptions] = useState<ProfileOption[]>([]);
  const [mappingPath, setMappingPath] = useState("");
  const [csvPath, setCsvPath] = useState("");
  const [activeSegment, setActiveSegment] = useState<VennSegment>("only_airtable");
  const [dirty, setDirty] = useState(false);

  const vennCounts = useMemo(
    () => ({
      only_airtable: operators.filter((o) => !o.mapped).length,
      in_both: operators.filter((o) => o.mapped).length,
      only_multilogin: unmatchedProfiles.length,
    }),
    [operators, unmatchedProfiles]
  );

  const segmentRows = useMemo(() => {
    if (activeSegment === "only_airtable") {
      return operators.filter((o) => !o.mapped);
    }
    if (activeSegment === "in_both") {
      return operators.filter((o) => o.mapped);
    }
    return [];
  }, [activeSegment, operators]);

  const applyPayload = useCallback((data: MappingPayload) => {
    const mapping = data.mapping || {};
    setOperators(Array.isArray(mapping.operators) ? mapping.operators : []);
    setUnmatchedProfiles(
      Array.isArray(mapping.unmatched_profiles) ? mapping.unmatched_profiles : []
    );
    setProfileOptions(Array.isArray(data.profiles) ? data.profiles : []);
    setMappingPath(data.json_path || data.path || "");
    setCsvPath(data.csv_path || "");
    if (data.venn?.counts) {
      if (data.venn.counts.only_airtable > 0) setActiveSegment("only_airtable");
      else if (data.venn.counts.in_both > 0) setActiveSegment("in_both");
      else setActiveSegment("only_multilogin");
    }
    setDirty(false);
  }, []);

  const loadMapping = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/operator-profile-mapping");
      if (!res.ok) {
        const text = await res.text();
        throw new Error(parseApiError(text, res.status));
      }
      const data = (await res.json()) as MappingPayload;
      applyPayload(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load mapping");
    } finally {
      setLoading(false);
    }
  }, [applyPayload]);

  useEffect(() => {
    void loadMapping();
  }, [loadMapping]);

  const handleSync = async (offline = false) => {
    setSyncing(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch(
        `/api/operator-profile-mapping/sync?offline=${offline ? "true" : "false"}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(parseApiError(text, res.status));
      }
      const data = (await res.json()) as MappingPayload;
      applyPayload(data);
      setSuccess("Mapping refreshed from Airtable and Multilogin.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const updateOperatorProfile = (email: string, profileId: string) => {
    const profile = profileOptions.find((p) => p.profile_id === profileId);
    let releasedProfile: ProfileOption | null = null;

    setOperators((prev) =>
      prev.map((op) => {
        if (op.doordash_email !== email) return op;
        if (op.multilogin_profile_id && op.multilogin_profile_id !== profileId) {
          releasedProfile = {
            profile_id: op.multilogin_profile_id,
            profile_name: op.multilogin_profile_name,
          };
        }
        if (!profileId) {
          if (op.multilogin_profile_id) {
            releasedProfile = {
              profile_id: op.multilogin_profile_id,
              profile_name: op.multilogin_profile_name,
            };
          }
          return {
            ...op,
            multilogin_profile_id: "",
            multilogin_profile_name: "",
            match_method: "",
            mapped: false,
          };
        }
        return {
          ...op,
          multilogin_profile_id: profileId,
          multilogin_profile_name: profile?.profile_name || op.multilogin_profile_name,
          match_method: "manual",
          mapped: true,
        };
      })
    );

    setUnmatchedProfiles((prev) => {
      let next = prev.filter((p) => p.profile_id !== profileId);
      if (releasedProfile && !next.some((p) => p.profile_id === releasedProfile!.profile_id)) {
        next = [...next, releasedProfile];
      }
      return next.sort((a, b) =>
        (a.profile_name || "").localeCompare(b.profile_name || "", undefined, { sensitivity: "base" })
      );
    });
    setDirty(true);
  };

  const linkProfileToOperator = (profileId: string, operatorEmail: string) => {
    updateOperatorProfile(operatorEmail, profileId);
    setUnmatchedProfiles((prev) => prev.filter((p) => p.profile_id !== profileId));
    setActiveSegment("in_both");
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const usedIds = new Set(
        operators.filter((o) => o.multilogin_profile_id).map((o) => o.multilogin_profile_id)
      );
      const remainingUnmatched = [
        ...unmatchedProfiles.filter((p) => !usedIds.has(p.profile_id)),
        ...profileOptions.filter((p) => !usedIds.has(p.profile_id)),
      ];
      const dedupedUnmatched = Array.from(
        new Map(remainingUnmatched.map((p) => [p.profile_id, p])).values()
      );

      const res = await fetch("/api/operator-profile-mapping", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operators,
          unmatched_profiles: dedupedUnmatched,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(parseApiError(text, res.status));
      }
      const data = (await res.json()) as MappingPayload;
      if (data.mapping) {
        applyPayload({
          path: data.path,
          json_path: data.json_path,
          csv_path: data.csv_path,
          mapping: data.mapping,
          venn: data.venn,
          profiles: data.profiles || profileOptions,
        });
      }
      const mapped = data.mapping?.stats?.operators_mapped;
      const total = data.mapping?.stats?.operators_total;
      setSuccess(
        `Mapping saved (${mapped ?? "?"}/${total ?? "?"} mapped). JSON + CSV updated — browser-use agents will use this on the next run.`
      );
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const unmappedOperators = operators.filter((o) => !o.mapped);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            to="/settings"
            className="mb-3 inline-flex items-center gap-2 text-sm text-ink-500 transition hover:text-brand-600 dark:text-white/55"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Settings
          </Link>
          <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
            Operator ↔ Multilogin mapping
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-600 dark:text-white/65">
            Canonical mapping used by Health Check, Data Run, Strategist, and all browser-use
            agents. Saved to{" "}
            <code className="rounded bg-brand-100 px-1 text-xs dark:bg-white/10">
              {mappingPath || "multilogin/operator_multilogin_mapping.json"}
            </code>
            {" "}and{" "}
            <code className="rounded bg-brand-100 px-1 text-xs dark:bg-white/10">
              {csvPath || "multilogin/operator_multilogin_mapping.csv"}
            </code>
            {" "}(<code className="text-xs">mapped</code> column updated on save).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleSync(false)}
            disabled={syncing || loading}
            className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2.5 text-sm font-medium text-ink-800 transition hover:bg-brand-50 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
          >
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync live
          </button>
          <button
            type="button"
            onClick={() => void handleSync(true)}
            disabled={syncing || loading}
            className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2.5 text-sm font-medium text-ink-800 transition hover:bg-brand-50 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
          >
            Sync offline
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || loading || !dirty}
            className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save mapping
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
          {success}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-20 text-ink-500 dark:text-white/55">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading mapping…
        </div>
      ) : (
        <>
          <section className="brand-card rounded-[28px] p-6">
            <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
              Coverage overview
            </h3>
            <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
              Click a region to inspect operators or profiles in that bucket.
            </p>
            <div className="mt-6">
              <OperatorMappingVenn
                counts={vennCounts}
                active={activeSegment}
                onSelect={setActiveSegment}
              />
            </div>
          </section>

          <section className="brand-card rounded-[28px] p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
                {activeSegment === "only_airtable" && "Only in Airtable — assign a Multilogin profile"}
                {activeSegment === "in_both" && "Mapped operators — edit assignments"}
                {activeSegment === "only_multilogin" && "Only in Multilogin — link to an Airtable operator"}
              </h3>
              {dirty && (
                <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-500/20 dark:text-amber-200">
                  Unsaved changes
                </span>
              )}
            </div>

            {activeSegment !== "only_multilogin" ? (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-brand-100 text-xs uppercase tracking-wide text-ink-500 dark:border-white/10 dark:text-white/50">
                      <th className="px-3 py-2">Operator</th>
                      <th className="px-3 py-2">DoorDash email</th>
                      <th className="px-3 py-2">Multilogin profile</th>
                      <th className="px-3 py-2">Match</th>
                    </tr>
                  </thead>
                  <tbody>
                    {segmentRows.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-8 text-center text-ink-500 dark:text-white/50">
                          No operators in this bucket.
                        </td>
                      </tr>
                    ) : (
                      segmentRows.map((op) => (
                        <tr
                          key={op.doordash_email || op.operator_name}
                          className="border-b border-brand-50 dark:border-white/5"
                        >
                          <td className="px-3 py-3 font-medium text-ink-900 dark:text-white">
                            {op.operator_name}
                          </td>
                          <td className="px-3 py-3 font-mono text-xs text-ink-600 dark:text-white/70">
                            {op.doordash_email || "—"}
                          </td>
                          <td className="px-3 py-3">
                            <select
                              value={op.multilogin_profile_id || ""}
                              onChange={(e) =>
                                updateOperatorProfile(op.doordash_email, e.target.value)
                              }
                              className="w-full max-w-md rounded-xl border border-brand-100 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white"
                            >
                              <option value="">— Not mapped —</option>
                              {profileOptions.map((p) => (
                                <option key={p.profile_id} value={p.profile_id}>
                                  {p.profile_name || p.profile_id}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-3 py-3 text-xs text-ink-500 dark:text-white/55">
                            {op.match_method || "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-brand-100 text-xs uppercase tracking-wide text-ink-500 dark:border-white/10 dark:text-white/50">
                      <th className="px-3 py-2">Profile name</th>
                      <th className="px-3 py-2">Profile ID</th>
                      <th className="px-3 py-2">Link to operator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unmatchedProfiles.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-8 text-center text-ink-500 dark:text-white/50">
                          All Multilogin profiles are mapped.
                        </td>
                      </tr>
                    ) : (
                      unmatchedProfiles.map((prof) => (
                        <tr
                          key={prof.profile_id}
                          className="border-b border-brand-50 dark:border-white/5"
                        >
                          <td className="px-3 py-3 font-medium text-ink-900 dark:text-white">
                            {prof.profile_name || "—"}
                          </td>
                          <td className="px-3 py-3 font-mono text-xs text-ink-500 dark:text-white/55">
                            {prof.profile_id}
                          </td>
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-2">
                              <select
                                defaultValue=""
                                onChange={(e) => {
                                  if (e.target.value) {
                                    linkProfileToOperator(prof.profile_id, e.target.value);
                                    e.target.value = "";
                                  }
                                }}
                                className="min-w-[220px] rounded-xl border border-brand-100 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white"
                              >
                                <option value="">Select operator…</option>
                                {unmappedOperators.map((op) => (
                                  <option key={op.doordash_email} value={op.doordash_email}>
                                    {op.operator_name}
                                  </option>
                                ))}
                              </select>
                              <Link2 className="h-4 w-4 text-brand-500" />
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="brand-card rounded-[28px] p-6">
            <div className="flex items-center gap-2">
              <Unlink className="h-5 w-5 text-ink-400" />
              <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
                Quick tips
              </h3>
            </div>
            <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-ink-600 dark:text-white/65">
              <li>
                <strong>Sync live</strong> pulls fresh operators from Airtable and profiles from
                Multilogin (requires API credentials in <code>.env</code>).
              </li>
              <li>
                <strong>Save mapping</strong> writes <code>multilogin/operator_multilogin_mapping.json</code> —
                all browser-use agents read this file immediately on next run.
              </li>
              <li>
                Manual edits are preserved across re-sync when <code>match_method</code> is{" "}
                <code>manual</code>.
              </li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
