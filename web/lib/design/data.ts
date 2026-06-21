// Demo estate + executor profile data, ported from the design system's
// ui_kits/web/data.jsx. Mirrors agent/seed/demo_estate.py (Robert A. Milligan).
// Cosmetic prototype data for the ported UI; the real values come from the agent.

export type AssetField = { label: string; value: string };
export type Asset = {
  id: string;
  kind: "Home" | "Bank" | "Car" | "Other";
  type: string;
  desc: string;
  value: number;
  appraised: boolean;
  fields: AssetField[];
};

export type Debt = {
  id: string;
  creditor: string;
  amount: number;
  type: "Secured" | "Unsecured";
  notified: boolean;
};

export type Beneficiary = {
  id: string;
  name: string;
  relationship: string;
  share: string;
  specificBequest: string;
  email: string;
  phone: string;
  address: string;
  notes: string;
};

export type Severity = "critical" | "warning" | "info";

export type Alert = {
  id: string;
  severity: Severity;
  title: string;
  daysRemaining?: number | null;
  timingStatus?: "dated" | "blocking" | "prerequisite" | "missing_data" | "no_deadline";
  rule: string;
  body: string;
  actionRequired: string;
  whatYouNeed?: string[];
  steps?: string[];
};

export type Task = {
  id: string;
  title: string;
  status: "done" | "todo" | "blocked";
};

export type DemoEstate = {
  id: string;
  deceasedName: string;
  dateOfDeath: string;
  appointmentDate: string;
  executor: { name: string; email: string };
  phase: number;
  phases: string[];
  assets: Asset[];
  debts: Debt[];
  beneficiaries: Beneficiary[];
  alerts: Alert[];
  alertsNext: Alert[];
  tasks: Task[];
};

