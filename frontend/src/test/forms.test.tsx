import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddressForm, addressSchema } from "@/components/forms/AddressForm";

describe("address validation", () => {
  it("accepts a valid Indian address", () => {
    const r = addressSchema.safeParse({ full_name: "Priya Sharma", phone: "9810012345", line1: "Flat 402, Lotus Residency", city: "Noida",
      state: "Uttar Pradesh", pin_code: "201301", is_default_billing: false, is_default_shipping: false });
    expect(r.success).toBe(true);
  });
  it("rejects bad PIN codes, phone numbers and states", () => {
    const r = addressSchema.safeParse({ full_name: "P", phone: "12345", line1: "x", city: "N", state: "Atlantis", pin_code: "012345" });
    expect(r.success).toBe(false);
    const fields = r.success ? [] : r.error.issues.map((i) => i.path[0]);
    expect(fields).toEqual(expect.arrayContaining(["phone", "pin_code", "state", "full_name"]));
  });
});

describe("<AddressForm>", () => {
  it("shows field errors and does not submit invalid data", async () => {
    const onSubmit = vi.fn();
    render(<AddressForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/PIN code/), "12");
    await userEvent.click(screen.getByRole("button", { name: "Save address" }));
    expect(await screen.findByText("Enter a valid 6-digit PIN code")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid 10-digit mobile number")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a complete address", async () => {
    const onSubmit = vi.fn();
    render(<AddressForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/Full name/), "Priya Sharma");
    await userEvent.type(screen.getByLabelText(/Mobile number/), "9810012345");
    await userEvent.type(screen.getByLabelText(/Flat, house/), "Flat 402, Lotus Residency");
    await userEvent.type(screen.getByLabelText(/PIN code/), "201301");
    await userEvent.type(screen.getByLabelText(/City/), "Noida");
    await userEvent.selectOptions(screen.getByLabelText("State"), "Uttar Pradesh");
    await userEvent.click(screen.getByRole("button", { name: "Save address" }));
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ pin_code: "201301", state: "Uttar Pradesh" });
  });
});
