import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Plus } from "lucide-react";
import { Button, EmptyState, Modal, PageSpinner } from "@/components/ui";
import { AddressForm } from "@/components/forms/AddressForm";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { useToast } from "@/features/toast";
import type { Address, AddressInput } from "@/types";
import { useSeo } from "@/hooks/useSeo";

export default function Addresses() {
  useSeo({ title: "Addresses", noindex: true });
  const qc = useQueryClient();
  const toast = useToast();
  const { data, isLoading } = useQuery({ queryKey: ["addresses"], queryFn: storeApi.addresses });
  const [editing, setEditing] = useState<Address | "new" | null>(null);
  const [confirmDel, setConfirmDel] = useState<Address | null>(null);
  const save = useMutation({
    mutationFn: (v: AddressInput) => (editing && editing !== "new" ? storeApi.updateAddress(editing.id, v) : storeApi.addAddress(v)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["addresses"] }); setEditing(null); toast("Address saved"); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const del = useMutation({
    mutationFn: (id: number) => storeApi.deleteAddress(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["addresses"] }); setConfirmDel(null); toast("Address removed"); },
  });
  if (isLoading) return <PageSpinner />;
  return (
    <div>
      <div className="mb-6 flex items-center justify-between"><h2 className="text-[28px]">Saved addresses</h2><Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" />Add address</Button></div>
      {!data?.length ? (
        <EmptyState icon={<MapPin className="h-6 w-6" />} title="No saved addresses" body="Save an address for faster checkout." action={<Button onClick={() => setEditing("new")}>Add an address</Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((a) => (
            <div key={a.id} className="card flex flex-col p-5">
              <div className="flex items-center gap-2"><span className="font-medium">{a.full_name}</span>{a.label && <span className="rounded-full bg-ivory-200 px-2 py-0.5 text-xs text-kajal-500">{a.label}</span>}
                {a.is_default_shipping && <span className="ml-auto rounded-full bg-gold-100 px-2 py-0.5 text-xs text-gold-800">Default</span>}</div>
              <p className="mt-2 flex-1 text-[15px] leading-6 text-kajal-700">{a.line1}{a.line2 && <>, {a.line2}</>}{a.landmark && <>, near {a.landmark}</>}<br />{a.city}, {a.state} {a.pin_code}<br />{a.phone}</p>
              <div className="mt-4 flex gap-4 text-sm"><button className="link-underline" onClick={() => setEditing(a)}>Edit</button><button className="text-kajal-500 hover:text-kumkum" onClick={() => setConfirmDel(a)}>Remove</button></div>
            </div>
          ))}
        </div>
      )}
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "Add address" : "Edit address"} size="lg">
        {editing && <AddressForm initial={editing === "new" ? undefined : { ...editing, line2: editing.line2 ?? "", landmark: editing.landmark ?? "" }} onSubmit={(v) => save.mutate(v)} busy={save.isPending} onCancel={() => setEditing(null)} />}
      </Modal>
      <Modal open={!!confirmDel} onClose={() => setConfirmDel(null)} title="Remove this address?" size="sm"
        footer={<><Button variant="ghost" onClick={() => setConfirmDel(null)}>Keep it</Button><Button variant="danger" loading={del.isPending} onClick={() => confirmDel && del.mutate(confirmDel.id)}>Remove address</Button></>}>
        <p className="text-kajal-700">{confirmDel?.line1}, {confirmDel?.city}</p>
      </Modal>
    </div>
  );
}
