import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useFieldArray, useForm, useWatch, type Control, type UseFormRegister, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ImagePlus, Plus, Star, Trash2 } from "lucide-react";
import {
  adminApi, isNotFound, localInputToUtc, utcToLocalInput, type AdminProduct, type ProductMeta, type ProductPayload,
} from "@/services/admin";
import { errorMessage } from "@/services/api";
import { FieldGrid, MiniInput, NoAccess, PageHeader, Panel, Switch, useConfirm } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { Alert, Button, ErrorState, Input, PageSpinner, Select, StatusBadge, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { cn } from "@/utils/cn";
import axios from "axios";

/* ------------------------------------------------------------------ schema */
const money = (label: string, required = true) =>
  z.string().trim().refine((v) => (!required && v === "") || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) > 0), { message: `${label} must be a positive amount (max 2 decimals)` });
const intStr = (label: string) => z.string().trim().refine((v) => v === "" || /^\d+$/.test(v), { message: `${label} must be a whole number` });

const variantSchema = z.object({
  id: z.number().nullable(),
  sku: z.string().trim().min(3, "SKU needs 3+ characters").max(60).regex(/^[A-Za-z0-9\-_]+$/, "Letters, numbers, - and _ only"),
  name: z.string().trim().min(1, "Name is required").max(150),
  mrp: money("MRP"),
  sale_price: money("Sale price"),
  cost_price: z.string().trim().refine((v) => v === "" || /^\d+(\.\d{1,2})?$/.test(v), "Cost must be an amount"),
  scheduled_sale_price: money("Scheduled price", false),
  sale_starts_at: z.string(),
  sale_ends_at: z.string(),
  weight_grams: z.string().trim().refine((v) => v === "" || (/^\d+(\.\d+)?$/.test(v)), "Weight must be a number"),
  is_active: z.boolean(),
  attribute_value_ids: z.array(z.number()),
  stock: intStr("Stock"),
  low_stock_threshold: intStr("Threshold"),
  on_hand: z.number().optional(),
  available: z.number().optional(),
  reserved: z.number().optional(),
}).superRefine((v, ctx) => {
  const mrp = Number(v.mrp), sale = Number(v.sale_price);
  if (mrp > 0 && sale > mrp) ctx.addIssue({ code: "custom", path: ["sale_price"], message: "Sale price can't be more than MRP" });
  if (v.scheduled_sale_price) {
    if (Number(v.scheduled_sale_price) > mrp) ctx.addIssue({ code: "custom", path: ["scheduled_sale_price"], message: "Scheduled price can't exceed MRP" });
    if (!v.sale_starts_at) ctx.addIssue({ code: "custom", path: ["sale_starts_at"], message: "Scheduled price needs a start date" });
  }
  if (v.sale_starts_at && v.sale_ends_at && v.sale_ends_at <= v.sale_starts_at) ctx.addIssue({ code: "custom", path: ["sale_ends_at"], message: "End must be after start" });
});

const schema = z.object({
  name: z.string().trim().min(2, "Name needs at least 2 characters").max(200),
  slug: z.string().trim().max(220),
  sku: z.string().trim().min(3, "SKU needs 3+ characters").max(50).regex(/^[A-Za-z0-9\-_]+$/, "Letters, numbers, - and _ only"),
  brand: z.string().trim().max(100),
  product_type: z.enum(["jewellery", "apparel"]),
  category_id: z.string().min(1, "Choose a category"),
  tax_rate_id: z.string(),
  status: z.enum(["draft", "active", "archived"]),
  is_featured: z.boolean(), is_bestseller: z.boolean(), is_new_arrival: z.boolean(),
  collection_ids: z.array(z.number()),
  tags: z.string(),
  short_description: z.string().max(300, "Keep it under 300 characters"),
  description: z.string(),
  seo_title: z.string().max(200),
  seo_description: z.string().max(300, "Keep it under 300 characters"),
  specifications: z.array(z.object({ key: z.string(), value: z.string() })),
  care_instructions: z.string(),
  size_chart: z.object({ enabled: z.boolean(), unit: z.string(), note: z.string(), columns: z.array(z.string()), rows: z.array(z.array(z.string())) }),
  min_order_qty: z.coerce.number().int().min(1, "At least 1").max(100),
  max_order_qty: z.coerce.number().int().min(1).max(100, "At most 100"),
  processing_days: z.coerce.number().int().min(0).max(30, "At most 30 days"),
  is_returnable: z.boolean(),
  return_window_days: z.coerce.number().int().min(0).max(60, "At most 60 days"),
  is_cod_available: z.boolean(),
  default_index: z.number(),
  variants: z.array(variantSchema).min(1, "Add at least one variant"),
}).superRefine((v, ctx) => {
  if (v.max_order_qty < v.min_order_qty) ctx.addIssue({ code: "custom", path: ["max_order_qty"], message: "Must be ≥ minimum quantity" });
  const seen = new Map<string, number>();
  v.variants.forEach((x, i) => {
    const k = x.sku.trim().toUpperCase();
    if (seen.has(k)) ctx.addIssue({ code: "custom", path: ["variants", i, "sku"], message: "Duplicate variant SKU" });
    seen.set(k, i);
  });
});
type FormValues = z.infer<typeof schema>;
type VariantForm = FormValues["variants"][number];

