"use client";

import React from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileText,
  LayoutGrid,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Upload,
} from "lucide-react";
import api from "@/src/lib/api";
import { cn } from "@/src/lib/utils";
import {
  getRequiredDocuments,
  getServiceRule,
  type RequiredDocument,
  type RequiredDocumentType,
  type ServiceCategory,
  type VerificationLevel,
} from "@/src/lib/tradie-verification";

interface CategoryTreeItem extends ServiceCategory {
  subcategories?: unknown[];
}

interface MyCategory {
  category_id: string;
}

interface TradiePass {
  abn_verified?: boolean;
  licence_verified?: boolean;
  pli_verified?: boolean;
  wc_verified?: boolean;
  white_card_verified?: boolean;
  swms_uploaded?: boolean;
  licence_doc_url?: string | null;
  pli_doc_url?: string | null;
  wc_doc_url?: string | null;
  swms_doc_url?: string | null;
}

interface Certification {
  category_id: string;
  category_name?: string;
  status: "pending" | "in_review" | "verified" | "rejected" | "expired" | string;
  photo_url?: string | null;
}

interface InsurancePolicy {
  insurance_type: string;
  status: "pending" | "in_review" | "verified" | "rejected" | "expired" | string;
  document_url?: string | null;
}

type DocStatus = "verified" | "in_review" | "missing" | "rejected" | "expired";

const statusCopy: Record<DocStatus, { label: string; className: string; icon: React.ElementType }> = {
  verified: { label: "Verified", className: "bg-emerald-400/10 text-emerald-200 border-emerald-300/20", icon: CheckCircle2 },
  in_review: { label: "In review", className: "bg-amber-400/10 text-amber-200 border-amber-300/20", icon: Clock3 },
  missing: { label: "Required", className: "bg-red-400/10 text-red-200 border-red-300/20", icon: ShieldAlert },
  rejected: { label: "Needs update", className: "bg-red-400/10 text-red-200 border-red-300/20", icon: AlertCircle },
  expired: { label: "Expired", className: "bg-red-400/10 text-red-200 border-red-300/20", icon: AlertCircle },
};

const levelCardClass: Record<VerificationLevel, string> = {
  basic: "border-white/5",
  standard: "border-amber-300/20",
  strict: "border-[#1DE9B6]/30",
};

function normaliseStatus(status?: string): DocStatus {
  if (status === "verified") return "verified";
  if (status === "pending" || status === "in_review") return "in_review";
  if (status === "rejected") return "rejected";
  if (status === "expired") return "expired";
  return "missing";
}

function getDocumentStatus(
  doc: RequiredDocument,
  pass: TradiePass | null,
  certifications: Certification[],
  insurancePolicies: InsurancePolicy[],
  selectedCategories: ServiceCategory[],
): DocStatus {
  if (doc.type === "abn") return pass?.abn_verified ? "verified" : "missing";
  if (doc.type === "white_card") return pass?.white_card_verified || pass?.wc_verified ? "verified" : "missing";
  if (doc.type === "swms") return pass?.swms_uploaded ? "verified" : "missing";
  if (doc.type === "public_liability") {
    const policyStatus = insurancePolicies.find((policy) => policy.insurance_type === "public_liability")?.status;
    if (policyStatus) return normaliseStatus(policyStatus);
    return pass?.pli_verified ? "verified" : "missing";
  }
  if (doc.type === "trade_licence") {
    const strictCategoryIds = selectedCategories
      .filter((category) => getServiceRule(category).level === "strict")
      .map((category) => category.id);
    const relevantCerts = certifications.filter((cert) => strictCategoryIds.includes(cert.category_id));
    if (strictCategoryIds.length === 0) return pass?.licence_verified ? "verified" : "missing";
    if (relevantCerts.some((cert) => cert.status === "rejected")) return "rejected";
    if (relevantCerts.some((cert) => cert.status === "expired")) return "expired";
    if (strictCategoryIds.every((id) => relevantCerts.some((cert) => cert.category_id === id && cert.status === "verified"))) {
      return "verified";
    }
    if (relevantCerts.some((cert) => cert.status === "pending" || cert.status === "in_review")) return "in_review";
    return "missing";
  }
  return "missing";
}

