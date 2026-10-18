import type { ReactNode } from "react";

export function AuthShell({ title, sub, children, image = "/static/tiles/festive-edit.svg" }: { title: string; sub?: ReactNode; children: ReactNode; image?: string }) {
  return (
    <div className="container-site grid items-center gap-12 py-12 lg:grid-cols-2 lg:py-20">
      <div className="hidden justify-center lg:flex">
        <div className="arch arch-frame w-[360px] bg-ivory-200 shadow-lift"><img src={image} alt="" className="aspect-[3/4] w-full object-cover" /></div>
      </div>
      <div className="mx-auto w-full max-w-md">
        <h1 className="text-[36px] leading-tight sm:text-[42px]">{title}</h1>
        {sub && <p className="mt-2 text-kajal-500">{sub}</p>}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}