const emptyVariant = (sku = ""): VariantForm => ({
  id: null, sku, name: "Default", mrp: "", sale_price: "", cost_price: "", scheduled_sale_price: "", sale_starts_at: "", sale_ends_at: "",
  weight_grams: "", is_active: true, attribute_value_ids: [], stock: "", low_stock_threshold: "5",
});

function toForm(p: AdminProduct | undefined): FormValues {
  if (!p) {
    return {
      name: "", slug: "", sku: "", brand: "LoveVital", product_type: "jewellery", category_id: "", tax_rate_id: "", status: "draft",
      is_featured: false, is_bestseller: false, is_new_arrival: true, collection_ids: [], tags: "", short_description: "", description: "",
      seo_title: "", seo_description: "", specifications: [{ key: "", value: "" }], care_instructions: "",
      size_chart: { enabled: false, unit: "inches", note: "", columns: ["Size", "Bust", "Waist"], rows: [["S", "", ""]] },
      min_order_qty: 1, max_order_qty: 10, processing_days: 1, is_returnable: true, return_window_days: 7, is_cod_available: true,
      default_index: 0, variants: [emptyVariant()],
    };
  }
  const sc = p.size_chart;
  return {
    name: p.name, slug: p.slug, sku: p.sku, brand: p.brand, product_type: p.product_type, category_id: String(p.category_id),
    tax_rate_id: p.tax_rate_id ? String(p.tax_rate_id) : "", status: p.status, is_featured: p.is_featured, is_bestseller: p.is_bestseller,
    is_new_arrival: p.is_new_arrival, collection_ids: p.collection_ids, tags: p.tags.join(", "), short_description: p.short_description ?? "",
    description: p.description ?? "", seo_title: p.seo_title ?? "", seo_description: p.seo_description ?? "",
    specifications: Object.entries(p.specifications ?? {}).map(([key, value]) => ({ key, value: String(value) })).concat(Object.keys(p.specifications ?? {}).length ? [] : [{ key: "", value: "" }]),
    care_instructions: p.care_instructions ?? "",
    size_chart: sc && Array.isArray(sc.columns)
      ? { enabled: true, unit: sc.unit ?? "inches", note: sc.note ?? "", columns: sc.columns.map(String), rows: (sc.rows ?? []).map((r) => sc.columns.map((_, i) => String(r[i] ?? ""))) }
      : { enabled: false, unit: "inches", note: "", columns: ["Size", "Bust", "Waist"], rows: [["S", "", ""]] },
    min_order_qty: p.min_order_qty, max_order_qty: p.max_order_qty, processing_days: p.processing_days, is_returnable: p.is_returnable,
    return_window_days: p.return_window_days, is_cod_available: p.is_cod_available,
    default_index: Math.max(0, p.variants.findIndex((v) => v.is_default)),
    variants: p.variants.map((v) => ({
      id: v.id, sku: v.sku, name: v.name, mrp: v.mrp, sale_price: v.sale_price, cost_price: v.cost_price ?? "",
      scheduled_sale_price: v.scheduled_sale_price ?? "", sale_starts_at: utcToLocalInput(v.sale_starts_at), sale_ends_at: utcToLocalInput(v.sale_ends_at),
      weight_grams: v.weight_grams ?? "", is_active: v.is_active, attribute_value_ids: v.attribute_value_ids, stock: "",
      low_stock_threshold: String(v.low_stock_threshold), on_hand: v.on_hand, available: v.available, reserved: v.reserved,
    })),
  };
}

function toPayload(v: FormValues, canCost: boolean): ProductPayload {
  const nul = (s: string) => (s.trim() === "" ? null : s.trim());
  const specs: Record<string, string> = {};
  v.specifications.forEach((s) => { if (s.key.trim()) specs[s.key.trim()] = s.value.trim(); });
  return {
    name: v.name.trim(), slug: nul(v.slug), sku: v.sku.trim().toUpperCase(), brand: v.brand.trim() || "LoveVital", product_type: v.product_type,
    category_id: Number(v.category_id), tax_rate_id: v.tax_rate_id ? Number(v.tax_rate_id) : null,
    short_description: nul(v.short_description), description: nul(v.description), specifications: specs, care_instructions: nul(v.care_instructions),
    size_chart: v.size_chart.enabled ? { unit: v.size_chart.unit, columns: v.size_chart.columns, rows: v.size_chart.rows, ...(v.size_chart.note ? { note: v.size_chart.note } : {}) } : null,
    tags: v.tags.split(",").map((t) => t.trim()).filter(Boolean), status: v.status, is_featured: v.is_featured, is_bestseller: v.is_bestseller,
    is_new_arrival: v.is_new_arrival, processing_days: v.processing_days, min_order_qty: v.min_order_qty, max_order_qty: v.max_order_qty,
    is_returnable: v.is_returnable, return_window_days: v.return_window_days, is_cod_available: v.is_cod_available,
    seo_title: nul(v.seo_title), seo_description: nul(v.seo_description), collection_ids: v.collection_ids,
    variants: v.variants.map((x, i) => ({
      ...(x.id ? { id: x.id } : {}), sku: x.sku.trim().toUpperCase(), name: x.name.trim(), mrp: x.mrp, sale_price: x.sale_price,
      ...(canCost ? { cost_price: nul(x.cost_price) } : {}),
      scheduled_sale_price: nul(x.scheduled_sale_price), sale_starts_at: localInputToUtc(x.sale_starts_at), sale_ends_at: localInputToUtc(x.sale_ends_at),
      weight_grams: nul(x.weight_grams), is_active: x.is_active, is_default: i === v.default_index, attribute_value_ids: x.attribute_value_ids,
      stock: !x.id && x.stock ? Number(x.stock) : null, low_stock_threshold: x.low_stock_threshold ? Number(x.low_stock_threshold) : null,
    })),
  };
}

