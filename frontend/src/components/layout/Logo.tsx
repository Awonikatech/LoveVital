import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";

export function ArchMark({ className }: { className?: string }) {
  return <img src="/logo.webp" alt="" aria-hidden width={320} height={241} className={cn("object-contain", className)} />;
}

export function Logo({ className, light }: { className?: string; light?: boolean }) {
  return (
    <Link to="/" className={cn("group inline-flex items-center gap-2", className)} aria-label="LoveVital home">
      <ArchMark className="h-12 w-auto sm:h-14" />
      <span className={cn("font-display text-[30px] leading-none tracking-[0.12em] sm:text-[34px]", light ? "text-ivory" : "text-kajal")}>LoveVital</span>
    </Link>
  );
}
