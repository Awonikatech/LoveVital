import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, Checkbox, Input, Select } from "@/components/ui";
import { INDIAN_STATES, PHONE_RE, PIN_RE } from "@/utils/india";
import type { AddressInput } from "@/types";

export const addressSchema = z.object({
  label: z.string().max(50).optional().nullable(),
  full_name: z.string().trim().min(2, "Enter the recipient's full name").max(150),
  phone: z.string().trim().regex(PHONE_RE, "Enter a valid 10-digit mobile number"),
  line1: z.string().trim().min(3, "Enter house / flat number and street").max(255),
  line2: z.string().max(255).optional().nullable(),
  landmark: z.string().max(150).optional().nullable(),
  city: z.string().trim().min(2, "Enter the city").max(100),
  state: z.string().refine((v) => INDIAN_STATES.includes(v), "Select a state"),
  pin_code: z.string().trim().regex(PIN_RE, "Enter a valid 6-digit PIN code"),
  is_default_shipping: z.boolean().default(false),
  is_default_billing: z.boolean().default(false),
});
export type AddressValues = z.infer<typeof addressSchema>;

export const emptyAddress: AddressValues = {
  label: "Home", full_name: "", phone: "", line1: "", line2: "", landmark: "", city: "", state: "", pin_code: "",
  is_default_shipping: false, is_default_billing: false,
};

export function AddressFields({ form, prefix = "" }: { form: ReturnType<typeof useForm<any>>; prefix?: string }) {
  const { register, formState: { errors } } = form;
  const e = (k: string) => {
    const parts = (prefix + k).split(".");
    let cur: any = errors;
    for (const p of parts) cur = cur?.[p];
    return cur?.message as string | undefined;
  };
  const n = (k: string) => (prefix + k) as any;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Input label="Full name" autoComplete="name" {...register(n("full_name"))} error={e("full_name")} required />
      <Input label="Mobile number" type="tel" inputMode="tel" autoComplete="tel-national" placeholder="10-digit mobile" {...register(n("phone"))} error={e("phone")} required />
      <Input className="sm:col-span-2" label="Flat, house no., building, street" autoComplete="address-line1" {...register(n("line1"))} error={e("line1")} required />
      <Input label="Area, colony (optional)" autoComplete="address-line2" {...register(n("line2"))} error={e("line2")} />
      <Input label="Landmark (optional)" {...register(n("landmark"))} error={e("landmark")} />
      <Input label="PIN code" inputMode="numeric" maxLength={6} autoComplete="postal-code" {...register(n("pin_code"))} error={e("pin_code")} required />
      <Input label="City / town" autoComplete="address-level2" {...register(n("city"))} error={e("city")} required />
      <Select label="State" autoComplete="address-level1" {...register(n("state"))} error={e("state")}>
        <option value="">Select state</option>
        {INDIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
      </Select>
      <Input label="Country" value="India" readOnly disabled />
    </div>
  );
}

export function AddressForm({ initial, onSubmit, submitLabel = "Save address", onCancel, busy }: {
  initial?: Partial<AddressValues>; onSubmit: (v: AddressInput) => void | Promise<void>; submitLabel?: string; onCancel?: () => void; busy?: boolean;
}) {
  const form = useForm<AddressValues>({ resolver: zodResolver(addressSchema) as any, defaultValues: { ...emptyAddress, ...initial } });
  return (
    <form onSubmit={form.handleSubmit((v) => onSubmit(v as AddressInput))} noValidate>
      <div className="mb-4 flex flex-wrap gap-2">
        {["Home", "Office", "Other"].map((l) => (
          <label key={l} className="cursor-pointer">
            <input type="radio" value={l} {...form.register("label")} className="peer sr-only" />
            <span className="chip peer-checked:chip-active">{l}</span>
          </label>
        ))}
      </div>
      <AddressFields form={form as any} />
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:gap-6">
        <Checkbox label="Default delivery address" {...form.register("is_default_shipping")} />
        <Checkbox label="Default billing address" {...form.register("is_default_billing")} />
      </div>
      <div className="mt-6 flex gap-2">
        <Button type="submit" loading={busy}>{submitLabel}</Button>
        {onCancel && <Button variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}
