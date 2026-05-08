"use client";

import React from "react";
import Link from "next/link";
import {
  AlertCircle,
  Bell,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronRight,
  ChevronDown,
  ClipboardCheck,
  FileCheck2,
  LayoutGrid,
  Loader2,
  MapPin,
  Save,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/src/lib/api";
import { cn } from "@/src/lib/utils";
import {
  getDocumentLabel,
  getHighestVerificationLevel,
  getLevelLabel,
  getRequiredDocuments,
  getServiceRule,
  type ServiceCategory,
  type VerificationLevel,
} from "@/src/lib/tradie-verification";

interface CategoryTreeItem extends ServiceCategory {
  subcategories?: unknown[];
}

interface MyCategory {
  category_id: string;
}

interface PreferenceSettings {
  accept_residential: boolean;
  accept_commercial: boolean;
  accept_high_intent: boolean;
  accept_planning: boolean;
  notify_new_lead: boolean;
  notify_email: boolean;
  notify_sms: boolean;
}

interface ServiceSuburb {
  suburb: string;
  postcode: string;
  state_code: string;
}

interface ServiceAreaDraft {
  suburb: string;
  postcode: string;
  state_code: string;
}

const DEFAULT_SETTINGS: PreferenceSettings = {
  accept_residential: true,
  accept_commercial: true,
  accept_high_intent: true,
  accept_planning: true,
  notify_new_lead: true,
  notify_email: true,
  notify_sms: false,
};

const levelStyles: Record<VerificationLevel, string> = {
  basic: "bg-white/5 text-gray-300 border-white/10",
  standard: "bg-amber-400/10 text-amber-200 border-amber-300/20",
  strict: "bg-[#1DE9B6]/10 text-[#1DE9B6] border-[#1DE9B6]/30",
};

const levelOrder: Record<VerificationLevel, number> = {
  strict: 0,
  standard: 1,
  basic: 2,
};

const filterLabels: Array<"all" | VerificationLevel> = ["all", "strict", "standard", "basic"];
const AU_STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

function hasSameIds(a: string[], b: string[]) {
  return a.length === b.length && a.every((id) => b.includes(id));
}

function hasSameSettings(a: PreferenceSettings, b: PreferenceSettings) {
  return (Object.keys(DEFAULT_SETTINGS) as Array<keyof PreferenceSettings>).every((key) => a[key] === b[key]);
}

function hasSameServiceAreas(a: ServiceSuburb[], b: ServiceSuburb[]) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function ToggleRow({
  title,
  description,
  enabled,
  onChange,
  icon: Icon,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onChange: () => void;
  icon: React.ElementType;
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      className="flex w-full items-center justify-between gap-4 rounded-lg border border-white/5 bg-white/[0.03] p-4 text-left transition-colors hover:border-white/10 hover:bg-white/[0.06]"
    >
      <span className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/5 text-[#1DE9B6]">
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-black text-white">{title}</span>
          <span className="mt-1 block text-xs font-bold leading-relaxed text-gray-500">{description}</span>
        </span>
      </span>
      <span className={cn("relative h-7 w-12 shrink-0 rounded-full transition-colors", enabled ? "bg-[#1DE9B6]" : "bg-white/10")}>
        <span className={cn("absolute top-1 h-5 w-5 rounded-full bg-[#0A0A0B] shadow-xl transition-all", enabled ? "right-1" : "left-1")} />
      </span>
    </button>
  );
}

export default function Preferences() {
  const [categories, setCategories] = React.useState<CategoryTreeItem[]>([]);
  const [selectedCategoryIds, setSelectedCategoryIds] = React.useState<string[]>([]);
  const [initialCategoryIds, setInitialCategoryIds] = React.useState<string[]>([]);
  const [settings, setSettings] = React.useState<PreferenceSettings>(DEFAULT_SETTINGS);
  const [initialSettings, setInitialSettings] = React.useState<PreferenceSettings>(DEFAULT_SETTINGS);
  const [profileState, setProfileState] = React.useState("");
  const [serviceAreas, setServiceAreas] = React.useState<ServiceSuburb[]>([]);
  const [initialServiceAreas, setInitialServiceAreas] = React.useState<ServiceSuburb[]>([]);
  const [areaDraft, setAreaDraft] = React.useState<ServiceAreaDraft>({ suburb: "", postcode: "", state_code: "" });
  const [searchQuery, setSearchQuery] = React.useState("");
  const [activeFilter, setActiveFilter] = React.useState<"all" | VerificationLevel>("all");
  const [openGroups, setOpenGroups] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [loadError, setLoadError] = React.useState("");

  React.useEffect(() => {
    let alive = true;

    async function load() {
      setLoading(true);
      setLoadError("");
      try {
        const [treeRes, myRes] = await Promise.all([
          api.get("/tradies/categories/tree"),
          api.get("/categories/my-categories"),
        ]);
        const [prefRes, profileRes] = await Promise.allSettled([
          api.get("/tradies/preferences/me"),
          api.get("/tradies/profile/me"),
        ]);

        if (!alive) return;
        const loadedCategories = (treeRes.data?.categories || []) as CategoryTreeItem[];
        const selectedIds = ((myRes.data || []) as MyCategory[]).map((item) => item.category_id);
        const loadedSettings = {
          ...DEFAULT_SETTINGS,
          ...(prefRes.status === "fulfilled" ? prefRes.value.data || {} : {}),
        } as PreferenceSettings;

        setCategories(loadedCategories);
        setSelectedCategoryIds(selectedIds);
        setInitialCategoryIds(selectedIds);
        setSettings(loadedSettings);
        setInitialSettings(loadedSettings);
        setProfileState(profileRes.status === "fulfilled" ? profileRes.value.data?.state || "" : "");
        const loadedAreas = prefRes.status === "fulfilled" ? prefRes.value.data?.service_suburbs || [] : [];
        setServiceAreas(loadedAreas);
        setInitialServiceAreas(loadedAreas);
        if (profileRes.status === "fulfilled" && profileRes.value.data?.state) {
          setAreaDraft((prev) => ({ ...prev, state_code: profileRes.value.data.state }));
        }
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        setLoadError(typeof detail === "string" ? detail : "Could not load your preferences.");
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, []);

  const selectedCategories = React.useMemo(
    () => categories.filter((category) => selectedCategoryIds.includes(category.id)),
    [categories, selectedCategoryIds],
  );

  const requiredDocuments = React.useMemo(
    () => getRequiredDocuments(selectedCategories),
    [selectedCategories],
  );

  const highestLevel = getHighestVerificationLevel(selectedCategories);
  const regulatedServices = selectedCategories.filter((category) => getServiceRule(category).documents.includes("trade_licence"));

  const visibleCategories = React.useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return categories
      .filter((category) => {
        const rule = getServiceRule(category);
        const matchesText = !q || category.name.toLowerCase().includes(q) || category.description?.toLowerCase().includes(q);
        const matchesFilter = activeFilter === "all" || rule.level === activeFilter;
        return matchesText && matchesFilter;
      })
      .sort((a, b) => {
        const aRule = getServiceRule(a);
        const bRule = getServiceRule(b);
        if (levelOrder[aRule.level] !== levelOrder[bRule.level]) return levelOrder[aRule.level] - levelOrder[bRule.level];
        return a.name.localeCompare(b.name);
      });
  }, [categories, searchQuery, activeFilter]);

  const groupedCategories = React.useMemo(() => {
    return visibleCategories.reduce<Record<string, CategoryTreeItem[]>>((groups, category) => {
      const group = getServiceRule(category).group;
      groups[group] = groups[group] || [];
      groups[group].push(category);
      return groups;
    }, {});
  }, [visibleCategories]);

  React.useEffect(() => {
    const groups = Object.keys(groupedCategories);
    setOpenGroups((prev) => {
      const stillVisible = prev.filter((group) => groups.includes(group));
      if (stillVisible.length) return stillVisible;
      return groups.slice(0, 2);
    });
  }, [groupedCategories]);

  const toggleCategory = (categoryId: string) => {
    setSelectedCategoryIds((prev) =>
      prev.includes(categoryId)
        ? prev.filter((id) => id !== categoryId)
        : [...prev, categoryId],
    );
  };

  const updateSetting = (key: keyof PreferenceSettings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const updateAreaDraft = (key: keyof ServiceAreaDraft, value: string) => {
    setAreaDraft((prev) => ({ ...prev, [key]: value }));
  };

  const addServiceArea = () => {
    const suburb = areaDraft.suburb.trim();
    const postcode = areaDraft.postcode.trim();
    const state_code = areaDraft.state_code.trim();
    if (!suburb || !postcode || !state_code) {
      toast.error("Add suburb, postcode, and state first.");
      return;
    }
    if (serviceAreas.length >= 20) {
      toast.error("Maximum 20 service areas allowed.");
      return;
    }
    const alreadyAdded = serviceAreas.some(
      (area) => area.suburb.toLowerCase() === suburb.toLowerCase() && area.postcode === postcode && area.state_code === state_code,
    );
    if (alreadyAdded) {
      toast.error("That service area is already selected.");
      return;
    }
    setServiceAreas((prev) => [...prev, { suburb, postcode, state_code }]);
    setAreaDraft({ suburb: "", postcode: "", state_code });
  };

  const removeServiceArea = (areaToRemove: ServiceSuburb) => {
    setServiceAreas((prev) =>
      prev.filter((area) => !(area.suburb === areaToRemove.suburb && area.postcode === areaToRemove.postcode && area.state_code === areaToRemove.state_code)),
    );
  };

  const toggleGroup = (group: string) => {
    setOpenGroups((prev) => (prev.includes(group) ? prev.filter((item) => item !== group) : [...prev, group]));
  };

  const saveChanges = async () => {
    setSaving(true);
    const next = new Set(selectedCategoryIds);
    const previous = new Set(initialCategoryIds);
    const toAdd = selectedCategoryIds.filter((id) => !previous.has(id));
    const toRemove = initialCategoryIds.filter((id) => !next.has(id));

    try {
      await Promise.all([
        ...toAdd.map((id) => api.post(`/categories/my-categories/${id}`)),
        ...toRemove.map((id) => api.delete(`/categories/my-categories/${id}`)),
        api.patch("/tradies/preferences/me", { ...settings, service_suburbs: serviceAreas }),
      ]);
      setInitialCategoryIds(selectedCategoryIds);
      setInitialSettings(settings);
      setInitialServiceAreas(serviceAreas);
      toast.success("Preferences saved.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Could not save preferences.");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges =
    !hasSameIds(selectedCategoryIds, initialCategoryIds) ||
    !hasSameSettings(settings, initialSettings) ||
    !hasSameServiceAreas(serviceAreas, initialServiceAreas);

  const verificationState = profileState || serviceAreas[0]?.state_code || "";

  if (loading) {
    return (
      <div className="flex min-h-[480px] items-center justify-center text-gray-400">
        <Loader2 className="mr-3 h-6 w-6 animate-spin text-[#1DE9B6]" />
        <span className="text-xs font-black uppercase tracking-[0.2em]">Loading preferences</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-24 md:space-y-8 md:pb-0">
      <nav className="sticky top-0 z-[100] -mx-4 border-b border-white/10 bg-[#0A0A0B]/95 px-4 py-3 backdrop-blur-md md:mx-0 md:px-0">
        <div className="flex items-center justify-between gap-3">
          <Link href="/tradie/dashboard" className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-[#1DE9B6]">
            <LayoutGrid className="h-4 w-4" />
            Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Preferences</span>
        </div>
      </nav>

      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-2">
          <p className="text-[11px] font-black uppercase tracking-[0.22em] text-[#1DE9B6]">Tradie lead setup</p>
          <h1 className="text-3xl font-black uppercase tracking-tight text-white md:text-4xl">Preferences</h1>
          <p className="max-w-2xl text-sm font-bold leading-relaxed text-gray-500 md:text-base">
            Choose the work you want, confirm what documents are needed, then tune which leads and alerts you receive.
          </p>
        </div>
        <button
          onClick={saveChanges}
          disabled={!hasChanges || saving}
          className={cn(
            "hidden items-center justify-center gap-3 rounded-lg px-8 py-4 text-xs font-black uppercase tracking-[0.16em] transition-all md:flex",
            hasChanges ? "bg-[#1DE9B6] text-[#0A0A0B] shadow-2xl shadow-[#1DE9B6]/20 hover:-translate-y-0.5" : "cursor-not-allowed bg-white/[0.08] text-gray-500",
          )}
        >
          {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          {saving ? "Saving" : "Save Changes"}
        </button>
      </header>

      {loadError && (
        <div className="flex gap-3 rounded-lg border border-red-400/20 bg-red-500/10 px-5 py-4 text-red-100">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="font-bold">{loadError}</p>
        </div>
      )}

      <section className="rounded-lg border border-[#1DE9B6]/15 bg-[#141416] p-4 shadow-2xl md:p-6">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#1DE9B6]/10 text-[#1DE9B6]">
              <MapPin className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-[#1DE9B6]">Start with service area</p>
              <h2 className="mt-1 text-xl font-black uppercase tracking-widest text-white">1. Service area and state</h2>
              <p className="mt-2 max-w-2xl text-sm font-bold leading-relaxed text-gray-500">
                Licensed services such as electrical, plumbing, gas, building, roofing, solar, and air conditioning should be checked against the state selected here before leads are matched.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {serviceAreas.length ? (
                  serviceAreas.map((area) => (
                    <span key={`${area.suburb}-${area.postcode}`} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-gray-300">
                      {area.suburb}, {area.state_code} {area.postcode}
                      <button type="button" onClick={() => removeServiceArea(area)} className="text-gray-500 transition-colors hover:text-white" aria-label={`Remove ${area.suburb}`}>
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))
                ) : (
                  <span className="rounded-full border border-amber-300/20 bg-amber-400/10 px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-amber-200">
                    No service suburbs selected
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-white/5 bg-white/[0.03] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-gray-600">Verification state</p>
            <p className="mt-2 text-3xl font-black text-white">{verificationState || "Missing"}</p>
            <p className="mt-3 text-xs font-bold leading-relaxed text-gray-500">
              Use the same state where licences or registrations will be checked.
            </p>
            <div className="mt-4 grid grid-cols-1 gap-2">
              <input
                type="text"
                value={areaDraft.suburb}
                onChange={(event) => updateAreaDraft("suburb", event.target.value)}
                placeholder="Suburb"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-sm font-bold text-white outline-none transition-colors placeholder:text-gray-700 focus:border-[#1DE9B6]"
              />
              <div className="grid grid-cols-[1fr_104px] gap-2">
                <input
                  type="text"
                  value={areaDraft.postcode}
                  onChange={(event) => updateAreaDraft("postcode", event.target.value)}
                  placeholder="Postcode"
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-sm font-bold text-white outline-none transition-colors placeholder:text-gray-700 focus:border-[#1DE9B6]"
                />
                <select
                  value={areaDraft.state_code}
                  onChange={(event) => updateAreaDraft("state_code", event.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-sm font-black text-white outline-none transition-colors focus:border-[#1DE9B6]"
                >
                  <option value="">State</option>
                  {AU_STATES.map((state) => (
                    <option key={state} value={state}>{state}</option>
                  ))}
                </select>
              </div>
              <button type="button" onClick={addServiceArea} className="rounded-lg bg-[#1DE9B6] px-4 py-3 text-xs font-black uppercase tracking-[0.16em] text-[#0A0A0B]">
                Add area
              </button>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "Verification state", value: verificationState || "Missing", icon: MapPin },
          { label: "Selected services", value: selectedCategoryIds.length || "None", icon: BriefcaseBusiness },
          { label: "Verification level", value: selectedCategories.length ? getLevelLabel(highestLevel) : "Not set", icon: ShieldCheck },
          { label: "Documents needed", value: requiredDocuments.length || "None", icon: FileCheck2 },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-lg border border-white/5 bg-[#141416] p-4">
              <Icon className="mb-4 h-5 w-5 text-[#1DE9B6]" />
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-gray-600">{item.label}</p>
              <p className="mt-2 text-sm font-black text-white md:text-base">{item.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <main className="space-y-5">
          <section className="rounded-lg border border-white/5 bg-[#141416] p-4 shadow-2xl md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3 text-[#1DE9B6]">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1DE9B6]/10">
                  <SlidersHorizontal className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-lg font-black uppercase tracking-widest text-white">2. Choose services</h2>
                  <p className="mt-1 text-xs font-bold text-gray-600">Open a dropdown, then select services you can do in {verificationState || "your state"}.</p>
                </div>
              </div>
              <div className="relative w-full lg:w-80">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
                <input
                  type="text"
                  placeholder="Search services"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 py-3 pl-11 pr-4 text-sm font-bold text-white transition-all focus:border-[#1DE9B6] focus:outline-none"
                />
              </div>
            </div>

            <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
              {filterLabels.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setActiveFilter(filter)}
                  className={cn(
                    "shrink-0 rounded-lg border px-4 py-2 text-[10px] font-black uppercase tracking-[0.16em] transition-colors",
                    activeFilter === filter ? "border-[#1DE9B6] bg-[#1DE9B6]/10 text-[#1DE9B6]" : "border-white/10 bg-white/[0.03] text-gray-500",
                  )}
                >
                  {filter === "all" ? "All" : getLevelLabel(filter)}
                </button>
              ))}
            </div>

            <div className="mt-6 space-y-3">
              {Object.entries(groupedCategories).map(([group, items]) => (
                <div key={group} className="overflow-hidden rounded-lg border border-white/5 bg-white/[0.02]">
                  <button
                    type="button"
                    onClick={() => toggleGroup(group)}
                    className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left transition-colors hover:bg-white/[0.04]"
                  >
                    <span>
                      <span className="block text-sm font-black uppercase tracking-widest text-white">{group}</span>
                      <span className="mt-1 block text-xs font-bold text-gray-600">
                        {items.filter((category) => selectedCategoryIds.includes(category.id)).length} selected from {items.length} services
                      </span>
                    </span>
                    <ChevronDown className={cn("h-5 w-5 shrink-0 text-[#1DE9B6] transition-transform", openGroups.includes(group) && "rotate-180")} />
                  </button>
                  {openGroups.includes(group) && (
                    <div className="grid grid-cols-1 gap-3 border-t border-white/5 p-3 sm:grid-cols-2">
                      {items.map((category) => {
                        const selected = selectedCategoryIds.includes(category.id);
                        const rule = getServiceRule(category);
                        const isStateRegulated = rule.documents.includes("trade_licence");
                        return (
                          <button
                            key={category.id}
                            onClick={() => toggleCategory(category.id)}
                            className={cn(
                              "min-h-[122px] rounded-lg border p-4 text-left transition-all",
                              selected
                                ? "border-[#1DE9B6]/70 bg-[#1DE9B6]/10 shadow-xl shadow-[#1DE9B6]/10"
                                : "border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.06]",
                            )}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <h4 className="text-sm font-black text-white">{category.name}</h4>
                                <p className="mt-2 line-clamp-2 text-xs font-bold leading-relaxed text-gray-500">{rule.reason}</p>
                              </div>
                              <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-full border", selected ? "border-[#1DE9B6] bg-[#1DE9B6] text-[#0A0A0B]" : "border-white/10 text-transparent")}>
                                <Check className="h-4 w-4" />
                              </span>
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2">
                              <span className={cn("rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-widest", levelStyles[rule.level])}>
                                {getLevelLabel(rule.level)}
                              </span>
                              {isStateRegulated && (
                                <span className="rounded-full border border-sky-300/20 bg-sky-400/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-sky-200">
                                  State licence
                                </span>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-white/5 bg-[#141416] p-4 shadow-2xl md:p-6">
            <div className="mb-5 flex items-start gap-3 text-[#1DE9B6]">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#1DE9B6]/10">
                <ShieldAlert className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-lg font-black uppercase tracking-widest text-white">3. Check verification</h2>
                <p className="mt-1 text-xs font-bold leading-relaxed text-gray-500">
                  State-regulated services should be reviewed against the state on your profile before leads are unlocked.
                </p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
              <div className="space-y-3">
                {selectedCategories.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm font-bold text-gray-500">
                    Select at least one service to see verification requirements.
                  </div>
                ) : regulatedServices.length === 0 ? (
                  <div className="rounded-lg border border-white/5 bg-white/[0.03] p-5">
                    <p className="font-black text-white">No state licence check flagged yet.</p>
                    <p className="mt-2 text-sm font-bold leading-relaxed text-gray-500">
                      Your selected services still require the listed business or insurance documents before they should receive leads.
                    </p>
                  </div>
                ) : (
                  regulatedServices.map((category) => {
                    const rule = getServiceRule(category);
                    return (
                      <div key={category.id} className="rounded-lg border border-white/5 bg-white/[0.03] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-black text-white">{category.name}</p>
                            <p className="mt-1 text-xs font-bold text-gray-500">Licence review state: {verificationState || "Add a service area state"}</p>
                          </div>
                          <span className="rounded-full border border-[#1DE9B6]/30 bg-[#1DE9B6]/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-[#1DE9B6]">
                            Strict
                          </span>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {rule.documents.map((doc) => (
                            <span key={doc} className="rounded-full border border-white/5 bg-white/5 px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-gray-400">
                              {getDocumentLabel(doc)}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="rounded-lg border border-white/5 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-gray-600">Profile state</p>
                <p className="mt-2 text-2xl font-black text-white">{verificationState || "Missing"}</p>
                <p className="mt-3 text-xs font-bold leading-relaxed text-gray-500">
                  This should match where the licence is issued or where you are allowed to perform the work.
                </p>
                <Link href="/tradie/profile" className="mt-4 inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-[#1DE9B6]">
                  Edit profile <ChevronRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </section>
        </main>

        <aside className="space-y-5">
          <section className="rounded-lg border border-white/5 bg-[#141416] p-4 shadow-2xl md:p-5">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1DE9B6]/10 text-[#1DE9B6]">
                <ClipboardCheck className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-black uppercase tracking-widest text-white">4. Lead matching</h2>
                <p className="mt-1 text-xs font-bold text-gray-600">Saved with preferences</p>
              </div>
            </div>
            <div className="space-y-3">
              <ToggleRow title="Residential jobs" description="Homes, apartments, strata homes." enabled={settings.accept_residential} onChange={() => updateSetting("accept_residential")} icon={MapPin} />
              <ToggleRow title="Commercial jobs" description="Offices, retail, worksites, and business premises." enabled={settings.accept_commercial} onChange={() => updateSetting("accept_commercial")} icon={Building2} />
              <ToggleRow title="Ready-to-hire leads" description="Customers looking to book or compare quotes now." enabled={settings.accept_high_intent} onChange={() => updateSetting("accept_high_intent")} icon={BriefcaseBusiness} />
              <ToggleRow title="Planning leads" description="Early research, budgeting, and future work." enabled={settings.accept_planning} onChange={() => updateSetting("accept_planning")} icon={SlidersHorizontal} />
            </div>
          </section>

          <section className="rounded-lg border border-white/5 bg-[#141416] p-4 shadow-2xl md:p-5">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1DE9B6]/10 text-[#1DE9B6]">
                <Bell className="h-5 w-5" />
              </span>
              <h2 className="text-base font-black uppercase tracking-widest text-white">Notifications</h2>
            </div>
            <div className="space-y-3">
              <ToggleRow title="New lead alerts" description="Master switch for incoming lead notifications." enabled={settings.notify_new_lead} onChange={() => updateSetting("notify_new_lead")} icon={Bell} />
              <ToggleRow title="Email" description="Send lead details and document reminders by email." enabled={settings.notify_email} onChange={() => updateSetting("notify_email")} icon={FileCheck2} />
              <ToggleRow title="SMS" description="Use SMS for urgent new lead alerts." enabled={settings.notify_sms} onChange={() => updateSetting("notify_sms")} icon={ShieldCheck} />
            </div>
          </section>

          <section className="rounded-lg border border-white/5 bg-[#141416] p-4 shadow-2xl md:p-5">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1DE9B6]/10 text-[#1DE9B6]">
                <FileCheck2 className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-black uppercase tracking-widest text-white">Documents</h2>
                <p className="mt-1 text-xs font-bold text-gray-600">{selectedCategories.length ? getLevelLabel(highestLevel) : "No services selected"}</p>
              </div>
            </div>
            {selectedCategories.length === 0 ? (
              <p className="text-sm font-bold leading-relaxed text-gray-500">Pick services first, then upload required evidence in Docs.</p>
            ) : (
              <div className="space-y-3">
                {requiredDocuments.map((doc) => (
                  <div key={doc.type} className="rounded-lg border border-white/5 bg-white/[0.03] p-4">
                    <p className="text-sm font-black text-white">{doc.label}</p>
                    <p className="mt-2 text-xs font-bold leading-relaxed text-gray-500">{doc.description}</p>
                    <p className="mt-3 text-[10px] font-black uppercase tracking-widest text-[#1DE9B6]">
                      Needed for {doc.serviceNames.slice(0, 2).join(", ")}
                      {doc.serviceNames.length > 2 ? ` +${doc.serviceNames.length - 2}` : ""}
                    </p>
                  </div>
                ))}
                <Link href="/tradie/docs" className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-[#1DE9B6]">
                  Open docs <ChevronRight className="h-4 w-4" />
                </Link>
              </div>
            )}
          </section>
        </aside>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-[120] border-t border-white/10 bg-[#0A0A0B]/95 p-4 backdrop-blur-md md:hidden">
        <button
          onClick={saveChanges}
          disabled={!hasChanges || saving}
          className={cn(
            "flex w-full items-center justify-center gap-3 rounded-lg px-6 py-4 text-xs font-black uppercase tracking-[0.16em]",
            hasChanges ? "bg-[#1DE9B6] text-[#0A0A0B]" : "cursor-not-allowed bg-white/[0.08] text-gray-500",
          )}
        >
          {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          {saving ? "Saving" : hasChanges ? "Save Changes" : "No Changes"}
        </button>
      </div>
    </div>
  );
}