function getActionLabel(type: RequiredDocumentType) {
  if (type === "abn") return "Add ABN";
  if (type === "public_liability") return "Add Insurance";
  if (type === "trade_licence") return "Add Licence";
  if (type === "white_card") return "Add White Card";
  return "Add SWMS";
}

function getActionHref(type: RequiredDocumentType) {
  if (type === "trade_licence") return "/tradie/onboarding";
  if (type === "public_liability") return "/tradie/profile";
  return "/tradie/profile";
}

export default function Docs() {
  const [categories, setCategories] = React.useState<CategoryTreeItem[]>([]);
  const [selectedCategoryIds, setSelectedCategoryIds] = React.useState<string[]>([]);
  const [pass, setPass] = React.useState<TradiePass | null>(null);
  const [certifications, setCertifications] = React.useState<Certification[]>([]);
  const [insurancePolicies, setInsurancePolicies] = React.useState<InsurancePolicy[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState("");

  React.useEffect(() => {
    let alive = true;

    async function load() {
      setLoading(true);
      setLoadError("");
      try {
        const [treeRes, myRes, passRes, certRes, insuranceRes] = await Promise.all([
          api.get("/tradies/categories/tree"),
          api.get("/categories/my-categories"),
          api.get("/compliance/my-pass").catch(() => ({ data: null })),
          api.get("/tradies/certifications/me").catch(() => ({ data: [] })),
          api.get("/tradies/insurance/me").catch(() => ({ data: [] })),
        ]);

        if (!alive) return;
        setCategories((treeRes.data?.categories || []) as CategoryTreeItem[]);
        setSelectedCategoryIds(((myRes.data || []) as MyCategory[]).map((item) => item.category_id));
        setPass(passRes.data || null);
        setCertifications((certRes.data || []) as Certification[]);
        setInsurancePolicies((insuranceRes.data || []) as InsurancePolicy[]);
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        setLoadError(typeof detail === "string" ? detail : "Could not load required documents.");
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

  const missingCount = requiredDocuments.filter(
    (doc) => getDocumentStatus(doc, pass, certifications, insurancePolicies, selectedCategories) !== "verified",
  ).length;

  if (loading) {
    return (
      <div className="min-h-[480px] flex items-center justify-center text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin mr-3 text-[#1DE9B6]" />
        <span className="font-black uppercase tracking-[0.2em] text-xs">Loading documents</span>
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <nav className="sticky top-0 z-[100] -mx-4 md:mx-0 bg-[#0A0A0B]/95 backdrop-blur-md border-b border-white/10 px-4 md:px-0 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link href="/tradie/dashboard" className="inline-flex items-center gap-2 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em]">
            <LayoutGrid className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Docs</span>
        </div>
      </nav>

      <header className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
        <div className="space-y-1">
          <h1 className="text-4xl font-black tracking-tighter text-white uppercase">Documents</h1>
          <p className="text-gray-500 font-bold text-base">
            Required documents are based on the services selected in Preferences.
          </p>
        </div>
        <Link
          href="/tradie/preferences"
          style={{ backgroundColor: "#1DE9B6" }}
          className="text-[#0A0A0B] px-10 py-5 rounded-2xl font-black text-xs uppercase tracking-[0.2em] flex items-center gap-3 hover:scale-105 transition-transform shadow-2xl shadow-[#1DE9B6]/30"
        >
          <ShieldCheck className="w-5 h-5" />
          <span>Edit Services</span>
        </Link>
      </header>

      {loadError && (
        <div className="rounded-3xl border border-red-400/20 bg-red-500/10 px-6 py-5 text-red-100 flex gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="font-bold">{loadError}</p>
        </div>
      )}

      {selectedCategories.length === 0 ? (
        <div style={{ backgroundColor: "#141416" }} className="rounded-[3rem] p-16 flex flex-col items-center justify-center text-center space-y-7 border border-white/5 shadow-2xl">
          <div className="w-20 h-20 rounded-[2rem] bg-white/5 flex items-center justify-center text-white/10">
            <FileText className="w-10 h-10" />
          </div>
          <div className="space-y-3">
            <h3 className="text-3xl font-black text-gray-300 tracking-tight uppercase">No services selected</h3>
            <p className="text-gray-500 font-bold max-w-md mx-auto leading-relaxed">
              Choose services in Preferences first. This page will then show only the documents those services require.
            </p>
          </div>
          <Link href="/tradie/preferences" className="px-8 py-4 rounded-2xl bg-white/5 text-gray-300 font-black text-xs uppercase tracking-[0.2em] hover:bg-white/10 transition-all">
            Open Preferences
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div style={{ backgroundColor: "#141416" }} className="rounded-[2rem] p-6 border border-white/5">
              <p className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">Selected Services</p>
              <p className="text-4xl font-black text-white mt-2">{selectedCategories.length}</p>
            </div>
            <div style={{ backgroundColor: "#141416" }} className="rounded-[2rem] p-6 border border-white/5">
              <p className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">Required Documents</p>
              <p className="text-4xl font-black text-white mt-2">{requiredDocuments.length}</p>
            </div>
            <div style={{ backgroundColor: "#141416" }} className="rounded-[2rem] p-6 border border-white/5">
              <p className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">Still Needed</p>
              <p className="text-4xl font-black text-[#1DE9B6] mt-2">{missingCount}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {requiredDocuments.map((doc) => {
              const status = getDocumentStatus(doc, pass, certifications, insurancePolicies, selectedCategories);
              const StatusIcon = statusCopy[status].icon;
              return (
                <div
                  key={doc.type}
                  style={{ backgroundColor: "#141416" }}
                  className={cn("rounded-[2.5rem] p-8 border shadow-xl space-y-7", levelCardClass[doc.level])}
                >
                  <div className="flex items-start justify-between gap-5">
                    <div className="flex items-start gap-5">
                      <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center shrink-0">
                        <FileText className="w-8 h-8 text-[#1DE9B6]" />
                      </div>
                      <div>
                        <h3 className="font-black text-gray-100 text-lg uppercase tracking-widest">{doc.label}</h3>
                        <p className="text-sm text-gray-500 font-bold leading-relaxed mt-2">{doc.description}</p>
                      </div>
                    </div>
                    <span className={cn("px-3 py-2 rounded-full text-[10px] font-black uppercase tracking-widest border flex items-center gap-2 shrink-0", statusCopy[status].className)}>
                      <StatusIcon className="w-3.5 h-3.5" />
                      {statusCopy[status].label}
                    </span>
                  </div>

                  <div className="space-y-3">
                    <p className="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">Required because of</p>
                    <div className="flex flex-wrap gap-2">
                      {doc.serviceNames.map((serviceName) => (
                        <span key={serviceName} className="px-3 py-2 rounded-full bg-white/5 border border-white/5 text-gray-400 text-[10px] font-black uppercase tracking-widest">
                          {serviceName}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3">
                    <Link href={getActionHref(doc.type)} className="flex-1 px-5 py-4 rounded-2xl bg-white/5 text-gray-300 font-black text-xs uppercase tracking-[0.18em] hover:bg-white/10 transition-all flex items-center justify-center gap-3">
                      <Upload className="w-4 h-4" />
                      {getActionLabel(doc.type)}
                    </Link>
                    {(doc.type === "trade_licence" || doc.type === "public_liability") && (
                      <Link
                        href={doc.type === "trade_licence" ? "/tradie/onboarding" : "/tradie/profile"}
                        className="px-5 py-4 rounded-2xl bg-[#1DE9B6]/10 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em] hover:bg-[#1DE9B6]/15 transition-all flex items-center justify-center gap-3"
                      >
                        <ExternalLink className="w-4 h-4" />
                        Details
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ backgroundColor: "#141416" }} className="rounded-[3rem] p-8 border border-white/5 shadow-2xl">
            <div className="flex items-start gap-4">
              <ShieldCheck className="w-6 h-6 text-[#1DE9B6] shrink-0 mt-1" />
              <div>
                <h3 className="text-xl font-black text-white uppercase tracking-widest">Strict verification rule</h3>
                <p className="text-gray-500 font-bold leading-relaxed mt-3 max-w-3xl">
                  Licensed or high-risk services stay blocked from full lead access until their required documents are verified.
                  Basic services can use lighter checks, so tradies are not asked for unnecessary paperwork.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
