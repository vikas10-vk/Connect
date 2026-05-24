"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, Zap, X, ChevronRight,
  Check, Bell, Clock, Calendar, Search,
  Mail, Lock, User, Eye, EyeOff, Loader2,
  AlertCircle, MapPin, ImagePlus, Trash2,
  AlertTriangle, BookmarkCheck, Sparkles, Plus,
  Save, CheckCircle2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/contexts/AuthContext';
import api from '@/src/lib/api';
import { TRADIE_CATEGORIES, getCategorySlug, CATEGORY_NAMES } from '@/src/constants/categories';
import { PROBLEM_SUGGESTIONS, detectCategory } from '@/src/constants/problems';

const DRAFT_KEY = 'proconnect_job_draft';

const STEPS = [
  { id: 1, title: 'Service' },
  { id: 2, title: 'Describe' },
  { id: 3, title: 'Details' },
  { id: 4, title: 'Location' },
  { id: 5, title: 'Account' },
];

const URGENCY_OPTIONS = [
  { id: 'emergency', label: 'Emergency', subtitle: 'Right now', icon: Bell, color: '#DC2626', bg: '#FEF2F2' },
  { id: 'asap', label: 'ASAP', subtitle: '24-48 hours', icon: Bell, color: '#D97706', bg: '#FFFBEB' },
  { id: 'next_few_days', label: 'This week', subtitle: 'Within a few days', icon: Clock, color: '#2563EB', bg: '#EFF6FF' },
  { id: 'next_few_weeks', label: 'Next few weeks', subtitle: 'No rush', icon: Calendar, color: '#16A34A', bg: '#F0FDF4' },
  { id: 'flexible', label: 'Flexible', subtitle: 'Best tradie first', icon: Calendar, color: '#7C3AED', bg: '#F5F3FF' },
];

// ── Guided questions per category ────────────────────────────────────────────
const GUIDED_QUESTIONS: Record<string, [string, string][]> = {
  'Plumbing': [
    ['Where exactly is the problem? (e.g. kitchen sink, bathroom, under the house)', 'Location of problem: '],
    ['Is there active leaking or water damage right now?', 'Active leak/water damage: '],
    ['Do you know the pipe material? (copper, PVC, unknown)', 'Pipe material: '],
  ],
  'Electrical': [
    ['Is this inside or outside the property?', 'Location: '],
    ['How many points, lights, or circuits need work?', 'Quantity: '],
    ['Is it a new installation or a repair to something existing?', 'Type of work: '],
  ],
  'Carpentry': [
    ['What is the approximate size or dimensions of the work area?', 'Dimensions/size: '],
    ['What timber or material is involved? (pine, hardwood, MDF, etc.)', 'Material: '],
    ['Do you have a design or plan ready, or do you need advice?', 'Design/plan ready: '],
  ],
  'Painting': [
    ['How many rooms or what area in square metres needs painting?', 'Area to paint: '],
    ['Is this interior, exterior, or both?', 'Interior/exterior: '],
    ['Do you need the surfaces prepared or repaired first?', 'Prep needed: '],
  ],
  'Roofing': [
    ['What is the roof material? (tiles, iron, colorbond, etc.)', 'Roof material: '],
    ['Is this a repair, full replacement, or new installation?', 'Type of work: '],
    ['Approximately how old is the roof?', 'Roof age: '],
  ],
  'Landscaping': [
    ['What is the approximate garden/yard size?', 'Area size: '],
    ['Is this a one-off clean-up or ongoing maintenance?', 'One-off or ongoing: '],
    ['Any specific plants, materials, or features you want included?', 'Specific requests: '],
  ],
  'Air Conditioning': [
    ['How many rooms or what size area needs cooling/heating?', 'Number of rooms/area: '],
    ['Is this a new installation, replacement, or service/repair?', 'Type of work: '],
    ['Do you have a brand preference or existing unit details?', 'Brand/unit details: '],
  ],
  'Tiling': [
    ['What is the approximate area to be tiled in square metres?', 'Area (sqm): '],
    ['What room or area is being tiled?', 'Location: '],
    ['Do you have tiles already, or do you need supply included?', 'Tiles: supply needed? '],
  ],
  'Builder': [
    ['Is this a new build, extension, or renovation?', 'Type of work: '],
    ['Do you have plans or council approval already?', 'Plans/approval: '],
    ['What is your approximate budget range?', 'Budget range: '],
  ],
  'Handyman': [
    ['How many separate tasks need doing?', 'Number of tasks: '],
    ['Are any tasks more than 30 minutes each?', 'Duration estimate: '],
    ['Do you have materials/parts, or does the tradie need to supply?', 'Materials: supplied or needed? '],
  ],
  'Pest Control': [
    ['What type of pest are you dealing with?', 'Pest type: '],
    ['Is this a residential or commercial property?', 'Property type: '],
    ['Is this an inspection, treatment, or both?', 'Service needed: '],
  ],
  'Fencing': [
    ['What type of fence material? (timber, colorbond, glass, etc.)', 'Fence material: '],
    ['How many metres of fencing is needed?', 'Length (metres): '],
    ['Is this a new fence or replacing an existing one?', 'New or replacement: '],
  ],
};

const DEFAULT_QUESTIONS: [string, string][] = [
  ['What is the approximate size or scope of the work?', 'Scope/size: '],
  ['Is this a repair, replacement, or new installation?', 'Type of work: '],
  ['Do you have any photos or measurements ready?', 'Photos/measurements: '],
];

function getGuidedQuestions(category: string): [string, string][] {
  const key = Object.keys(GUIDED_QUESTIONS).find(k =>
    category.toLowerCase().includes(k.toLowerCase()) ||
    k.toLowerCase().includes(category.toLowerCase())
  );
  return key ? GUIDED_QUESTIONS[key] : DEFAULT_QUESTIONS;
}

interface SuburbSuggestion {
  suburb: string; postcode: string; state_code: string; label: string;
}
interface UploadedPhoto {
  key: string; url: string; preview: string; name: string;
}

// Use getCategorySlug for accurate DB slug resolution
const toSlug = getCategorySlug;

function parseApiError(err: any): string {
  const data = err?.response?.data;
  if (!data) return 'Something went wrong. Please try again.';
  if (Array.isArray(data.detail)) return data.detail.map((e: any) => e.msg || String(e)).join(', ');
  if (typeof data.detail === 'string') return data.detail;
  if (typeof data.message === 'string') return data.message;
  if (typeof data === 'string') return data;
  return 'Failed to post job. Please try again.';
}

