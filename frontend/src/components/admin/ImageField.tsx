import { useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { adminApi } from "@/services/admin";
import { errorMessage } from "@/services/api";
import { useToast } from "@/features/toast";
import { Spinner } from "@/components/ui";

const TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

/** Upload to /admin/uploads/image and hand back the URL; also allows pasting a URL. */
export function ImageField({ label, value, onChange, folder, disabled }: {
  label: string; value: string; onChange: (url: string) => void; folder: "content" | "categories" | "collections" | "banners"; disabled?: boolean;
}) {
  const toast = useToast();
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const pick = async (f: File | undefined) => {
    if (!f) return;
    if (!TYPES.includes(f.type)) return toast("Only JPEG, PNG, WebP or GIF images are allowed", "error");
    if (f.size > 5 * 1024 * 1024) return toast("Image must be smaller than 5 MB", "error");
    setBusy(true);
    try { onChange((await adminApi.uploadImage(f, folder)).url); toast("Image uploaded"); }
    catch (e) { toast(errorMessage(e), "error"); }
    finally { setBusy(false); if (ref.current) ref.current.value = ""; }
  };
  return (
    <div>
      <span className="label">{label}</span>
      <div className="flex items-start gap-3">
        <div className="relative flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-gold-200/60 bg-ivory-200">
          {value ? <img src={value} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="h-5 w-5 text-kajal-300" aria-hidden />}
          {busy && <span className="absolute inset-0 flex items-center justify-center bg-white/70"><Spinner /></span>}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <input className="input h-9 py-0 text-sm" aria-label={`${label} URL`} value={value} onChange={(e) => onChange(e.target.value)} placeholder="/media/… or https://…" disabled={disabled} />
          <div className="flex gap-2">
            <label className={`chip cursor-pointer ${disabled ? "pointer-events-none opacity-50" : ""}`}>
              Upload image
              <input ref={ref} type="file" accept={TYPES.join(",")} className="sr-only" disabled={disabled} onChange={(e) => pick(e.target.files?.[0])} />
            </label>
            {value && !disabled && <button type="button" className="chip" onClick={() => onChange("")}><X className="h-3.5 w-3.5" aria-hidden />Remove</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