/* ------------------------------------------------------------------ page */
export default function ProductEditor() {
  const { id } = useParams();
  const isNew = !id;
  const pid = Number(id);
  const meta = useQuery({ queryKey: ["admin", "product-meta"], queryFn: adminApi.productMeta, staleTime: 5 * 60_000 });
  const prod = useQuery({ queryKey: ["admin", "product", pid], queryFn: () => adminApi.product(pid), enabled: !isNew && Number.isFinite(pid) });

  if (meta.isPending || (!isNew && prod.isPending)) return <PageSpinner />;
  const err = meta.error ?? prod.error;
  if (err) {
    if (axios.isAxiosError(err) && err.response?.status === 403) return <NoAccess what="Products" />;
    if (isNotFound(err)) return <ErrorState message="This product doesn't exist or was deleted." />;
    return <ErrorState message={errorMessage(err)} onRetry={() => { meta.refetch(); prod.refetch(); }} />;
  }
  return <Editor key={prod.data?.updated_at ?? "new"} meta={meta.data!} product={isNew ? undefined : prod.data} />;
}

const SECTIONS = [
  ["basics", "Basics"], ["descriptions", "Descriptions & SEO"], ["details", "Specifications & care"], ["rules", "Purchase rules"],
  ["variants", "Variants & pricing"], ["images", "Images"],
] as const;