// ── Cancel modal ──────────────────────────────────────────────────────────────
function CancelModal({ step, selectedCategory, jobTitle, onSave, onDiscard, onResume }: {
  step: number; selectedCategory: string; jobTitle: string;
  onSave: () => void; onDiscard: () => void; onResume: () => void;
}) {
  const progress = Math.round((step / 5) * 100);
  const stepLabels = ['Service', 'Describe', 'Details', 'Location', 'Account'];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onResume} />
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        className="relative bg-white rounded-3xl w-full max-w-sm shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}>
        <div className="px-6 pt-6 pb-4 text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-7 h-7 text-amber-500" />
          </div>
          <h2 className="text-lg font-black text-gray-900">Cancel booking?</h2>
          <p className="text-sm text-gray-500 mt-1">Step {step} of 5  -  progress will be lost.</p>
        </div>
        <div className="mx-6 mb-4 p-4 rounded-2xl bg-gray-50 border border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-brand-gold rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs font-bold text-gray-500">{progress}%</span>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {stepLabels.map((label, i) => (
              <span key={label} className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full',
                i + 1 < step ? 'bg-emerald-100 text-emerald-700' :
                  i + 1 === step ? 'bg-brand-gold/10 text-brand-gold' : 'bg-gray-100 text-gray-400'
              )}>
                {label}
              </span>
            ))}
          </div>
          {(selectedCategory || jobTitle) && (
            <div className="mt-3 pt-3 border-t border-gray-200 space-y-1">
              {selectedCategory && <p className="text-xs text-gray-600"><span className="font-bold">Service:</span> {selectedCategory}</p>}
              {jobTitle && <p className="text-xs text-gray-600"><span className="font-bold">Job:</span> {jobTitle}</p>}
            </div>
          )}
        </div>
        <div className="px-6 pb-6 space-y-3">
          <button onClick={onSave}
            className="w-full flex items-center justify-center gap-2 py-3.5 rounded-2xl font-bold text-sm text-white hover:opacity-90 transition-all"
            style={{ background: 'linear-gradient(135deg, #D4AA3A, #EBCB66)' }}>
            <BookmarkCheck className="w-4 h-4" /> Save progress & exit
          </button>
          <button onClick={onDiscard} className="w-full py-3 rounded-2xl font-bold text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors">
            Discard & leave
          </button>
          <button onClick={onResume} className="w-full py-2 text-xs font-bold text-gray-400 hover:text-gray-600 transition-colors">
            Keep editing
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Guided questions ──────────────────────────────────────────────────────────
function GuidedQuestions({
  category, description, onAppend,
}: {
  category: string; description: string; onAppend: (text: string) => void;
}) {
  // P1 FIX: questions are derived fresh from category on every render
  const questions = getGuidedQuestions(category);
  const [dismissed, setDismissed] = useState<number[]>([]);

  // Reset dismissed when category changes  -  P1 fix
  const prevCat = useRef(category);
  useEffect(() => {
    if (prevCat.current !== category) {
      setDismissed([]);
      prevCat.current = category;
    }
  }, [category]);

  const visible = questions.filter((_, i) => {
    if (dismissed.includes(i)) return false;
    const prefix = questions[i][1].trim().toLowerCase();
    return !description.toLowerCase().includes(prefix);
  });

  if (visible.length === 0) return null;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
      <div className="flex items-center gap-2">
        <Sparkles className="w-3.5 h-3.5 text-violet-500" />
        <p className="text-xs font-bold text-violet-700">Help tradies quote accurately  -  add these details:</p>
      </div>
      <div className="space-y-2">
        {visible.map((q, idx) => {
          const originalIdx = questions.indexOf(q);
          return (
            <motion.div key={originalIdx} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="flex items-start gap-2 bg-violet-50/60 border border-violet-100 rounded-xl px-3 py-2.5 group">
              <div className="w-1.5 h-1.5 rounded-full bg-violet-400 mt-1.5 shrink-0" />
              <p className="text-xs text-gray-600 flex-1 leading-relaxed">{q[0]}</p>
              <div className="flex items-center gap-1 shrink-0 ml-2">
                <button onClick={() => onAppend(q[1])}
                  className="flex items-center gap-1 text-[10px] font-bold text-violet-600 bg-violet-100 hover:bg-violet-200 px-2.5 py-1.5 rounded-lg transition-colors">
                  <Plus className="w-2.5 h-2.5" /> Add
                </button>
                <button onClick={() => setDismissed(prev => [...prev, originalIdx])}
                  className="text-gray-300 hover:text-gray-400 transition-colors p-1">
                  <X className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}

// ── P4: Beautiful Summary Card ────────────────────────────────────────────────
function JobSummaryCard({
  selectedCategory, jobTitle, urgency, suburb, state, postcode, photos, onEdit,
}: {
  selectedCategory: string; jobTitle: string; urgency: string;
  suburb: string; state: string; postcode: string;
  photos: UploadedPhoto[];
  onEdit: (step: number) => void;
}) {
  const selectedUrgency = URGENCY_OPTIONS.find(u => u.id === urgency);

  return (
    <div className="overflow-hidden rounded-3xl border border-gray-100 shadow-lg">
      {/* Hero header */}
      <div className="relative px-6 pt-6 pb-5 overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #071D36 0%, #173452 100%)' }}>
        <div className="absolute top-0 right-0 w-48 h-48 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #D4AA3A, transparent)', transform: 'translate(25%, -25%)' }} />
        <div className="relative">
          <div className="flex items-start justify-between gap-3 mb-3">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(212,170,58,0.25)', color: '#FFA07A' }}>
              <Zap className="w-3 h-3" /> {selectedCategory}
            </span>
            {selectedUrgency && (
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full"
                style={{ background: `${selectedUrgency.color}25`, color: selectedUrgency.color }}>
                <selectedUrgency.icon className="w-3 h-3" /> {selectedUrgency.label}
              </span>
            )}
          </div>
          <h3 className="text-xl font-black text-white leading-tight">{jobTitle || 'Your job'}</h3>
          {suburb && (
            <p className="flex items-center gap-1.5 text-sm mt-2" style={{ color: 'rgba(255,255,255,0.65)' }}>
              <MapPin className="w-3.5 h-3.5" /> {suburb}, {state} {postcode}
            </p>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 bg-white border-b border-gray-100">
        {[
          { label: 'Service', value: selectedCategory || ' - ', step: 1 },
          { label: 'Urgency', value: selectedUrgency?.label || ' - ', step: 2 },
          { label: 'Photos', value: photos.length > 0 ? `${photos.length} attached` : 'None', step: 2 },
        ].map(({ label, value, step }) => (
          <button key={label} onClick={() => onEdit(step)}
            className="px-4 py-3.5 text-left hover:bg-gray-50 transition-colors group">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">{label}</p>
            <p className="text-sm font-bold text-gray-900 truncate">{value}</p>
            <p className="text-[10px] text-brand-gold opacity-0 group-hover:opacity-100 transition-opacity">Edit ↗</p>
          </button>
        ))}
      </div>

      {/* Photos strip */}
      {photos.length > 0 && (
        <div className="bg-white border-b border-gray-100 px-4 py-3">
          <div className="flex gap-2">
            {photos.slice(0, 4).map((p, i) => (
              <div key={p.key} className="w-14 h-14 rounded-xl overflow-hidden border border-gray-100 shrink-0 relative">
                <img src={p.preview} alt="" className="w-full h-full object-cover" />
                {i === 3 && photos.length > 4 && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <span className="text-white text-xs font-black">+{photos.length - 4}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trust row */}
      <div className="bg-gradient-to-r from-emerald-50 to-teal-50 px-5 py-3.5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <p className="text-xs font-black text-emerald-800">Ready to match tradies</p>
            <p className="text-[10px] text-emerald-600 mt-0.5">3 steps completed  |  Verified professionals only</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs font-black text-emerald-800">Free</p>
          <p className="text-[10px] text-emerald-600">No obligation</p>
        </div>
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
function BookingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, login, register, user } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const visibleSteps = isAuthenticated ? STEPS.slice(0, 4) : STEPS;

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [showCancel, setShowCancel] = useState(false);

  // ── P2: Field error state ──
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [shakeStep, setShakeStep] = useState(false);

  // ── P5: Auto-save indicator ──
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saveIndicator, setSaveIndicator] = useState<'saving' | 'saved' | null>(null);

  // ── Canonical categories fetched from API (same source as tradie picker) ──
  // Both homeowners and tradies must see the identical list so that whatever the
  // homeowner selects maps to exactly the same category_id the tradie registered under.
  const [apiCategories, setApiCategories] = useState<typeof TRADIE_CATEGORIES>(TRADIE_CATEGORIES);
  const [categoriesLoaded, setCategoriesLoaded] = useState(false);

  useEffect(() => {
    api.get('/categories')
      .then(res => {
        // Backend returns { name, slug, icon_slug, description }
        // Map to the same shape as TRADIE_CATEGORIES for drop-in replacement.
        const mapped = (res.data as { name: string; slug: string; icon_slug?: string; description?: string }[])
          .map(c => ({
            name: c.name,
            slug: c.slug,
            icon: TRADIE_CATEGORIES.find(t => t.slug === c.slug)?.icon ?? '',
            description: c.description ?? '',
          }));
        if (mapped.length > 0) setApiCategories(mapped);
      })
      .catch(() => { /* silently fall back to hardcoded TRADIE_CATEGORIES */ })
      .finally(() => setCategoriesLoaded(true));
  }, []);

  // Step 1
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get('category') || '');
  const [categorySearch, setCategorySearch] = useState('');
  const [suggestions, setSuggestions] = useState<typeof PROBLEM_SUGGESTIONS>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Step 2
  const [description, setDescription] = useState('');
  const [urgency, setUrgency] = useState('next_few_days');
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [photoUploading, setPhotoUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 3
  const [jobTitle, setJobTitle] = useState('');
  const [jobType, setJobType] = useState<'residential' | 'commercial'>('residential');
  const [serviceType, setServiceType] = useState('repair');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState('');
  const [aiError, setAiError] = useState(false);
  const [aiMissingInfo, setAiMissingInfo] = useState('');
  // ── P1: AI version for manual regeneration ──
  const [aiVersion, setAiVersion] = useState(0);

  // Step 4
  const [locationQuery, setLocationQuery] = useState('');
  const [locationSuggestions, setLocationSuggestions] = useState<SuburbSuggestion[]>([]);
  const [locationLoading, setLocationLoading] = useState(false);
  const [suburb, setSuburb] = useState('');
  const [state, setState] = useState('');
  const [postcode, setPostcode] = useState('');
  // ── P3: Postcode manual field search ──
  const [postcodeQuery, setPostcodeQuery] = useState('');
  const [postcodeSuggestions, setPostcodeSuggestions] = useState<SuburbSuggestion[]>([]);
  const locationDebounce = useRef<NodeJS.Timeout | null>(null);
  const postcodeDebounce = useRef<NodeJS.Timeout | null>(null);

  // Step 5
  const [authMode, setAuthMode] = useState<'login' | 'register'>('register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [pwdFocused, setPwdFocused] = useState(false);
  const [authError, setAuthError] = useState('');
  // OTP verification (register flow only)
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpVerified, setOtpVerified] = useState(false);
  const [otpError, setOtpError] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);

  // ── Build draft ──────────────────────────────────────────────────────────
  const buildDraft = useCallback(() => ({
    step, selectedCategory, jobTitle, description, urgency,
    jobType, serviceType, suburb, state, postcode, locationQuery,
    savedAt: new Date().toISOString(),
  }), [step, selectedCategory, jobTitle, description, urgency, jobType, serviceType, suburb, state, postcode, locationQuery]);

  // ── P5: Auto-save to localStorage ───────────────────────────────────────
  const autoSave = useCallback(() => {
    if (step < 2 && !selectedCategory) return; // nothing worth saving yet
    setSaveIndicator('saving');
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(buildDraft()));
      setLastSaved(new Date());
      setTimeout(() => setSaveIndicator('saved'), 300);
      setTimeout(() => setSaveIndicator(null), 2500);
    } catch {
      setSaveIndicator(null);
    }
  }, [buildDraft, step, selectedCategory]);

  // ── P5: Auto-save on step change ────────────────────────────────────────
  useEffect(() => {
    if (step > 1) autoSave();
  }, [step]);

  // ── P5: Auto-save on description change (debounced) ─────────────────────
  useEffect(() => {
    if (!description) return;
    const t = setTimeout(() => autoSave(), 2000);
    return () => clearTimeout(t);
  }, [description]);

  // ── P5: Save on tab/window close ────────────────────────────────────────
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (step > 1 && selectedCategory) {
        try { localStorage.setItem(DRAFT_KEY, JSON.stringify(buildDraft())); } catch { }
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [step, selectedCategory, buildDraft]);

  // ── Pre-fill from search params ──────────────────────────────────────────
  useEffect(() => {
    const q = searchParams.get('q');
    const cat = searchParams.get('category');
    const decodedQ = q ? decodeURIComponent(q) : '';
    const decodedCat = cat ? decodeURIComponent(cat) : '';

    if (decodedQ) setDescription(decodedQ);

    // Resolve category: prefer explicit ?category param, then detect from ?q
    let resolvedCat = '';
    if (decodedCat) {
      resolvedCat = decodedCat;
    } else if (decodedQ) {
      resolvedCat = detectCategory(decodedQ);
    }

    if (resolvedCat) {
      setSelectedCategory(resolvedCat);
      // Also pre-fill the search box so the user sees what was typed
      if (decodedQ) setCategorySearch(decodedQ);
    }

    // Jump to describe step if we have both a description and a category
    if (decodedQ && resolvedCat) {
      setStep(2);
    }
  }, []);

  // ── Restore draft ────────────────────────────────────────────────────────
  useEffect(() => {
    if (searchParams.get('q')) return;
    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        const d = JSON.parse(saved);
        if (d.selectedCategory) setSelectedCategory(d.selectedCategory);
        if (d.jobTitle) setJobTitle(d.jobTitle);
        if (d.description) setDescription(d.description);
        if (d.urgency) setUrgency(d.urgency);
        if (d.jobType) setJobType(d.jobType);
        if (d.serviceType) setServiceType(d.serviceType);
        if (d.suburb) setSuburb(d.suburb);
        if (d.state) setState(d.state);
        if (d.postcode) setPostcode(d.postcode);
        if (d.locationQuery) setLocationQuery(d.locationQuery);
        if (d.step) setStep(d.step);
        toast.success('Draft restored!');
      }
    } catch { }
  }, []);

  // ── Location search (suburb + postcode in same input) ────────────────────
  useEffect(() => {
    if (locationDebounce.current) clearTimeout(locationDebounce.current);
    if (locationQuery.length < 2) { setLocationSuggestions([]); return; }
    locationDebounce.current = setTimeout(async () => {
      setLocationLoading(true);
      try {
        const res = await fetch(`/api/suburbs?q=${encodeURIComponent(locationQuery)}`);
        if (res.ok) setLocationSuggestions(await res.json());
      } catch { }
      setLocationLoading(false);
    }, 350);
    return () => { if (locationDebounce.current) clearTimeout(locationDebounce.current); };
  }, [locationQuery]);

  // ── Problem suggestions (semantic + literal matching) ───────────────────
  useEffect(() => {
    if (categorySearch.length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      setActiveIdx(-1);
      return;
    }
    const q = categorySearch.toLowerCase();

    // 1. Literal substring matches on problem text or category name
    const literalMatches = PROBLEM_SUGGESTIONS.filter(s =>
      s.problem.toLowerCase().includes(q) ||
      s.category.toLowerCase().includes(q)
    );

    // 2. Semantic keyword detection — show suggestions from detected category
    const detectedCat = detectCategory(categorySearch);
    const semanticMatches = detectedCat
      ? PROBLEM_SUGGESTIONS.filter(s =>
          s.category.toLowerCase() === detectedCat.toLowerCase() &&
          !literalMatches.includes(s)
        )
      : [];

    // Combine: literal first, then semantic fill, cap at 6
    const combined = [...literalMatches, ...semanticMatches].slice(0, 6);
    setSuggestions(combined);
    setShowDropdown(combined.length > 0);
    setActiveIdx(-1);
  }, [categorySearch]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleCategorySearchEnter = () => {
    setShowDropdown(false);
    if (!categorySearch.trim()) return;
    const cat = detectCategory(categorySearch);
    if (cat) {
      // Only accept the detected category if it exists in the canonical API-fetched list.
      // This prevents setting a non-canonical name that would fail to match tradies.
      const isCanonical = apiCategories.some(c => c.name.toLowerCase() === cat.toLowerCase());
      if (isCanonical) {
        setSelectedCategory(cat);
        if (!description) setDescription(categorySearch);
        setFieldErrors(e => ({ ...e, category: '' }));
        setStep(2);
        return;
      }
    }
    // Could not auto-detect a canonical category  -  carry the text into description
    // so the user can still describe their problem, but keep them on Step 1 to
    // explicitly pick a service tile.
    if (!description) setDescription(categorySearch);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showDropdown) {
      if (e.key === 'Enter') handleCategorySearchEnter();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        handleSuggestionClick(suggestions[activeIdx]);
      } else {
        handleCategorySearchEnter();
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  const handleSuggestionClick = (s: typeof PROBLEM_SUGGESTIONS[0]) => {
    setCategorySearch(s.problem);
    setShowDropdown(false);
    // Validate the suggestion's category against the API-fetched canonical list.
    // PROBLEM_SUGGESTIONS.category should always match TRADIE_CATEGORIES[].name,
    // but we verify here so a stale suggestion never silently sets a wrong category.
    const canonical = apiCategories.find(c => c.name.toLowerCase() === s.category.toLowerCase());
    if (canonical) {
      setSelectedCategory(canonical.name);
      if (!description) setDescription(s.problem);
      setFieldErrors(e => ({ ...e, category: '' }));
      setStep(2);
    } else {
      // Category in suggestion doesn't match canonical list  -  keep user on Step 1
      // and pre-fill description so they can manually pick the right service tile.
      if (!description) setDescription(s.problem);
      setFieldErrors(e => ({ ...e, category: `Could not auto-select "${s.category}". Please pick a service below.` }));
    }
  };

  // ── P3: Postcode-only search in manual entry ─────────────────────────────
  useEffect(() => {
    if (postcodeDebounce.current) clearTimeout(postcodeDebounce.current);
    const digits = postcodeQuery.replace(/\D/g, '');
    if (digits.length < 3) { setPostcodeSuggestions([]); return; }
    postcodeDebounce.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suburbs?q=${encodeURIComponent(digits)}`);
        if (res.ok) setPostcodeSuggestions(await res.json());
      } catch { }
    }, 300);
    return () => { if (postcodeDebounce.current) clearTimeout(postcodeDebounce.current); };
  }, [postcodeQuery]);

  // ── P1 FIX: AI re-runs when step becomes 3 OR aiVersion bumps ───────────
  useEffect(() => {
    if (step !== 3) return;
    setAiLoading(true);
    setAiError(false);
    setAiExplanation('');
    setJobTitle('');
    setAiMissingInfo('');

    const urgencyLabel = URGENCY_OPTIONS.find(u => u.id === urgency)?.label || urgency;

    api.post('/ai/analyse-job', {
      description: `${description}\n\nUrgency: ${urgencyLabel}`,
      category: selectedCategory,
      photo_urls: photos.map(p => p.url),
    }).then(res => {
      const explanation = res.data.explanation || '';
      // If the AI returned an empty brief (e.g. Groq failed but backend returned 200),
      // treat it as an error so the user sees the fallback message instead of a blank step.
      if (!explanation) {
        setAiError(true);
        setJobTitle(res.data.title || `${selectedCategory} job`);
        setJobType(res.data.job_type || 'residential');
        setServiceType(res.data.service_type || 'repair');
      } else {
        setJobTitle(res.data.title);
        setJobType(res.data.job_type);
        setServiceType(res.data.service_type);
        setAiExplanation(explanation);
        setAiMissingInfo(res.data.missing_info || '');
      }
    }).catch(() => {
      setAiError(true);
    }).finally(() => {
      setAiLoading(false);
    });
    // P1 FIX: depend on aiVersion so "Regenerate" button triggers a fresh call
    // also depend on selectedCategory and description so going back and changing either
    // will produce a fresh brief when returning to step 3
  }, [step, aiVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectLocation = (s: SuburbSuggestion) => {
    setSuburb(s.suburb); setState(s.state_code); setPostcode(s.postcode);
    setLocationQuery(s.label); setLocationSuggestions([]);
    setPostcodeQuery(''); setPostcodeSuggestions([]);
    setFieldErrors(e => ({ ...e, location: '' }));
  };

  const clearLocation = () => {
    setSuburb(''); setState(''); setPostcode('');
    setLocationQuery(''); setLocationSuggestions([]);
  };

  const saveDraft = () => {
    setShowCancel(false);
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(buildDraft()));
      toast.success('Progress saved!');
      router.push('/dashboard');
    } catch { router.push('/dashboard'); }
  };

  const discardDraft = () => {
    setShowCancel(false);
    try { localStorage.removeItem(DRAFT_KEY); } catch { }
    router.push('/');
  };

  // ── Photo upload ──────────────────────────────────────────────────────────
  const handlePhotoSelect = async (files: FileList | null) => {
    if (!files || photos.length >= 5) return;
    const file = files[0]; if (!file) return;
    if (file.size > 10_000_000) { toast.error('Photo must be under 10MB.'); return; }
    if (!file.type.startsWith('image/')) { toast.error('Please select an image.'); return; }
    setPhotoUploading(true);
    try {
      const formData = new FormData(); formData.append('file', file);
      const res = await fetch('/api/upload-photo', { method: 'POST', body: formData });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Upload failed'); }
      const { key, public_url } = await res.json();
      setPhotos(prev => [...prev, { key, url: public_url, preview: URL.createObjectURL(file), name: file.name }]);
      toast.success('Photo added.');
    } catch (err: any) { toast.error(err.message || 'Failed to upload photo'); }
    finally { setPhotoUploading(false); if (fileInputRef.current) fileInputRef.current.value = ''; }
  };

  const removePhoto = (key: string) => setPhotos(prev => prev.filter(p => p.key !== key));

  const handleAppendQuestion = (prefix: string) => {
    const newText = description ? `${description.trimEnd()}\n${prefix}` : prefix;
    setDescription(newText);
    setFieldErrors(e => ({ ...e, description: '' }));
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = newText.length;
        textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
      }
    }, 50);
  };

  // ── P2: Validate current step and return errors ───────────────────────────
  const validateStep = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (step === 1) {
      if (!selectedCategory) {
        errors.category = 'Please select a service.';
      } else {
        // Guard: confirm the selected category name maps to a known canonical slug.
        // This catches cases where detectCategory() or a suggestion returned a name
        // that doesn't exist in the API-fetched list, which would cause a matching failure.
        const slug = selectedCategorySlug();
        if (!slug) errors.category = `"${selectedCategory}" is not a recognised service. Please select from the list.`;
      }
    }
    if (step === 2) {
      if (description.trim().length < 10) errors.description = `Add more detail  -  at least 10 characters (${description.length}/10)`;
      if (!urgency) errors.urgency = 'Please select how urgent this job is.';
    }
    if (step === 3 && jobTitle.trim().length < 3) errors.jobTitle = 'Please enter a project title (min 3 characters).';
    if (step === 4) {
      if (!suburb || !state) errors.location = 'Please select your suburb or enter your location.';
    }
    if (step === 5) {
      if (!email.trim()) errors.email = 'Email address is required.';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = 'Enter a valid email address.';
      if (!password) errors.password = 'Password is required.';
      else if (authMode === 'register') {
        if (password.length < 8) errors.password = 'Password must be at least 8 characters.';
        else if (!/[A-Z]/.test(password)) errors.password = 'Password must contain at least one uppercase letter.';
        else if (!/[a-z]/.test(password)) errors.password = 'Password must contain at least one lowercase letter.';
        else if (!/\d/.test(password)) errors.password = 'Password must contain at least one number.';
      }
    }
    return errors;
  };

  const canProceed = () => {
    if (step === 1) return !!selectedCategory;
    if (step === 2) return description.length >= 10 && !!urgency;
    if (step === 3) return !aiLoading && jobTitle.length >= 3;
    if (step === 4) return !!suburb && !!state;
    return true;
  };

  const triggerShake = () => {
    setShakeStep(true);
    setTimeout(() => setShakeStep(false), 500);
  };

  const prevStep = () => {
    setFieldErrors({});
    setStep(s => Math.max(s - 1, 1));
  };

  const nextStep = async () => {
    // Auto-detect category in Step 1 when user typed a description instead of clicking a tile.
    // Validate the detected name against apiCategories so we only accept canonical names.
    if (step === 1 && !selectedCategory && categorySearch.trim()) {
      const cat = detectCategory(categorySearch);
      if (cat) {
        // Confirm the detected name exists in the API-fetched canonical list
        const isCanonical = apiCategories.some(c => c.name.toLowerCase() === cat.toLowerCase());
        if (isCanonical) {
          setSelectedCategory(cat);
          if (!description) setDescription(categorySearch);
          setFieldErrors({});
          setStep(2);
          return;
        }
      }
    }

    // P2: Run validation before proceeding
    const errors = validateStep();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      triggerShake();
      // Show first error as toast
      toast.error(Object.values(errors)[0]);
      return;
    }
    setFieldErrors({});

    if (step === 4 && isAuthenticated) {
      setLoading(true);
      try {
        await postJob();
        try { localStorage.removeItem(DRAFT_KEY); } catch { }
        toast.success('Job posted! Tradies will be in touch.');
        router.push('/dashboard');
      } catch (err: any) {
        toast.error(parseApiError(err));
        setLoading(false);
      }
      return;
    }
    setStep(s => Math.min(s + 1, 5));
  };

  const postJob = async () => {
    // Resolve slug from the fetched canonical list first, fall back to local map.
    // This guarantees the slug we send is always one the backend can look up
    // directly without relying on NLP  -  so the job lands on the exact category
    // the tradie registered under.
    const slug = selectedCategorySlug();
    if (!slug) {
      throw new Error(`Could not resolve a valid service slug for "${selectedCategory}". Please go back and re-select the service.`);
    }

    const res = await api.post('/jobs', {
      title: jobTitle,
      description: aiExplanation || description,
      category_slug: slug,
      suburb, state, postcode, urgency,
      job_type: jobType, service_type: serviceType,
      job_stage: 'ready_to_hire', intent_level: 'high',
      contact_name: user?.name || fullName || email.split('@')[0],
      contact_phone: '',
    });
    const jobId = res.data?.id || res.data?.job_id;
    if (jobId && photos.length > 0) {
      await Promise.allSettled(photos.map(p => api.post('/uploads/confirm', { key: p.key, url: p.url, job_id: jobId })));
    }
  };

  // Send OTP after account is created (register flow)
  const handleRegisterAndSendOtp = async () => {
    const errors = validateStep();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors); triggerShake();
      toast.error(Object.values(errors)[0]); return;
    }
    setLoading(true); setAuthError(''); setOtpError('');
    try {
      // Create the account  -  backend sends OTP email automatically on register
      await register({ email, password, name: fullName || email.split('@')[0], role: 'homeowner' });
      // Now send OTP explicitly (account is created & logged in at this point)
      try {
        await api.post('/auth/send-email-otp');
        toast.success('A 6-digit code was sent to your email.');
      } catch (otpErr: any) {
        // 429 = OTP already sent recently  -  still show the OTP input
        if (otpErr?.response?.status !== 429) throw otpErr;
        toast.success('Check your email for the verification code.');
      }
      setOtpSent(true);
    } catch (err: any) {
      let msg = parseApiError(err);
      if (err?.response?.status === 401)
        msg = 'Could not create account. Email may already be in use.';
      setAuthError(msg); toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // Verify the OTP the user typed, then post the job
  const handleVerifyOtpAndPost = async () => {
    if (!otpCode || otpCode.length < 4) { setOtpError('Please enter the code from your email.'); return; }
    setOtpLoading(true); setOtpError('');
    try {
      await api.post('/auth/verify-email-otp', { code: otpCode.trim() });
      setOtpVerified(true);
      // OTP passed  -  now post the job
      await postJob();
      try { localStorage.removeItem(DRAFT_KEY); } catch { }
      toast.success('Job posted! Tradies will be in touch.');
      router.push('/dashboard');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Invalid or expired code. Try again.';
      setOtpError(msg);
    } finally {
      setOtpLoading(false);
    }
  };

  const handleFinalSubmit = async () => {
    const errors = validateStep();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors); triggerShake();
      toast.error(Object.values(errors)[0]); return;
    }
    setLoading(true); setAuthError('');
    try {
      if (!isAuthenticated) {
        // Login flow: straight through  -  no OTP needed for returning users
        await login(email, password);
      }
      await postJob();
      try { localStorage.removeItem(DRAFT_KEY); } catch { }
      toast.success('Job posted! Tradies will be in touch.');
      router.push('/dashboard');
    } catch (err: any) {
      let msg = parseApiError(err);
      if (err?.response?.status === 401)
        msg = 'Wrong email or password. Try again.';
      setAuthError(msg); toast.error(msg); setLoading(false);
    }
  };

  // Use API-fetched categories (same endpoint as tradie preferences picker).
  // Falls back to hardcoded TRADIE_CATEGORIES while loading or on fetch error.
  const filteredCategories = apiCategories.filter(c =>
    c.name.toLowerCase().includes(categorySearch.toLowerCase()) ||
    c.description.toLowerCase().includes(categorySearch.toLowerCase())
  );

  // Returns the canonical slug for the currently selected category, or '' if unknown.
  // This is validated before every job POST so we never send an unresolvable slug.
  const selectedCategorySlug = (): string => {
    const match = apiCategories.find(
      c => c.name.toLowerCase() === selectedCategory.toLowerCase()
    );
    return match ? match.slug : getCategorySlug(selectedCategory);
  };
  const selectedUrgency = URGENCY_OPTIONS.find(u => u.id === urgency);
  const showGuidedQuestions = step === 2 && description.length >= 20 && !!selectedCategory;
  const showManualEntry = !suburb && locationQuery.length >= 3 && !locationLoading && locationSuggestions.length === 0;

  // ── Save indicator text ──────────────────────────────────────────────────
  const savedText = lastSaved
    ? `Saved ${lastSaved.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })}`
    : null;

  return (
    <div className="min-h-screen font-sans" style={{ background: '#FFF8E7' }}>
      {showCancel && (
        <CancelModal step={step} selectedCategory={selectedCategory} jobTitle={jobTitle}
          onSave={saveDraft} onDiscard={discardDraft} onResume={() => setShowCancel(false)} />
      )}

      {/* ── Sticky top wrapper: header + progress bar ── */}
      <div className="sticky top-0 z-50">
      {/* Header */}
      <header className="backdrop-blur-md shadow-md" style={{ background: '#071D36', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap justify-between items-center gap-3">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: '#D4AA3A', boxShadow: '0 3px 10px rgba(212,170,58,0.3)' }}>
            <Zap className="w-5 h-5 fill-current" style={{ color: '#071D36' }} />
          </div>
          <span className="text-lg sm:text-xl font-black tracking-tight" style={{ color: '#D4AA3A' }}>ProConnect</span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap justify-end">
          {/* P5: Auto-save indicator */}
          <AnimatePresence>
            {(saveIndicator || savedText) && (
              <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 8 }}
                className="flex items-center gap-1.5">
                {saveIndicator === 'saving' ? (
                  <span className="text-xs text-gray-400 font-medium flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" /> Saving...
                  </span>
                ) : (
                  <span className="text-xs text-emerald-600 font-bold flex items-center gap-1">
                    <Check className="w-3 h-3" /> {saveIndicator === 'saved' ? 'Saved' : savedText}
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          {/* P5: Manual save button */}
          {step > 1 && !saveIndicator && (
            <button onClick={autoSave}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 font-medium transition-colors px-2 py-1 rounded-lg hover:bg-gray-100">
              <Save className="w-3.5 h-3.5" /> Save
            </button>
          )}
          <button onClick={() => setShowCancel(true)}
            className="flex items-center gap-2 font-bold text-sm transition-colors"
            style={{ color: 'rgba(255,255,255,0.6)' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}>
            <X className="w-4 h-4" /> Cancel
          </button>
        </div>
        </div>
      </header>

      {/* Progress bar  -  stays visible with header */}
      <div className="border-b border-gray-100 shadow-sm" style={{ background: '#FFF8E7' }}>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-2 pb-3">
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {visibleSteps.map((s, i) => (
            <React.Fragment key={s.id}>
              <div className="flex flex-col items-center gap-1">
                <div className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
                  step > s.id ? "bg-brand-gold text-white" :
                    step === s.id ? "bg-white border-2 border-brand-gold text-brand-gold shadow-sm" :
                      "bg-white border-2 border-gray-200 text-gray-300"
                )}>
                  {step > s.id ? <Check className="w-3.5 h-3.5" /> : s.id}
                </div>
                <span className={cn("text-[10px] font-bold hidden sm:block",
                  step === s.id ? "text-brand-gold" : "text-gray-300")}>
                  {s.title}
                </span>
              </div>
              {i < visibleSteps.length - 1 && (
                <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden mb-3">
                  <motion.div initial={false} animate={{ width: step > s.id ? '100%' : '0%' }}
                    transition={{ duration: 0.35 }} className="h-full bg-brand-gold rounded-full" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
      </div>
      </div>{/* end sticky top wrapper */}

      {/* ── Steps ── */}
      <main className={cn("max-w-2xl mx-auto px-4 sm:px-6 pt-6 pb-32", shakeStep && "animate-shake")}>
        <AnimatePresence mode="wait">

          {/* Step 1: Category */}
          {step === 1 && (
            <motion.div key="s1" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-6">
              <div>
                <h2 className="text-2xl sm:text-3xl font-black text-gray-900">What do you need help with?</h2>
                <p className="text-gray-500 mt-2">Choose the service you need so we can match the right tradies.</p>
                {searchParams.get('q') && (
                  <div className="mt-3 flex items-center gap-2 bg-violet-50 border border-violet-100 rounded-xl px-4 py-2.5">
                    <Sparkles className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                    <p className="text-xs text-violet-700 font-medium">Your description is ready  -  pick a service and we'll continue from there.</p>
                  </div>
                )}
                {/* P2: Category error */}
                {fieldErrors.category && (
                  <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="mt-3 flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-4 py-2.5">
                    <AlertCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                    <p className="text-xs text-red-600 font-medium">{fieldErrors.category}</p>
                  </motion.div>
                )}
              </div>
              <div className="relative z-20">
                <div className="flex items-center bg-white rounded-2xl p-1 pl-4 border-2 border-gray-100 focus-within:border-brand-gold/40 transition-all shadow-sm">
                  <Search className="w-5 h-5 text-gray-400 shrink-0" />
                  <input
                    ref={inputRef}
                    type="text"
                    placeholder="e.g. fix leaking tap, broken fence, no power..."
                    value={categorySearch}
                    onChange={e => setCategorySearch(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
                    className="flex-1 min-w-0 bg-transparent border-none focus:outline-none focus:ring-0 text-sm px-3 text-gray-800 placeholder-gray-400 py-3"
                  />
                  {(() => {
                    const detected = detectCategory(categorySearch);
                    const canonical = detected
                      ? apiCategories.find(c => c.name.toLowerCase() === detected.toLowerCase())
                      : null;
                    return canonical ? (
                      <span className="hidden sm:flex items-center gap-1 text-[11px] font-bold text-[#D4AA3A] bg-[#D4AA3A]/8 px-2.5 py-1 rounded-full mr-2 whitespace-nowrap">
                        {canonical.name}
                      </span>
                    ) : null;
                  })()}
                </div>

                <AnimatePresence>
                  {showDropdown && suggestions.length > 0 && (() => {
                    const detectedForDropdown = detectCategory(categorySearch);
                    const canonicalForDropdown = detectedForDropdown
                      ? apiCategories.find(c => c.name.toLowerCase() === detectedForDropdown.toLowerCase())
                      : null;
                    return (
                      <motion.div
                        ref={dropdownRef}
                        initial={{ opacity: 0, y: -4, scale: 0.99 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -4, scale: 0.99 }}
                        transition={{ duration: 0.12 }}
                        className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-100 rounded-3xl shadow-2xl overflow-hidden z-50"
                      >
                        {/* Detected category quick-select banner */}
                        {canonicalForDropdown && (
                          <div className="px-4 pt-3 pb-2 border-b border-gray-50">
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-[#D4AA3A] animate-pulse" />
                                <span className="text-xs font-bold text-gray-600">Detected service:</span>
                                <span className="text-xs font-black text-[#D4AA3A]">{canonicalForDropdown.name}</span>
                              </div>
                              <button
                                onClick={() => handleSuggestionClick({ problem: categorySearch, category: canonicalForDropdown.name, icon: '' })}
                                className="flex items-center gap-1 text-[11px] font-bold text-white bg-[#D4AA3A] hover:bg-[#B8891D] px-3 py-1.5 rounded-full transition-colors shrink-0"
                              >
                                Select <ChevronRight className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        )}
                        <div className="px-3 pt-2 pb-1">
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 mb-2">Common issues — click to select</p>
                        </div>
                        {suggestions.map((s, i) => (
                          <button
                            key={i}
                            onMouseEnter={() => setActiveIdx(i)}
                            onClick={() => handleSuggestionClick(s)}
                            className={`w-full text-left px-5 py-3 flex items-center gap-3 transition-colors ${activeIdx === i ? 'bg-[#D4AA3A]/5' : 'hover:bg-gray-50'}`}
                          >
                            <span className="flex-1 text-sm font-semibold text-gray-800">{s.problem}</span>
                            <span className="text-[11px] font-bold text-[#D4AA3A] bg-[#D4AA3A]/8 px-2.5 py-1 rounded-full shrink-0">
                              {s.category}
                            </span>
                            <ChevronRight className="w-3.5 h-3.5 text-gray-300 shrink-0" />
                          </button>
                        ))}
                      </motion.div>
                    );
                  })()}
                </AnimatePresence>
              </div>
              {/* Show detected category hint above grid when not yet selected */}
              {(() => {
                const detectedGrid = categorySearch.length >= 2 ? detectCategory(categorySearch) : '';
                const canonicalGrid = detectedGrid
                  ? apiCategories.find(c => c.name.toLowerCase() === detectedGrid.toLowerCase())
                  : null;
                return (canonicalGrid && selectedCategory !== canonicalGrid.name) ? (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-3 bg-[#D4AA3A]/8 border border-[#D4AA3A]/20 rounded-2xl px-4 py-3"
                  >
                    <Sparkles className="w-4 h-4 text-[#D4AA3A] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-gray-700">We detected: <span className="text-[#D4AA3A]">{canonicalGrid.name}</span></p>
                      <p className="text-[11px] text-gray-400 mt-0.5 truncate">{canonicalGrid.description}</p>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedCategory(canonicalGrid.name);
                        setFieldErrors(e => ({ ...e, category: '' }));
                        if (!description) setDescription(categorySearch);
                        setStep(2);
                      }}
                      className="flex items-center gap-1.5 text-xs font-bold text-white bg-[#D4AA3A] hover:bg-[#B8891D] px-4 py-2 rounded-xl transition-colors shrink-0"
                    >
                      Use this <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </motion.div>
                ) : null;
              })()}
              <div className="grid grid-cols-2 min-[420px]:grid-cols-2 sm:grid-cols-4 gap-3 max-h-[60vh] overflow-y-auto pr-1 sm:pr-2 pb-2 custom-scrollbar">
                {filteredCategories.map(cat => {
                  const detectedGridTile = categorySearch.length >= 2 ? detectCategory(categorySearch) : '';
                  const isDetected = detectedGridTile && cat.name.toLowerCase() === detectedGridTile.toLowerCase() && selectedCategory !== cat.name;
                  return (
                    <button key={cat.slug} onClick={() => {
                      setSelectedCategory(cat.name);
                      setFieldErrors(e => ({ ...e, category: '' }));
                      setStep(2);
                    }}
                      className={cn("p-4 rounded-2xl border-2 flex flex-col items-center gap-2 transition-all group text-center relative",
                        selectedCategory === cat.name
                          ? "border-brand-gold bg-brand-gold/5"
                          : isDetected
                            ? "border-[#D4AA3A]/50 bg-[#D4AA3A]/5 ring-2 ring-[#D4AA3A]/20"
                            : "border-gray-100 bg-white hover:border-brand-gold/30 hover:shadow-md"
                      )}>
                      {isDetected && (
                        <div className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-[#D4AA3A] rounded-full flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-white" />
                        </div>
                      )}
                      <span className={cn("text-xs font-bold leading-snug",
                        selectedCategory === cat.name ? "text-brand-gold" : isDetected ? "text-[#D4AA3A]" : "text-gray-800")}>{cat.name}</span>
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* Step 2: Describe */}
          {step === 2 && (
            <motion.div key="s2" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-6">
              <div>
                <h2 className="text-2xl sm:text-3xl font-black text-gray-900">Describe the job</h2>
                <p className="text-gray-500 mt-2">Tell us what's needed  -  AI writes the professional brief in the next step.</p>
              </div>
              <div className="bg-white rounded-3xl border border-gray-100 p-6 shadow-sm space-y-6">
                {/* Description */}
                <div className="space-y-2">
                  <label className="text-sm font-bold text-gray-700">What needs to be done? *</label>
                  <textarea ref={textareaRef} rows={5}
                    placeholder={`e.g. "Bathroom floor tiles cracked in several places, about 15sqm. White ceramic. Grout lines need repointing. Access through back gate."`}
                    value={description} onChange={e => { setDescription(e.target.value); setFieldErrors(e2 => ({ ...e2, description: '' })); }}
                    className={cn("w-full bg-brand-ivory/50 border rounded-xl px-4 py-4 text-sm font-medium focus:outline-none focus:ring-2 transition-all resize-none",
                      fieldErrors.description
                        ? "border-red-300 focus:border-red-400 focus:ring-red-100"
                        : "border-gray-200 focus:border-brand-gold/50 focus:ring-brand-gold/10"
                    )} />
                  {/* P2: Description error */}
                  {fieldErrors.description ? (
                    <p className="text-xs text-red-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> {fieldErrors.description}
                    </p>
                  ) : (
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-gray-400">{description.length} chars  -  include materials, quantities, location</p>
                      {description.length >= 10 && description.length < 40 && (
                        <p className="text-xs text-amber-600 font-medium">More detail = better AI brief</p>
                      )}
                    </div>
                  )}
                  <AnimatePresence>
                    {showGuidedQuestions && (
                      <GuidedQuestions category={selectedCategory} description={description} onAppend={handleAppendQuestion} />
                    )}
                  </AnimatePresence>
                </div>

                {/* Urgency */}
                <div className="space-y-2">
                  <label className="text-sm font-bold text-gray-700">How urgent is this? *</label>
                  <div className="flex flex-wrap gap-2">
                    {URGENCY_OPTIONS.map(opt => {
                      const isSelected = urgency === opt.id;
                      return (
                        <button key={opt.id} onClick={() => { setUrgency(opt.id); setFieldErrors(e => ({ ...e, urgency: '' })); }}
                          className={cn("flex items-center gap-2 px-4 py-2.5 rounded-2xl border-2 text-sm font-bold transition-all",
                            isSelected ? "border-brand-gold bg-brand-gold text-white shadow-sm" : "border-gray-100 bg-gray-50 text-gray-600 hover:border-gray-200"
                          )}>
                          <opt.icon className="w-3.5 h-3.5" />
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                  {fieldErrors.urgency ? (
                    <p className="text-xs text-red-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> {fieldErrors.urgency}
                    </p>
                  ) : selectedUrgency && (
                    <p className="text-xs text-gray-400 pl-1">{selectedUrgency.subtitle}  -  AI will include this timing in the brief</p>
                  )}
                </div>

                {/* Photos */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm font-bold text-gray-700">Photos</label>
                      <span className="text-gray-400 font-normal text-sm">  -  optional but recommended</span>
                    </div>
                    {photos.length > 0 && <span className="text-xs text-gray-400">{photos.length}/5</span>}
                  </div>
                  <p className="text-xs text-gray-400">Photos help AI detect the problem type and materials automatically.</p>
                  {photos.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {photos.map(photo => (
                        <div key={photo.key} className="relative aspect-square rounded-xl overflow-hidden group border border-gray-100">
                          <img src={photo.preview} alt={photo.name} className="w-full h-full object-cover" />
                          <button onClick={() => removePhoto(photo.key)}
                            className="absolute top-1.5 right-1.5 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {photos.length < 5 && (
                    <>
                      <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/heic"
                        className="hidden" onChange={e => handlePhotoSelect(e.target.files)} />
                      <button onClick={() => fileInputRef.current?.click()} disabled={photoUploading}
                        className="w-full border-2 border-dashed border-gray-200 rounded-2xl py-7 flex flex-col items-center gap-3 hover:border-brand-gold/40 hover:bg-brand-ivory/30 transition-all group disabled:opacity-50">
                        {photoUploading
                          ? <Loader2 className="w-7 h-7 text-brand-gold animate-spin" />
                          : <div className="w-11 h-11 rounded-2xl bg-brand-ivory flex items-center justify-center group-hover:scale-110 transition-transform">
                            <ImagePlus className="w-5 h-5 text-brand-gold" />
                          </div>
                        }
                        <div className="text-center">
                          <p className="font-bold text-gray-700 text-sm">{photoUploading ? 'Uploading...' : 'Add photos of the problem'}</p>
                          <p className="text-xs text-gray-400 mt-0.5">PNG, JPG, WEBP up to 10MB</p>
                        </div>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* Step 3: AI Brief */}
          {step === 3 && (
            <motion.div key="s3" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl sm:text-3xl font-black text-gray-900">Your job brief</h2>
                  <p className="text-gray-500 mt-2">AI wrote a professional brief for tradies. Review and edit anything.</p>
                </div>
                {/* P1: Regenerate button */}
                {!aiLoading && (
                  <button onClick={() => setAiVersion(v => v + 1)}
                    className="flex items-center gap-1.5 text-xs font-bold text-brand-gold bg-brand-gold/10 hover:bg-brand-gold/15 px-3 py-2 rounded-xl transition-colors shrink-0 mt-1">
                    Regenerate
                  </button>
                )}
              </div>
              {aiLoading ? (
                <div className="bg-white rounded-3xl border border-gray-100 p-14 shadow-sm flex flex-col items-center gap-4">
                  <Loader2 className="w-10 h-10 text-brand-gold animate-spin" />
                  <p className="text-sm font-bold text-gray-700">Writing your job brief...</p>
                  <p className="text-xs text-gray-400">Reading description{photos.length > 0 ? ', photos' : ''} and urgency for {selectedCategory}</p>
                </div>
              ) : (
                <div className="bg-white rounded-3xl border border-gray-100 p-6 shadow-sm space-y-5">
                  {aiMissingInfo && (
                    <div className="flex items-start gap-3 bg-amber-50 border border-amber-100 rounded-2xl px-4 py-3">
                      <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-amber-800 mb-0.5">Tradies may need more detail</p>
                        <p className="text-xs text-amber-700">Consider adding: {aiMissingInfo}</p>
                      </div>
                    </div>
                  )}
                  {aiExplanation && !aiError && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-bold text-gray-700">Job brief</label>
                        <span className="text-[10px] font-bold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">AI written</span>
                      </div>
                      <textarea rows={4} value={aiExplanation} onChange={e => setAiExplanation(e.target.value)}
                        className="w-full bg-violet-50 border border-violet-100 rounded-xl px-4 py-3.5 text-sm leading-relaxed text-gray-800 focus:outline-none focus:border-violet-300 transition-all resize-none" />
                      <p className="text-xs text-gray-400">This is what tradies read when deciding to quote.</p>
                    </div>
                  )}
                  {aiError && (
                    <div className="flex items-center gap-2 bg-amber-50 border border-amber-100 px-4 py-3 rounded-2xl">
                      <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                      <p className="text-sm text-amber-800">AI unavailable  -  your original description will be used.</p>
                    </div>
                  )}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-bold text-gray-700">Project title *</label>
                      {!aiError && <span className="text-[10px] font-bold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">AI filled</span>}
                    </div>
                    <input type="text" value={jobTitle}
                      onChange={e => { setJobTitle(e.target.value); setFieldErrors(er => ({ ...er, jobTitle: '' })); }}
                      maxLength={100}
                      className={cn("w-full bg-brand-ivory/50 border rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:ring-2 transition-all",
                        fieldErrors.jobTitle
                          ? "border-red-300 focus:border-red-400 focus:ring-red-100"
                          : "border-gray-200 focus:border-brand-gold/50 focus:ring-brand-gold/10"
                      )} />
                    {fieldErrors.jobTitle && (
                      <p className="text-xs text-red-500 font-medium flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" /> {fieldErrors.jobTitle}
                      </p>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <label className="text-sm font-bold text-gray-700">Job type</label>
                        {!aiError && <span className="text-[10px] font-bold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">AI filled</span>}
                      </div>
                      <select value={serviceType} onChange={e => setServiceType(e.target.value)}
                        className="w-full bg-brand-ivory/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-gold/50 transition-all appearance-none">
                        <option value="repair">Repair</option>
                        <option value="new_installation">New installation</option>
                        <option value="replace">Replace</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <label className="text-sm font-bold text-gray-700">Area</label>
                        {!aiError && <span className="text-[10px] font-bold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">AI filled</span>}
                      </div>
                      <select value={jobType} onChange={e => setJobType(e.target.value as 'residential' | 'commercial')}
                        className="w-full bg-brand-ivory/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-gold/50 transition-all appearance-none">
                        <option value="residential">Residential</option>
                        <option value="commercial">Commercial</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-xs text-gray-400">Urgency in brief:</span>
                    {selectedUrgency && (
                      <span className="flex items-center gap-1 text-xs font-bold px-3 py-1 rounded-full bg-brand-gold/10 text-brand-gold">
                        <selectedUrgency.icon className="w-3 h-3" /> {selectedUrgency.label}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 4: Location */}
          {step === 4 && (
            <motion.div key="s4" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-6">
              <div>
                <h2 className="text-2xl sm:text-3xl font-black text-gray-900">Where is the job?</h2>
                <p className="text-gray-500 mt-2">We connect you with tradies who work in your area.</p>
              </div>
              <div className="bg-white rounded-3xl border border-gray-100 p-6 shadow-sm space-y-5">
                {/* P3: Main location input  -  accepts suburb name OR postcode */}
                <div className="relative">
                  <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                  <input
                    type="text"
                    inputMode="search"
                    placeholder="Suburb name or 4-digit postcode..."
                    value={locationQuery}
                    onChange={e => { setLocationQuery(e.target.value); if (suburb) clearLocation(); setFieldErrors(er => ({ ...er, location: '' })); }}
                    autoComplete="off"
                    className={cn("w-full bg-brand-ivory/50 border-2 rounded-2xl pl-12 pr-12 py-4 text-base font-medium focus:outline-none focus:ring-2 transition-all",
                      fieldErrors.location
                        ? "border-red-300 focus:border-red-400 focus:ring-red-100"
                        : "border-gray-200 focus:border-brand-gold/50 focus:ring-brand-gold/10"
                    )}
                  />
                  {locationLoading && <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-brand-gold animate-spin" />}
                  {suburb && !locationLoading && (
                    <button onClick={clearLocation} className="absolute right-4 top-1/2 -translate-y-1/2">
                      <X className="w-5 h-5 text-gray-400 hover:text-gray-600" />
                    </button>
                  )}
                  <AnimatePresence>
                    {locationSuggestions.length > 0 && (
                      <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                        className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 overflow-hidden">
                        {locationSuggestions.map(s => (
                          <button key={`${s.suburb}-${s.postcode}`} onClick={() => selectLocation(s)}
                            className="w-full text-left px-5 py-3.5 hover:bg-brand-ivory transition-colors text-sm flex items-center gap-3 border-b border-gray-50 last:border-0">
                            <MapPin className="w-4 h-4 text-brand-gold shrink-0" />
                            <span className="font-medium text-gray-800">{s.suburb}</span>
                            <span className="text-xs text-gray-400 ml-auto">{s.state_code} {s.postcode}</span>
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* P2: Location error */}
                {fieldErrors.location && (
                  <p className="text-xs text-red-500 font-medium flex items-center gap-1 -mt-2">
                    <AlertCircle className="w-3 h-3" /> {fieldErrors.location}
                  </p>
                )}

                {/* Selected location confirmation */}
                {suburb && (
                  <div className="flex items-center gap-3 bg-green-50 border border-green-100 px-5 py-4 rounded-2xl">
                    <Check className="w-5 h-5 text-green-600 shrink-0" />
                    <div>
                      <p className="font-bold text-green-800 text-sm">{suburb}, {state} {postcode}</p>
                      <p className="text-xs text-green-600 mt-0.5">Tradies in this area will see your job.</p>
                    </div>
                  </div>
                )}

                {/* P3: Manual entry with postcode search dropdown */}
                {showManualEntry && (
                  <div className="space-y-3 pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-500 font-medium">Enter manually:</p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label className="text-xs font-bold text-gray-600">Suburb</label>
                        <input type="text" placeholder="Suburb" value={suburb}
                          onChange={e => setSuburb(e.target.value)}
                          className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none transition-all" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-bold text-gray-600">State</label>
                        <select value={state} onChange={e => setState(e.target.value)}
                          className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none appearance-none">
                          <option value="">State</option>
                          {['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      {/* P3 FIX: Postcode with its own dropdown search */}
                      <div className="space-y-1 relative">
                        <label className="text-xs font-bold text-gray-600">Postcode</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder="0000"
                          value={postcodeQuery || postcode}
                          onChange={e => {
                            const val = e.target.value.replace(/\D/g, '').slice(0, 4);
                            setPostcodeQuery(val);
                            setPostcode(val);
                          }}
                          maxLength={4}
                          className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none transition-all"
                        />
                        <AnimatePresence>
                          {postcodeSuggestions.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                              className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-100 rounded-xl shadow-xl z-50 overflow-hidden max-h-40 overflow-y-auto">
                              {postcodeSuggestions.slice(0, 6).map(s => (
                                <button key={`${s.suburb}-${s.postcode}`}
                                  onClick={() => selectLocation(s)}
                                  className="w-full text-left px-3 py-2 hover:bg-brand-ivory text-xs flex items-center gap-2 border-b border-gray-50 last:border-0 transition-colors">
                                  <span className="font-bold text-gray-800">{s.postcode}</span>
                                  <span className="text-gray-500">{s.suburb}, {s.state_code}</span>
                                </button>
                              ))}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* Step 5: Account + P4 Beautiful Summary */}
          {step === 5 && (
            <motion.div key="s5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-5">

              {/* Account section */}
              <div className="bg-white rounded-3xl border border-gray-100 p-6 shadow-sm space-y-5">
                {/* ── OTP verification screen (register only, after account created) ── */}
                {otpSent && !otpVerified ? (
                  <>
                    <div>
                      <h2 className="text-2xl font-black text-gray-900">Verify your email</h2>
                      <p className="text-sm text-gray-500 mt-1">
                        We sent a 6-digit code to <strong>{email}</strong>. Enter it below to post your job.
                      </p>
                    </div>
                    {otpError && (
                      <div className="flex items-center gap-2 bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-xl text-sm">
                        <AlertCircle className="w-4 h-4 shrink-0" />{otpError}
                      </div>
                    )}
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="000000"
                      value={otpCode}
                      onChange={e => { setOtpCode(e.target.value.replace(/\D/g, '')); setOtpError(''); }}
                      className="w-full bg-brand-ivory/50 border border-gray-200 rounded-xl px-4 py-4 text-2xl font-black text-center tracking-[0.4em] focus:outline-none focus:border-brand-gold/50 focus:ring-2 focus:ring-brand-gold/10 transition-all"
                    />
                    <button
                      type="button"
                      onClick={handleVerifyOtpAndPost}
                      disabled={otpLoading || otpCode.length < 4}
                      className="w-full bg-brand-gold text-white py-3.5 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                    >
                      {otpLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Verifying...</> : <><Check className="w-4 h-4" /> Verify &amp; Post Job</>}
                    </button>
                    <button
                      type="button"
                      onClick={async () => { try { await api.post('/auth/resend-email-otp'); toast.success('New code sent.'); } catch { toast.error('Could not resend. Try again.'); } }}
                      className="w-full text-xs text-gray-400 hover:text-brand-gold transition-colors"
                    >
                      Didn't receive it? Resend code
                    </button>
                  </>
                ) : (
                  <>
                    <div>
                      <h2 className="text-2xl font-black text-gray-900">
                        {authMode === 'register' ? 'Create your free account' : 'Welcome back'}
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        {authMode === 'register' ? 'One account to post jobs and receive quotes.' : 'Log in to post your job.'}
                      </p>
                    </div>
                    <div className="flex bg-brand-ivory rounded-xl p-1">
                      {(['register', 'login'] as const).map(mode => (
                        <button key={mode} onClick={() => { setAuthMode(mode); setAuthError(''); setFieldErrors({}); setOtpSent(false); setOtpCode(''); setOtpError(''); }}
                          className={cn("flex-1 py-2.5 rounded-lg text-sm font-bold transition-all",
                            authMode === mode ? "bg-white text-brand-gold shadow-sm" : "text-gray-500"
                          )}>
                          {mode === 'register' ? 'Create Account' : 'Log In'}
                        </button>
                      ))}
                    </div>
                    {authError && (
                      <div className="flex items-center gap-2 bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-xl text-sm">
                        <AlertCircle className="w-4 h-4 shrink-0" />{authError}
                      </div>
                    )}
                    <div className="space-y-3">
                      {authMode === 'register' && (
                        <div className="relative">
                          <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                          <input type="text" placeholder="Full name" value={fullName} onChange={e => setFullName(e.target.value)}
                            className="w-full bg-brand-ivory/50 border border-gray-200 rounded-xl pl-11 pr-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-gold/50 focus:ring-2 focus:ring-brand-gold/10 transition-all" />
                        </div>
                      )}
                      <div className="relative">
                        <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input type="email" placeholder="Email address" value={email}
                          onChange={e => { setEmail(e.target.value); setFieldErrors(er => ({ ...er, email: '' })); }}
                          className={cn("w-full bg-brand-ivory/50 border rounded-xl pl-11 pr-4 py-3.5 text-sm font-medium focus:outline-none focus:ring-2 transition-all",
                            fieldErrors.email ? "border-red-300 focus:border-red-400 focus:ring-red-100" : "border-gray-200 focus:border-brand-gold/50 focus:ring-brand-gold/10"
                          )} />
                        {fieldErrors.email && <p className="text-xs text-red-500 font-medium mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {fieldErrors.email}</p>}
                      </div>
                      <div className="relative">
                        <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <button type="button" onClick={() => setShowPassword(p => !p)}
                          className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-brand-gold transition-colors">
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                        <input type={showPassword ? 'text' : 'password'} placeholder="Password" value={password}
                          onChange={e => { setPassword(e.target.value); setFieldErrors(er => ({ ...er, password: '' })); }}
                          onFocus={() => setPwdFocused(true)}
                          onBlur={() => setPwdFocused(false)}
                          className={cn("w-full bg-brand-ivory/50 border rounded-xl pl-11 pr-12 py-3.5 text-sm font-medium focus:outline-none focus:ring-2 transition-all",
                            fieldErrors.password ? "border-red-300 focus:border-red-400 focus:ring-red-100" : "border-gray-200 focus:border-brand-gold/50 focus:ring-brand-gold/10"
                          )} />
                        {/* Live password rules  -  register mode only */}
                        {authMode === 'register' && pwdFocused && password.length > 0 && (
                          <div className="mt-2 px-1 grid grid-cols-2 gap-1">
                            {([
                              [password.length >= 8,    '8+ characters'],
                              [/[A-Z]/.test(password),  'Uppercase letter'],
                              [/[a-z]/.test(password),  'Lowercase letter'],
                              [/\d/.test(password),     'Number (0-9)'],
                            ] as [boolean, string][]).map(([ok, label]) => (
                              <div key={label} className="flex items-center gap-1.5 text-xs" style={{ color: ok ? '#16A34A' : '#9CA3AF' }}>
                                <CheckCircle2 className="w-3 h-3 shrink-0" style={{ opacity: ok ? 1 : 0.35 }} />
                                {label}
                              </div>
                            ))}
                          </div>
                        )}
                        {fieldErrors.password && <p className="text-xs text-red-500 font-medium mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {fieldErrors.password}</p>}
                      </div>
                    </div>
                    {authMode === 'login' && (
                      <div className="text-right">
                        <Link href="/forgot-password" className="text-xs text-brand-gold hover:underline font-medium">Forgot password?</Link>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Job summary card */}
              <div className="bg-white rounded-3xl border border-gray-100 p-6 shadow-sm">
                <h3 className="text-base font-bold text-gray-900 mb-3">Your job summary</h3>
                <div className="space-y-2">
                  {selectedCategory && (
                    <div className="flex justify-between items-center py-1 border-b border-gray-50">
                      <span className="text-sm text-gray-500">Category</span>
                      <span className="text-sm font-semibold text-gray-900">{selectedCategory}</span>
                    </div>
                  )}
                  {jobTitle && (
                    <div className="flex justify-between items-center py-1 border-b border-gray-50">
                      <span className="text-sm text-gray-500">Title</span>
                      <span className="text-sm font-semibold text-gray-900 text-right max-w-[60%]">{jobTitle}</span>
                    </div>
                  )}
                  {suburb && (
                    <div className="flex justify-between items-center py-1 border-b border-gray-50">
                      <span className="text-sm text-gray-500">Location</span>
                      <span className="text-sm font-semibold text-gray-900">{suburb}{state ? `, ${state}` : ''}</span>
                    </div>
                  )}
                  {urgency && (
                    <div className="flex justify-between items-center py-1">
                      <span className="text-sm text-gray-500">Urgency</span>
                      <span className="text-sm font-semibold text-gray-900">{selectedUrgency?.label || urgency}</span>
                    </div>
                  )}
                </div>
              </div>

            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* Footer navigation */}
      <footer className="sticky bottom-0 z-40 bg-white border-t border-gray-100 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <button
            onClick={prevStep}
            className="flex items-center gap-2 text-gray-500 hover:text-brand-gold font-medium text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex items-center gap-1.5">
            {[1,2,3,4,5].map(s => (
              <div key={s} className={cn("rounded-full transition-all",
                s === step ? "w-6 h-2 bg-brand-gold" : s < step ? "w-2 h-2 bg-brand-gold/50" : "w-2 h-2 bg-gray-200"
              )} />
            ))}
          </div>
          {step < 5 ? (
            <button
              onClick={nextStep}
              disabled={loading}
              className="flex items-center gap-2 bg-brand-gold text-white px-5 py-2.5 rounded-2xl font-bold text-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:brightness-105"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Next <ChevronRight className="w-4 h-4" /></>}
            </button>
          ) : (otpSent && !otpVerified) ? null : (
            <button
              onClick={authMode === 'register' ? handleRegisterAndSendOtp : handleFinalSubmit}
              disabled={loading || otpLoading}
              className="flex items-center gap-2 bg-brand-gold text-white px-5 py-2.5 rounded-2xl font-bold text-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:brightness-105"
            >
              {loading || otpLoading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> {authMode === 'register' ? 'Creating account...' : 'Posting job...'}</>
                : authMode === 'register'
                  ? <>Create Account &amp; Continue <ChevronRight className="w-4 h-4" /></>
                  : <>Post Job <ChevronRight className="w-4 h-4" /></>
              }
            </button>
          )}
        </div>
      </footer>

    </div>
  );
}

function BookPageInner() {
  return <BookingContent />;
}

export default function BookPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#FFF8E7' }}>
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#D4AA3A' }} />
      </div>
    }>
      <BookPageInner />
    </Suspense>
  );
}