export const DEMO_ESTATE: DemoEstate = {
  id: "demo-milligan",
  deceasedName: "Robert A. Milligan",
  dateOfDeath: "June 3, 2026",
  appointmentDate: "June 10, 2026",
  executor: { name: "Dana Milligan", email: "dana@demo.com" },
  phase: 2,
  phases: ["File petition", "Appointment", "Inventory", "Notify creditors", "Pay debts", "Distribute"],
  assets: [
    {
      id: "a1",
      kind: "Home",
      type: "Real estate",
      desc: "1847 Marin Ave, Berkeley CA",
      value: 220000,
      appraised: false,
      fields: [
        { label: "Address", value: "1847 Marin Ave, Berkeley, CA 94706" },
        { label: "County", value: "Alameda" },
        { label: "Parcel (APN)", value: "048-1234-567" },
      ],
    },
    {
      id: "a2",
      kind: "Bank",
      type: "Bank account",
      desc: "Wells Fargo checking …4412",
      value: 38240,
      appraised: true,
      fields: [
        { label: "Institution", value: "Wells Fargo" },
        { label: "Account number", value: "…4412" },
        { label: "Account type", value: "Checking" },
      ],
    },
    {
      id: "a3",
      kind: "Bank",
      type: "Retirement",
      desc: "Fidelity IRA …7731",
      value: 26500,
      appraised: true,
      fields: [
        { label: "Provider", value: "Fidelity" },
        { label: "Account number", value: "…7731" },
        { label: "Account type", value: "Traditional IRA" },
        { label: "Beneficiary named", value: "Yes" },
      ],
    },
    {
      id: "a4",
      kind: "Car",
      type: "Vehicle",
      desc: "2019 Honda Civic",
      value: 12000,
      appraised: false,
      fields: [
        { label: "Make & model", value: "Honda Civic" },
        { label: "Year", value: "2019" },
        { label: "VIN", value: "2HGFC2F69KH5…" },
      ],
    },
  ],
  debts: [
    { id: "d1", creditor: "First Republic Mortgage", amount: 141000, type: "Secured", notified: false },
    { id: "d2", creditor: "UCSF Medical Center", amount: 4200, type: "Unsecured", notified: false },
    { id: "d3", creditor: "Chase Visa", amount: 3100, type: "Unsecured", notified: false },
  ],
  beneficiaries: [
    {
      id: "b1",
      name: "Dana Milligan",
      relationship: "Daughter",
      share: "40%",
      specificBequest: "The family home at 1847 Marin Ave",
      email: "dana@demo.com",
      phone: "(510) 555-0147",
      address: "1847 Marin Ave, Berkeley, CA 94706",
      notes: "Also serving as executor of the estate.",
    },
    {
      id: "b2",
      name: "Sarah Milligan",
      relationship: "Daughter",
      share: "40%",
      specificBequest: "None",
      email: "sarah.m@example.com",
      phone: "(510) 555-0182",
      address: "22 Ridge Rd, Oakland, CA 94611",
      notes: "",
    },
    {
      id: "b3",
      name: "Marcus Milligan",
      relationship: "Son",
      share: "20%",
      specificBequest: "Grandfather's watch collection",
      email: "marcus.m@example.com",
      phone: "(415) 555-0143",
      address: "88 Lake St, San Francisco, CA 94118",
      notes: "Minor — share held in trust until age 21.",
    },
  ],
  alerts: [
    {
      id: "alert-creditor-notice",
      severity: "critical",
      title: "Known creditors haven't been notified",
      daysRemaining: 20,
      rule: "CA Probate Code §9051",
      body: "California gives you 30 days from the date your letters testamentary were issued (June 10). Miss it and you can be held personally liable for late distributions.",
      actionRequired: "Send a certified creditor notice to UCSF Medical Center and Chase Visa.",
      whatYouNeed: [
        "The estate's mailing address and your letters testamentary date (June 10, 2026)",
        "Names and addresses for UCSF Medical Center and Chase Visa",
        "Access to a post office that offers certified mail with return receipt",
      ],
      steps: [
        "Open the Letters page and generate a creditor notice for each known creditor. Executor AI fills in the estate details and the §9051 language for you.",
        "Review each draft. Confirm the creditor name, the amount owed, and that the claim deadline is correct.",
        "Print and sign both letters.",
        "Mail each one by certified mail with return receipt requested. Regular mail does not satisfy the rule.",
        "Keep the certified-mail receipts and the green return cards. Add the mailing date here so the claim window is tracked.",
      ],
    },
    {
      id: "alert-de-160-inventory",
      severity: "warning",
      title: "DE-160 Inventory & Appraisal is blocked",
      daysRemaining: 9,
      rule: "DE-160 Inventory & Appraisal",
      body: "Two assets, the Berkeley home and the Honda Civic, still need an appraisal before the inventory can be filed.",
      actionRequired: "Schedule appraisals for 1847 Marin Ave and the 2019 Honda Civic.",
      whatYouNeed: [
        "The court-appointed Probate Referee for Alameda County (Executor AI can look this up)",
        "Address and access details for 1847 Marin Ave",
        "The VIN and mileage for the 2019 Honda Civic",
      ],
      steps: [
        "Contact the Probate Referee assigned to this estate to request appraisals of the home and the vehicle. Cash accounts you can value yourself.",
        "Provide access to the property and the vehicle details so the referee can complete the valuation.",
        "Enter the appraised values on the Documents page as they come back.",
        "Once both assets show an appraised value, Executor AI assembles the DE-160 packet.",
        "Review the inventory, sign it, and file it with the court before the 4-month deadline.",
      ],
    },
    {
      id: "alert-final-1040",
      severity: "info",
      title: "Final Form 1040 due April 15, 2027",
      daysRemaining: 299,
      rule: "IRS, final personal return",
      body: "Robert's final personal income tax return is due next April. Most executors miss the separate estate return (Form 1041), we'll remind you.",
      actionRequired: "Gather Robert's 2026 income records when convenient.",
      whatYouNeed: [
        "Robert's W-2s, 1099s, and any pension or Social Security statements for 2026",
        "Last year's filed return as a reference",
        "The estate EIN (already obtained) for any estate-level income",
      ],
      steps: [
        "Collect Robert's income documents for 2026 as they arrive. There's no rush yet, this isn't due until next April.",
        "Upload them to the Documents page so they're in one place when you file.",
        "Decide whether you'll work with a tax preparer or file yourself.",
        "If the estate earns more than $600 of income, you'll also need Form 1041, Executor AI will flag that separately.",
      ],
    },
  ],
  alertsNext: [
    {
      id: "alert-de-160-ready",
      severity: "warning",
      title: "File the DE-160 Inventory & Appraisal",
      daysRemaining: 30,
      rule: "DE-160 Inventory & Appraisal",
      body: "Both assets are appraised now, so the full inventory can be filed. California requires it within four months of your appointment.",
      actionRequired: "Review the DE-160 packet Executor AI assembled and file it with the court.",
      whatYouNeed: [
        "The appraised values for every asset (now on file)",
        "The court case number for the estate",
        "Your signature as executor",
      ],
      steps: [
        "Open the DE-160 packet Executor AI assembled from your documents and appraisals.",
        "Check every asset and value against your records.",
        "Sign the inventory where indicated.",
        "File it with the Superior Court that issued your letters, and keep a stamped copy.",
      ],
    },
    {
      id: "inv2",
      severity: "info",
      title: "Open the estate bank account",
      daysRemaining: 21,
      rule: "Estate EIN obtained",
      body: "With the EIN in hand, open one dedicated account so every dollar in and out of the estate flows through a single place.",
      actionRequired: "Open an estate checking account at your bank using the EIN and your letters.",
      whatYouNeed: [
        "The estate EIN (already obtained)",
        "A certified copy of your letters testamentary",
        "A certified death certificate",
      ],
      steps: [
        "Call the bank ahead and confirm what they require to open an estate account.",
        "Bring the EIN, your letters, and a death certificate to the branch.",
        "Move estate funds into the new account; never mix them with personal money.",
        "Add the new account on the Documents page so it's part of the inventory.",
      ],
    },
    {
      id: "inv3",
      severity: "info",
      title: "Start an estate ledger",
      daysRemaining: 30,
      rule: "Final accounting",
      body: "The court will eventually want a full accounting. Recording every transaction from day one makes that simple instead of painful.",
      actionRequired: "Begin logging every payment and deposit for the estate.",
      whatYouNeed: [
        "Statements for the new estate account",
        "Receipts for any estate expenses you've already paid",
      ],
      steps: [
        "Create one running log of money in and money out, with dates and purpose.",
        "Keep every receipt and invoice with the matching ledger line.",
        "Update it each time the estate pays or receives anything.",
      ],
    },
  ],
  tasks: [
    { id: "t1", title: "Order 12 certified death certificates", status: "done" },
    { id: "t2", title: "Obtain estate EIN from the IRS", status: "done" },
    { id: "t3", title: "Notify all known creditors by certified mail", status: "todo" },
    { id: "t4", title: "Schedule property & vehicle appraisals", status: "todo" },
    { id: "t5", title: "Prepare DE-160 Inventory & Appraisal", status: "blocked" },
  ],
};

