"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Paperclip, X, Sparkles, Loader2, Bot, User } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { toast } from "sonner";
import api from "@/src/lib/api";
import { useAuth } from "@/src/contexts/AuthContext";
import MessageRenderer, { UIComponent } from "@/src/components/tradie/ai/MessageRenderer";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    ui_component?: UIComponent | null;
    image_preview?: string;
    timestamp: Date;
}

const QUICK_ACTIONS_HOMEOWNER = [
    "Find me a plumber nearby",
    "I need an electrician urgently",
    "Show my active jobs",
    "Check my home appliances",
];

const QUICK_ACTIONS_TRADIE = [
    "Show my latest leads",
    "Check my TradiePASS score",
    "Generate a SWMS document",
    "Show my earnings summary",
];

export default function AIChatInterface() {
    const { user } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId] = useState(() => `session-${Date.now()}`);
    const [imageBase64, setImageBase64] = useState<string | null>(null);
    const [imageMime, setImageMime] = useState("image/jpeg");
    const [imagePreview, setImagePreview] = useState<string | null>(null);

    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const fileRef = useRef<HTMLInputElement>(null);

    const quickActions =
        user?.role === "tradie" ? QUICK_ACTIONS_TRADIE : QUICK_ACTIONS_HOMEOWNER;

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isLoading]);

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = "auto";
            inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
        }
    }, [input]);

    const handleImageUpload = useCallback((file: File) => {
        if (file.size > 7_000_000) {
            toast.error("Image too large. Please use a photo under 7MB.");
            return;
        }

        setImageMime(file.type || "image/jpeg");

        // Generate preview URL
        const previewUrl = URL.createObjectURL(file);
        setImagePreview(previewUrl);

        // Convert to base64 (strip data URI prefix)
        const reader = new FileReader();
        reader.onload = (e) => {
            const result = e.target?.result as string;
            const base64 = result.split(",")[1];
            setImageBase64(base64);
        };
        reader.readAsDataURL(file);
    }, []);

    const clearImage = useCallback(() => {
        setImageBase64(null);
        setImagePreview(null);
        if (fileRef.current) fileRef.current.value = "";
    }, []);

    const sendMessage = useCallback(
        async (text?: string) => {
            const messageText = (text || input).trim();
            if (!messageText && !imageBase64) return;
            if (isLoading) return;

            const userMessage: Message = {
                id: `msg-${Date.now()}`,
                role: "user",
                content: messageText || "Photo uploaded",
                image_preview: imagePreview || undefined,
                timestamp: new Date(),
            };

            setMessages((prev) => [...prev, userMessage]);
            setInput("");
            setIsLoading(true);

            const sentImageBase64 = imageBase64;
            const sentImageMime = imageMime;
            clearImage();

            try {
                const response = await api.post("/ai/chat", {
                    message: messageText || "Please analyse this photo",
                    session_id: sessionId,
                    image_base64: sentImageBase64 || null,
                    image_mime: sentImageMime,
                });

                const data = response.data;

                const assistantMessage: Message = {
                    id: `msg-${Date.now()}-ai`,
                    role: "assistant",
                    content: data.response || "",
                    ui_component: data.ui_component || null,
                    timestamp: new Date(),
                };

                setMessages((prev) => [...prev, assistantMessage]);
            } catch (error: any) {
                const errMsg =
                    error?.response?.status === 401
                        ? "Please log in to use the AI assistant."
                        : "Something went wrong. Please try again.";

                toast.error(errMsg);

                setMessages((prev) => [
                    ...prev,
                    {
                        id: `msg-${Date.now()}-err`,
                        role: "assistant",
                        content: errMsg,
                        timestamp: new Date(),
                    },
                ]);
            } finally {
                setIsLoading(false);
                inputRef.current?.focus();
            }
        },
        [input, imageBase64, imageMime, imagePreview, isLoading, sessionId, clearImage]
    );

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const resetChat = () => {
        setMessages([]);
        clearImage();
        setInput("");
    };

    const isEmpty = messages.length === 0;

    return (
        <div className="flex-1 flex flex-col w-full bg-brand-ivory">

            {/* ── Empty state / welcome ─────────────────────────────────────────── */}
            <AnimatePresence>
                {isEmpty && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex-1 flex flex-col items-center justify-center px-6 pb-8"
                    >
                        <div className="w-16 h-16 rounded-2xl bg-brand-terracotta flex items-center justify-center shadow-lg shadow-brand-terracotta/20 mb-6">
                            <Sparkles className="w-8 h-8 text-white fill-current" />
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900 mb-2 text-center">
                            Hi {user?.name?.split(" ")[0] || "there"}
                        </h2>
                        <p className="text-gray-500 text-center max-w-sm mb-8 leading-relaxed">
                            {user?.role === "tradie"
                                ? "I can help you find leads, check compliance, generate SWMS docs, and track your earnings."
                                : "Tell me what needs fixing  -  I'll find the right tradie for you. You can also upload a photo of the problem."}
                        </p>

                        {/* Quick action chips */}
                        <div className="flex flex-wrap gap-2 justify-center max-w-md">
                            {quickActions.map((action) => (
                                <button
                                    key={action}
                                    onClick={() => sendMessage(action)}
                                    className="text-sm bg-white text-gray-700 border border-gray-200 px-4 py-2 rounded-xl hover:border-brand-terracotta/30 hover:text-brand-terracotta hover:bg-brand-terracotta/5 transition-all duration-200 font-medium"
                                >
                                    {action}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Message thread ────────────────────────────────────────────────── */}
            {!isEmpty && (
                <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2 }}
                            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                        >
                            {/* Avatar */}
                            <div
                                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${msg.role === "user"
                                        ? "bg-brand-terracotta"
                                        : "bg-white border border-gray-100 shadow-sm"
                                    }`}
                            >
                                {msg.role === "user" ? (
                                    <User className="w-4 h-4 text-white" />
                                ) : (
                                    <Sparkles className="w-4 h-4 text-brand-terracotta" />
                                )}
                            </div>

                            {/* Bubble + component */}
                            <div className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
                                {/* Image preview (user uploads) */}
                                {msg.image_preview && (
                                    <img
                                        src={msg.image_preview}
                                        alt="Uploaded"
                                        className="w-40 h-32 object-cover rounded-xl mb-2 border border-gray-100"
                                    />
                                )}

                                {/* Text bubble */}
                                {msg.content && (
                                    <div
                                        className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.role === "user"
                                                ? "bg-brand-terracotta text-white rounded-tr-sm"
                                                : "bg-white text-gray-800 border border-gray-100 shadow-sm rounded-tl-sm"
                                            }`}
                                    >
                                        {msg.content}
                                    </div>
                                )}

                                {/* Generative UI component */}
                                {msg.ui_component && (
                                    <div className="w-full max-w-sm">
                                        <MessageRenderer component={msg.ui_component} />
                                    </div>
                                )}

                                <span className="text-xs text-gray-400 mt-1 px-1">
                                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                </span>
                            </div>
                        </motion.div>
                    ))}

                    {/* Typing indicator */}
                    {isLoading && (
                        <motion.div
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex gap-3"
                        >
                            <div className="w-8 h-8 rounded-xl bg-white border border-gray-100 shadow-sm flex items-center justify-center">
                                <Sparkles className="w-4 h-4 text-brand-terracotta" />
                            </div>
                            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-full bg-brand-terracotta/40 animate-bounce [animation-delay:0ms]" />
                                <div className="w-2 h-2 rounded-full bg-brand-terracotta/40 animate-bounce [animation-delay:150ms]" />
                                <div className="w-2 h-2 rounded-full bg-brand-terracotta/40 animate-bounce [animation-delay:300ms]" />
                            </div>
                        </motion.div>
                    )}

                    <div ref={bottomRef} />
                </div>
            )}

            {/* ── Input area ────────────────────────────────────────────────────── */}
            <div className="border-t border-gray-100 bg-white px-4 py-3">

                {/* Image preview strip */}
                {imagePreview && (
                    <div className="mb-3 flex items-center gap-2">
                        <div className="relative">
                            <img
                                src={imagePreview}
                                alt="Preview"
                                className="w-12 h-12 object-cover rounded-xl border border-gray-100"
                            />
                            <button
                                onClick={clearImage}
                                className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                        <p className="text-xs text-gray-500">Photo ready  -  add a message or send now</p>
                    </div>
                )}

                <div className="flex items-end gap-2">
                    {/* Photo upload button */}
                    <button
                        onClick={() => fileRef.current?.click()}
                        className="w-10 h-10 rounded-xl bg-brand-ivory flex items-center justify-center text-gray-400 hover:text-brand-terracotta hover:bg-brand-terracotta/5 transition-all duration-200 shrink-0"
                        title="Upload a photo"
                    >
                        <Paperclip className="w-5 h-5" />
                    </button>
                    <input
                        ref={fileRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleImageUpload(file);
                        }}
                    />

                    {/* Text input */}
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={
                            user?.role === "tradie"
                                ? "Ask about leads, compliance, earnings..."
                                : "Tell me what needs fixing, or upload a photo..."
                        }
                        rows={1}
                        className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:border-brand-terracotta/40 focus:ring-2 focus:ring-brand-terracotta/10 transition-all bg-brand-ivory placeholder:text-gray-400"
                    />

                    {/* Send / reset */}

                    <button
                        onClick={() => sendMessage()}
                        disabled={isLoading || (!input.trim() && !imageBase64)}
                        className="w-10 h-10 rounded-xl bg-brand-terracotta flex items-center justify-center text-white disabled:opacity-40 hover:shadow-lg hover:shadow-brand-terracotta/20 hover:-translate-y-0.5 transition-all duration-200 shrink-0"
                    >
                        {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Send className="w-4 h-4" />
                        )}
                    </button>
                </div>

                <p className="text-xs text-center text-gray-400 mt-2">
                    ProConnect AI  |  powered by Groq
                </p>
            </div>
        </div>
    );
}
