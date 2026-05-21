import { create } from "zustand";

export type Message = {
  id: string;
  text: string;
  sender: "user" | "ai";
  imageUrls?: string[] | null; // <--- Ubah jadi array (tambah 's' dan '[]')
};

export type Room = {
  id: string;
  title: string;
  messages: Message[];
};

type ChatStore = {
  rooms: Room[];
  activeRoomId: string | null;
  setActiveRoom: (id: string | null) => void;
  createNewRoom: (title: string, id: string) => void;
  addMessage: (
    roomId: string,
    text: string,
    sender: "user" | "ai",
    imageUrls?: string[] | null,
  ) => void;

  // 1. TAMBAH INI: Untuk load daftar room dari API
  setRooms: (rooms: Room[]) => void;
  // 2. TAMBAH INI: Untuk load history chat dari API
  setMessages: (roomId: string, messages: Message[]) => void;
  // 3. TAMBAH INI: Untuk hapus room
  deleteRoom: (roomId: string) => void;
};

export const useChatStore = create<ChatStore>((set) => ({
  rooms: [],
  activeRoomId: null,

  setActiveRoom: (id) => set({ activeRoomId: id }),

  createNewRoom: (title, id) =>
    set((state) => ({
      rooms: [{ id, title, messages: [] }, ...state.rooms],
      activeRoomId: id,
    })),

  deleteRoom: (roomId) =>
    set((state) => ({
      // Filter/buang room yang ID-nya sama dengan yang dihapus
      rooms: state.rooms.filter((room) => room.id !== roomId),
    })),

  addMessage: (roomId, text, sender, imageUrls = null) =>
    set((state) => ({
      rooms: state.rooms.map((room) =>
        room.id === roomId
          ? {
              ...room,
              messages: [
                ...room.messages,
                // Ganti imageUrl menjadi imageUrls
                { id: crypto.randomUUID(), text, sender, imageUrls },
              ],
            }
          : room,
      ),
    })),

  // IMPLEMENTASI FUNGSI BARU
  setRooms: (rooms) => set({ rooms }),

  setMessages: (roomId, messages) =>
    set((state) => ({
      rooms: state.rooms.map((room) =>
        room.id === roomId ? { ...room, messages } : room,
      ),
    })),
}));
