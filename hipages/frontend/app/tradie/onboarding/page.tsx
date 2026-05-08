"use client";

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import {
    Zap, Loader2, ArrowRight, ArrowLeft, Check, CheckCircle2,
    Mail, Lock, User, Phone, MapPin, Building2, Hash,
    Briefcase, Users, Search, X, AlertCircle, Sparkles,
    ShieldCheck, FileText, Eye, EyeOff, Plus, Calendar,
    Award, Shield, ChevronDown, SkipForward, Info,
} from 'lucide-react';
import api from '@/src/lib/api';
import { saveToken } from '@/src/lib/auth';
import { useAuth } from '@/src/contexts/AuthContext';

const C = {
    paper: '#FAF7F1', panel: '#F3EFE7', card: '#FFFFFF',
    line: '#E8E2D4', lineSoft: '#EFEAE0',
    ink: '#1A1A1A', ink2: '#4A4A48', ink3: '#8A8882', ink4: '#B8B5AE',
    brass: '#A68A4E', brassL: '#F4EEDD', brassB: '#E6D9B5',
    sage: '#5B7560', sageL: '#EDF3EE',
    amber: '#9A6B1E', amberL: '#F7EED8',
    rose: '#A8423A', roseL: '#F7E6E4',
};
const SHADOW_MD = '0 4px 14px rgba(26,26,26,0.06), 0 1px 3px rgba(26,26,26,0.04)';
const SHADOW_SM = '0 1px 3px rgba(26,26,26,0.05), 0 1px 2px rgba(26,26,26,0.03)';
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";

const AU_STATES = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'];

const STATE_REGISTRY_NAMES: Record<string, string> = {
    VIC: 'VBA — Victorian Building Authority',
    NSW: 'NSW Fair Trading',
    QLD: 'QBCC — Queensland Building & Construction Commission',
    WA: 'WA Building Commission',
    SA: 'Consumer & Business Services SA',
    TAS: 'Consumer, Building & Occupational Services TAS',
    NT: 'NT Government Licensing',
    ACT: 'Access Canberra',
};

const LICENCE_REQUIRED_TRADES = [
    'Electrician', 'EV Charger Installation', 'Plumber', 'Gas Fitter',
    'Hot Water System Installer', 'Drains Installer', 'Builder',
    'Renovation and Extensions Builder', 'Asbestos Removal',
    'Demolition Services', 'Pool Builder', 'Pool Fence Installer',
    'Bricklayer', 'Concretor', 'Roofer', 'Waterproofer',
    'Air Conditioning Installer', 'Glazier',
    'electrical', 'plumbing', 'gas-fitting', 'building', 'roofing',
    'waterproofing', 'hvac', 'glazing', 'solar', 'demolition',
];

const isLicenceRequired = (name: string) =>
    LICENCE_REQUIRED_TRADES.some(t => name.toLowerCase().includes(t.toLowerCase()));