export const fmtMoney = (n: number): string => "$" + n.toLocaleString();

export type ExecutorProfile = {
  name: string;
  email: string;
  phone: string;
  age: number;
  gender: string;
  state: string;
  county: string;
  relationship: string;
  address: string;
};

export const EXECUTOR_PROFILE: ExecutorProfile = {
  name: "Dana Milligan",
  email: "dana@demo.com",
  phone: "(510) 555-0147",
  age: 41,
  gender: "Female",
  state: "California",
  county: "Alameda",
  relationship: "Daughter of the deceased",
  address: "1847 Marin Ave, Berkeley, CA 94706",
};

export type EstateProfile = {
  id: string;
  deceasedName: string;
  role: string;
  relationship: string;
  state: string;
  county: string;
  phase: number;
  seeded: boolean;
  // True for the demo, or once a real estate has at least one parsed document.
  // Gates the chat and letters screens; distinct from `seeded`, which drives the
  // cosmetic demo data.
  hasDocuments: boolean;
};

export const ESTATE_PROFILES: EstateProfile[] = [
  { id: "demo-milligan", deceasedName: "Robert A. Milligan", role: "Executor", relationship: "Father", state: "California", county: "Alameda", phase: 2, seeded: true, hasDocuments: true },
  { id: "est-reyes", deceasedName: "Gloria Reyes", role: "Co-executor", relationship: "Aunt", state: "California", county: "Contra Costa", phase: 1, seeded: false, hasDocuments: false },
];

export const GENDER_OPTIONS = ["Female", "Male", "Non-binary", "Prefer not to say"];
export const ROLE_OPTIONS = ["Executor", "Co-executor", "Administrator", "Successor trustee"];
export const RELATIONSHIP_OPTIONS = ["Spouse", "Child", "Parent", "Sibling", "Other family", "Friend", "Attorney", "Other"];
export const US_STATES = ["California", "Arizona", "Nevada", "Oregon", "Washington", "Texas", "New York", "Florida", "Illinois", "Other"];

export const ASSET_TYPES = ["Real estate", "Bank account", "Retirement", "Vehicle", "Personal property", "Other"];
export const SUGGESTED_FIELDS: Record<string, string[]> = {
  "Real estate": ["Address", "County", "Parcel (APN)"],
  "Bank account": ["Institution", "Account number", "Account type"],
  Retirement: ["Provider", "Account number", "Account type"],
  Vehicle: ["Make & model", "Year", "VIN"],
  "Personal property": ["Item", "Location"],
  Other: ["Detail"],
};
export const ASSET_KIND: Record<string, Asset["kind"]> = {
  "Real estate": "Home",
  "Bank account": "Bank",
  Retirement: "Bank",
  Vehicle: "Car",
  "Personal property": "Other",
  Other: "Other",
};

export type DocChecklistItem = {
  id: string;
  label: string;
  why: string;
  required: boolean;
  uploaded: boolean;
};

export const DOC_CHECKLIST: DocChecklistItem[] = [
  { id: "will", label: "Will or trust", why: "Names beneficiaries, the executor, and any specific bequests.", required: true, uploaded: true },
  { id: "death-cert", label: "Death certificate", why: "Every bank and agency requires a certified copy. Order 10–12.", required: true, uploaded: false },
  { id: "bank", label: "Bank & brokerage statements", why: "Sets account balances for the inventory.", required: true, uploaded: true },
  { id: "tax", label: "Most recent tax return", why: "Helps prepare the final 1040 and spot recurring income.", required: true, uploaded: false },
  { id: "deed", label: "Property deed", why: "Only if the estate owns real estate. Confirms title.", required: false, uploaded: true },
  { id: "mortgage", label: "Mortgage & loan statements", why: "Only if there are secured debts to pay in order.", required: false, uploaded: false },
  { id: "insurance", label: "Insurance policies", why: "If there's life or property coverage to claim or continue.", required: false, uploaded: false },
  { id: "vehicle", label: "Vehicle titles", why: "Only if the estate includes a car, boat, or other vehicle.", required: false, uploaded: false },
];
