"use client";

import { useState, useEffect, useRef } from "react";
import { UserCircle, Paperclip, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useChatStore } from "@/store/chatStore";

import Sidebar from "./sidebar";
import BubbleChat from "./BubbleChat";

// Helper untuk mengambil token JWT dari Cookies browser
const getToken = () => {
  if (typeof document !== "undefined") {
    const match = document.cookie.match(new RegExp("(^| )token=([^;]+)"));
    if (match) return match[2];
  }
  return null;
};

export default function ChatPage() {
  const router = useRouter();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [inputText, setInputText] = useState("");

  // State berupa Array of Files untuk multi-gambar
  const [selectedImages, setSelectedImages] = useState<File[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    rooms,
    activeRoomId,
    setActiveRoom,
    createNewRoom,
    addMessage,
    setRooms,
    setMessages,
  } = useChatStore();
  const activeRoom = rooms.find((r) => r.id === activeRoomId);

  // ==========================================
  // EFFECT 1: Tarik Daftar Room
  // ==========================================
  useEffect(() => {
    const fetchRooms = async () => {
      const token = getToken();
      if (!token) {
        router.push("/login");
        return;
      }

      try {
        const res = await fetch("http://127.0.0.1:8000/room", {
          headers: { Authorization: `Bearer ${token}` },
        });
        const result = await res.json();

        if (result.status === "success") {
          const formattedRooms = result.data.map((room: any) => ({
            id: room.id,
            title: room.title,
            messages: [],
          }));
          setRooms(formattedRooms.reverse());
        }
      } catch (error) {
        console.error("Gagal menarik daftar room:", error);
      }
    };
    fetchRooms();
  }, [router, setRooms]);

  // ==========================================
  // EFFECT 2: Tarik History Chat
  // ==========================================
  useEffect(() => {
    const fetchChatHistory = async () => {
      if (!activeRoomId) return;
      const currentRoom = rooms.find((r) => r.id === activeRoomId);
      if (currentRoom && currentRoom.messages.length > 0) return;

      const token = getToken();
      if (!token) return;

      try {
        const res = await fetch(`http://127.0.0.1:8000/chat/${activeRoomId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const result = await res.json();

        if (result.status === "success") {
          const historyMessages = result.data.map((msg: any) => ({
            id: msg.id,
            text: msg.content,
            sender: msg.role === "assistant" ? "ai" : "user",
            imageUrls: msg.image_urls || null, // Ambil array gambar dari DB
          }));
          setMessages(activeRoomId, historyMessages);
        }
      } catch (error) {
        console.error("Gagal menarik history chat:", error);
      }
    };
    fetchChatHistory();
  }, [activeRoomId, rooms, setMessages]);

  // ==========================================
  // FUNGSI HANDLE GAMBAR (BARU & AMAN)
  // ==========================================
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      // Ubah dari FileList ke Array murni
      const newFilesArray = Array.from(files);
      // Tambahkan ke state gambar yang sudah ada sebelumnya
      setSelectedImages((prev) => [...prev, ...newFilesArray]);
    }
    // Kosongkan value input text agar bisa pilih gambar yang sama lagi jika perlu
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveImage = (indexToRemove: number) => {
    setSelectedImages((prev) => prev.filter((_, i) => i !== indexToRemove));
  };

  // ==========================================
  // EKSEKUTOR PENGIRIMAN PESAN
  // ==========================================
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() && selectedImages.length === 0) return;

    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    setIsLoading(true);
    let currentRoomId = activeRoomId;

    try {
      // 1. Buat Room jika kosong
      if (!currentRoomId) {
        const titleText = inputText.trim()
          ? inputText.split(" ").slice(0, 5).join(" ") + "..."
          : "Gambar Baru...";

        const roomRes = await fetch("http://127.0.0.1:8000/room", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ title: titleText }),
        });

        const roomData = await roomRes.json();
        if (roomData.status !== "success") throw new Error("Gagal buat room");
        currentRoomId = roomData.data.room_id;

        createNewRoom(titleText, currentRoomId as string);
        setActiveRoom(currentRoomId as string);
      }

      const finalRoomId = currentRoomId as string;
      const textToSend = inputText || "Tolong analisa gambar ini.";

      // 2. Optimistic UI: Render semua gambar ke layar
      const previewUrls =
        selectedImages.length > 0
          ? selectedImages.map((file) => URL.createObjectURL(file))
          : null;

      addMessage(finalRoomId, textToSend, "user", previewUrls);

      // Kosongkan form secepatnya
      setInputText("");
      setSelectedImages([]);

      // 3. Masukkan ke FormData
      const formData = new FormData();
      formData.append("room_id", finalRoomId);
      formData.append("content", textToSend);

      // Looping multi-gambar
      selectedImages.forEach((file) => {
        formData.append("images", file);
      });

      // 4. Kirim ke Backend API
      const chatRes = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const chatData = await chatRes.json();
      if (chatData.status === "success") {
        addMessage(finalRoomId, chatData.data, "ai");
      } else {
        throw new Error(chatData.data);
      }
    } catch (error) {
      console.error("Gagal mengirim pesan:", error);
      addMessage(
        (currentRoomId as string) || "error",
        "Maaf, terjadi kesalahan.",
        "ai",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-zinc-950 overflow-hidden text-zinc-200 font-sans">
      <Sidebar />

      <div className="flex flex-1 flex-col relative">
        {/* HEADER & PROFILE */}
        <header className="flex h-16 items-center justify-end border-b border-zinc-800 bg-zinc-950 px-6 shrink-0">
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="rounded-full bg-zinc-800 p-2 text-zinc-400 hover:text-white transition-colors"
          >
            <UserCircle size={28} />
          </button>
        </header>

        {/* AREA BUBBLE CHAT */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
          {!activeRoomId ? (
            <div className="flex h-full items-center justify-center text-zinc-200 text-3xl text-center px-4">
              Halo! Agen AI siap membantu Anda.
            </div>
          ) : (
            activeRoom?.messages.map((msg) => (
              <BubbleChat
                key={msg.id}
                text={msg.text}
                sender={msg.sender}
                imageUrls={msg.imageUrls}
              />
            ))
          )}
          {isLoading && (
            <div className="text-zinc-500 text-sm animate-pulse ml-4">
              Agen sedang berpikir...
            </div>
          )}
        </div>

        {/* INPUT TEKS & GAMBAR */}
        <div className="p-4 shrink-0 bg-zinc-950">
          {/* GALERI PREVIEW GAMBAR (Sebelum Dikirim) */}
          {selectedImages.length > 0 && (
            <div className="mx-auto max-w-4xl mb-3 flex flex-wrap items-center gap-3">
              {selectedImages.map((file, index) => (
                <div
                  key={index}
                  className="relative rounded-lg border border-zinc-700 bg-zinc-800 p-2 flex items-center gap-3 pr-8 shadow-md"
                >
                  {/* Thumbnail Gambar */}
                  <img
                    src={URL.createObjectURL(file)}
                    alt="preview"
                    className="h-10 w-10 object-cover rounded-md border border-zinc-600"
                  />
                  {/* Nama File */}
                  <p className="text-xs text-zinc-300 truncate max-w-32 font-medium">
                    {file.name}
                  </p>
                  {/* Tombol Hapus per Gambar */}
                  <button
                    onClick={() => handleRemoveImage(index)}
                    className="absolute -top-2 -right-2 bg-red-600 text-white rounded-full p-1 hover:bg-red-500 transition-colors shadow-lg"
                    type="button"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <form
            onSubmit={handleSendMessage}
            className="mx-auto flex max-w-4xl items-center gap-3 rounded-xl border border-zinc-700 bg-zinc-900 p-2 focus-within:border-zinc-500 transition-all"
          >
            {/* INPUT FILE (MULTIPLE) */}
            <input
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-zinc-400 hover:text-white transition-colors"
            >
              <Paperclip size={20} />
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ketik pesan Anda..."
              className="flex-1 bg-transparent px-3 py-2 text-sm text-zinc-200 placeholder-zinc-400 focus:outline-none disabled:opacity-50"
              disabled={isLoading}
            />

            <button
              type="submit"
              disabled={
                isLoading || (!inputText.trim() && selectedImages.length === 0)
              }
              className="rounded-lg bg-zinc-100 p-2 text-zinc-900 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send size={18} />
            </button>
          </form>
        </div>

        {/* POP-UP PROFILE */}
        {isProfileOpen && (
          <div className="absolute right-6 top-20 w-64 rounded-xl border border-zinc-800 bg-zinc-900 p-4 shadow-2xl z-50">
            <h3 className="mb-4 text-sm font-semibold text-zinc-100 border-b border-zinc-800 pb-2">
              Edit Profil
            </h3>
            <div className="space-y-3">
              <button
                onClick={() => {
                  document.cookie =
                    "token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                  router.push("/login");
                }}
                className="w-full rounded-lg bg-red-900/50 py-2 text-xs font-semibold text-red-200 hover:bg-red-900 transition-colors mt-2 border border-red-800"
              >
                Logout
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