const formatAbn = (raw: string) => {
    const d = raw.replace(/\D/g, '').slice(0, 11);
    if (d.length <= 2) return d;
    if (d.length <= 5) return `${d.slice(0, 2)} ${d.slice(2)}`;
    if (d.length <= 8) return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5)}`;
    return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5, 8)} ${d.slice(8)}`;
};
const formatPhone = (raw: string) => {
    const d = raw.replace(/\D/g, '').slice(0, 10);
    if (d.length <= 4) return d;
    if (d.length <= 7) return `${d.slice(0, 4)} ${d.slice(4)}`;
    return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`;
};
const formatCurrency = (raw: string) => {
    const digits = raw.replace(/[^0-9.]/g, '');
    const num = parseFloat(digits);
    if (isNaN(num)) return raw;
    return num.toLocaleString('en-AU', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
};

interface Suburb { suburb: string; postcode: string; state_code: string; label: string; }
interface CategoryItem { id: string; name: string; slug?: string; }

interface CertEntry {
    category_id: string;
    category_name: string;
    licence_number: string;
    issuing_state: string;
    holder_name: string;
    issued_at: string;
    expires_at: string;
    photo_url: string;
    skip: boolean;
}

interface InsuranceEntry {
    insurer_name: string;
    policy_number: string;
    coverage_amount_raw: string;
    holder_name: string;
    expires_at: string;
    document_url: string;
    skip: boolean;
}

type StepId = 1 | 2 | 3 | 4 | 5 | 6 | 7;
type SubmitPhase = 'idle' | 'profile' | 'certs' | 'insurance' | 'done';

const STEPS: { id: StepId; label: string; sub: string }[] = [
    { id: 1, label: 'Account', sub: 'Create your login' },
    { id: 2, label: 'Verify', sub: 'Confirm your email' },
    { id: 3, label: 'Business', sub: 'About your business' },
    { id: 4, label: 'Services', sub: 'What you offer' },
    { id: 5, label: 'Licences', sub: 'Trade certifications' },
    { id: 6, label: 'Insurance', sub: 'Public liability' },
    { id: 7, label: 'Submit', sub: 'Review & submit' },
];

export default function TradieOnboardingPage() {
    const router = useRouter();
    const { fetchUser, user, isAuthenticated, isLoading: authLoading } = useAuth();
    const [step, setStep] = useState<StepId>(1);
    const [submitting, setSubmitting] = useState(false);
    const [submitPhase, setSubmitPhase] = useState<SubmitPhase>('idle');
    // Resume detection — show a spinner while we work out where they left off
    const [resumeChecking, setResumeChecking] = useState(true);

    // ── Step 1: Account ──────────────────────────────────────────────────────
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [phone, setPhone] = useState('');
    const [suburbInput, setSuburbInput] = useState('');
    const [suburbResults, setSuburbResults] = useState<Suburb[]>([]);
    const [selectedSuburb, setSelectedSuburb] = useState<Suburb | null>(null);
    const [suburbSearching, setSuburbSearching] = useState(false);
    const [showSuburbDrop, setShowSuburbDrop] = useState(false);
    const suburbTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [step1Error, setStep1Error] = useState('');

    useEffect(() => {
        const saved = localStorage.getItem('onboarding_suburb');
        if (saved) {
            try { 
                const parsed = JSON.parse(saved);
                setSelectedSuburb(parsed);
                setSuburbInput(parsed.label);
            } catch {}
        }
    }, []);

    useEffect(() => {
        if (selectedSuburb) {
            localStorage.setItem('onboarding_suburb', JSON.stringify(selectedSuburb));
        }
    }, [selectedSuburb]);

    // ── Step 2: OTP ──────────────────────────────────────────────────────────
    const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', '']);
    const [otpSending, setOtpSending] = useState(false);
    const [otpVerifying, setOtpVerifying] = useState(false);
    const [otpError, setOtpError] = useState('');
    const [resendCooldown, setResendCooldown] = useState(0);
    const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

    // ── Step 3: Business ─────────────────────────────────────────────────────
    const [businessName, setBusinessName] = useState('');
    const [abn, setAbn] = useState('');
    const [soloOrTeam, setSoloOrTeam] = useState<'solo' | 'team'>('solo');
    const [teamSize, setTeamSize] = useState<'2-5' | '6-10' | '10+' | ''>('');
    const [bio, setBio] = useState('');

    // ── Step 4: Services ─────────────────────────────────────────────────────
    const [allCategories, setAllCategories] = useState<CategoryItem[]>([]);
    const [catLoading, setCatLoading] = useState(false);
    const [catSearchQuery, setCatSearchQuery] = useState('');
    const [selectedCatIds, setSelectedCatIds] = useState<string[]>([]);
    const [radiusKm, setRadiusKm] = useState<number>(25);

    // ── Step 5: Licences ─────────────────────────────────────────────────────
    const [certEntries, setCertEntries] = useState<CertEntry[]>([]);

    // ── Step 6: Insurance ────────────────────────────────────────────────────
    const [insurance, setInsurance] = useState<InsuranceEntry>({
        insurer_name: '', policy_number: '',
        coverage_amount_raw: '', holder_name: '',
        expires_at: '', document_url: '', skip: false,
    });

    // ── Resume detection: fires once auth state settles ───────────────────────
    // If user already has a valid token (came back mid-flow or after OTP verify),
    // skip the auth steps and land on the first incomplete step (3–7).
    useEffect(() => {
        if (authLoading) return; // wait for auth context to initialise

        if (!isAuthenticated || !user) {
            // Not logged in — normal flow, start at step 1
            setResumeChecking(false);
            return;
        }

        // Logged in but email not verified → resume at OTP step
        if (!user.email_verified) {
            // We no longer automatically resend here to avoid 429 errors.
            // The OTP from registration might still be valid. 
            // If they need a new one, they can click "Resend code".
            setStep(2);
            setResendCooldown(60);
            setResumeChecking(false);
            return;
        }

        // Email verified — find the first incomplete step (3–7)
        const detectStep = async () => {
            try {
                // Does a tradie profile exist?
                const profileRes = await api.get('/tradies/profile/me');
                const profile = profileRes.data;

                // Restore any profile data we already have
                setBusinessName(profile.business_name || '');
                setAbn(profile.abn ? formatAbn(profile.abn) : '');
                setBio(profile.bio || '');
                setSoloOrTeam(profile.solo_or_team === 'team' ? 'team' : 'solo');

                // Does the profile have categories?
                try {
                    const catsRes = await api.get('/categories/my-categories');
                    const myCats: { id?: string; category_id?: string; name?: string }[] = catsRes.data || [];

                    if (myCats.length > 0) {
                        const ids = myCats.map(c => c.category_id || c.id || '').filter(Boolean);
                        setSelectedCatIds(ids);

                        // Does the profile have certifications?
                        const certsRes = await api.get('/tradies/certifications/me').catch(() => ({ data: [] }));
                        const insurRes = await api.get('/tradies/insurance/me').catch(() => ({ data: [] }));

                        if ((certsRes.data || []).length > 0 || (insurRes.data || []).length > 0) {
                            // Certs/insurance already submitted → go to final review
                            setStep(7);
                        } else {
                            // Has categories but no certs/insurance → go to licences
                            setStep(5);
                        }
                    } else {
                        // Has profile but no categories → go to services
                        setStep(4);
                    }
                } catch {
                    setStep(4);
                }
            } catch (err: any) {
                if (err?.response?.status === 404) {
                    // No profile yet — start at business details
                    setStep(3);
                } else {
                    // Unknown error — start fresh
                    setStep(3);
                }
            } finally {
                setResumeChecking(false);
            }
        };

        detectStep();
    }, [authLoading, isAuthenticated, user]);

    // ── Suburb debounce ───────────────────────────────────────────────────────
    useEffect(() => {
        if (selectedSuburb && suburbInput === selectedSuburb.label) return;
        if (suburbTimerRef.current) clearTimeout(suburbTimerRef.current);
        if (suburbInput.length < 2) { setSuburbResults([]); return; }
        setSuburbSearching(true);
        suburbTimerRef.current = setTimeout(async () => {
            try {
                const res = await fetch(`/api/suburbs?q=${encodeURIComponent(suburbInput)}&limit=8`);
                setSuburbResults(await res.json());
            } catch { setSuburbResults([]); }
            finally { setSuburbSearching(false); }
        }, 250);
    }, [suburbInput, selectedSuburb]);

    // ── OTP resend cooldown ───────────────────────────────────────────────────
    useEffect(() => {
        if (resendCooldown <= 0) return;
        const t = setInterval(() => setResendCooldown(c => Math.max(0, c - 1)), 1000);
        return () => clearInterval(t);
    }, [resendCooldown]);

    // ── Load categories on step 4 ─────────────────────────────────────────────
    useEffect(() => {
        if (step !== 4 || allCategories.length > 0) return;
        setCatLoading(true);
        api.get('/categories/')
            .then(r => setAllCategories(r.data || []))
            .catch(() => toast.error('Could not load services. Try again.'))
            .finally(() => setCatLoading(false));
    }, [step]);

    // ── Derived ───────────────────────────────────────────────────────────────
    const filteredCategories = useMemo(() => {
        if (!catSearchQuery) return allCategories;
        const q = catSearchQuery.toLowerCase();
        return allCategories.filter(c => c.name.toLowerCase().includes(q));
    }, [allCategories, catSearchQuery]);

    const selectedCatNames = useMemo(
        () => allCategories.filter(c => selectedCatIds.includes(c.id)).map(c => c.name),
        [allCategories, selectedCatIds],
    );
    const licensedSelectedCats = useMemo(
        () => allCategories.filter(c => selectedCatIds.includes(c.id) && isLicenceRequired(c.name)),
        [allCategories, selectedCatIds],
    );

    const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
    const step1Valid =
        fullName.trim().length >= 2 && isEmail(email) && password.length >= 8 &&
        phone.replace(/\D/g, '').length === 10 && !!selectedSuburb;
    const step3Valid =
        businessName.trim().length >= 2 && abn.replace(/\D/g, '').length === 11 &&
        (soloOrTeam === 'solo' || (soloOrTeam === 'team' && !!teamSize));
    const step4Valid = selectedCatIds.length > 0;
    const step5Valid = certEntries.every(e =>
        e.skip || (e.licence_number.trim().length >= 2 && e.issuing_state && e.holder_name.trim().length >= 2)
    );
    const step6Valid =
        insurance.skip ||
        (insurance.insurer_name.trim().length >= 2 &&
            insurance.policy_number.trim().length >= 2 &&
            insurance.coverage_amount_raw.replace(/[^0-9.]/g, '').length > 0 &&
            insurance.holder_name.trim().length >= 2 &&
            !!insurance.expires_at);

    // ── Shared input styles ───────────────────────────────────────────────────
    const labelStyle: React.CSSProperties = {
        fontSize: 11, fontWeight: 600, color: C.ink2,
        textTransform: 'uppercase', letterSpacing: '0.08em',
        display: 'block', marginBottom: 8,
    };
    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '13px 16px', borderRadius: 12,
        border: `1.5px solid ${C.line}`, background: C.paper,
        fontSize: 14.5, color: C.ink, outline: 'none',
        boxSizing: 'border-box', fontFamily: UI, transition: 'all 0.15s',
    };
    const inputFocusOn = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        e.target.style.borderColor = C.brass; e.target.style.background = C.card;
    };
    const inputFocusOff = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        e.target.style.borderColor = C.line; e.target.style.background = C.paper;
    };

    // ── Step 1: Account handlers ──────────────────────────────────────────────
    const handleStep1Submit = async () => {
        setStep1Error('');
        if (!step1Valid) { setStep1Error('Please complete all fields correctly.'); return; }
        setSubmitting(true);
        try {
            // POST /auth/register is now idempotent for unverified emails.
            // It returns 200 whether creating a new user or resending OTP to an
            // existing unverified account — so we never get a 400 for that case.
            await api.post('/auth/register', {
                email: email.trim().toLowerCase(), password,
                full_name: fullName.trim(), phone: phone.replace(/\D/g, ''), role: 'tradie',
            });

            // Log in to get a JWT (works for both new + existing-unverified users)
            const loginRes = await api.post('/auth/login', { email: email.trim().toLowerCase(), password });
            saveToken(loginRes.data.access_token);

            // Note: /auth/register automatically sends the first OTP, so we don't send it again here to avoid 429s.
            setResendCooldown(60);
            setStep(2);
        } catch (e: any) {
            const detail = e?.response?.data?.detail;

            // The only 400 we still get is "already registered + verified" → tell them to sign in
            if (e?.response?.status === 400) {
                setStep1Error('An account with this email already exists. Please sign in instead.');
                return;
            }

            let msg = 'Could not create account.';
            if (typeof detail === 'string') msg = detail;
            else if (Array.isArray(detail) && detail.length > 0)
                msg = detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join(', ');
            else if (e?.message) msg = e.message;
            setStep1Error(msg);
        } finally { setSubmitting(false); }
    };

    // ── Step 2: OTP handlers ──────────────────────────────────────────────────
    const handleOtpChange = (idx: number, val: string) => {
        const digit = val.replace(/\D/g, '').slice(-1);
        const next = [...otpDigits]; next[idx] = digit;
        setOtpDigits(next); setOtpError('');
        if (digit && idx < 5) otpRefs.current[idx + 1]?.focus();
        if (next.every(d => d !== '') && !otpVerifying) handleVerifyOtp(next.join(''));
    };
    const handleOtpKeyDown = (idx: number, e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Backspace' && !otpDigits[idx] && idx > 0) otpRefs.current[idx - 1]?.focus();
        if (e.key === 'ArrowLeft' && idx > 0) otpRefs.current[idx - 1]?.focus();
        if (e.key === 'ArrowRight' && idx < 5) otpRefs.current[idx + 1]?.focus();
    };
    const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
        if (pasted.length === 6) {
            const next = pasted.split('');
            setOtpDigits(next); setOtpError('');
            otpRefs.current[5]?.focus();
            handleVerifyOtp(pasted);
        }
    };
    const handleVerifyOtp = async (code: string) => {
        setOtpVerifying(true); setOtpError('');
        try {
            await api.post('/auth/verify-email-otp', { code });
            toast.success('Email verified.');
            setStep(3);
        } catch (e: any) {
            const detail = e?.response?.data?.detail;
            setOtpError(typeof detail === 'string' ? detail : 'Invalid code.');
            setOtpDigits(['', '', '', '', '', '']);
            otpRefs.current[0]?.focus();
        } finally { setOtpVerifying(false); }
    };
    const handleResendOtp = async () => {
        if (resendCooldown > 0) return;
        setOtpSending(true); setOtpError('');
        try {
            await api.post('/auth/resend-email-otp');
            toast.success('New code sent.'); setResendCooldown(60);
            setOtpDigits(['', '', '', '', '', '']);
            otpRefs.current[0]?.focus();
        } catch (e: any) {
            const detail = e?.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : 'Could not resend code.');
        } finally { setOtpSending(false); }
    };

    // ── Step 4 → Step 5: Init cert entries from licensed categories ───────────
    const handleStep4Continue = () => {
        const licensed = allCategories.filter(c =>
            selectedCatIds.includes(c.id) && isLicenceRequired(c.name)
        );
        const existingIds = certEntries.map(e => e.category_id);
        const newEntries = licensed
            .filter(c => !existingIds.includes(c.id))
            .map(c => ({
                category_id: c.id,
                category_name: c.name,
                licence_number: '',
                issuing_state: selectedSuburb?.state_code || '',
                holder_name: fullName.trim(),
                issued_at: '',
                expires_at: '',
                photo_url: '',
                skip: false,
            }));
        const pruned = certEntries.filter(e => selectedCatIds.includes(e.category_id));
        setCertEntries([...pruned, ...newEntries]);
        setStep(5);
    };

    const updateCert = (idx: number, field: keyof CertEntry, value: string | boolean) => {
        setCertEntries(prev => prev.map((e, i) => i === idx ? { ...e, [field]: value } : e));
    };

    // ── Step 6 → Step 7: Back from insurance ─────────────────────────────────
    const handleStep6Back = () => {
        setStep(certEntries.length > 0 ? 5 : 4);
    };

    // ── Final submit ──────────────────────────────────────────────────────────
    const handleFinalSubmit = async () => {
        if (!selectedSuburb) return;
        setSubmitting(true);

        // Phase 1: Create profile
        setSubmitPhase('profile');
        try {
            await api.post('/tradies/onboarding/submit', {
                business_name: businessName.trim(),
                abn: abn.replace(/\D/g, ''),
                suburb: selectedSuburb.suburb,
                state: selectedSuburb.state_code,
                postcode: selectedSuburb.postcode,
                solo_or_team: soloOrTeam,
                team_size: soloOrTeam === 'team' ? teamSize : null,
                phone: phone.replace(/\D/g, ''),
                bio: bio.trim() || null,
                category_ids: selectedCatIds,
                radius_km: radiusKm,
            });
            await fetchUser?.();
        } catch (e: any) {
            const detail = e?.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : 'Could not submit profile. Try again.');
            setSubmitting(false);
            setSubmitPhase('idle');
            return;
        }

        // Phase 2: Submit certifications (non-fatal — user can add from dashboard)
        setSubmitPhase('certs');
        const certErrors: string[] = [];
        for (const entry of certEntries.filter(e => !e.skip && e.licence_number.trim())) {
            try {
                await api.post('/tradies/certifications/submit', {
                    category_id: entry.category_id,
                    licence_number: entry.licence_number.trim().toUpperCase(),
                    issuing_state: entry.issuing_state,
                    holder_name: entry.holder_name.trim(),
                    issued_at: entry.issued_at || null,
                    expires_at: entry.expires_at || null,
                    photo_url: entry.photo_url || null,
                });
            } catch {
                certErrors.push(entry.category_name);
            }
        }
        if (certErrors.length > 0) {
            toast.error(`Could not submit licence for: ${certErrors.join(', ')}. Add from your dashboard.`);
        }

        // Phase 3: Submit insurance (non-fatal)
        setSubmitPhase('insurance');
        if (!insurance.skip && insurance.policy_number.trim() && insurance.insurer_name.trim()) {
            try {
                const rawAmt = insurance.coverage_amount_raw.replace(/[^0-9.]/g, '');
                const cents = Math.round(parseFloat(rawAmt) * 100);
                await api.post('/tradies/insurance/submit', {
                    insurance_type: 'public_liability',
                    insurer_name: insurance.insurer_name.trim(),
                    policy_number: insurance.policy_number.trim().toUpperCase(),
                    coverage_amount_cents: cents,
                    holder_name: insurance.holder_name.trim(),
                    expires_at: insurance.expires_at,
                    document_url: insurance.document_url || null,
                });
            } catch {
                toast.error('Could not submit insurance details. Add from your dashboard.');
            }
        }

        setSubmitPhase('done');
        toast.success('Profile submitted — our team will review within 1 business day.');
        setTimeout(() => router.push('/tradie/dashboard'), 700);
    };

    const submitPhaseLabel = {
        idle: '', profile: 'Creating your profile…',
        certs: 'Submitting licences…', insurance: 'Submitting insurance…', done: 'Done!',
    }[submitPhase];

    // ── While checking where to resume, show a neutral loading screen ─────────
    if (resumeChecking) {
        return (
            <div style={{ minHeight: '100vh', background: C.paper, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, fontFamily: UI }}>
                <div style={{ width: 48, height: 48, borderRadius: 14, background: C.ink, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Zap size={22} color={C.card} fill={C.card} />
                </div>
                <Loader2 size={20} color={C.brass} style={{ animation: 'spin 1s linear infinite' }} />
                <p style={{ fontSize: 14, color: C.ink3, margin: 0 }}>Checking your progress…</p>
                <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
            </div>
        );
    }

    return (
        <div className="onboarding-root" style={{
            minHeight: '100vh', background: C.paper, fontFamily: UI, color: C.ink,
            display: 'flex', flexDirection: 'column',
        }}>

            {/* ── Header ── */}
            <header style={{
                padding: '20px 28px', borderBottom: `1px solid ${C.line}`,
                background: `${C.paper}E6`, backdropFilter: 'blur(10px)',
                position: 'sticky', top: 0, zIndex: 100,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 9, background: C.ink, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Zap size={16} color={C.card} fill={C.card} />
                    </div>
                    <div>
                        <p style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 500, color: C.ink, margin: 0, letterSpacing: '-0.01em', lineHeight: 1 }}>ProConnect</p>
                        <p style={{ fontSize: 10, fontWeight: 600, color: C.ink3, margin: '3px 0 0', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Tradie onboarding</p>
                    </div>
                </div>
                <a href="/tradie/login" style={{ fontSize: 12.5, fontWeight: 600, color: C.ink3, textDecoration: 'none' }}>
                    Already a member? <span style={{ color: C.brass }}>Sign in</span>
                </a>
            </header>

            {/* ── Stepper ── */}
            <div style={{ padding: '24px 28px 8px', maxWidth: 760, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'space-between' }}>
                    {STEPS.map((s, i) => {
                        const done = step > s.id;
                        const active = step === s.id;
                        return (
                            <React.Fragment key={s.id}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
                                    <div style={{
                                        width: 27, height: 27, borderRadius: '50%',
                                        background: done ? C.sage : active ? C.ink : C.panel,
                                        color: done || active ? C.card : C.ink3,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: 11, fontWeight: 700, flexShrink: 0,
                                        border: `1.5px solid ${done ? C.sage : active ? C.ink : C.line}`,
                                        transition: 'all 0.25s',
                                    }}>
                                        {done ? <Check size={13} strokeWidth={3} /> : s.id}
                                    </div>
                                    <span className="step-label" style={{ fontSize: 12, fontWeight: 600, color: active ? C.ink : done ? C.ink2 : C.ink4, whiteSpace: 'nowrap' }}>{s.label}</span>
                                </div>
                                {i < STEPS.length - 1 && (
                                    <div style={{ flex: 1, height: 1.5, background: done ? C.sage : C.line, transition: 'background 0.25s', minWidth: 8 }} />
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>
            </div>

            {/* ── Main content ── */}
            <main style={{ flex: 1, padding: '20px 28px 60px', maxWidth: 640, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
                <AnimatePresence mode="wait">

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 1 — Account (EXISTING, PRESERVED EXACTLY)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 1 && (
                        <motion.div key="s1" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 28 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 1 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>Create your account</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>Quick details first — we'll send a verification code to your email next.</p>
                            </div>
                            {step1Error && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18, background: C.roseL, border: `1px solid ${C.rose}30`, color: C.rose, padding: '10px 14px', borderRadius: 10, fontSize: 13 }}>
                                    <AlertCircle size={14} />{step1Error}
                                </div>
                            )}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                <div>
                                    <label style={labelStyle}>Full name</label>
                                    <div style={{ position: 'relative' }}>
                                        <User size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input value={fullName} onChange={e => setFullName(e.target.value)} placeholder="John Smith" style={{ ...inputStyle, paddingLeft: 40 }} onFocus={inputFocusOn} onBlur={inputFocusOff} autoComplete="name" />
                                    </div>
                                </div>
                                <div>
                                    <label style={labelStyle}>Email</label>
                                    <div style={{ position: 'relative' }}>
                                        <Mail size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" style={{ ...inputStyle, paddingLeft: 40 }} onFocus={inputFocusOn} onBlur={inputFocusOff} autoComplete="email" />
                                    </div>
                                </div>
                                <div>
                                    <label style={labelStyle}>Password</label>
                                    <div style={{ position: 'relative' }}>
                                        <Lock size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input type={showPwd ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" style={{ ...inputStyle, paddingLeft: 40, paddingRight: 44 }} onFocus={inputFocusOn} onBlur={inputFocusOff} autoComplete="new-password" />
                                        <button type="button" onClick={() => setShowPwd(s => !s)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: C.ink3, padding: 4, display: 'flex' }}>
                                            {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                                        </button>
                                    </div>
                                    {password && password.length < 8 && <p style={{ fontSize: 11.5, color: C.amber, margin: '6px 0 0' }}>Use at least 8 characters.</p>}
                                </div>
                                <div>
                                    <label style={labelStyle}>Mobile number</label>
                                    <div style={{ position: 'relative' }}>
                                        <Phone size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input value={phone} onChange={e => setPhone(formatPhone(e.target.value))} placeholder="04XX XXX XXX" maxLength={12} style={{ ...inputStyle, paddingLeft: 40, fontVariantNumeric: 'tabular-nums' }} onFocus={inputFocusOn} onBlur={inputFocusOff} autoComplete="tel-national" inputMode="numeric" />
                                    </div>
                                </div>
                                <div style={{ position: 'relative' }}>
                                    <label style={labelStyle}>Your suburb</label>
                                    <div style={{ position: 'relative' }}>
                                        <MapPin size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input value={suburbInput}
                                            onChange={e => { setSuburbInput(e.target.value); setSelectedSuburb(null); setShowSuburbDrop(true); }}
                                            onFocus={e => { inputFocusOn(e); setShowSuburbDrop(true); }}
                                            onBlur={e => { inputFocusOff(e); setTimeout(() => setShowSuburbDrop(false), 150); }}
                                            placeholder="Start typing your suburb…"
                                            style={{ ...inputStyle, paddingLeft: 40 }} autoComplete="off" />
                                        {suburbSearching && <Loader2 size={13} className="animate-spin" style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', color: C.ink3 }} />}
                                        {selectedSuburb && !suburbSearching && <CheckCircle2 size={15} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', color: C.sage }} />}
                                    </div>
                                    {showSuburbDrop && suburbResults.length > 0 && (
                                        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4, background: C.card, border: `1px solid ${C.line}`, borderRadius: 12, boxShadow: SHADOW_MD, maxHeight: 240, overflowY: 'auto', zIndex: 5 }}>
                                            {suburbResults.map((r, i) => (
                                                <button key={`${r.suburb}-${r.postcode}`} type="button"
                                                    onMouseDown={() => { setSelectedSuburb(r); setSuburbInput(r.label); setSuburbResults([]); setShowSuburbDrop(false); }}
                                                    style={{ width: '100%', padding: '10px 16px', border: 'none', borderBottom: i < suburbResults.length - 1 ? `1px solid ${C.lineSoft}` : 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', transition: 'background 0.12s' }}
                                                    onMouseEnter={e => e.currentTarget.style.background = C.paper}
                                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                                                    <span style={{ fontSize: 13.5, fontWeight: 600, color: C.ink }}>{r.suburb}</span>
                                                    <span style={{ fontSize: 12, color: C.ink3, marginLeft: 8 }}>{r.state_code} {r.postcode}</span>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <button onClick={handleStep1Submit} disabled={!step1Valid || submitting}
                                    style={{ marginTop: 8, padding: '15px 22px', borderRadius: 12, border: 'none', background: (!step1Valid || submitting) ? C.ink3 : C.ink, color: C.card, fontSize: 14, fontWeight: 600, cursor: (!step1Valid || submitting) ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                    {submitting ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
                                    {submitting ? 'Creating account…' : 'Continue to email verification'}
                                </button>
                                <p style={{ fontSize: 11.5, color: C.ink4, textAlign: 'center', margin: '4px 0 0', lineHeight: 1.6 }}>
                                    By continuing you agree to our <a href="/terms" style={{ color: C.ink3 }}>Terms</a> and <a href="/privacy" style={{ color: C.ink3 }}>Privacy Policy</a>.
                                </p>
                            </div>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 2 — Email OTP (EXISTING, PRESERVED EXACTLY)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 2 && (
                        <motion.div key="s2" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 28 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 2 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>Verify your email</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>
                                    We sent a 6-digit code to <strong style={{ color: C.ink }}>{email}</strong>. It expires in 10 minutes.
                                </p>
                            </div>
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 16 }}>
                                {otpDigits.map((d, i) => (
                                    <input key={i} ref={el => { otpRefs.current[i] = el; }}
                                        type="text" inputMode="numeric" maxLength={1} value={d}
                                        onChange={e => handleOtpChange(i, e.target.value)}
                                        onKeyDown={e => handleOtpKeyDown(i, e)}
                                        onPaste={i === 0 ? handleOtpPaste : undefined}
                                        autoFocus={i === 0} disabled={otpVerifying}
                                        style={{ width: 50, height: 60, textAlign: 'center', fontSize: 28, fontWeight: 500, fontFamily: DISPLAY, border: `1.5px solid ${otpError ? C.rose : d ? C.brass : C.line}`, borderRadius: 12, background: d ? C.brassL : C.paper, color: C.ink, outline: 'none', boxSizing: 'border-box', transition: 'all 0.15s' }} />
                                ))}
                            </div>
                            {otpError && (
                                <p style={{ fontSize: 13, color: C.rose, textAlign: 'center', margin: '0 0 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                                    <AlertCircle size={13} />{otpError}
                                </p>
                            )}
                            {otpVerifying && (
                                <p style={{ fontSize: 13, color: C.ink3, textAlign: 'center', margin: '0 0 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                                    <Loader2 size={13} className="animate-spin" />Verifying…
                                </p>
                            )}
                            <div style={{ textAlign: 'center', margin: '24px 0 8px' }}>
                                <p style={{ fontSize: 13, color: C.ink3, margin: '0 0 6px' }}>Didn't receive the code?</p>
                                <button onClick={handleResendOtp} disabled={resendCooldown > 0 || otpSending}
                                    style={{ background: 'none', border: 'none', color: resendCooldown > 0 ? C.ink4 : C.brass, fontSize: 13, fontWeight: 600, cursor: resendCooldown > 0 ? 'not-allowed' : 'pointer', padding: '6px 12px', textDecoration: resendCooldown > 0 ? 'none' : 'underline' }}>
                                    {otpSending ? 'Sending…' : resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                                </button>
                            </div>
                            <button onClick={() => setStep(1)} disabled={otpVerifying}
                                style={{ margin: '8px auto 0', display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: C.ink3, fontSize: 12.5, cursor: 'pointer', padding: '6px 10px' }}>
                                <ArrowLeft size={12} /> Wrong email? Go back
                            </button>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 3 — Business (EXISTING, PRESERVED EXACTLY)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 3 && (
                        <motion.div key="s3" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 28 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 3 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>About your business</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>Quick details so we can verify your business and connect you with the right jobs.</p>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                                <div>
                                    <label style={labelStyle}>Business name</label>
                                    <div style={{ position: 'relative' }}>
                                        <Building2 size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input value={businessName} onChange={e => setBusinessName(e.target.value)} placeholder="e.g. Smith's Plumbing" style={{ ...inputStyle, paddingLeft: 40 }} onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                    </div>
                                    <p style={{ fontSize: 11.5, color: C.ink4, margin: '6px 0 0' }}>This is what homeowners will see on your profile.</p>
                                </div>
                                <div>
                                    <label style={labelStyle}>Australian Business Number (ABN)</label>
                                    <div style={{ position: 'relative' }}>
                                        <Hash size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                        <input value={abn} onChange={e => setAbn(formatAbn(e.target.value))} placeholder="11 222 333 444" maxLength={14} style={{ ...inputStyle, paddingLeft: 40, fontVariantNumeric: 'tabular-nums', letterSpacing: '0.05em' }} onFocus={inputFocusOn} onBlur={inputFocusOff} inputMode="numeric" />
                                    </div>
                                    <p style={{ fontSize: 11.5, color: C.ink4, margin: '6px 0 0' }}>11 digits — verified by our team against the Australian Business Register.</p>
                                </div>
                                <div>
                                    <label style={labelStyle}>Are you working solo, or with a team?</label>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        {([
                                            { v: 'solo', label: 'Just me', sub: 'Sole trader', icon: User },
                                            { v: 'team', label: 'I have a team', sub: 'Multiple workers', icon: Users },
                                        ] as const).map(opt => {
                                            const Icon = opt.icon;
                                            const sel = soloOrTeam === opt.v;
                                            return (
                                                <button key={opt.v} onClick={() => setSoloOrTeam(opt.v)}
                                                    style={{ padding: '16px 18px', borderRadius: 12, textAlign: 'left', border: `1.5px solid ${sel ? C.brass : C.line}`, background: sel ? C.brassL : C.paper, cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                                    <div style={{ width: 36, height: 36, borderRadius: 10, background: sel ? C.brass : C.card, color: sel ? C.card : C.ink3, border: `1px solid ${sel ? C.brass : C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.15s' }}>
                                                        <Icon size={16} />
                                                    </div>
                                                    <div>
                                                        <p style={{ fontSize: 14, fontWeight: 600, color: C.ink, margin: '0 0 2px' }}>{opt.label}</p>
                                                        <p style={{ fontSize: 12, color: C.ink3, margin: 0 }}>{opt.sub}</p>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                                <AnimatePresence>
                                    {soloOrTeam === 'team' && (
                                        <motion.div key="teamsize" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.22 }} style={{ overflow: 'hidden' }}>
                                            <label style={labelStyle}>Team size</label>
                                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                                {(['2-5', '6-10', '10+'] as const).map(s => {
                                                    const sel = teamSize === s;
                                                    return (
                                                        <button key={s} onClick={() => setTeamSize(s)}
                                                            style={{ padding: '10px 18px', borderRadius: 10, border: `1.5px solid ${sel ? C.brass : C.line}`, background: sel ? C.brassL : C.paper, color: sel ? C.brass : C.ink2, fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s' }}>
                                                            {s} {s === '10+' ? 'workers' : 'people'}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                            <p style={{ fontSize: 11.5, color: C.ink4, margin: '8px 0 0' }}>You'll add team members from your dashboard later.</p>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                                <div>
                                    <label style={labelStyle}>About your work <span style={{ color: C.ink4, textTransform: 'none', letterSpacing: 0 }}>(optional but recommended)</span></label>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                                        {['🔧 10+ years experience', '✅ Licensed & insured', '⚡ Same-day availability', '📸 Before & after photos', '🏆 5-star rated on Google', '🔒 Fixed-price quotes', '📞 Free on-site quotes', '🚐 Fully equipped van'].map(chip => (
                                            <button key={chip} type="button"
                                                onClick={() => {
                                                    const text = chip.replace(/^\S+ /, '');
                                                    const sep = bio.trim() ? '. ' : '';
                                                    setBio(prev => (prev + sep + text).slice(0, 500));
                                                }}
                                                style={{ padding: '5px 10px', borderRadius: 20, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 12, cursor: 'pointer', transition: 'all 0.12s' }}
                                                onMouseEnter={e => { e.currentTarget.style.borderColor = C.brass; e.currentTarget.style.background = C.brassL; e.currentTarget.style.color = C.brass; }}
                                                onMouseLeave={e => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.background = C.paper; e.currentTarget.style.color = C.ink2; }}>
                                                {chip}
                                            </button>
                                        ))}
                                    </div>
                                    <textarea rows={4} value={bio} onChange={e => setBio(e.target.value.slice(0, 500))}
                                        placeholder="e.g. Licensed plumber with 12 years experience. Fixed-price quotes, same-day availability, 5-star rated."
                                        style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.6 }}
                                        onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                    <p style={{ fontSize: 11, color: C.ink4, marginTop: 5, fontVariantNumeric: 'tabular-nums' }}>{bio.length}/500</p>
                                </div>
                                <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                                    <button onClick={() => setStep(2)} style={{ padding: '15px 22px', borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <ArrowLeft size={14} /> Back
                                    </button>
                                    <button onClick={() => setStep(4)} disabled={!step3Valid}
                                        style={{ flex: 1, padding: '15px 22px', borderRadius: 12, border: 'none', background: step3Valid ? C.ink : C.ink3, color: C.card, fontSize: 14, fontWeight: 600, cursor: step3Valid ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                        Continue <ArrowRight size={14} />
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 4 — Services (EXISTING, PRESERVED EXACTLY)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 4 && (
                        <motion.div key="s4" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 24 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 4 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>What services do you offer?</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>Choose all that apply. You can add or remove services from your dashboard anytime.</p>
                            </div>
                            <div style={{ position: 'relative', marginBottom: 14 }}>
                                <Search size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                <input value={catSearchQuery} onChange={e => setCatSearchQuery(e.target.value)} placeholder="Search services…" style={{ ...inputStyle, paddingLeft: 40 }} onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                {catSearchQuery && (
                                    <button onClick={() => setCatSearchQuery('')} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: C.ink3, padding: 4, display: 'flex' }}>
                                        <X size={14} />
                                    </button>
                                )}
                            </div>
                            {selectedCatIds.length > 0 && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '8px 14px', background: C.brassL, border: `1px solid ${C.brassB}`, borderRadius: 20, width: 'fit-content' }}>
                                    <CheckCircle2 size={13} color={C.brass} />
                                    <span style={{ fontSize: 12, fontWeight: 600, color: C.brass }}>{selectedCatIds.length} {selectedCatIds.length === 1 ? 'service' : 'services'} selected</span>
                                </div>
                            )}
                            {licensedSelectedCats.length > 0 && (
                                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                                    style={{ padding: '14px 16px', marginBottom: 14, borderRadius: 12, background: C.amberL, border: `1px solid ${C.amber}40`, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                    <ShieldCheck size={18} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
                                    <div>
                                        <p style={{ fontSize: 13, fontWeight: 700, color: C.amber, margin: '0 0 4px' }}>Licence required for {licensedSelectedCats.length} of your selected trades</p>
                                        <p style={{ fontSize: 12.5, color: C.ink2, margin: 0, lineHeight: 1.55 }}>
                                            You'll enter your licence details in the next step. Our admin team verifies manually — usually within 1 business day.
                                        </p>
                                    </div>
                                </motion.div>
                            )}
                            {catLoading ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '32px 0', justifyContent: 'center', color: C.ink3 }}>
                                    <Loader2 size={16} className="animate-spin" />
                                    <span style={{ fontSize: 13 }}>Loading services…</span>
                                </div>
                            ) : (
                                <>
                                    {selectedCatIds.length > 0 && (
                                        <div style={{ background: C.brassL, border: `1px solid ${C.brassB}`, borderRadius: 12, padding: '14px 16px', marginBottom: 12 }}>
                                            <p style={{ fontSize: 10, fontWeight: 700, color: C.brass, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
                                                Selected ({selectedCatIds.length})
                                            </p>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                                {allCategories.filter(c => selectedCatIds.includes(c.id)).map(cat => (
                                                    <button key={cat.id}
                                                        onClick={() => setSelectedCatIds(prev => prev.filter(id => id !== cat.id))}
                                                        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 20, background: C.card, border: `1px solid ${C.brassB}`, color: C.ink2, fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.12s' }}
                                                        onMouseEnter={e => { e.currentTarget.style.background = '#FFEBEB'; e.currentTarget.style.borderColor = '#F5C0C0'; e.currentTarget.style.color = '#A33030'; }}
                                                        onMouseLeave={e => { e.currentTarget.style.background = C.card; e.currentTarget.style.borderColor = C.brassB; e.currentTarget.style.color = C.ink2; }}>
                                                        {cat.name}<X size={11} strokeWidth={2.5} />
                                                    </button>
                                                ))}
                                            </div>
                                            <p style={{ fontSize: 11, color: C.brass, marginTop: 8 }}>Tap any chip above to remove it</p>
                                        </div>
                                    )}
                                    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
                                        <div style={{ padding: '10px 14px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                            <p style={{ fontSize: 11, fontWeight: 600, color: C.ink3, margin: 0 }}>
                                                {catSearchQuery ? `${filteredCategories.filter(c => !selectedCatIds.includes(c.id)).length} matching` : `${allCategories.filter(c => !selectedCatIds.includes(c.id)).length} available`} — tap to add
                                            </p>
                                            {selectedCatIds.length > 0 && (
                                                <button onClick={() => setSelectedCatIds([])} style={{ fontSize: 11, color: C.rose, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Clear all</button>
                                            )}
                                        </div>
                                        <div style={{ padding: 10, maxHeight: 300, overflowY: 'auto' }}>
                                            <div className="cat-grid-onboard">
                                                {filteredCategories.filter(cat => !selectedCatIds.includes(cat.id)).map(cat => {
                                                    const lic = isLicenceRequired(cat.name);
                                                    return (
                                                        <button key={cat.id}
                                                            onClick={() => setSelectedCatIds(prev => [...prev, cat.id])}
                                                            style={{ padding: '10px 12px', borderRadius: 10, textAlign: 'left', border: `1.5px solid ${C.line}`, background: C.paper, color: C.ink3, fontSize: 12.5, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 8 }}
                                                            onMouseEnter={e => { e.currentTarget.style.borderColor = C.brassB; e.currentTarget.style.background = C.brassL; e.currentTarget.style.color = C.brass; }}
                                                            onMouseLeave={e => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.background = C.paper; e.currentTarget.style.color = C.ink3; }}>
                                                            <Plus size={12} style={{ flexShrink: 0, opacity: 0.5 }} />
                                                            <span style={{ flex: 1, minWidth: 0 }}>{cat.name}</span>
                                                            {lic && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: C.amberL, color: C.amber, letterSpacing: '0.04em', flexShrink: 0 }}>LIC</span>}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                            {filteredCategories.filter(c => !selectedCatIds.includes(c.id)).length === 0 && catSearchQuery && (
                                                <p style={{ fontSize: 13, color: C.ink4, fontStyle: 'italic', textAlign: 'center', padding: '20px 12px', margin: 0 }}>No services match "{catSearchQuery}"</p>
                                            )}
                                        </div>
                                    </div>
                                </>
                            )}
                            <div style={{ marginTop: 18, padding: '18px 20px', background: C.card, border: `1px solid ${C.line}`, borderRadius: 14 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                    <div>
                                        <p style={{ fontSize: 11, fontWeight: 600, color: C.ink2, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 4px' }}>How far will you travel for jobs?</p>
                                        <p style={{ fontSize: 12.5, color: C.ink3, margin: 0, lineHeight: 1.5 }}>We'll match jobs within this radius of your home suburb.</p>
                                    </div>
                                    <div style={{ padding: '6px 14px', borderRadius: 20, background: C.brassL, color: C.brass, fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, minWidth: 64, textAlign: 'center', flexShrink: 0 }}>
                                        {radiusKm}<span style={{ fontSize: 12, fontFamily: UI, marginLeft: 2, opacity: 0.7 }}>km</span>
                                    </div>
                                </div>
                                <input type="range" min={5} max={50} step={5} value={radiusKm} onChange={e => setRadiusKm(parseInt(e.target.value, 10))}
                                    style={{ width: '100%', height: 6, borderRadius: 3, appearance: 'none', WebkitAppearance: 'none', background: `linear-gradient(to right, ${C.brass} 0%, ${C.brass} ${((radiusKm - 5) / 45) * 100}%, ${C.line} ${((radiusKm - 5) / 45) * 100}%, ${C.line} 100%)`, outline: 'none', cursor: 'pointer' }} />
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 10.5, color: C.ink4, fontWeight: 500 }}>
                                    <span>5 km</span><span>25 km</span><span>50 km</span>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 12, marginTop: 18 }}>
                                <button onClick={() => setStep(3)} style={{ padding: '15px 22px', borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <ArrowLeft size={14} /> Back
                                </button>
                                <button onClick={handleStep4Continue} disabled={!step4Valid}
                                    style={{ flex: 1, padding: '15px 22px', borderRadius: 12, border: 'none', background: step4Valid ? C.ink : C.ink3, color: C.card, fontSize: 14, fontWeight: 600, cursor: step4Valid ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                    Continue <ArrowRight size={14} />
                                </button>
                            </div>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 5 — Licences (NEW)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 5 && (
                        <motion.div key="s5" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 24 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 5 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>Trade licence details</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>
                                    {certEntries.length === 0
                                        ? "None of your selected services require a trade licence — continue to the next step."
                                        : "Enter your licence number for each trade. Our admin team verifies directly with the state registry — no document upload needed."}
                                </p>
                            </div>

                            {certEntries.length === 0 ? (
                                <div style={{ padding: '28px 24px', background: C.sageL, border: `1px solid ${C.sage}40`, borderRadius: 16, textAlign: 'center', marginBottom: 24 }}>
                                    <CheckCircle2 size={32} color={C.sage} style={{ marginBottom: 12 }} />
                                    <p style={{ fontFamily: DISPLAY, fontSize: 20, color: C.ink, margin: '0 0 8px', fontWeight: 500 }}>No licences required</p>
                                    <p style={{ fontSize: 13.5, color: C.ink2, margin: 0, lineHeight: 1.6 }}>The services you selected don't require a trade licence. Continue to add your insurance details.</p>
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 8 }}>
                                    {certEntries.map((entry, idx) => (
                                        <motion.div key={entry.category_id}
                                            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: idx * 0.06, duration: 0.24 }}
                                            style={{
                                                background: entry.skip ? C.panel : C.card,
                                                border: `1.5px solid ${entry.skip ? C.line : C.brassB}`,
                                                borderRadius: 16, overflow: 'hidden',
                                                transition: 'all 0.2s',
                                            }}>
                                            {/* Card header */}
                                            <div style={{ padding: '16px 20px', borderBottom: `1px solid ${entry.skip ? C.lineSoft : C.brassB}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: entry.skip ? 'transparent' : C.brassL }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                    <Award size={16} color={entry.skip ? C.ink4 : C.brass} />
                                                    <span style={{ fontSize: 14, fontWeight: 700, color: entry.skip ? C.ink4 : C.ink }}>{entry.category_name}</span>
                                                </div>
                                                <button onClick={() => updateCert(idx, 'skip', !entry.skip)}
                                                    style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 20, border: `1px solid ${entry.skip ? C.sage : C.line}`, background: entry.skip ? C.sageL : 'transparent', color: entry.skip ? C.sage : C.ink3, fontSize: 11.5, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s' }}>
                                                    {entry.skip ? <><CheckCircle2 size={11} /> Added later</> : <><SkipForward size={11} /> Add later</>}
                                                </button>
                                            </div>

                                            <AnimatePresence>
                                                {!entry.skip && (
                                                    <motion.div key="cert-form" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }} style={{ overflow: 'hidden' }}>
                                                        <div style={{ padding: '20px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                                                            {/* State registry info */}
                                                            <div style={{ padding: '10px 14px', background: C.amberL, borderRadius: 10, display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                                                                <Info size={13} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
                                                                <p style={{ fontSize: 12, color: C.ink2, margin: 0, lineHeight: 1.55 }}>
                                                                    Our team verifies this against{' '}
                                                                    <strong>{STATE_REGISTRY_NAMES[entry.issuing_state] || 'the state registry'}</strong>.
                                                                    {!entry.issuing_state && ' Select your issuing state first.'}
                                                                </p>
                                                            </div>

                                                            {/* Issuing state */}
                                                            <div>
                                                                <label style={labelStyle}>Issuing state / territory</label>
                                                                <div style={{ position: 'relative' }}>
                                                                    <select value={entry.issuing_state}
                                                                        onChange={e => updateCert(idx, 'issuing_state', e.target.value)}
                                                                        style={{ ...inputStyle, paddingRight: 36, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
                                                                        onFocus={inputFocusOn} onBlur={inputFocusOff}>
                                                                        <option value="">Select state…</option>
                                                                        {AU_STATES.map(s => <option key={s} value={s}>{s} — {STATE_REGISTRY_NAMES[s]}</option>)}
                                                                    </select>
                                                                    <ChevronDown size={14} style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                                                </div>
                                                            </div>

                                                            {/* Licence number */}
                                                            <div>
                                                                <label style={labelStyle}>Licence number</label>
                                                                <input value={entry.licence_number}
                                                                    onChange={e => updateCert(idx, 'licence_number', e.target.value.toUpperCase())}
                                                                    placeholder="e.g. VL12345 or PLB98765"
                                                                    style={{ ...inputStyle, fontFamily: 'monospace', letterSpacing: '0.08em', fontSize: 15 }}
                                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                                <p style={{ fontSize: 11.5, color: C.ink4, margin: '5px 0 0' }}>Enter the number exactly as it appears on your licence card.</p>
                                                            </div>

                                                            {/* Holder name */}
                                                            <div>
                                                                <label style={labelStyle}>Name on licence</label>
                                                                <input value={entry.holder_name}
                                                                    onChange={e => updateCert(idx, 'holder_name', e.target.value)}
                                                                    placeholder="Exactly as printed on the licence"
                                                                    style={inputStyle}
                                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                            </div>

                                                            {/* Dates row */}
                                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                                                <div>
                                                                    <label style={labelStyle}>Issue date <span style={{ color: C.ink4, textTransform: 'none', letterSpacing: 0 }}>(optional)</span></label>
                                                                    <div style={{ position: 'relative' }}>
                                                                        <Calendar size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                                                        <input type="date" value={entry.issued_at}
                                                                            onChange={e => updateCert(idx, 'issued_at', e.target.value)}
                                                                            style={{ ...inputStyle, paddingLeft: 36, fontSize: 13 }}
                                                                            onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                                    </div>
                                                                </div>
                                                                <div>
                                                                    <label style={labelStyle}>Expiry date <span style={{ color: C.ink4, textTransform: 'none', letterSpacing: 0 }}>(optional)</span></label>
                                                                    <div style={{ position: 'relative' }}>
                                                                        <Calendar size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                                                        <input type="date" value={entry.expires_at}
                                                                            onChange={e => updateCert(idx, 'expires_at', e.target.value)}
                                                                            style={{ ...inputStyle, paddingLeft: 36, fontSize: 13 }}
                                                                            onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {/* Optional photo URL */}
                                                            <div>
                                                                <label style={labelStyle}>
                                                                    Licence card photo URL <span style={{ color: C.ink4, textTransform: 'none', letterSpacing: 0 }}>(optional — speeds up verification)</span>
                                                                </label>
                                                                <input value={entry.photo_url}
                                                                    onChange={e => updateCert(idx, 'photo_url', e.target.value)}
                                                                    placeholder="Paste S3/cloud URL after uploading via your dashboard…"
                                                                    style={{ ...inputStyle, fontSize: 13 }}
                                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                                <p style={{ fontSize: 11.5, color: C.ink4, margin: '5px 0 0' }}>Upload a clear photo of your licence card from your dashboard and paste the URL here. Helps admin verify faster.</p>
                                                            </div>
                                                        </div>
                                                    </motion.div>
                                                )}
                                            </AnimatePresence>

                                            {entry.skip && (
                                                <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
                                                    <Info size={13} color={C.ink4} style={{ flexShrink: 0 }} />
                                                    <p style={{ fontSize: 12.5, color: C.ink4, margin: 0, lineHeight: 1.5 }}>
                                                        You can add this licence from <strong>Dashboard → Licences & Certifications</strong>. You won't receive leads in this category until a licence is verified.
                                                    </p>
                                                </div>
                                            )}
                                        </motion.div>
                                    ))}
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                                <button onClick={() => setStep(4)} style={{ padding: '15px 22px', borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <ArrowLeft size={14} /> Back
                                </button>
                                <button onClick={() => setStep(6)} disabled={!step5Valid}
                                    style={{ flex: 1, padding: '15px 22px', borderRadius: 12, border: 'none', background: step5Valid ? C.ink : C.ink3, color: C.card, fontSize: 14, fontWeight: 600, cursor: step5Valid ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                    Continue <ArrowRight size={14} />
                                </button>
                            </div>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 6 — Insurance (NEW)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 6 && (
                        <motion.div key="s6" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 24 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 6 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>Public liability insurance</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>
                                    Required before you can receive paid job leads. Australian law requires most trades to carry public liability insurance.
                                </p>
                            </div>

                            {/* Why this matters */}
                            <div style={{ padding: '14px 18px', background: C.amberL, border: `1px solid ${C.amber}40`, borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                <Shield size={18} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
                                <div>
                                    <p style={{ fontSize: 13, fontWeight: 700, color: C.amber, margin: '0 0 4px' }}>Why we require this</p>
                                    <p style={{ fontSize: 12.5, color: C.ink2, margin: 0, lineHeight: 1.55 }}>
                                        If something goes wrong on site, your public liability insurance protects both you and the homeowner.
                                        A $20M policy is standard for most Australian trades. Our admin verifies the policy with your insurer.
                                    </p>
                                </div>
                            </div>

                            {/* Skip toggle */}
                            <button onClick={() => setInsurance(p => ({ ...p, skip: !p.skip }))}
                                style={{ width: '100%', padding: '14px 18px', borderRadius: 12, border: `1.5px solid ${insurance.skip ? C.sage : C.line}`, background: insurance.skip ? C.sageL : C.paper, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', marginBottom: 16, transition: 'all 0.2s' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <SkipForward size={15} color={insurance.skip ? C.sage : C.ink3} />
                                    <div style={{ textAlign: 'left' }}>
                                        <p style={{ fontSize: 13.5, fontWeight: 600, color: insurance.skip ? C.sage : C.ink2, margin: 0 }}>I'll add insurance from my dashboard</p>
                                        <p style={{ fontSize: 12, color: C.ink4, margin: '2px 0 0' }}>You won't receive paid job leads until this is verified.</p>
                                    </div>
                                </div>
                                <div style={{ width: 20, height: 20, borderRadius: '50%', border: `2px solid ${insurance.skip ? C.sage : C.line}`, background: insurance.skip ? C.sage : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.15s' }}>
                                    {insurance.skip && <Check size={12} color={C.card} strokeWidth={3} />}
                                </div>
                            </button>

                            <AnimatePresence>
                                {!insurance.skip && (
                                    <motion.div key="ins-form" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.24 }} style={{ overflow: 'hidden' }}>
                                        <div style={{ background: C.card, border: `1.5px solid ${C.brassB}`, borderRadius: 16, padding: '22px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>

                                            {/* Insurer name */}
                                            <div>
                                                <label style={labelStyle}>Insurer name</label>
                                                <input value={insurance.insurer_name}
                                                    onChange={e => setInsurance(p => ({ ...p, insurer_name: e.target.value }))}
                                                    placeholder="e.g. QBE, Allianz, CGU, IAG, Vero"
                                                    style={inputStyle}
                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                            </div>

                                            {/* Policy number */}
                                            <div>
                                                <label style={labelStyle}>Policy number</label>
                                                <input value={insurance.policy_number}
                                                    onChange={e => setInsurance(p => ({ ...p, policy_number: e.target.value.toUpperCase() }))}
                                                    placeholder="e.g. PLB-2024-123456"
                                                    style={{ ...inputStyle, fontFamily: 'monospace', letterSpacing: '0.05em' }}
                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                            </div>

                                            {/* Coverage amount */}
                                            <div>
                                                <label style={labelStyle}>Coverage amount (AUD)</label>
                                                <div style={{ position: 'relative' }}>
                                                    <span style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: C.ink3, fontSize: 15, fontWeight: 600, pointerEvents: 'none' }}>$</span>
                                                    <input value={insurance.coverage_amount_raw}
                                                        onChange={e => setInsurance(p => ({ ...p, coverage_amount_raw: e.target.value.replace(/[^0-9.]/g, '') }))}
                                                        placeholder="20,000,000"
                                                        style={{ ...inputStyle, paddingLeft: 28, fontVariantNumeric: 'tabular-nums' }}
                                                        inputMode="numeric"
                                                        onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                </div>
                                                <p style={{ fontSize: 11.5, color: C.ink4, margin: '5px 0 0' }}>$20,000,000 ($20M) is standard for most Australian trades. Enter the number without commas.</p>
                                            </div>

                                            {/* Policy holder name */}
                                            <div>
                                                <label style={labelStyle}>Policy holder name</label>
                                                <input value={insurance.holder_name}
                                                    onChange={e => setInsurance(p => ({ ...p, holder_name: e.target.value }))}
                                                    placeholder="Name as on the policy certificate"
                                                    style={inputStyle}
                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                <p style={{ fontSize: 11.5, color: C.ink4, margin: '5px 0 0' }}>Usually your business name or your personal name for sole traders.</p>
                                            </div>

                                            {/* Expiry date */}
                                            <div>
                                                <label style={labelStyle}>Policy expiry date</label>
                                                <div style={{ position: 'relative' }}>
                                                    <Calendar size={13} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                                    <input type="date" value={insurance.expires_at}
                                                        onChange={e => setInsurance(p => ({ ...p, expires_at: e.target.value }))}
                                                        style={{ ...inputStyle, paddingLeft: 40 }}
                                                        onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                </div>
                                            </div>

                                            {/* Optional document URL */}
                                            <div>
                                                <label style={labelStyle}>Certificate of currency URL <span style={{ color: C.ink4, textTransform: 'none', letterSpacing: 0 }}>(optional — speeds up verification)</span></label>
                                                <input value={insurance.document_url}
                                                    onChange={e => setInsurance(p => ({ ...p, document_url: e.target.value }))}
                                                    placeholder="Paste S3/cloud URL after uploading your certificate…"
                                                    style={{ ...inputStyle, fontSize: 13 }}
                                                    onFocus={inputFocusOn} onBlur={inputFocusOff} />
                                                <p style={{ fontSize: 11.5, color: C.ink4, margin: '5px 0 0' }}>Upload your certificate of currency from your dashboard and paste the URL here. Our team can verify much faster with this.</p>
                                            </div>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                                <button onClick={handleStep6Back} style={{ padding: '15px 22px', borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 14, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <ArrowLeft size={14} /> Back
                                </button>
                                <button onClick={() => setStep(7)} disabled={!step6Valid}
                                    style={{ flex: 1, padding: '15px 22px', borderRadius: 12, border: 'none', background: step6Valid ? C.ink : C.ink3, color: C.card, fontSize: 14, fontWeight: 600, cursor: step6Valid ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                    Review & submit <ArrowRight size={14} />
                                </button>
                            </div>
                        </motion.div>
                    )}

                    {/* ═══════════════════════════════════════════════════════════
                        STEP 7 — Review & Submit (was step 5, UPDATED SUMMARY)
                    ═══════════════════════════════════════════════════════════ */}
                    {step === 7 && (
                        <motion.div key="s7" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
                            <div style={{ marginBottom: 28 }}>
                                <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Step 7 of 7</p>
                                <h1 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.025em', lineHeight: 1.15 }}>Almost done — quick review</h1>
                                <p style={{ fontSize: 14.5, color: C.ink2, margin: 0, lineHeight: 1.6, maxWidth: 480 }}>Take a look at your details, then submit for our team to verify.</p>
                            </div>

                            <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, boxShadow: SHADOW_SM, overflow: 'hidden', marginBottom: 18 }}>
                                {/* Account */}
                                <div style={{ padding: '18px 22px', borderBottom: `1px solid ${C.lineSoft}` }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                        <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Account</p>
                                        <button onClick={() => setStep(1)} style={{ fontSize: 11, color: C.brass, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Edit</button>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px 14px', fontSize: 13 }}>
                                        <span style={{ color: C.ink3 }}>Name</span><span style={{ color: C.ink, fontWeight: 500 }}>{fullName}</span>
                                        <span style={{ color: C.ink3 }}>Email</span><span style={{ color: C.ink, fontWeight: 500 }}>{email} <CheckCircle2 size={12} color={C.sage} style={{ display: 'inline', marginLeft: 4, verticalAlign: '-2px' }} /></span>
                                        <span style={{ color: C.ink3 }}>Phone</span><span style={{ color: C.ink, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{phone}</span>
                                        <span style={{ color: C.ink3 }}>Location</span><span style={{ color: C.ink, fontWeight: 500 }}>{selectedSuburb?.label}</span>
                                    </div>
                                </div>

                                {/* Business */}
                                <div style={{ padding: '18px 22px', borderBottom: `1px solid ${C.lineSoft}` }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                        <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Business</p>
                                        <button onClick={() => setStep(3)} style={{ fontSize: 11, color: C.brass, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Edit</button>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px 14px', fontSize: 13 }}>
                                        <span style={{ color: C.ink3 }}>Business</span><span style={{ color: C.ink, fontWeight: 500 }}>{businessName}</span>
                                        <span style={{ color: C.ink3 }}>ABN</span><span style={{ color: C.ink, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{abn}</span>
                                        <span style={{ color: C.ink3 }}>Structure</span><span style={{ color: C.ink, fontWeight: 500 }}>{soloOrTeam === 'solo' ? 'Sole trader' : `Team — ${teamSize} people`}</span>
                                    </div>
                                </div>

                                {/* Services */}
                                <div style={{ padding: '18px 22px', borderBottom: certEntries.length > 0 || !insurance.skip ? `1px solid ${C.lineSoft}` : 'none' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                        <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Services ({selectedCatIds.length})</p>
                                        <button onClick={() => setStep(4)} style={{ fontSize: 11, color: C.brass, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Edit</button>
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                        {selectedCatNames.slice(0, 12).map(name => (
                                            <span key={name} style={{ fontSize: 11.5, padding: '4px 10px', borderRadius: 12, background: C.paper, border: `1px solid ${C.line}`, color: C.ink2, fontWeight: 500 }}>{name}</span>
                                        ))}
                                        {selectedCatNames.length > 12 && <span style={{ fontSize: 11.5, padding: '4px 10px', color: C.ink4 }}>+{selectedCatNames.length - 12} more</span>}
                                    </div>
                                </div>

                                {/* Licences summary */}
                                {certEntries.length > 0 && (
                                    <div style={{ padding: '18px 22px', borderBottom: !insurance.skip ? `1px solid ${C.lineSoft}` : 'none' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                            <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Licences</p>
                                            <button onClick={() => setStep(5)} style={{ fontSize: 11, color: C.brass, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Edit</button>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                            {certEntries.map(e => (
                                                <div key={e.category_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13 }}>
                                                    <span style={{ color: C.ink2, fontWeight: 500 }}>{e.category_name}</span>
                                                    {e.skip
                                                        ? <span style={{ fontSize: 11, color: C.ink4, background: C.panel, padding: '2px 8px', borderRadius: 10 }}>Add later</span>
                                                        : <span style={{ fontSize: 11, color: C.sage, background: C.sageL, padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
                                                            {e.licence_number} · {e.issuing_state}
                                                        </span>
                                                    }
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Insurance summary */}
                                {!insurance.skip && (
                                    <div style={{ padding: '18px 22px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                            <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Insurance</p>
                                            <button onClick={() => setStep(6)} style={{ fontSize: 11, color: C.brass, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Edit</button>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px 14px', fontSize: 13 }}>
                                            <span style={{ color: C.ink3 }}>Insurer</span><span style={{ color: C.ink, fontWeight: 500 }}>{insurance.insurer_name}</span>
                                            <span style={{ color: C.ink3 }}>Policy #</span><span style={{ color: C.ink, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{insurance.policy_number}</span>
                                            <span style={{ color: C.ink3 }}>Coverage</span><span style={{ color: C.ink, fontWeight: 500 }}>${parseFloat(insurance.coverage_amount_raw || '0').toLocaleString('en-AU')}</span>
                                            <span style={{ color: C.ink3 }}>Expires</span><span style={{ color: C.ink, fontWeight: 500 }}>{insurance.expires_at}</span>
                                        </div>
                                    </div>
                                )}
                                {insurance.skip && certEntries.length === 0 && (
                                    <div style={{ padding: '18px 22px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: C.amberL, borderRadius: 10 }}>
                                            <AlertCircle size={14} color={C.amber} />
                                            <p style={{ fontSize: 12.5, color: C.ink2, margin: 0, lineHeight: 1.55 }}>
                                                Insurance skipped — add from <strong>Dashboard → Insurance</strong> before you can receive paid leads.
                                            </p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* What happens next */}
                            <div style={{ padding: '18px 20px', marginBottom: 18, borderRadius: 14, background: C.brassL, border: `1px solid ${C.brassB}` }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                                    <Sparkles size={15} color={C.brass} />
                                    <p style={{ fontFamily: DISPLAY, fontSize: 16, fontWeight: 500, color: C.ink, margin: 0, letterSpacing: '-0.01em' }}>What happens next</p>
                                </div>
                                <ol style={{ margin: 0, padding: '0 0 0 20px', fontSize: 13, color: C.ink2, lineHeight: 1.75 }}>
                                    <li>Our team reviews your profile — usually within 1 business day.</li>
                                    <li>Any submitted licences are verified against the relevant state registry.</li>
                                    <li>Any submitted insurance policy is confirmed with your insurer.</li>
                                    <li>Once all three are approved, you'll start receiving matched job leads automatically.</li>
                                </ol>
                            </div>

                            {/* Submit phase indicator */}
                            {submitPhase !== 'idle' && submitPhase !== 'done' && (
                                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                                    style={{ padding: '12px 18px', marginBottom: 14, background: C.panel, border: `1px solid ${C.line}`, borderRadius: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <Loader2 size={14} className="animate-spin" color={C.brass} />
                                    <span style={{ fontSize: 13, color: C.ink2, fontWeight: 500 }}>{submitPhaseLabel}</span>
                                </motion.div>
                            )}

                            <div style={{ display: 'flex', gap: 12 }}>
                                <button onClick={() => setStep(6)} disabled={submitting} style={{ padding: '15px 22px', borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 14, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <ArrowLeft size={14} /> Back
                                </button>
                                <button onClick={handleFinalSubmit} disabled={submitting}
                                    style={{ flex: 1, padding: '15px 22px', borderRadius: 12, border: 'none', background: submitting ? C.ink3 : C.ink, color: C.card, fontSize: 14, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.15s' }}>
                                    {submitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} strokeWidth={3} />}
                                    {submitting ? (submitPhaseLabel || 'Submitting…') : 'Submit for review'}
                                </button>
                            </div>
                        </motion.div>
                    )}

                </AnimatePresence>
            </main>

            <style>{`
        * { box-sizing: border-box; }
        body { margin: 0; }
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600&family=Inter:wght@400;500;600;700&display=swap');
        .cat-grid-onboard { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 6px; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
        ::selection { background: ${C.brass}; color: ${C.card}; }
        select option { font-size: 14px; }
        input[type="date"]::-webkit-calendar-picker-indicator { opacity: 0.5; cursor: pointer; }
        @media (max-width: 640px) {
          .step-label { display: none; }
          .cat-grid-onboard { grid-template-columns: 1fr; }
          .onboarding-root header { padding: 16px 18px !important; }
        }
        @media (max-width: 480px) {
          input[type="text"], input[type="email"], input[type="tel"], input[type="password"] { font-size: 16px !important; }
        }
        input[type="range"] { -webkit-appearance: none; }
        input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; background: ${C.ink}; border: 3px solid ${C.card}; border-radius: 50%; cursor: pointer; }
      `}</style>
        </div>
    );
}
