"use client";

import React from "react";
import Link from "next/link";
import { AlertCircle, Bell, Check, FileCheck2, LayoutGrid, Loader2, MapPin, Save, Search, ShieldCheck } from "lucide-react";
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

export default function Preferences() {
  const [categories, setCategories] = React.useState<CategoryTreeItem[]>([]);
  const [selectedCategoryIds, setSelectedCategoryIds] = React.useState<string[]>([]);
  const [initialCategoryIds, setInitialCategoryIds] = React.useState<string[]>([]);
  const [searchQuery, setSearchQuery] = React.useState("");
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

        if (!alive) return;
        const loadedCategories = (treeRes.data?.categories || []) as CategoryTreeItem[];
        const selectedIds = ((myRes.data || []) as MyCategory[]).map((item) => item.category_id);
        setCategories(loadedCategories);
        setSelectedCategoryIds(selectedIds);
        setInitialCategoryIds(selectedIds);
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

  const visibleCategories = React.useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return categories
      .filter((category) => !q || category.name.toLowerCase().includes(q) || category.description?.toLowerCase().includes(q))
      .sort((a, b) => {
        const aRule = getServiceRule(a);
        const bRule = getServiceRule(b);
        if (levelOrder[aRule.level] !== levelOrder[bRule.level]) return levelOrder[aRule.level] - levelOrder[bRule.level];
        return a.name.localeCompare(b.name);
      });
  }, [categories, searchQuery]);

  const groupedCategories = React.useMemo(() => {
    return visibleCategories.reduce<Record<string, CategoryTreeItem[]>>((groups, category) => {
      const group = getServiceRule(category).group;
      groups[group] = groups[group] || [];
      groups[group].push(category);
      return groups;
    }, {});
  }, [visibleCategories]);

  const toggleCategory = (categoryId: string) => {
    setSelectedCategoryIds((prev) =>
      prev.includes(categoryId)
        ? prev.filter((id) => id !== categoryId)
        : [...prev, categoryId],
    );
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
      ]);
      setInitialCategoryIds(selectedCategoryIds);
      toast.success("Preferences saved.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Could not save preferences.");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges =
    selectedCategoryIds.length !== initialCategoryIds.length ||
    selectedCategoryIds.some((id) => !initialCategoryIds.includes(id));

  if (loading) {
    return (
      <div className="min-h-[480px] flex items-center justify-center text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin mr-3 text-[#1DE9B6]" />
        <span className="font-black uppercase tracking-[0.2em] text-xs">Loading preferences</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 md:space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700 overflow-x-hidden">
      <nav className="sticky top-0 z-[100] -mx-4 md:mx-0 bg-[#0A0A0B]/95 backdrop-blur-md border-b border-white/10 px-4 md:px-0 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link href="/tradie/dashboard" className="inline-flex items-center gap-2 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em]">
            <LayoutGrid className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Preferences</span>
        </div>
      </nav>

      <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4 md:gap-6">
        <div className="space-y-1">
          <h1 className="text-3xl md:text-4xl font-black tracking-tighter text-white uppercase">Preferences</h1>
          <p className="text-gray-500 font-bold text-sm md:text-base">Choose services and see the verification documents they require.</p>
        </div>
        <button
          onClick={saveChanges}
          disabled={!hasChanges || saving}
          style={{ backgroundColor: hasChanges ? "#1DE9B6" : "rgba(255,255,255,0.08)" }}
          className={cn(
            "text-[#0A0A0B] w-full sm:w-auto justify-center px-6 md:px-10 py-4 md:py-5 rounded-2xl font-black text-xs uppercase tracking-[0.16em] md:tracking-[0.2em] flex items-center gap-3 transition-all shadow-2xl",
            hasChanges ? "hover:scale-105 shadow-[#1DE9B6]/30" : "text-gray-500 cursor-not-allowed shadow-black/20",
          )}
        >
          {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
          <span>{saving ? "Saving" : "Save Changes"}</span>
        </button>
      </header>

      {loadError && (
        <div className="rounded-3xl border border-red-400/20 bg-red-500/10 px-6 py-5 text-red-100 flex gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="font-bold">{loadError}</p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5 md:gap-8">
        <section style={{ backgroundColor: "#141416" }} className="rounded-3xl md:rounded-[3rem] p-4 md:p-10 border border-white/5 shadow-2xl space-y-5 md:space-y-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
            <div className="flex items-center gap-4 text-[#1DE9B6]">
              <div className="w-10 h-10 rounded-xl bg-[#1DE9B6]/10 flex items-center justify-center">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg md:text-xl font-black uppercase tracking-widest">Services</h3>
                <p className="text-xs font-bold text-gray-600 mt-1">{selectedCategoryIds.length} selected</p>
              </div>
            </div>
            <div className="relative w-full md:w-80">
              <Search className="w-4 h-4 text-gray-600 absolute left-4 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search services..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-2xl pl-11 pr-4 py-3 text-sm text-white font-bold focus:outline-none focus:border-[#1DE9B6] transition-all"
              />
            </div>
          </div>

          {Object.entries(groupedCategories).map(([group, items]) => (
            <div key={group} className="space-y-3 md:space-y-4">
              <h4 className="text-[11px] font-black text-gray-500 uppercase tracking-[0.22em]">{group}</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 md:gap-3">
                {items.map((category) => {
                  const selected = selectedCategoryIds.includes(category.id);
                  const rule = getServiceRule(category);
                  return (
                    <button
                      key={category.id}
                      onClick={() => toggleCategory(category.id)}
                      className={cn(
                        "text-left rounded-2xl border p-3 md:p-5 transition-all min-h-0 md:min-h-[128px]",
                        selected
                          ? "bg-[#1DE9B6]/10 border-[#1DE9B6]/60 shadow-xl shadow-[#1DE9B6]/10"
                          : "bg-white/[0.03] border-white/5 hover:bg-white/[0.06] hover:border-white/10",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h5 className="font-black text-white text-xs md:text-sm uppercase tracking-widest">{category.name}</h5>
                          <p className="text-[11px] md:text-xs font-bold text-gray-500 mt-1.5 md:mt-2 leading-relaxed line-clamp-1 md:line-clamp-2">{rule.reason}</p>
                        </div>
                        <span className={cn("w-6 h-6 rounded-full border flex items-center justify-center shrink-0", selected ? "bg-[#1DE9B6] border-[#1DE9B6] text-[#0A0A0B]" : "border-white/10 text-transparent")}>
                          <Check className="w-4 h-4" />
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 md:gap-2 mt-3 md:mt-4">
                        <span className={cn("px-2.5 md:px-3 py-1 md:py-1.5 rounded-full text-[9px] md:text-[10px] font-black uppercase tracking-widest border", levelStyles[rule.level])}>
                          {getLevelLabel(rule.level)}
                        </span>
                        {rule.documents.map((doc) => (
                          <span key={doc} className="px-2.5 md:px-3 py-1 md:py-1.5 rounded-full text-[9px] md:text-[10px] font-black uppercase tracking-widest bg-white/5 text-gray-500 border border-white/5">
                            {getDocumentLabel(doc)}
                          </span>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        <aside className="space-y-5 md:space-y-6">
          <div style={{ backgroundColor: "#141416" }} className="rounded-3xl md:rounded-[3rem] p-5 md:p-8 border border-white/5 shadow-2xl">
            <div className="flex items-center gap-4 text-[#1DE9B6] mb-6">
              <div className="w-10 h-10 rounded-xl bg-[#1DE9B6]/10 flex items-center justify-center">
                <FileCheck2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-black uppercase tracking-widest">Document Rules</h3>
                <p className="text-xs font-bold text-gray-600 mt-1">{selectedCategories.length ? getLevelLabel(highestLevel) : "No services selected"}</p>
              </div>
            </div>

            {selectedCategories.length === 0 ? (
              <p className="text-gray-500 font-bold leading-relaxed">Select services to see which documents will be required in the Documents section.</p>
            ) : (
              <div className="space-y-3">
                {requiredDocuments.map((doc) => (
                  <div key={doc.type} className="rounded-2xl bg-white/[0.03] border border-white/5 p-4">
                    <p className="text-white font-black text-sm uppercase tracking-widest">{doc.label}</p>
                    <p className="text-xs text-gray-500 font-bold leading-relaxed mt-2">{doc.description}</p>
                    <p className="text-[10px] text-[#1DE9B6] font-black uppercase tracking-widest mt-3">
                      Needed for {doc.serviceNames.slice(0, 2).join(", ")}
                      {doc.serviceNames.length > 2 ? ` +${doc.serviceNames.length - 2}` : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ backgroundColor: "#141416" }} className="rounded-3xl md:rounded-[3rem] p-5 md:p-8 border border-white/5 shadow-2xl space-y-5 md:space-y-8">
            <div className="flex items-center gap-4 text-[#1DE9B6]">
              <div className="w-10 h-10 rounded-xl bg-[#1DE9B6]/10 flex items-center justify-center">
                <MapPin className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-black uppercase tracking-widest">Lead Area</h3>
            </div>
            <div className="space-y-3">
              <label className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em] ml-2">Max Distance (km)</label>
              <input
                type="number"
                defaultValue={30}
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-5 text-white font-bold focus:outline-none focus:border-[#1DE9B6] transition-all"
              />
            </div>
            <div className="space-y-3">
              <label className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em] ml-2">Min Budget ($)</label>
              <input
                type="number"
                defaultValue={0}
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-5 text-white font-bold focus:outline-none focus:border-[#1DE9B6] transition-all"
              />
            </div>
          </div>

          <div style={{ backgroundColor: "#141416" }} className="rounded-3xl md:rounded-[3rem] p-5 md:p-8 border border-white/5 shadow-2xl space-y-5 md:space-y-6">
            <div className="flex items-center gap-4 text-[#1DE9B6]">
              <div className="w-10 h-10 rounded-xl bg-[#1DE9B6]/10 flex items-center justify-center">
                <Bell className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-black uppercase tracking-widest">Notifications</h3>
            </div>
            {["Email notifications", "SMS notifications", "Auto-decline leads outside preferences"].map((label, index) => (
              <div key={label} className="flex items-center justify-between py-4 px-5 rounded-2xl bg-white/[0.02] border border-white/5">
                <span className="text-gray-400 font-bold tracking-wide text-sm">{label}</span>
                <span className={cn("w-14 h-7 rounded-full relative transition-all shadow-inner", index === 0 ? "bg-[#1DE9B6]" : "bg-white/10")}>
                  <span className={cn("absolute top-1 w-5 h-5 rounded-full bg-[#0A0A0B] shadow-xl transition-all", index === 0 ? "right-1" : "left-1")} />
                </span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