function Editor({ meta, product }: { meta: ProductMeta; product?: AdminProduct }) {
  const { can } = useAuth();
  const write = can("products:write");
  const canCost = meta.can_view_cost;
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [serverError, setServerError] = useState<string | null>(null);
  const defaults = useMemo(() => toForm(product), [product]);
  const form = useForm<FormValues>({ resolver: zodResolver(schema) as any, defaultValues: defaults, mode: "onBlur" });
  const { register, control, handleSubmit, formState: { errors, isDirty, isSubmitting } } = form;

  const save = async (v: FormValues) => {
    setServerError(null);
    try {
      const body = toPayload(v, canCost);
      const saved = product ? await adminApi.updateProduct(product.id, body) : await adminApi.createProduct(body);
      qc.invalidateQueries({ queryKey: ["admin", "products"] });
      qc.setQueryData(["admin", "product", saved.id], saved);
      toast(product ? "Product saved" : "Product created — you can add images now", "success");
      if (!product) nav(`/admin/products/${saved.id}#images`, { replace: true });
      else form.reset(toForm(saved));
    } catch (e) {
      const m = errorMessage(e);
      setServerError(m);
      toast(m, "error");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  const onInvalid = (errs: FieldErrors<FormValues>) => {
    toast("Please fix the highlighted fields", "error");
    const first = document.querySelector<HTMLElement>("[aria-invalid='true']");
    first?.focus();
    if (errs.variants && !first) document.getElementById("variants")?.scrollIntoView({ behavior: "smooth" });
  };

  const del = useAdminMutation(() => adminApi.deleteProduct(product!.id), {
    invalidate: [["admin", "products"]], success: (r) => r.message ?? "Product deleted",
    onSuccess: (r) => { if (r.archived) qc.invalidateQueries({ queryKey: ["admin", "product", product!.id] }); else nav("/admin/products"); },
  });
  const remove = async () => {
    const r = await confirm({ title: "Delete this product?", body: "Products with order history are archived instead, to keep invoices intact.", confirmLabel: "Delete product", danger: true });
    if (r.ok) del.mutate(undefined);
  };

  // Warn before leaving with unsaved changes.
  useEffect(() => {
    if (!isDirty) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [isDirty]);

  const saveBar = write && (
    <div className="flex items-center gap-2">
      {isDirty && <span className="hidden text-sm text-kajal-500 sm:inline">Unsaved changes</span>}
      <Button type="submit" form="product-form" size="sm" loading={isSubmitting}>{product ? "Save product" : "Create product"}</Button>
    </div>
  );

  return (
    <>
      <PageHeader
        back={<Link to="/admin/products" className="inline-flex items-center gap-1 text-sm text-kajal-500 hover:text-kajal"><ArrowLeft className="h-4 w-4" aria-hidden />Products</Link>}
        title={product ? product.name : "New product"}
        sub={product ? <span className="inline-flex flex-wrap items-center gap-2"><StatusBadge status={product.status} /> {product.sku} · {product.total_stock} available · {product.sold_count} sold</span> : "Fill in the basics and at least one variant. Images can be added after saving."}
        actions={<>
          {product && <a href={`/product/${product.slug}`} target="_blank" rel="noreferrer" className="text-sm text-kajal-500 underline decoration-gold-300 underline-offset-4 hover:text-kajal">View in store</a>}
          {product && write && <Button variant="ghost" size="sm" className="text-kumkum" onClick={remove} loading={del.isPending}><Trash2 className="h-4 w-4" aria-hidden />Delete</Button>}
          {saveBar}
        </>} />

      {!write && <Alert className="mb-4">You can view this product but not edit it.</Alert>}
      {serverError && <Alert tone="error" className="mb-4">{serverError}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[180px_1fr]">
        <nav aria-label="Editor sections" className="hidden xl:block">
          <ul className="sticky top-20 space-y-1 text-sm">
            {SECTIONS.map(([id, label]) => (
              <li key={id}><a href={`#${id}`} className="block rounded-lg px-3 py-1.5 text-kajal-500 hover:bg-white hover:text-kajal">{label}</a></li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 space-y-6">
          <form id="product-form" onSubmit={handleSubmit(save, onInvalid)} noValidate className="space-y-6">
            <fieldset disabled={!write} className="min-w-0 space-y-6">
              <Basics meta={meta} register={register} control={control} errors={errors} />
              <Descriptions register={register} errors={errors} control={control} />
              <Details register={register} control={control} />
              <Rules register={register} control={control} errors={errors} />
              <Variants meta={meta} control={control} register={register} errors={errors} canCost={canCost} productSku={form.getValues("sku")} />
            </fieldset>
          </form>
          <Panel id="images" title="Images" className="scroll-mt-20">
            {product ? <Images product={product} write={write} /> : <p className="text-sm text-kajal-500">Save the product first, then upload images here.</p>}
          </Panel>
          {write && (
            <div className="sticky bottom-0 z-10 -mx-4 flex justify-end border-t border-gold-200/60 bg-ivory/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
              {saveBar}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

type SecProps = { register: UseFormRegister<FormValues>; control: Control<FormValues>; errors: FieldErrors<FormValues> };

function Basics({ meta, register, control, errors }: SecProps & { meta: ProductMeta }) {
  return (
    <Panel id="basics" title="Basics" className="scroll-mt-20">
      <FieldGrid>
        <Input label="Product name" required {...register("name")} error={errors.name?.message} />
        <Input label="URL slug" {...register("slug")} error={errors.slug?.message} hint="Leave blank to generate from the name." />
        <Input label="Product SKU" required {...register("sku")} error={errors.sku?.message} className="uppercase-input" />
        <Input label="Brand" {...register("brand")} />
        <Select label="Product type" {...register("product_type")} options={[{ value: "jewellery", label: "Jewellery" }, { value: "apparel", label: "Apparel" }]} />
        <Select label="Category" {...register("category_id")} error={errors.category_id?.message}>
          <option value="">Choose a category</option>
          {meta.categories.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </Select>
        <Select label="GST rate" {...register("tax_rate_id")} hint="Prices are GST-inclusive.">
          <option value="">Use category default</option>
          {meta.tax_rates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </Select>
        <Select label="Status" {...register("status")} options={[{ value: "draft", label: "Draft — hidden from store" }, { value: "active", label: "Active — visible in store" }, { value: "archived", label: "Archived" }]} />
        <Input label="Tags" {...register("tags")} hint="Comma separated, e.g. festive, bridal" className="sm:col-span-2" />
      </FieldGrid>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3">
        <Controller control={control} name="is_featured" render={({ field }) => <Switch label="Featured" checked={field.value} onChange={field.onChange} />} />
        <Controller control={control} name="is_bestseller" render={({ field }) => <Switch label="Bestseller" checked={field.value} onChange={field.onChange} />} />
        <Controller control={control} name="is_new_arrival" render={({ field }) => <Switch label="New arrival" checked={field.value} onChange={field.onChange} />} />
      </div>
      {meta.collections.length > 0 && (
        <fieldset className="mt-5">
          <legend className="label">Collections</legend>
          <Controller control={control} name="collection_ids" render={({ field }) => (
            <div className="flex flex-wrap gap-2">
              {meta.collections.map((c) => {
                const on = field.value.includes(c.id);
                return (
                  <button key={c.id} type="button" aria-pressed={on} className={cn("chip", on && "chip-active")}
                    onClick={() => field.onChange(on ? field.value.filter((x) => x !== c.id) : [...field.value, c.id])}>{c.name}</button>
                );
              })}
            </div>
          )} />
        </fieldset>
      )}
    </Panel>
  );
}

function CharCount({ control, name, max }: { control: Control<FormValues>; name: "short_description" | "seo_title" | "seo_description"; max: number }) {
  const v = useWatch({ control, name }) ?? "";
  return <span className={cn("tabular", v.length > max ? "text-kumkum" : "text-kajal-400")}>{v.length}/{max}</span>;
}

function Descriptions({ register, errors, control }: SecProps) {
  return (
    <Panel id="descriptions" title="Descriptions & SEO" className="scroll-mt-20">
      <div className="space-y-4">
        <Textarea label="Short description" rows={2} {...register("short_description")} error={errors.short_description?.message}
          hint={<span className="flex justify-between"><span>Shown near the price.</span><CharCount control={control} name="short_description" max={300} /></span>} />
        <Textarea label="Full description" rows={6} {...register("description")} />
        <FieldGrid>
          <Input label="SEO title" {...register("seo_title")} error={errors.seo_title?.message} hint={<span className="flex justify-between"><span>Defaults to the product name.</span><CharCount control={control} name="seo_title" max={60} /></span>} />
          <Textarea label="SEO description" rows={2} {...register("seo_description")} error={errors.seo_description?.message} hint={<span className="flex justify-end"><CharCount control={control} name="seo_description" max={160} /></span>} />
        </FieldGrid>
      </div>
    </Panel>
  );
}

function Details({ register, control }: Omit<SecProps, "errors">) {
  const specs = useFieldArray({ control, name: "specifications" });
  return (
    <Panel id="details" title="Specifications & care" className="scroll-mt-20">
      <fieldset>
        <legend className="label">Specifications</legend>
        <div className="space-y-2">
          {specs.fields.map((f, i) => (
            <div key={f.id} className="flex gap-2">
              <MiniInput label={`Specification ${i + 1} name`} placeholder="e.g. Material" {...register(`specifications.${i}.key`)} className="w-2/5" />
              <MiniInput label={`Specification ${i + 1} value`} placeholder="e.g. Brass alloy" {...register(`specifications.${i}.value`)} className="flex-1" />
              <button type="button" aria-label={`Remove specification ${i + 1}`} onClick={() => specs.remove(i)} className="rounded-lg p-2 text-kajal-400 hover:bg-ivory-200 hover:text-kumkum"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => specs.append({ key: "", value: "" })}><Plus className="h-4 w-4" aria-hidden />Add specification</Button>
      </fieldset>
      <Textarea className="mt-5" label="Care instructions" rows={3} {...register("care_instructions")} />
      <SizeChartEditor control={control} register={register} />
    </Panel>
  );
}

function SizeChartEditor({ control, register }: Omit<SecProps, "errors">) {
  return (
    <Controller control={control} name="size_chart" render={({ field }) => {
      const sc = field.value;
      const upd = (p: Partial<typeof sc>) => field.onChange({ ...sc, ...p });
      return (
        <fieldset className="mt-6">
          <legend className="sr-only">Size chart</legend>
          <Switch label="Show a size chart" checked={sc.enabled} onChange={(v) => upd({ enabled: v })} />
          {sc.enabled && (
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-3">
                <Select label="Unit" className="w-40" value={sc.unit} onChange={(e) => upd({ unit: e.target.value })} options={[{ value: "inches", label: "Inches" }, { value: "cm", label: "Centimetres" }, { value: "mm", label: "Millimetres" }]} />
                <Input label="Note" className="min-w-[220px] flex-1" value={sc.note} onChange={(e) => upd({ note: e.target.value })} placeholder="e.g. Garment measurements" />
              </div>
              <div className="overflow-x-auto rounded-xl border border-gold-200/60">
                <table className="text-sm">
                  <thead>
                    <tr>
                      {sc.columns.map((c, ci) => (
                        <th key={ci} className="border-b border-gold-200/60 bg-ivory-50 p-1.5">
                          <div className="flex items-center gap-1">
                            <MiniInput label={`Column ${ci + 1} heading`} value={c} className="w-28 font-medium" onChange={(e) => upd({ columns: sc.columns.map((x, j) => (j === ci ? e.target.value : x)) })} />
                            {sc.columns.length > 1 && (
                              <button type="button" aria-label={`Remove column ${c || ci + 1}`} className="p-1 text-kajal-400 hover:text-kumkum"
                                onClick={() => upd({ columns: sc.columns.filter((_, j) => j !== ci), rows: sc.rows.map((r) => r.filter((_, j) => j !== ci)) })}><Trash2 className="h-3.5 w-3.5" /></button>
                            )}
                          </div>
                        </th>
                      ))}
                      <th className="border-b border-gold-200/60 bg-ivory-50 p-1.5">
                        <Button variant="ghost" size="sm" onClick={() => upd({ columns: [...sc.columns, ""], rows: sc.rows.map((r) => [...r, ""]) })}>Add column</Button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sc.rows.map((r, ri) => (
                      <tr key={ri}>
                        {r.map((cell, ci) => (
                          <td key={ci} className="p-1.5">
                            <MiniInput label={`Row ${ri + 1}, ${sc.columns[ci] || `column ${ci + 1}`}`} value={cell} className="w-28"
                              onChange={(e) => upd({ rows: sc.rows.map((row, j) => (j === ri ? row.map((x, k) => (k === ci ? e.target.value : x)) : row)) })} />
                          </td>
                        ))}
                        <td className="p-1.5">
                          <button type="button" aria-label={`Remove row ${ri + 1}`} className="p-1.5 text-kajal-400 hover:text-kumkum" onClick={() => upd({ rows: sc.rows.filter((_, j) => j !== ri) })}><Trash2 className="h-4 w-4" /></button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Button variant="ghost" size="sm" onClick={() => upd({ rows: [...sc.rows, sc.columns.map(() => "")] })}><Plus className="h-4 w-4" aria-hidden />Add row</Button>
            </div>
          )}
        </fieldset>
      );
    }} />
  );
}

function Rules({ register, control, errors }: SecProps) {
  const returnable = useWatch({ control, name: "is_returnable" });
  return (
    <Panel id="rules" title="Purchase rules" className="scroll-mt-20">
      <FieldGrid cols={4}>
        <Input label="Minimum quantity" type="number" min={1} max={100} {...register("min_order_qty")} error={errors.min_order_qty?.message} />
        <Input label="Maximum quantity" type="number" min={1} max={100} {...register("max_order_qty")} error={errors.max_order_qty?.message} />
        <Input label="Processing days" type="number" min={0} max={30} {...register("processing_days")} error={errors.processing_days?.message} hint="Days before dispatch." />
        <Input label="Return window (days)" type="number" min={0} max={60} disabled={!returnable} {...register("return_window_days")} error={errors.return_window_days?.message} />
      </FieldGrid>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3">
        <Controller control={control} name="is_returnable" render={({ field }) => <Switch label="Returnable" checked={field.value} onChange={field.onChange} />} />
        <Controller control={control} name="is_cod_available" render={({ field }) => <Switch label="Cash on delivery allowed" checked={field.value} onChange={field.onChange} />} />
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ variants */
function Variants({ meta, control, register, errors, canCost, productSku }: SecProps & { meta: ProductMeta; canCost: boolean; productSku: string }) {
  const arr = useFieldArray({ control, name: "variants", keyName: "_key" });
  const sku = useWatch({ control, name: "sku" }) || productSku;
  const add = () => arr.append(emptyVariant(sku ? `${sku.toUpperCase()}-${arr.fields.length + 1}` : ""));
  return (
    <Panel id="variants" title="Variants & pricing" className="scroll-mt-20"
      action={<Button variant="outline" size="sm" onClick={add}><Plus className="h-4 w-4" aria-hidden />Add variant</Button>}>
      {errors.variants?.root?.message && <Alert tone="error" className="mb-3">{errors.variants.root.message}</Alert>}
      {typeof errors.variants?.message === "string" && <Alert tone="error" className="mb-3">{errors.variants.message}</Alert>}
      <p className="mb-4 text-sm text-kajal-500">
        Each variant is a sellable SKU with its own price and stock. The default variant is shown first on the product page.
        {canCost ? " Cost price is visible to administrators only." : ""}
      </p>
      <div className="space-y-3">
        {arr.fields.map((f, i) => (
          <VariantCard key={f._key} i={i} meta={meta} control={control} register={register} errors={errors} canCost={canCost}
            onRemove={arr.fields.length > 1 ? () => arr.remove(i) : undefined} />
        ))}
      </div>
    </Panel>
  );
}

function VariantCard({ i, meta, control, register, errors, canCost, onRemove }: SecProps & { i: number; meta: ProductMeta; canCost: boolean; onRemove?: () => void }) {
  const v = useWatch({ control, name: `variants.${i}` }) as VariantForm;
  const defaultIndex = useWatch({ control, name: "default_index" });
  const e = errors.variants?.[i];
  const [open, setOpen] = useState(!v?.id);
  const pct = Number(v?.mrp) > 0 && Number(v?.sale_price) > 0 ? Math.round((1 - Number(v.sale_price) / Number(v.mrp)) * 100) : 0;
  const hasError = !!e;
  useEffect(() => { if (hasError) setOpen(true); }, [hasError]);
  const axes = meta.attributes.filter((a) => a.is_variant_axis);
  const others = meta.attributes.filter((a) => !a.is_variant_axis);
  const margin = canCost && Number(v?.cost_price) > 0 && Number(v?.sale_price) > 0 ? ((Number(v.sale_price) - Number(v.cost_price)) / Number(v.sale_price)) * 100 : null;
  return (
    <div className={cn("rounded-xl border bg-ivory-50/60", hasError ? "border-kumkum/50" : "border-gold-200/60", v && !v.is_active && "opacity-75")}>
      <div className="grid grid-cols-2 items-start gap-3 p-3 sm:grid-cols-[1.2fr_1.2fr_0.8fr_0.8fr_auto] sm:p-4">
        <Field label="SKU" error={e?.sku?.message}><MiniInput label={`Variant ${i + 1} SKU`} {...register(`variants.${i}.sku`)} aria-invalid={!!e?.sku || undefined} className="uppercase" /></Field>
        <Field label="Name" error={e?.name?.message}><MiniInput label={`Variant ${i + 1} name`} {...register(`variants.${i}.name`)} aria-invalid={!!e?.name || undefined} placeholder="e.g. Gold / M" /></Field>
        <Field label="MRP (₹)" error={e?.mrp?.message}><MiniInput label={`Variant ${i + 1} MRP`} inputMode="decimal" {...register(`variants.${i}.mrp`)} aria-invalid={!!e?.mrp || undefined} className="tabular" /></Field>
        <Field label={<>Sale price {pct > 0 && <span className="text-kumkum">· {pct}% off</span>}</>} error={e?.sale_price?.message}>
          <MiniInput label={`Variant ${i + 1} sale price`} inputMode="decimal" {...register(`variants.${i}.sale_price`)} aria-invalid={!!e?.sale_price || undefined} className="tabular" />
        </Field>
        <div className="col-span-2 flex items-center gap-1 self-end sm:col-span-1 sm:pb-0.5">
          <Controller control={control} name="default_index" render={({ field }) => (
            <label className="mr-2 inline-flex cursor-pointer items-center gap-1.5 text-sm text-kajal-700">
              <input type="radio" name="default-variant" checked={field.value === i} onChange={() => field.onChange(i)} className="accent-[#B8862B]" />Default
            </label>
          )} />
          <Controller control={control} name={`variants.${i}.is_active`} render={({ field }) => <Switch label="Active" checked={field.value} onChange={field.onChange} />} />
          <button type="button" aria-expanded={open} aria-label={open ? "Hide variant details" : "Show variant details"} onClick={() => setOpen(!open)}
            className="ml-auto rounded-lg p-1.5 text-kajal-500 hover:bg-ivory-200"><ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} /></button>
          {onRemove && (
            <button type="button" aria-label={`Remove variant ${i + 1}`} disabled={defaultIndex === i && false} onClick={onRemove} className="rounded-lg p-1.5 text-kajal-400 hover:bg-ivory-200 hover:text-kumkum"><Trash2 className="h-4 w-4" /></button>
          )}
        </div>
      </div>
      {v?.id && (
        <p className="-mt-1 px-4 pb-3 text-xs text-kajal-500 tabular">
          On hand {v.on_hand} · reserved {v.reserved} · available {v.available} — adjust stock from <Link to={`/admin/inventory?q=${encodeURIComponent(v.sku)}`} className="underline decoration-gold-300 underline-offset-2">Inventory</Link>.
        </p>
      )}
      {open && (
        <div className="space-y-4 border-t border-gold-200/50 p-3 sm:p-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {canCost && (
              <Field label={<>Cost price {margin !== null && <span className="text-kajal-400">· {margin.toFixed(1)}% margin</span>}</>} error={e?.cost_price?.message}>
                <MiniInput label={`Variant ${i + 1} cost price`} inputMode="decimal" {...register(`variants.${i}.cost_price`)} className="tabular" />
              </Field>
            )}
            <Field label="Weight (g)" error={e?.weight_grams?.message}><MiniInput label={`Variant ${i + 1} weight`} inputMode="decimal" {...register(`variants.${i}.weight_grams`)} /></Field>
            {!v?.id && <Field label="Opening stock" error={e?.stock?.message}><MiniInput label={`Variant ${i + 1} opening stock`} inputMode="numeric" {...register(`variants.${i}.stock`)} placeholder="0" /></Field>}
            <Field label="Low-stock alert at" error={e?.low_stock_threshold?.message}><MiniInput label={`Variant ${i + 1} low stock threshold`} inputMode="numeric" {...register(`variants.${i}.low_stock_threshold`)} /></Field>
          </div>
          <fieldset className="rounded-lg border border-gold-200/50 bg-white p-3">
            <legend className="px-1 text-sm font-medium text-kajal-700">Scheduled sale price</legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Price (₹)" error={e?.scheduled_sale_price?.message}><MiniInput label={`Variant ${i + 1} scheduled price`} inputMode="decimal" {...register(`variants.${i}.scheduled_sale_price`)} /></Field>
              <Field label="Starts" error={e?.sale_starts_at?.message}><MiniInput label={`Variant ${i + 1} sale start`} type="datetime-local" {...register(`variants.${i}.sale_starts_at`)} /></Field>
              <Field label="Ends (optional)" error={e?.sale_ends_at?.message}><MiniInput label={`Variant ${i + 1} sale end`} type="datetime-local" {...register(`variants.${i}.sale_ends_at`)} /></Field>
            </div>
            <p className="mt-2 text-xs text-kajal-500">While the schedule is live, this price replaces the sale price. Times are in your local time zone.</p>
          </fieldset>
          <Controller control={control} name={`variants.${i}.attribute_value_ids`} render={({ field }) => {
            const pick = (attrValues: number[], val: string) => {
              const rest = field.value.filter((x) => !attrValues.includes(x));
              field.onChange(val ? [...rest, Number(val)] : rest);
            };
            const sel = (a: ProductMeta["attributes"][number]) => {
              const ids = a.values.map((x) => x.id);
              const cur = field.value.find((x) => ids.includes(x));
              return (
                <label key={a.id} className="block">
                  <span className="mb-1 block text-xs text-kajal-500">{a.name}</span>
                  <select className="input h-9 py-0 text-[14px]" value={cur ?? ""} onChange={(ev) => pick(ids, ev.target.value)}>
                    <option value="">—</option>
                    {a.values.map((x) => <option key={x.id} value={x.id}>{x.value}</option>)}
                  </select>
                </label>
              );
            };
            return (
              <div>
                <p className="mb-2 text-sm font-medium text-kajal-700">Attributes</p>
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{axes.map(sel)}</div>
                {others.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm text-kajal-500 hover:text-kajal">More attributes (filters)</summary>
                    <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">{others.map(sel)}</div>
                  </details>
                )}
              </div>
            );
          }} />
        </div>
      )}
    </div>
  );
}

function Field({ label, error, children }: { label: ReactNode; error?: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <span className="mb-1 block text-xs text-kajal-500">{label}</span>
      {children}
      {error && <p className="mt-1 text-xs text-kumkum">{error}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ images */
const MAX_MB = 5;
function Images({ product, write }: { product: AdminProduct; write: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(0);
  const key = ["admin", "product", product.id];
  const refresh = () => { qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["admin", "products"] }); };
  const images = [...product.images].sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.display_order - b.display_order);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    const list = Array.from(files);
    for (const f of list) {
      if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(f.type)) { toast(`${f.name}: only JPEG, PNG, WebP or GIF`, "error"); continue; }
      if (f.size > MAX_MB * 1024 * 1024) { toast(`${f.name}: must be under ${MAX_MB} MB`, "error"); continue; }
      setUploading((n) => n + 1);
      try { await adminApi.uploadProductImage(product.id, f); toast(`Uploaded ${f.name}`); }
      catch (e) { toast(errorMessage(e), "error"); }
      finally { setUploading((n) => n - 1); }
    }
    if (input.current) input.current.value = "";
    refresh();
  };
  const primary = useAdminMutation((iid: number) => adminApi.patchImage(product.id, iid, { is_primary: true }), { success: "Primary image updated", onSuccess: refresh });
  const remove = useAdminMutation((iid: number) => adminApi.deleteImage(product.id, iid), { success: "Image removed", onSuccess: refresh });
  const reorder = useAdminMutation(async (order: number[]) => {
    await Promise.all(order.map((iid, idx) => adminApi.patchImage(product.id, iid, { display_order: idx })));
  }, { onSuccess: refresh });
  const move = (idx: number, dir: -1 | 1) => {
    const ids = images.map((x) => x.id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    reorder.mutate(ids);
  };

  return (
    <div>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {images.map((img, idx) => (
          <li key={img.id} className="group overflow-hidden rounded-xl border border-gold-200/60 bg-white">
            <div className="relative aspect-square bg-ivory-200">
              <img src={img.url} alt={img.alt_text ?? ""} className="h-full w-full object-cover" loading="lazy" />
              {img.is_primary && <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-kajal/85 px-2 py-0.5 text-xs text-ivory"><Star className="h-3 w-3 fill-gold-200 text-gold-200" aria-hidden />Primary</span>}
            </div>
            {write && (
              <div className="flex items-center justify-between gap-1 px-1.5 py-1.5">
                <div className="flex">
                  <button type="button" aria-label="Move earlier" disabled={idx === 0 || reorder.isPending} onClick={() => move(idx, -1)} className="rounded p-1.5 text-kajal-500 hover:bg-ivory-200 disabled:opacity-30"><ArrowUp className="h-4 w-4 -rotate-90" /></button>
                  <button type="button" aria-label="Move later" disabled={idx === images.length - 1 || reorder.isPending} onClick={() => move(idx, 1)} className="rounded p-1.5 text-kajal-500 hover:bg-ivory-200 disabled:opacity-30"><ArrowDown className="h-4 w-4 -rotate-90" /></button>
                </div>
                {!img.is_primary && <button type="button" onClick={() => primary.mutate(img.id)} className="rounded px-1.5 py-1 text-xs text-kajal-700 hover:bg-ivory-200">Set primary</button>}
                <button type="button" aria-label="Delete image" onClick={async () => { if ((await confirm({ title: "Delete this image?", confirmLabel: "Delete image", danger: true })).ok) remove.mutate(img.id); }}
                  className="rounded p-1.5 text-kajal-400 hover:bg-ivory-200 hover:text-kumkum"><Trash2 className="h-4 w-4" /></button>
              </div>
            )}
          </li>
        ))}
        {write && (
          <li>
            <label className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-gold-300 bg-gold-50/40 p-3 text-center text-sm text-kajal-700 hover:bg-gold-50">
              <ImagePlus className="h-6 w-6 text-gold-600" aria-hidden />
              {uploading ? `Uploading ${uploading}…` : "Upload images"}
              <span className="text-xs text-kajal-400">JPEG, PNG, WebP, GIF · up to {MAX_MB} MB</span>
              <input ref={input} type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif" className="sr-only" onChange={(e) => onFiles(e.target.files)} />
            </label>
          </li>
        )}
      </ul>
      {!images.length && !write && <p className="text-sm text-kajal-500">No images yet.</p>}
    </div>
  );
}


